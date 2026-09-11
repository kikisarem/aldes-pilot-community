#include "netlog.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "lwip/tcp.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"

#define RING_SIZE 32768u
#define NETLOG_LINE_MAX  512u

static uint8_t s_ring[RING_SIZE];
static volatile uint32_t s_head; /* écriture */
static volatile uint32_t s_tail; /* lecture  */
static uint32_t s_dropped;

static struct tcp_pcb *s_listen;
static struct tcp_pcb *s_client;

static uint32_t ring_used(void) {
  return (s_head - s_tail) & (RING_SIZE - 1);
}

static uint32_t ring_free(void) {
  return RING_SIZE - 1 - ring_used();
}

static void ring_push(const uint8_t *p, uint32_t n) {
  if (n > ring_free()) {
    /* Le ring est plein : on jette la ligne plutôt que d'écraser l'historique,
     * un trou en fin de log est plus lisible qu'un log corrompu au milieu. */
    s_dropped++;
    return;
  }
  for (uint32_t i = 0; i < n; i++) {
    s_ring[(s_head + i) & (RING_SIZE - 1)] = p[i];
  }
  s_head = (s_head + n) & (RING_SIZE - 1);
}

/* ----------------------------------------------------------------- lwIP cb */

static void client_close(struct tcp_pcb *pcb) {
  if (!pcb) return;
  tcp_arg(pcb, NULL);
  tcp_sent(pcb, NULL);
  tcp_recv(pcb, NULL);
  tcp_err(pcb, NULL);
  tcp_poll(pcb, NULL, 0);
  tcp_close(pcb);
  if (s_client == pcb) s_client = NULL;
}

static err_t on_recv(void *arg, struct tcp_pcb *pcb, struct pbuf *p, err_t err) {
  (void)arg;
  if (err != ERR_OK || p == NULL) {
    client_close(pcb);
    return ERR_OK;
  }
  /* On ignore tout ce que le client envoie, on ne fait que cracher du log. */
  tcp_recved(pcb, p->tot_len);
  pbuf_free(p);
  return ERR_OK;
}

static void on_err(void *arg, err_t err) {
  (void)arg;
  (void)err;
  s_client = NULL; /* pcb déjà libéré par lwIP */
}

static err_t on_accept(void *arg, struct tcp_pcb *pcb, err_t err) {
  (void)arg;
  if (err != ERR_OK || pcb == NULL) return ERR_VAL;

  if (s_client) client_close(s_client);

  s_client = pcb;
  tcp_arg(pcb, NULL);
  tcp_recv(pcb, on_recv);
  tcp_err(pcb, on_err);
  tcp_nagle_disable(pcb);
  return ERR_OK;
}

/* -------------------------------------------------------------------- API */

void netlog_init(uint16_t port) {
  s_head = s_tail = 0;
  s_dropped = 0;

  cyw43_arch_lwip_begin();
  s_listen = tcp_new_ip_type(IPADDR_TYPE_V4);
  if (s_listen) {
    tcp_bind(s_listen, IP_ANY_TYPE, port);
    s_listen = tcp_listen_with_backlog(s_listen, 1);
    tcp_accept(s_listen, on_accept);
  }
  cyw43_arch_lwip_end();
}

bool netlog_connected(void) {
  return s_client != NULL;
}

uint32_t netlog_dropped(void) {
  return s_dropped;
}

void netlog_printf(const char *fmt, ...) {
  char line[NETLOG_LINE_MAX];
  int n;

  /* Horodatage relatif au boot, en ms : c'est ce qui permet de mesurer la
   * cadence des Hello (65-80 s attendues) et le délai post-énumération. */
  n = snprintf(line, sizeof(line), "[%8lu] ", (unsigned long)to_ms_since_boot(get_absolute_time()));
  if (n < 0) return;

  va_list ap;
  va_start(ap, fmt);
  int m = vsnprintf(line + n, sizeof(line) - (uint32_t)n - 2, fmt, ap);
  va_end(ap);
  if (m < 0) return;

  uint32_t len = (uint32_t)n + (uint32_t)m;
  if (len > sizeof(line) - 2) len = sizeof(line) - 2;
  line[len++] = '\r';
  line[len++] = '\n';

  ring_push((const uint8_t *)line, len);
}

void netlog_hex(const char *prefix, const uint8_t *data, uint32_t len) {
  char line[NETLOG_LINE_MAX];
  uint32_t i = 0;

  while (i < len) {
    uint32_t chunk = len - i;
    if (chunk > 32) chunk = 32;

    int n = snprintf(line, sizeof(line), "%s +%03lu:", prefix, (unsigned long)i);
    for (uint32_t j = 0; j < chunk && n > 0 && (uint32_t)n < sizeof(line) - 4; j++) {
      n += snprintf(line + n, sizeof(line) - (uint32_t)n, " %02X", data[i + j]);
    }
    netlog_printf("%s", line);
    i += chunk;
  }
}

void netlog_poll(void) {
  if (!s_client) return;

  cyw43_arch_lwip_begin();

  struct tcp_pcb *pcb = s_client;
  if (pcb) {
    bool wrote = false;
    while (ring_used() > 0) {
      uint16_t sndbuf = tcp_sndbuf(pcb);
      if (sndbuf == 0) break;

      uint32_t contiguous = RING_SIZE - s_tail;
      uint32_t used = ring_used();
      uint32_t chunk = used < contiguous ? used : contiguous;
      if (chunk > sndbuf) chunk = sndbuf;
      if (chunk > 1024) chunk = 1024;

      err_t e = tcp_write(pcb, &s_ring[s_tail], (uint16_t)chunk, TCP_WRITE_FLAG_COPY);
      if (e != ERR_OK) break;

      s_tail = (s_tail + chunk) & (RING_SIZE - 1);
      wrote = true;
    }
    if (wrote) tcp_output(pcb);
  }

  cyw43_arch_lwip_end();
}
