/* Setup only: USB CDC/control/log services are never started in this mode. */
#include "provision_config.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "pico/rand.h"
#include "pico/unique_id.h"
#include "hardware/watchdog.h"
#include "lwip/tcp.h"
#include "dhcpserver.h"
#include "dnsserver.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <strings.h>
wifi_settings runtime_wifi;
extern bool provision_save(const wifi_settings *);
static struct tcp_pcb *client;
static char request[2048],reply_buf[4096],nonce[65],token[65];
static size_t used;static unsigned idle;
static bool responded,save_pending,saved,save_failed;
static wifi_settings incoming;
static void random_hex(char *out){for(int i=0;i<8;i++)snprintf(out+i*8,9,"%08lx",(unsigned long)get_rand_32());}
static void gone(void *arg,err_t err){(void)arg;(void)err;client=NULL;}
static err_t abort_client(struct tcp_pcb *pcb){if(client==pcb)client=NULL;tcp_arg(pcb,NULL);tcp_err(pcb,NULL);tcp_recv(pcb,NULL);tcp_sent(pcb,NULL);tcp_poll(pcb,NULL,0);tcp_abort(pcb);return ERR_ABRT;}
static err_t sent(void *arg,struct tcp_pcb *pcb,u16_t len){(void)arg;(void)len;/* keep response until peer closes; bounded by poll */(void)pcb;return ERR_OK;}
static err_t poll_client(void *arg,struct tcp_pcb *pcb){(void)arg;if(++idle>10)return abort_client(pcb);return ERR_OK;}
static err_t respond(struct tcp_pcb *pcb,const char *status,const char *body){int n=snprintf(reply_buf,sizeof reply_buf,"HTTP/1.1 %s\r\nContent-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: %u\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'\r\n\r\n%s",status,(unsigned)strlen(body),body);responded=true;if(n<0||n>=(int)sizeof reply_buf||tcp_write(pcb,reply_buf,n,TCP_WRITE_FLAG_COPY)!=ERR_OK)return abort_client(pcb);tcp_output(pcb);return ERR_OK;}
static err_t handle(struct tcp_pcb *pcb){
 char *end=strstr(request,"\r\n\r\n");if(!end)return ERR_OK;
 if(!strncmp(request,"GET / ",7)){
 char body[3000];snprintf(body,sizeof body,"<!doctype html><meta name=viewport content='width=device-width'><title>Aldes Pilot — Wi-Fi</title><style>body{font:18px system-ui;max-width:32em;margin:2em auto;padding:1em}input,button{box-sizing:border-box;width:100%%;padding:12px;margin:8px 0}code{overflow-wrap:anywhere}</style><h1>Connecter le Pico</h1><p>Configuration locale. Réseau Wi-Fi 2,4 GHz WPA2/WPA3. Aucun pilotage de la PAC pendant cette étape.</p><p>Copiez ce token dans les options du bridge Home Assistant avant de valider :</p><code>%s</code><form method=post action=/save><input type=hidden name=nonce value='%s'><label>Nom du Wi-Fi<input name=ssid maxlength=32 required autocomplete=off></label><label>Mot de passe<input type=password name=password minlength=8 maxlength=63 required autocomplete=new-password></label><details><summary>Adresse fixe (facultatif, réseau /24)</summary><label>Adresse libre du Pico<input name=ip placeholder='192.168.1.50'></label><label>Passerelle<input name=gateway placeholder='192.168.1.1'></label></details><p>Sans adresse fixe, trouvez ensuite le Pico dans la liste DHCP du routeur.</p><label><input style='width:auto' type=checkbox required> J’ai copié le token.</label><button>Enregistrer et redémarrer</button></form>",token,nonce);return respond(pcb,"200 OK",body);
 }
 if(!strncmp(request,"POST /save ",11)){
  size_t length=0;bool has_length=false;char *line=strstr(request,"\r\n")+2;
  while(line<end){char *e=strstr(line,"\r\n");if(!e)return respond(pcb,"400 Bad Request","Requête invalide");
   if(!strncasecmp(line,"Transfer-Encoding:",18))return respond(pcb,"400 Bad Request","Encodage refusé");
   if(!strncasecmp(line,"Content-Length:",15)){if(has_length)return respond(pcb,"400 Bad Request","Longueur ambiguë");char *stop;unsigned long v=strtoul(line+15,&stop,10);while(stop<e&&*stop==' ')stop++;if(stop!=e||v>1024)return respond(pcb,"413 Content Too Large","Formulaire trop long");length=v;has_length=true;}
   line=e+2;
  }
  if(!has_length||!length)return respond(pcb,"400 Bad Request","Longueur requise");
  size_t header=end+4-request;if(used<header+length)return ERR_OK;if(used!=header+length||save_pending||saved)return respond(pcb,"409 Conflict","Une configuration est déjà en cours");
  if(!config_form(end+4,nonce,token,&incoming))return respond(pcb,"400 Bad Request","Paramètres invalides. Revenez au formulaire : mot de passe 8–63 caractères ; adresses fixes distinctes sur le même /24.");
  save_pending=true;return respond(pcb,"200 OK","<meta name=viewport content='width=device-width'><h1>Configuration reçue</h1><p>Enregistrement en cours. Le Pico redémarrera si l’écriture est vérifiée. Reconnectez votre téléphone au Wi-Fi de la maison. Ce message ne confirme pas encore la connexion au routeur.</p>");
 }
 return respond(pcb,"404 Not Found","Ouvrez http://192.168.4.1/ pour configurer le Pico.");
}
static err_t receive(void *arg,struct tcp_pcb *pcb,struct pbuf *p,err_t err){(void)arg;if(!p||err!=ERR_OK){if(p)pbuf_free(p);return abort_client(pcb);}if(responded||used+p->tot_len>=sizeof request){pbuf_free(p);return abort_client(pcb);}size_t n=p->tot_len;pbuf_copy_partial(p,request+used,n,0);tcp_recved(pcb,n);pbuf_free(p);if(memchr(request+used,0,n))return abort_client(pcb);used+=n;request[used]=0;idle=0;return handle(pcb);}
static err_t accept_client(void *arg,struct tcp_pcb *pcb,err_t err){(void)arg;if(err!=ERR_OK)return err;if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;used=0;idle=0;responded=false;tcp_recv(pcb,receive);tcp_err(pcb,gone);tcp_sent(pcb,sent);tcp_poll(pcb,poll_client,2);return ERR_OK;}
void provision_run(void){
 random_hex(nonce);random_hex(token);char id[2*PICO_UNIQUE_BOARD_ID_SIZE_BYTES+1],ssid[40];pico_get_unique_board_id_string(id,sizeof id);snprintf(ssid,sizeof ssid,"Aldes-Setup-%.8s",id+8);
 cyw43_arch_enable_ap_mode(ssid,NULL,CYW43_AUTH_OPEN);
 ip_addr_t ip,mask;IP4_ADDR(&ip,192,168,4,1);IP4_ADDR(&mask,255,255,255,0);
 dhcp_server_t dhcp;dns_server_t dns;
 cyw43_arch_lwip_begin();struct netif *nif=&cyw43_state.netif[CYW43_ITF_AP];netif_set_addr(nif,&ip,&mask,&ip);
 dhcp_server_init(&dhcp,nif,&ip,&mask);dns_server_init(&dns,nif,&ip);
 struct tcp_pcb *pcb=tcp_new_ip_type(IPADDR_TYPE_V4);if(!pcb||tcp_bind(pcb,&ip,80)!=ERR_OK)panic("Setup HTTP bind failed");struct tcp_pcb *listen=tcp_listen_with_backlog(pcb,1);if(!listen)panic("Setup HTTP listen failed");tcp_accept(listen,accept_client);cyw43_arch_lwip_end();
 absolute_time_t deadline=make_timeout_time_ms(600000),reboot_at=at_the_end_of_time;
 while(!time_reached(deadline)){
  wifi_settings copy;bool write=false;cyw43_arch_lwip_begin();if(save_pending&&!saved&&!save_failed){copy=incoming;save_pending=false;write=true;}cyw43_arch_lwip_end();
  if(write){bool ok=provision_save(&copy);cyw43_arch_lwip_begin();saved=ok;save_failed=!ok;cyw43_arch_lwip_end();if(ok)reboot_at=make_timeout_time_ms(3000);}
  if(saved&&time_reached(reboot_at)){watchdog_reboot(0,0,0);while(true)tight_loop_contents();}
  cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,(to_ms_since_boot(get_absolute_time())/250)%2);sleep_ms(50);
 }
 cyw43_arch_lwip_begin();if(client)abort_client(client);tcp_close(listen);dhcp_server_deinit(&dhcp);dns_server_deinit(&dns);cyw43_arch_lwip_end();cyw43_arch_disable_ap_mode();
 /* Physical power cycle required after setup timeout; do not expose AP on Wi-Fi loss. */
 while(true)sleep_ms(1000);
}
