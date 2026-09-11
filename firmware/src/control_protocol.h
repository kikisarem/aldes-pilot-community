#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define TX_MAX 512
/* Fail closed. ARM authorizes exactly one attempt within 30 seconds. */
typedef struct { bool armed; uint32_t armed_at; uint32_t last_id; } tx_gate;
void gate_disarm(tx_gate *g);
void gate_arm(tx_gate *g, uint32_t now);
bool gate_take(tx_gate *g, uint32_t now, uint32_t id);
bool parse_send(const char *line, uint32_t *id, uint8_t *out, uint16_t *len);
