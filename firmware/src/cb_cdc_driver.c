/* Driver de classe USB "clone ConnectBox".
 *
 * On n'utilise PAS le driver CDC intégré de TinyUSB (CFG_TUD_CDC=0). Raison :
 * cdcd_init() force line_coding = 115200/8N1 et cdcd_control_xfer_cb() renvoie
 * cette structure telle quelle sur GET_LINE_CODING, sans passer par le moindre
 * callback applicatif. Impossible d'y répondre 00×7 sans patcher TinyUSB.
 *
 * Ce driver-ci est enregistré via usbd_app_driver_get_cb(). Il donne :
 *   - la réponse exacte à GET_LINE_CODING (variable de l'expérience n°1) ;
 *   - le log de TOUTES les requêtes de contrôle, y compris GET_LINE_CODING,
 *     que les compteurs de juin (ctrl_lc=0) ne voyaient pas ;
 *   - le log de chaque transaction bulk OUT + le réassemblage des trames
 *     FA FD LEN FF opcode ... FE cksum.
 *
 * Workbench v1 : bulk IN uniquement sur demande authentifiee explicite.
 * Aucun pong/poll automatique. Le journal OUT brut reste la preuve RX.
 */

#include <string.h>

#include "class/cdc/cdc.h"
#include "device/usbd_pvt.h"
#include "netlog.h"
#include "cb_tx.h"
#include "netcontrol.h"
#include "control_protocol.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include "hardware/structs/usb.h"

/* Variable de l'expérience : réponse à GET_LINE_CODING.
 *   1 → 00 00 00 00 00 00 00   (ce que renvoie la vraie ConnectBox)
 *   0 → 00 C2 01 00 00 00 08   (115200 8N1, le défaut TinyUSB, = branche témoin)
 */
#ifndef CB_LINE_CODING_ZERO
#define CB_LINE_CODING_ZERO 1
#endif

#if CB_LINE_CODING_ZERO
static uint8_t s_line_coding[7] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
static const char *const s_variant = "B (GET_LINE_CODING = 00 x7, comme la vraie CB)";
#else
static uint8_t s_line_coding[7] = {0x00, 0xC2, 0x01, 0x00, 0x00, 0x00, 0x08};
static const char *const s_variant = "A (GET_LINE_CODING = 115200 8N1, temoin TinyUSB)";
#endif

static uint8_t s_set_lc_buf[8];

static uint8_t s_ep_out;
static uint8_t s_ep_in;
static uint8_t s_ep_notif;

CFG_TUSB_MEM_SECTION static uint8_t s_out_buf[64] CFG_TUSB_MEM_ALIGN;

/* Called only from the main task, never from TCP/IRQ callbacks. */
CFG_TUSB_MEM_SECTION static uint8_t tx_buf[TX_MAX] CFG_TUSB_MEM_ALIGN;
static bool tx_busy, tx_zlp;
static uint32_t tx_started, tx_id;
static uint16_t tx_len;
static const char *tx_state = "IDLE";
/* Diagnostic only: no endpoint writes, no automatic transmission. */
static uint32_t lc_diag_queued, lc_diag_failed, lc_diag_data, lc_diag_ack, lc_diag_report_ms;
static uint32_t diag_loops, diag_usb_max_us, diag_control_max_us;
static uint32_t diag_last_report, diag_last_loop, diag_loop_gap_max_us;
static void tx_diag(const char *event) {
  uint8_t ep = s_ep_in & 15u;
  uint32_t ctrl = (tud_inited() && ep) ? usb_dpram->ep_buf_ctrl[ep].in : 0;
  netlog_printf("TXDIAG %s id=%lu ep=%u pending=%u age_ms=%lu buf=%08lx loops=%lu usb_max_us=%lu ctl_max_us=%lu gap_max_us=%lu",
    event, (unsigned long)tx_id, s_ep_in, tx_busy,
    (unsigned long)(to_ms_since_boot(get_absolute_time())-tx_started),
    (unsigned long)ctrl, (unsigned long)diag_loops,
    (unsigned long)diag_usb_max_us, (unsigned long)diag_control_max_us,
    (unsigned long)diag_loop_gap_max_us);
}
void cb_tx_diag_loop(uint32_t usb_us, uint32_t control_us) {
  uint32_t now=time_us_32();
  if (diag_last_loop && now-diag_last_loop>diag_loop_gap_max_us) diag_loop_gap_max_us=now-diag_last_loop;
  diag_last_loop=now; diag_loops++;
  if (usb_us>diag_usb_max_us) diag_usb_max_us=usb_us;
  if (control_us>diag_control_max_us) diag_control_max_us=control_us;
  uint32_t ms=to_ms_since_boot(get_absolute_time());
  if (ms-lc_diag_report_ms>=10000u) {
    lc_diag_report_ms=ms;
    netlog_printf("LCDIAG cumulative queued=%lu failed=%lu data=%lu ack=%lu",
      (unsigned long)lc_diag_queued, (unsigned long)lc_diag_failed,
      (unsigned long)lc_diag_data, (unsigned long)lc_diag_ack);
  }
  if (tx_busy && ms-diag_last_report>=1000u) {
    diag_last_report=ms; tx_diag("PENDING");
  }
}

