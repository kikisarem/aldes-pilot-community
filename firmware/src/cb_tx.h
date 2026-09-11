#pragma once
#include <stdbool.h>
#include <stdint.h>
#define CB_TX_TIMEOUT_MS 90000u
bool cb_tx_start(const uint8_t *data, uint16_t len, uint32_t id);
bool cb_tx_busy(void);
void cb_tx_service(void);
void cb_tx_cancel(void);
const char *cb_tx_state(void);
uint32_t cb_tx_id(void);

void cb_tx_diag_loop(uint32_t usb_us, uint32_t control_us);
