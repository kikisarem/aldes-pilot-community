#include "control_protocol.h"
#include <string.h>
void gate_disarm(tx_gate *g) { g->armed = false; }
void gate_arm(tx_gate *g, uint32_t now) { g->armed = true; g->armed_at = now; }
bool gate_take(tx_gate *g, uint32_t now, uint32_t id) {
 bool ok = g->armed && (uint32_t)(now-g->armed_at) < 30000u && id > g->last_id;
 g->armed = false;
 if (ok) g->last_id = id;
 return ok;
}
static int nibble(char c) {
 if(c >= '0' && c <= '9') return c-'0';
 if(c >= 'a' && c <= 'f') return c-'a'+10;
 if(c >= 'A' && c <= 'F') return c-'A'+10;
 return -1;
}
bool parse_send(const char *p, uint32_t *id, uint8_t *out, uint16_t *len) {
 if (strncmp(p,"SEND ",5)) return false;
 p+=5; uint32_t n=0; unsigned digits=0;
 while (*p >= '0' && *p <= '9') {
  unsigned v=(unsigned)(*p++-'0');
  if (n > (UINT32_MAX-v)/10u) return false;
  n=n*10u+v; digits++;
 }
 if (!digits || !n || *p++ != ' ') return false;
 size_t size=strlen(p);
 if (!size || size%2 || size > TX_MAX*2) return false;
 for(size_t i=0;i<size;i+=2) {
  int a=nibble(p[i]), b=nibble(p[i+1]);
  if(a<0 || b<0) return false;
  out[i/2]=(uint8_t)(a*16+b);
 }
 *len=(uint16_t)(size/2); *id=n; return true;
}