bool cb_tx_busy(void) { return tx_busy; }
const char *cb_tx_state(void) { return tx_state; }
uint32_t cb_tx_id(void) { return tx_id; }
bool cb_tx_start(const uint8_t *data, uint16_t len, uint32_t id) {
 if (!len || len > TX_MAX || tx_busy || !tud_inited() || !tud_mounted() || !s_ep_in) return false;
 if (!usbd_edpt_claim(0,s_ep_in)) { tx_diag("CLAIM_FAILED"); return false; }
 memcpy(tx_buf,data,len);
 tx_len=len; tx_id=id; tx_zlp=false; tx_busy=true;
 tx_started=to_ms_since_boot(get_absolute_time()); tx_state="PENDING";
 netlog_printf("TX id=%lu SUBMIT len=%u (not proof of PAC action)",(unsigned long)id,len);
 netlog_hex("TX raw",tx_buf,len);
 tx_diag("BEFORE_ARM");
 if (!usbd_edpt_xfer(0,s_ep_in,tx_buf,len)) {
  usbd_edpt_release(0,s_ep_in); tx_busy=false; tx_state="SUBMIT_FAILED"; tx_diag("ARM_FAILED"); return false;
 }
 tx_diag("ARM_ACCEPTED");
 return true;
}
void cb_tx_cancel(void) {
 if (!tx_busy) return;
 /* Full controller reset removes pending DPRAM packets. Remain disconnected
  * until an explicit USBON command, with no replay of the cancelled request. */
 tud_deinit(0);
 tx_busy=false; tx_state="ABORTED_USB_OFF";
 netcontrol_usb_reset();
 netlog_printf("TX id=%lu ABORTED_USB_OFF; partial delivery possible; no retry",(unsigned long)tx_id);
}
void cb_tx_service(void) {
 if (tx_busy && (uint32_t)(to_ms_since_boot(get_absolute_time())-tx_started)>=CB_TX_TIMEOUT_MS) cb_tx_cancel();
}

/* Compteurs — publiés périodiquement par main.c */
uint32_t cb_n_get_line_coding;
uint32_t cb_n_set_line_coding;
uint32_t cb_n_set_control_line_state;
uint32_t cb_n_send_break;
uint32_t cb_n_ctrl_other;
uint32_t cb_n_out_xfer;
uint32_t cb_n_out_bytes;
uint32_t cb_n_out_errors;
uint32_t cb_n_out_zlp;
uint32_t cb_n_out_rearm_failed;
uint32_t cb_n_frames;
uint32_t cb_n_frames_phase; /* 0x22 valide : changement de phase prouve   */
uint32_t cb_n_frames_live;  /* 0x21 valide portant des valeurs vivantes   */
uint32_t cb_n_frames_bad;  /* checksum ou cadrage invalide */
uint32_t cb_n_truncated;

const char *cb_variant_name(void) { return s_variant; }

/* --------------------------------------------------- réassemblage de trames */
/* Cadrage observé : FA FD [LEN] FF [opcode] ... FE [checksum], LEN = longueur
 * totale de la trame (0x29=41 pour le Hello, 0x70=112, 0xAF=175). */

