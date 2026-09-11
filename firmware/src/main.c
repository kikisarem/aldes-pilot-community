#include "cb_tx.h"
/* Clone ConnectBox sur Pico W — expérience n°1 : GET_LINE_CODING.
 *
 * Ordre de démarrage volontaire : le CYW43 est initialisé AVANT tusb_init().
 * cyw43_arch_init() bloque ~1 s pour charger son firmware ; si l'USB était déjà
 * présenté au bus pendant ce temps, la T.One pourrait timeout en pleine
 * énumération. Là, le device apparaît une seconde après la mise sous tension et
 * l'hôte l'énumère normalement.
 *
 * L'association WiFi, elle, est asynchrone : tud_task() tourne pendant.
 */

#include <stdio.h>

#include "lwip/netif.h"
#include "netlog.h"
#include "netcontrol.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "tusb.h"

/* Le mot de passe arrive par ce header, généré en 0600 dans un répertoire
 * temporaire par tools/bin/wifi-secret et détruit après le build. */
#if __has_include("wifi_config.h")
#include "wifi_config.h"
#endif

#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif

/* IP statique : on ne dépend pas du DHCP de la maison. */
#ifndef CB_IP_A
#define CB_IP_A 192
#define CB_IP_B 168
#define CB_IP_C 0
#define CB_IP_D 5
#endif
#ifndef CB_GW_D
#define CB_GW_D 1
#endif
#define CB_LOG_PORT 8765

extern const char *cb_variant_name(void);
extern uint32_t cb_n_get_line_coding;
extern uint32_t cb_n_set_line_coding;
extern uint32_t cb_n_set_control_line_state;
extern uint32_t cb_n_send_break;
extern uint32_t cb_n_ctrl_other;
extern uint32_t cb_n_out_xfer;
extern uint32_t cb_n_out_bytes;
extern uint32_t cb_n_out_errors;
extern uint32_t cb_n_out_zlp;
extern uint32_t cb_n_out_rearm_failed;
extern uint32_t cb_n_frames;
extern uint32_t cb_n_frames_phase;
extern uint32_t cb_n_frames_live;
extern uint32_t cb_n_frames_bad;
extern uint32_t cb_n_truncated;

/* Codes LED — seul canal de diagnostic quand le Wi-Fi est muet : l'USB est
 * monopolisé par le clone CDC (descripteurs byte-exacts, verify.py les vérifie)
 * et l'UART GP0/GP1 demande un adaptateur. Motif répété toutes les ~2 s :
 *
 *   1 impulsion   association en cours          (CYW43_LINK_DOWN)
 *   2 impulsions  SSID introuvable              (CYW43_LINK_NONET)
 *                 -> bande 2,4 GHz absente, hors de portée, ou SSID masqué
 *   3 impulsions  authentification refusée      (CYW43_LINK_BADAUTH)
 *                 -> mauvaise PSK, ou type d'auth non supporté par l'AP
 *   4 impulsions  échec générique               (CYW43_LINK_FAIL)
 *   allumée fixe  associée, netlog en écoute
 *   clignotement rapide  client TCP connecté sur 8765
 *
 * Une seule écriture SPI par transition : la LED du Pico W est derrière le
 * CYW43, on ne la pilote pas depuis la boucle serrée.
 */
static void led_service(int pulses) {
  static int s_pulses = -99;
  static int s_step;
  static bool s_on;
  static absolute_time_t s_next;

  if (pulses != s_pulses) {
    s_pulses = pulses;
    s_step = 0;
    s_on = false;
    s_next = get_absolute_time();
  }
  if (absolute_time_diff_us(get_absolute_time(), s_next) > 0) return;

  if (s_pulses == 0) { /* associée : allumée fixe */
    if (!s_on) {
      s_on = true;
      cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
    }
    s_next = make_timeout_time_ms(500);
    return;
  }
  if (s_pulses < 0) { /* client netlog : clignotement rapide */
    s_on = !s_on;
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, s_on);
    s_next = make_timeout_time_ms(120);
    return;
  }
  if (s_step < 2 * s_pulses) { /* N impulsions courtes */
    s_on = !s_on;
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, s_on);
    s_next = make_timeout_time_ms(150);
    s_step++;
  } else { /* pause longue avant répétition */
    if (s_on) {
      s_on = false;
      cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
    }
    s_next = make_timeout_time_ms(1400);
    s_step = 0;
  }
}

static int led_code_for(int link, bool client) {
  if (client) return -1;
  switch (link) {
    case CYW43_LINK_JOIN:    return 0;
    case CYW43_LINK_NONET:   return 2;
    case CYW43_LINK_BADAUTH: return 3;
    case CYW43_LINK_FAIL:    return 4;
    default:                 return 1;
  }
}

/* Le SSID est diffusé en 5 GHz (canal 36) ET en 2,4 GHz (canal 2). Le CYW43439
 * est mono-bande 2,4 GHz : il verra donc bien le BSS, mais un AP en WPA2/WPA3
 * transition ou en WPA/WPA2 mixte TKIP+AES refuse un join annoncé en
 * WPA2-AES pur. On fait tourner les trois variantes d'un essai à l'autre ;
 * si les trois échouent en BADAUTH, la PSK elle-même est en cause. */
static const uint32_t k_auth[] = {
    CYW43_AUTH_WPA2_AES_PSK,
    CYW43_AUTH_WPA2_MIXED_PSK,
    CYW43_AUTH_WPA3_WPA2_AES_PSK,
};
static unsigned s_auth_idx;

