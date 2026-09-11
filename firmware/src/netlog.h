#ifndef NETLOG_H
#define NETLOG_H

#include <stdbool.h>
#include <stdint.h>

/* Logger TCP : le port USB du Pico est pris par la T.One, le seul canal de
 * sortie est le WiFi. Tout est bufferisé dans un ring, on ne perd donc pas les
 * lignes émises avant que le client `nc` ne se connecte. */

void netlog_init(uint16_t port);
void netlog_poll(void);
void netlog_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
void netlog_hex(const char *prefix, const uint8_t *data, uint32_t len);
bool netlog_connected(void);
uint32_t netlog_dropped(void);

#endif