#define FRAME_MAX 300
static uint8_t s_frame[FRAME_MAX];
static uint16_t s_frame_idx;
static uint16_t s_frame_len;
static uint8_t s_frame_state;

static void frame_reset(void) {
  s_frame_idx = 0;
  s_frame_len = 0;
  s_frame_state = 0;
}

/* Checksum. Le dossier donnait un CRC-8 DARC (init 0xB8, poly reflechi 0x9C,
 * xor 0xFF, sur frame[4:-1]) qui colle sur le Hello de 41 o mais rend 0xDA au
 * lieu de 0x17 sur la trame publique de 112 o : sur-ajustement sur un seul
 * echantillon. La somme 8 bits, elle, colle sur les deux — le dernier octet est
 * le complement a 2 de la somme des precedents, donc Somme(trame) == 0 mod 256.
 * On journalise les deux a chaque trame : chaque run tranche gratuitement. */

static uint8_t crc8_darc(const uint8_t *d, uint16_t n) {
  uint8_t crc = 0xB8;
  for (uint16_t i = 0; i < n; i++) {
    crc ^= d[i];
    for (uint8_t b = 0; b < 8; b++) crc = (crc & 1) ? (uint8_t)((crc >> 1) ^ 0x9C) : (uint8_t)(crc >> 1);
  }
  return crc ^ 0xFF;
}

static void frame_emit(void) {
  uint8_t opcode = (s_frame_len >= 5) ? s_frame[4] : 0xFF;

  uint8_t sum = 0;
  for (uint16_t i = 0; i < s_frame_len; i++) sum = (uint8_t)(sum + s_frame[i]);
  bool sum_ok = (sum == 0);
  bool framing_ok = (s_frame[3] == 0xFF) && (s_frame[s_frame_len - 2] == 0xFE);
  uint8_t crc = crc8_darc(&s_frame[4], (uint16_t)(s_frame_len - 5));
  bool crc_ok = (crc == s_frame[s_frame_len - 1]);
  bool valid = sum_ok && framing_ok;

  /* Deux oracles distincts, et non un seul.
   *
   * Le 0x22 public de 112 o, decode en LE16, donne 16,00 / 24,00 / 22,00 /
   * 31,00 degres puis des temporisations et des seuils : ce sont des BORNES de
   * consigne, pas des mesures. Un 0x22 prouve donc un changement de phase, pas
   * une lecture live.
   *
   * Les valeurs vivantes sont dans le 0x21 : consignes K1-K4 a D0 07 et mesures
   * BD 07 D0 07 E9 07 46 08, soit des LE16 entre 1000 et 3500 (10,00 a 35,00
   * degres).
   *
   * On n'exige PAS l'en-tete nul de la T.One publique. Le sous-record versionne
   * FF 21 25 81 08 du Status vit a l'interieur d'une trame 0x25 et ne remonte
   * donc jamais ici comme trame autonome ; exiger l'en-tete nul ne protegerait
   * de rien et raterait un vrai 0x21 emis dans le dialecte versionne du
   * proprietaire. On journalise l'en-tete, on ne filtre pas dessus.
   */
  bool phase = valid && (opcode == 0x22);

  bool live = false;
  uint8_t plausibles = 0;
  if (valid && opcode == 0x21 && s_frame_len >= 24) {
    for (uint16_t i = 5; i + 1 < (uint16_t)(s_frame_len - 2); i += 2) {
      uint16_t v = (uint16_t)(s_frame[i] | (s_frame[i + 1] << 8));
      if (v >= 1000 && v <= 3500) plausibles++;
    }
    live = (plausibles >= 4);
  }

  cb_n_frames++;
  if (!valid) cb_n_frames_bad++;
  if (phase) cb_n_frames_phase++;
  if (live) cb_n_frames_live++;

  netlog_printf("FRAME #%lu opcode=0x%02X len=%u somme=%s cadrage=%s crc8darc=0x%02X(%s)%s%s",
                (unsigned long)cb_n_frames, opcode, s_frame_len, sum_ok ? "OK" : "KO",
                framing_ok ? "OK" : "KO", crc, crc_ok ? "OK" : "KO",
                phase ? "  <<<< 0x22 : CHANGEMENT DE PHASE >>>>" : "",
                live ? "  <<<< 0x21 : VALEURS VIVANTES >>>>" : "");
  if (opcode == 0x21 && s_frame_len >= 9) {
    netlog_printf("      en-tete apres FF 21 : %02X %02X %02X %02X, LE16 en 1000-3500 : %u",
                  s_frame[5], s_frame[6], s_frame[7], s_frame[8], plausibles);
  }
  netlog_hex("      ", s_frame, s_frame_len);
  frame_reset();
}

