#ifndef _TUSB_CONFIG_H_
#define _TUSB_CONFIG_H_

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CFG_TUSB_MCU
#define CFG_TUSB_MCU          OPT_MCU_RP2040
#endif

#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS           OPT_OS_PICO
#endif

#ifndef CFG_TUSB_DEBUG
#define CFG_TUSB_DEBUG        0
#endif

#define CFG_TUD_ENABLED       1
#define CFG_TUD_MAX_SPEED     OPT_MODE_FULL_SPEED

#ifndef CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_SECTION
#endif

#ifndef CFG_TUSB_MEM_ALIGN
#define CFG_TUSB_MEM_ALIGN    __attribute__ ((aligned(4)))
#endif

#define CFG_TUD_ENDPOINT0_SIZE 64

/* Aucun driver de classe built-in : le clone ConnectBox est fourni par
 * l'application via usbd_app_driver_get_cb() (cf. src/cb_cdc_driver.c).
 * C'est ce qui nous donne le contrôle byte-exact sur GET_LINE_CODING. */
#define CFG_TUD_CDC           0
#define CFG_TUD_MSC           0
#define CFG_TUD_HID           0
#define CFG_TUD_MIDI          0
#define CFG_TUD_AUDIO         0
#define CFG_TUD_VIDEO         0
#define CFG_TUD_VENDOR        0
#define CFG_TUD_USBTMC        0
#define CFG_TUD_DFU           0
#define CFG_TUD_DFU_RUNTIME   0
#define CFG_TUD_ECM_RNDIS     0
#define CFG_TUD_NCM           0
#define CFG_TUD_BTH           0

#ifdef __cplusplus
}
#endif

#endif
