/* Descripteurs USB — clone byte-exact de l'AldesConnect Box (STM32 VCP).
 *
 * Source des octets : capture publique HACF #505 (1er janvier 2026), reproduite
 * dans FABLE_FRESH_USB_REVIEW.md. Les tableaux ci-dessous sont recopiés
 * littéralement depuis cette capture — ne pas "nettoyer", ne pas régénérer avec
 * les macros TUD_CDC_DESCRIPTOR : la macro TinyUSB insère un IAD et une classe
 * device 0xEF, ce que la vraie ConnectBox ne fait pas.
 */

#include <string.h>

#include "netlog.h"
#include "tusb.h"

/* ------------------------------------------------------------------ device */
/* 12 01 00 02 02 02 00 40 83 04 40 57 00 02 01 02 03 01 */
static uint8_t const desc_device[] = {
    0x12,       /* bLength                                                    */
    0x01,       /* bDescriptorType = DEVICE                                   */
    0x00, 0x02, /* bcdUSB 2.00                                                */
    0x02,       /* bDeviceClass    = CDC                                      */
    0x02,       /* bDeviceSubClass = ACM                                      */
    0x00,       /* bDeviceProtocol                                            */
    0x40,       /* bMaxPacketSize0 = 64                                       */
    0x83, 0x04, /* idVendor  0x0483 STMicroelectronics                        */
    0x40, 0x57, /* idProduct 0x5740 STM32 Virtual ComPort                     */
    0x00, 0x02, /* bcdDevice 2.00                                             */
    0x01,       /* iManufacturer                                              */
    0x02,       /* iProduct                                                   */
    0x03,       /* iSerialNumber                                              */
    0x01        /* bNumConfigurations                                         */
};

/* Journalisation au niveau enumeration. Ces callbacks ne passent JAMAIS par le
 * driver de classe : sans eux, "on logge toutes les requetes de controle" est
 * faux — GET_DESCRIPTOR, SET_ADDRESS et SET_CONFIGURATION restent invisibles.
 * Or la sequence d'enumeration est en elle-meme une signature de la pile hote,
 * et un oracle secondaire pour comparer notre T.One a celle de la capture. */
uint32_t cb_n_desc_device;
uint32_t cb_n_desc_config;
uint32_t cb_n_desc_string;

uint8_t const *tud_descriptor_device_cb(void) {
  cb_n_desc_device++;
  netlog_printf("ENUM GET_DESCRIPTOR device #%lu", (unsigned long)cb_n_desc_device);
  return desc_device;
}

/* ----------------------------------------------------------- configuration */
/* 67 octets, sans IAD, self-powered 0xC0, 100 mA */
static uint8_t const desc_configuration[] = {
    /* Configuration, 2 interfaces, total 0x0043 = 67                         */
    0x09, 0x02, 0x43, 0x00, 0x02, 0x01, 0x00, 0xC0, 0x32,
    /* Interface 0 : CDC control, 1 EP, class 02 / sub 02 / proto 01          */
    0x09, 0x04, 0x00, 0x00, 0x01, 0x02, 0x02, 0x01, 0x00,
    /* CDC Header, bcdCDC 1.10                                                */
    0x05, 0x24, 0x00, 0x10, 0x01,
    /* CDC Call Management, capabilities 0x00, data interface 1               */
    0x05, 0x24, 0x01, 0x00, 0x01,
    /* CDC ACM, capabilities 0x02                                             */
    0x04, 0x24, 0x02, 0x02,
    /* CDC Union, master 0, slave 1                                           */
    0x05, 0x24, 0x06, 0x00, 0x01,
    /* EP 0x82 IN interrupt, 8 octets, bInterval 0x10                         */
    0x07, 0x05, 0x82, 0x03, 0x08, 0x00, 0x10,
    /* Interface 1 : CDC data, 2 EP, class 0x0A                               */
    0x09, 0x04, 0x01, 0x00, 0x02, 0x0A, 0x00, 0x00, 0x00,
    /* EP 0x01 OUT bulk 64                                                    */
    0x07, 0x05, 0x01, 0x02, 0x40, 0x00, 0x00,
    /* EP 0x81 IN bulk 64                                                     */
    0x07, 0x05, 0x81, 0x02, 0x40, 0x00, 0x00};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
  cb_n_desc_config++;
  netlog_printf("ENUM GET_DESCRIPTOR config #%lu (index=%u)", (unsigned long)cb_n_desc_config,
                index);
  return desc_configuration;
}

/* ----------------------------------------------------------------- strings */
static char const *const string_desc_arr[] = {
    NULL,                     /* 0 : langid, traité à part                    */
    "STMicroelectronics",     /* 1 : iManufacturer                            */
    "STM32 Virtual ComPort",  /* 2 : iProduct                                 */
    "00000000001A",           /* 3 : iSerialNumber                            */
};

static uint16_t _desc_str[32];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
  uint8_t chr_count;

  cb_n_desc_string++;
  netlog_printf("ENUM GET_DESCRIPTOR string index=%u langid=0x%04X", index, langid);

  if (index == 0) {
    _desc_str[1] = 0x0409; /* English (United States) */
    chr_count = 1;
  } else {
    if (index >= TU_ARRAY_SIZE(string_desc_arr)) return NULL;

    char const *str = string_desc_arr[index];
    chr_count = (uint8_t)strlen(str);
    if (chr_count > 31) chr_count = 31;

    for (uint8_t i = 0; i < chr_count; i++) {
      _desc_str[1 + i] = (uint16_t)str[i];
    }
  }

  _desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));
  return _desc_str;
}


/* ----------------------------------------------- evenements de bus et vendor */

void tud_mount_cb(void) { netlog_printf("ENUM SET_CONFIGURATION : device monte"); }

void tud_umount_cb(void) { netlog_printf("ENUM device demonte"); }

void tud_suspend_cb(bool remote_wakeup_en) {
  netlog_printf("BUS suspend (remote_wakeup_en=%d)", remote_wakeup_en ? 1 : 0);
}

void tud_resume_cb(void) { netlog_printf("BUS resume"); }

/* Juin n'avait vu aucune requete vendor, mais son instrumentation ne pouvait pas
 * en voir. Ici on les journalise avant de staller. */
bool tud_vendor_control_xfer_cb(uint8_t rhport, uint8_t stage,
                                tusb_control_request_t const *request) {
  (void)rhport;
  if (stage == CONTROL_STAGE_SETUP) {
    netlog_printf(
        "CTRL VENDOR bmRequestType=0x%02X bRequest=0x%02X wValue=0x%04X wIndex=0x%04X wLength=%u "
        "-> stall",
        request->bmRequestType, request->bRequest, request->wValue, request->wIndex,
        request->wLength);
  }
  return false;
}