static void frame_feed(const uint8_t *data, uint32_t len) {
  for (uint32_t i = 0; i < len; i++) {
    uint8_t b = data[i];

    switch (s_frame_state) {
      case 0:
        if (b == 0xFA) {
          s_frame[0] = b;
          s_frame_idx = 1;
          s_frame_state = 1;
        }
        break;

      case 1:
        if (b == 0xFD) {
          s_frame[1] = b;
          s_frame_idx = 2;
          s_frame_state = 2;
        } else {
          frame_reset();
          if (b == 0xFA) { /* resynchro immédiate sur un nouveau FA */
            s_frame[0] = b;
            s_frame_idx = 1;
            s_frame_state = 1;
          }
        }
        break;

      case 2:
        s_frame[2] = b;
        s_frame_len = b;
        s_frame_idx = 3;
        if (s_frame_len < 6 || s_frame_len > FRAME_MAX) {
          netlog_printf("FRAME longueur aberrante 0x%02X, resynchro", b);
          frame_reset();
        } else {
          s_frame_state = 3;
        }
        break;

      case 3:
        s_frame[s_frame_idx++] = b;
        if (s_frame_idx >= s_frame_len) frame_emit();
        break;

      default:
        frame_reset();
        break;
    }
  }
}

/* ------------------------------------------------------------ class driver */

static void cb_init(void) {
  s_ep_out = s_ep_in = s_ep_notif = 0;
  frame_reset();
}

static bool cb_deinit(void) { return true; }

static void cb_reset(uint8_t rhport) {
  if (tx_busy) { tx_busy=false; tx_state="RESET_DELIVERY_UNKNOWN"; }
  netcontrol_usb_reset();
  (void)rhport;
  s_ep_out = s_ep_in = s_ep_notif = 0;
  frame_reset();
  netlog_printf("USB bus reset");
}

static uint16_t cb_open(uint8_t rhport, tusb_desc_interface_t const *itf_desc, uint16_t max_len) {
  uint8_t const *p_desc = (uint8_t const *)itf_desc;

  /* usbd appelle open() une interface a la fois. Sans IAD et avec CFG_TUD_CDC=0,
   * son rattrapage assoc_itf_count=2 est desactive (il est garde par #if
   * CFG_TUD_CDC et teste driver->open == cdcd_open). Si on consommait les deux
   * interfaces d'un coup, itf2drv[1] resterait DRVID_INVALID et toute requete de
   * controle visant l'interface 1 partirait en STALL silencieux, sans passer par
   * nous ni etre journalisee. On accepte donc chaque interface separement. */

  /* --- interface data (classe 0x0A) --- */
  if (TUSB_CLASS_CDC_DATA == itf_desc->bInterfaceClass) {
    uint16_t drv_len = tu_desc_len(p_desc);
    p_desc = tu_desc_next(p_desc);

    TU_ASSERT(usbd_open_edpt_pair(rhport, p_desc, 2, TUSB_XFER_BULK, &s_ep_out, &s_ep_in), 0);
    drv_len = (uint16_t)(drv_len + 2 * sizeof(tusb_desc_endpoint_t));
    TU_VERIFY(drv_len <= max_len, 0);

    netlog_printf("OPEN itf data : out=0x%02X in=0x%02X (drv_len=%u)", s_ep_out, s_ep_in, drv_len);

    /* Reception immediate ; bulk IN reste muet sans demande explicite. */
    if (s_ep_out) {
      TU_ASSERT(usbd_edpt_xfer(rhport, s_ep_out, s_out_buf, sizeof(s_out_buf)), 0);
    }
    return drv_len;
  }

  /* --- interface de controle CDC/ACM --- */
  TU_VERIFY(TUSB_CLASS_CDC == itf_desc->bInterfaceClass &&
                CDC_COMM_SUBCLASS_ABSTRACT_CONTROL_MODEL == itf_desc->bInterfaceSubClass,
            0);

  uint16_t drv_len = tu_desc_len(p_desc);
  p_desc = tu_desc_next(p_desc);

  /* descripteurs fonctionnels CDC (header / call mgmt / acm / union) */
  while (TUSB_DESC_CS_INTERFACE == tu_desc_type(p_desc) && drv_len <= max_len) {
    drv_len = (uint16_t)(drv_len + tu_desc_len(p_desc));
    p_desc = tu_desc_next(p_desc);
  }

  /* endpoint de notification */
  if (TUSB_DESC_ENDPOINT == tu_desc_type(p_desc)) {
    tusb_desc_endpoint_t const *ep = (tusb_desc_endpoint_t const *)p_desc;
    TU_ASSERT(usbd_edpt_open(rhport, ep), 0);
    s_ep_notif = ep->bEndpointAddress;
    drv_len = (uint16_t)(drv_len + tu_desc_len(p_desc));
    p_desc = tu_desc_next(p_desc);
  }

  TU_VERIFY(drv_len <= max_len, 0);
  netlog_printf("OPEN itf ctrl : notif=0x%02X (drv_len=%u)", s_ep_notif, drv_len);
  return drv_len;
}