static void apply_static_ip(void) {
  ip4_addr_t ip, mask, gw;
  IP4_ADDR(&ip, CB_IP_A, CB_IP_B, CB_IP_C, CB_IP_D);
  IP4_ADDR(&mask, 255, 255, 255, 0);
  IP4_ADDR(&gw, CB_IP_A, CB_IP_B, CB_IP_C, CB_GW_D);

  cyw43_arch_lwip_begin();
  struct netif *nif = &cyw43_state.netif[CYW43_ITF_STA];
  netif_set_addr(nif, &ip, &mask, &gw);
  netif_set_up(nif);
  cyw43_arch_lwip_end();
}

int main(void) {
  stdio_init_all(); /* UART GP0/GP1 — inutilisé ici, mais gratuit */

  bool wifi_ok = (cyw43_arch_init_with_country(CYW43_COUNTRY_FRANCE) == 0);
  if (wifi_ok) {
    cyw43_arch_enable_sta_mode();
    /* cyw43_wifi_set_up() arme CYW43_DEFAULT_PM = PM2 (power save agressif).
     * En PM2 le CYW43 dort entre deux beacons et laisse tomber des ARP
     * unicast : la carte est associée mais reste muette, exactement le
     * symptôme "ARP incomplete". On coupe. */
    cyw43_wifi_pm(&cyw43_state, CYW43_NONE_PM);
    apply_static_ip();
    cyw43_arch_wifi_connect_async(WIFI_SSID, WIFI_PASSWORD, k_auth[s_auth_idx]);
    netlog_init(CB_LOG_PORT);
    netcontrol_init();
  }

  netlog_printf("================================================================");
  netlog_printf("Workbench TXDIAG v1.2 TX90 / Pico W — variante %s", cb_variant_name());
  netlog_printf("IP statique %u.%u.%u.%u, log TCP port %u", CB_IP_A, CB_IP_B, CB_IP_C, CB_IP_D,
                CB_LOG_PORT);
  netlog_printf("WiFi SSID \"%s\", init %s", WIFI_SSID, wifi_ok ? "ok" : "ECHEC");
  netlog_printf("Oracle 1 : trame 0x22 valide = changement de phase");
  netlog_printf("Oracle 2 : trame 0x21 valide portant des LE16 en 1000-3500 = valeurs vivantes");
  netlog_printf("================================================================");

  tud_init(0);

  absolute_time_t next_status = make_timeout_time_ms(10000);
  absolute_time_t next_wifi_retry = make_timeout_time_ms(20000);
  int last_link = -99;

  while (true) {
    uint32_t diag_t0=time_us_32();
    if (tud_inited()) tud_task();
    uint32_t diag_t1=time_us_32();
    if (wifi_ok) netcontrol_poll();
    uint32_t diag_t2=time_us_32();
    cb_tx_diag_loop(diag_t1-diag_t0, diag_t2-diag_t1);
    netlog_poll();

    if (wifi_ok) {
      int link = cyw43_wifi_link_status(&cyw43_state, CYW43_ITF_STA);
      if (link != last_link) {
        last_link = link;
        netlog_printf("WiFi link status = %d", link);
        if (link == CYW43_LINK_JOIN) {
          apply_static_ip();
          const ip4_addr_t *a = netif_ip4_addr(&cyw43_state.netif[CYW43_ITF_STA]);
          netlog_printf("associe avec auth[%u], netif addr %s, link_up=%d", s_auth_idx,
                        ip4addr_ntoa(a), netif_is_link_up(&cyw43_state.netif[CYW43_ITF_STA]));
        }
      }

      /* L'expérience est un one-shot : une association ratée au cold-boot
       * coûterait tout le run. On relance tant qu'on n'est pas associé. */
      if (absolute_time_diff_us(get_absolute_time(), next_wifi_retry) < 0) {
        next_wifi_retry = make_timeout_time_ms(20000);
        if (link < CYW43_LINK_JOIN) {
          s_auth_idx = (s_auth_idx + 1) % (sizeof(k_auth) / sizeof(k_auth[0]));
          netlog_printf("WiFi non associe (status=%d), essai auth[%u]=0x%08lx", link, s_auth_idx,
                        (unsigned long)k_auth[s_auth_idx]);
          cyw43_arch_wifi_connect_async(WIFI_SSID, WIFI_PASSWORD, k_auth[s_auth_idx]);
        }
      }
      led_service(led_code_for(link, netlog_connected()));
    }

    if (absolute_time_diff_us(get_absolute_time(), next_status) < 0) {
      next_status = make_timeout_time_ms(10000);
      netlog_printf(
          "STATUS mounted=%d | GET_LC=%lu SET_LC=%lu SET_CLS=%lu BREAK=%lu autres=%lu | OUT "
          "xfer=%lu octets=%lu | trames=%lu dont phase(0x22)=%lu live(0x21)=%lu invalides=%lu "
          "tronquees=%lu "
          "| log perdus=%lu | rx_errors=%lu rx_zlp=%lu rx_rearm_failed=%lu",
          tud_mounted() ? 1 : 0, (unsigned long)cb_n_get_line_coding,
          (unsigned long)cb_n_set_line_coding, (unsigned long)cb_n_set_control_line_state,
          (unsigned long)cb_n_send_break, (unsigned long)cb_n_ctrl_other,
          (unsigned long)cb_n_out_xfer, (unsigned long)cb_n_out_bytes, (unsigned long)cb_n_frames,
          (unsigned long)cb_n_frames_phase, (unsigned long)cb_n_frames_live,
          (unsigned long)cb_n_frames_bad,
          (unsigned long)cb_n_truncated, (unsigned long)netlog_dropped(),
          (unsigned long)cb_n_out_errors, (unsigned long)cb_n_out_zlp,
          (unsigned long)cb_n_out_rearm_failed);
    }
  }
}
