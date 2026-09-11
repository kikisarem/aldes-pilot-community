/* Single control client, separate from passive TCP 8765. No USB in callbacks. */
#include "netcontrol.h"
#include "cb_tx.h"
#include "control_protocol.h"
#if CB_PROVISIONING
#include "provision_config.h"
#else
#include "control_config.h"
#endif
#include "netlog.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "lwip/tcp.h"
#include "tusb.h"
#include <stdio.h>
#include <string.h>
static struct tcp_pcb *client;
static char line[1100];
static size_t used;
static bool ready, lost, authenticated, usb_reset;
static uint32_t last_activity;
static tx_gate gate;
static uint32_t now(void) { return to_ms_since_boot(get_absolute_time()); }
void netcontrol_usb_reset(void) { gate_disarm(&gate); usb_reset=true; }
static void drop(void) {
 if(client) {
  struct tcp_pcb *p=client; client=NULL;
  tcp_arg(p,NULL); tcp_err(p,NULL); tcp_recv(p,NULL); tcp_abort(p);
 }
 lost=true;
}
static bool reply(const char *s) {
 if(!client) return false;
 if(tcp_write(client,s,(u16_t)strlen(s),TCP_WRITE_FLAG_COPY)!=ERR_OK) { drop(); return false; }
 tcp_output(client); return true;
}
static void on_error(void *arg, err_t err) { (void)arg;(void)err; client=NULL; lost=true; }
static err_t receive(void *arg,struct tcp_pcb *pcb,struct pbuf *p,err_t err) {
 (void)arg;
 if(!p || err!=ERR_OK) { if(p) pbuf_free(p); drop(); return ERR_ABRT; }
 bool bad=false;
 for(struct pbuf *q=p;q;q=q->next) {
  const unsigned char *v=q->payload;
  for(u16_t i=0;i<q->len;i++) {
   unsigned char c=v[i];
   if(ready || used>=sizeof(line)-1 || (c!='\n' && c!='\r' && (c<32 || c>126))) { bad=true; break; }
   if(c=='\n') { if(used && line[used-1]=='\r') used--; line[used]=0; ready=true; }
   else line[used++]=(char)c;
  }
  if(bad) break;
 }
 tcp_recved(pcb,p->tot_len); pbuf_free(p); last_activity=now();
 if(bad) {drop();return ERR_ABRT;}
 return ERR_OK;
}
static err_t accept_client(void *arg,struct tcp_pcb *pcb,err_t err) {
 (void)arg;
 if(err!=ERR_OK || !pcb) return ERR_VAL;
 if(client || lost) {tcp_abort(pcb);return ERR_ABRT;}
 client=pcb; used=0;ready=false;authenticated=false;gate_disarm(&gate);last_activity=now();
 tcp_recv(pcb,receive);tcp_err(pcb,on_error);tcp_nagle_disable(pcb);
 if(!reply("WORKBENCH 1 AUTH_REQUIRED\n")) return ERR_ABRT;
 return ERR_OK;
}
void netcontrol_init(void) {
 cyw43_arch_lwip_begin();
 struct tcp_pcb *p=tcp_new_ip_type(IPADDR_TYPE_V4);
 if(p) {
  if(tcp_bind(p,IP_ANY_TYPE,8766)==ERR_OK) {
   struct tcp_pcb *l=tcp_listen_with_backlog(p,1);
   if(l) tcp_accept(l,accept_client); else tcp_close(p);
  } else tcp_close(p);
 }
 cyw43_arch_lwip_end();
}
static void command(void) {
 if(!authenticated) {
#if CB_PROVISIONING
  if(!strncmp(line,"AUTH ",5) && runtime_wifi.token[0] && !strcmp(line+5,runtime_wifi.token))
#else
  if(!strcmp(line,"AUTH " CONTROL_TOKEN))
#endif
  {authenticated=true;reply("OK AUTH\n");}
  else drop();
  return;
 }
 if(!strcmp(line,"STATUS")) {
  char b[240];
  snprintf(b,sizeof(b),"STATUS mounted=%u usb=%u armed=%u last=%lu txid=%lu tx=%s max=512 tx_timeout_ms=%u\n",
   tud_inited() && tud_mounted(),tud_inited(),gate.armed && (uint32_t)(now()-gate.armed_at)<30000u,
   (unsigned long)gate.last_id,(unsigned long)cb_tx_id(),cb_tx_state(),(unsigned)CB_TX_TIMEOUT_MS); reply(b);
 } else if(!strcmp(line,"ARM")) {
  if(!tud_inited() || !tud_mounted() || cb_tx_busy()) {gate_disarm(&gate);reply("ERR USB_NOT_READY\n");}
  else {gate_arm(&gate,now());reply("OK ARM ONE_ATTEMPT 30000ms\n");}
 } else if(!strcmp(line,"STOP")) {
  gate_disarm(&gate);cb_tx_cancel();reply("OK STOP\n");
 } else if(!strcmp(line,"USBON")) {
  gate_disarm(&gate);
  if(cb_tx_busy()) reply("ERR BUSY\n");
  else if(tud_inited() || tud_init(0)) reply("OK USBON NO_REPLAY\n");
  else reply("ERR USB_INIT\n");
 } else {
  uint32_t id; uint16_t len; uint8_t bytes[TX_MAX];
  if(!parse_send(line,&id,bytes,&len)) {gate_disarm(&gate);reply("ERR COMMAND_OR_HEX\n");}
  else if(!gate_take(&gate,now(),id)) reply("ERR NOT_ARMED_EXPIRED_OR_ID\n");
  else if(!cb_tx_start(bytes,len,id)) reply("ERR NOT_SUBMITTED ID_CONSUMED\n");
  else reply("OK SUBMITTED\n");
 }
}
void netcontrol_poll(void) {
 /* Synchronizes against the SDK background TCP callbacks. */
 cyw43_arch_lwip_begin();
 if(client && (uint32_t)(now()-last_activity)>60000u) drop();
 if(lost) {
  gate_disarm(&gate);cb_tx_cancel(); used=0;ready=false;authenticated=false;lost=false;
 }
 cb_tx_service();
 if(usb_reset) {
  usb_reset=false; gate_disarm(&gate);
  if(ready) {used=0;ready=false;reply("ERR USB_RESET COMMAND_DISCARDED\n");}
 }
 if(ready && client) {
  command();memset(line,0,sizeof(line));used=0;ready=false;
 }
 cyw43_arch_lwip_end();
}