static bool cb_control_xfer(uint8_t rhport, uint8_t stage, tusb_control_request_t const *request) {
  if (request->bRequest == CDC_REQUEST_GET_LINE_CODING &&
      request->bmRequestType_bit.type == TUSB_REQ_TYPE_CLASS &&
      stage != CONTROL_STAGE_SETUP) {
    if (stage == CONTROL_STAGE_DATA) lc_diag_data++;
    if (stage == CONTROL_STAGE_ACK) lc_diag_ack++;
    netlog_printf("LCDIAG phase=%u", (unsigned)stage);
  }
  if (stage == CONTROL_STAGE_SETUP) {
    netlog_printf("CTRL bmRequestType=0x%02X bRequest=0x%02X wValue=0x%04X wIndex=0x%04X wLength=%u",
                  request->bmRequestType, request->bRequest, request->wValue, request->wIndex,
                  request->wLength);
  }

  /* On ne prend que les requêtes de classe ; le standard (GET/SET_INTERFACE)
   * est renvoyé à usbd qui sait y répondre tout seul. */
  if (request->bmRequestType_bit.type != TUSB_REQ_TYPE_CLASS) return false;

  switch (request->bRequest) {
    case CDC_REQUEST_GET_LINE_CODING:
      if (stage == CONTROL_STAGE_SETUP) {
        cb_n_get_line_coding++;
        netlog_printf("  GET_LINE_CODING #%lu -> reponse %02X %02X %02X %02X %02X %02X %02X",
                      (unsigned long)cb_n_get_line_coding, s_line_coding[0], s_line_coding[1],
                      s_line_coding[2], s_line_coding[3], s_line_coding[4], s_line_coding[5],
                      s_line_coding[6]);
        bool queued = tud_control_xfer(rhport, request, s_line_coding, 7);
        if (queued) lc_diag_queued++; else lc_diag_failed++;
        netlog_printf("LCDIAG queued=%u", (unsigned)queued);
      }
      break;

    case CDC_REQUEST_SET_LINE_CODING:
      if (stage == CONTROL_STAGE_SETUP) {
        cb_n_set_line_coding++;
        tud_control_xfer(rhport, request, s_set_lc_buf, 7);
      } else if (stage == CONTROL_STAGE_DATA) {
        netlog_printf("  SET_LINE_CODING #%lu = %02X %02X %02X %02X %02X %02X %02X",
                      (unsigned long)cb_n_set_line_coding, s_set_lc_buf[0], s_set_lc_buf[1],
                      s_set_lc_buf[2], s_set_lc_buf[3], s_set_lc_buf[4], s_set_lc_buf[5],
                      s_set_lc_buf[6]);
      }
      break;

    case CDC_REQUEST_SET_CONTROL_LINE_STATE:
      if (stage == CONTROL_STAGE_SETUP) {
        cb_n_set_control_line_state++;
        netlog_printf("  SET_CONTROL_LINE_STATE #%lu DTR=%u RTS=%u",
                      (unsigned long)cb_n_set_control_line_state, request->wValue & 1u,
                      (request->wValue >> 1) & 1u);
        tud_control_status(rhport, request);
      }
      break;

    case CDC_REQUEST_SEND_BREAK:
      if (stage == CONTROL_STAGE_SETUP) {
        cb_n_send_break++;
        netlog_printf("  SEND_BREAK #%lu", (unsigned long)cb_n_send_break);
        tud_control_status(rhport, request);
      }
      break;

    default:
      if (stage == CONTROL_STAGE_SETUP) {
        cb_n_ctrl_other++;
        netlog_printf("  requete de classe INCONNUE 0x%02X -> stall", request->bRequest);
      }
      return false;
  }

  return true;
}

static bool cb_xfer_cb(uint8_t rhport, uint8_t ep_addr, xfer_result_t result,
                       uint32_t xferred_bytes) {
  if (ep_addr == s_ep_out) {
    if (result != XFER_RESULT_SUCCESS) {
      cb_n_out_errors++;
      netlog_printf("OUT ERROR result=%u bytes=%lu count=%lu", (unsigned)result,
                    (unsigned long)xferred_bytes, (unsigned long)cb_n_out_errors);
    } else if (!xferred_bytes) {
      cb_n_out_zlp++;
      netlog_printf("OUT ZLP count=%lu", (unsigned long)cb_n_out_zlp);
    }
    if (result == XFER_RESULT_SUCCESS && xferred_bytes) {
      cb_n_out_xfer++;
      cb_n_out_bytes += xferred_bytes;
      netlog_printf("OUT xfer #%lu, %lu octets", (unsigned long)cb_n_out_xfer,
                    (unsigned long)xferred_bytes);
      netlog_hex("   raw", s_out_buf, xferred_bytes);
      frame_feed(s_out_buf, xferred_bytes);

      /* Un paquet court termine le transfert USB. Si le parseur est encore au
       * milieu d'une trame, elle est tronquee : sans ce reset, elle avalerait la
       * trame suivante et l'oracle pourrait rater un 0x21/0x22. */
      if (xferred_bytes < sizeof(s_out_buf) && s_frame_state != 0) {
        cb_n_truncated++;
        netlog_printf("FRAME tronquee (fin de transfert a %u/%u octets) -> resynchro", s_frame_idx,
                      s_frame_len);
        frame_reset();
      }
    }
    /* réarmement immédiat : un NAK prolongé fausserait le timing observé */
    if (!usbd_edpt_xfer(rhport, s_ep_out, s_out_buf, sizeof(s_out_buf))) {
      cb_n_out_rearm_failed++;
      netlog_printf("OUT REARM_FAILED count=%lu", (unsigned long)cb_n_out_rearm_failed);
    }
  } else if (ep_addr == s_ep_in) {
    tx_diag("CALLBACK");
    if (tx_busy) {
      if (result != XFER_RESULT_SUCCESS || xferred_bytes != (tx_zlp ? 0u : tx_len)) {
        tx_busy=false; tx_state="TRANSFER_FAILED";
      } else if (!tx_zlp && tx_len % 64u == 0) {
        tx_zlp=true;
        if (!usbd_edpt_xfer(rhport,s_ep_in,NULL,0)) {
          tx_busy=false; tx_state="ZLP_FAILED";
        }
      } else {
        tx_busy=false; tx_state="USB_DONE";
      }
      netlog_printf("TX id=%lu state=%s result=%u bytes=%lu (USB receipt only)",
        (unsigned long)tx_id,tx_state,result,(unsigned long)xferred_bytes);
    }
  }
  return true;
}

static usbd_class_driver_t const s_cb_driver[] = {{.name = "CBCLONE",
                                                   .init = cb_init,
                                                   .deinit = cb_deinit,
                                                   .reset = cb_reset,
                                                   .open = cb_open,
                                                   .control_xfer_cb = cb_control_xfer,
                                                   .xfer_cb = cb_xfer_cb,
                                                   .sof = NULL}};

usbd_class_driver_t const *usbd_app_driver_get_cb(uint8_t *driver_count) {
  *driver_count = 1;
  return s_cb_driver;
}
