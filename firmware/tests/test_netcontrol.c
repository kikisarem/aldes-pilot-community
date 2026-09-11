#include "test_hal.h"
#include "cb_tx.h"
bool cb_tx_start(const uint8_t *b,uint16_t n,uint32_t id){assert(n==8 && b[0]==0xfd);submissions++;busy=true;job=id;state="PENDING";return true;}
bool cb_tx_busy(void){return busy;}
void cb_tx_service(void){}
void cb_tx_cancel(void){if(busy){busy=false;inited=false;state="ABORTED_USB_OFF";}}
const char *cb_tx_state(void){return state;}
uint32_t cb_tx_id(void){return job;}
#include "../src/netcontrol.c"
static void feed(const char *text){struct pbuf p={0,(void*)text,(u16_t)strlen(text),(u16_t)strlen(text)};receive(NULL,&fake,&p,ERR_OK);}
static void cmd(const char *s){feed(s);netcontrol_poll();}
static void connect_auth(void){assert(accept_client(NULL,&fake,ERR_OK)==ERR_OK);cmd("AUTH test-token\n");assert(authenticated);}
int main(void){
 netcontrol_init();netcontrol_poll();assert(submissions==0);
 connect_auth();cmd("STATUS\n");assert(submissions==0);
 cmd("SEND 1 FDFA08FF4121FEA2\n");assert(submissions==0);
 cmd("ARM\n");feed("SEND 1 FDFA08");netcontrol_poll();assert(submissions==0);
 feed("FF4121FEA2\n");assert(submissions==0);netcontrol_poll();assert(submissions==1);
 cmd("ARM\n");assert(!gate.armed); /* busy */
 drop();netcontrol_poll();assert(!busy && !inited && !gate.armed);
 connect_auth();cmd("USBON\n");assert(inited && usbstarts==1 && submissions==1);
 cmd("ARM\n");cmd("SEND 1 FDFA08FF4121FEA2\n");assert(submissions==1); /* duplicate */
 cmd("ARM\n");clock_ms+=30000;cmd("SEND 2 FDFA08FF4121FEA2\n");assert(submissions==1);
 cmd("ARM\n");netcontrol_usb_reset();netcontrol_poll();cmd("SEND 2 FDFA08FF4121FEA2\n");assert(submissions==1);
 cmd("ARM\n");feed("SEND 2 FDFA08FF4121FEA2\nSTATUS\n");netcontrol_poll();assert(submissions==1 && !client);
 connect_auth();cmd("ARM\n");char big[1200];memset(big,'x',1199);big[1199]=0;feed(big);netcontrol_poll();assert(!client && !gate.armed);
 connect_auth();cmd("ARM\n");clock_ms+=61000;netcontrol_poll();assert(!client && !gate.armed);
 accept_client(NULL,&fake,ERR_OK);cmd("AUTH wrong\n");netcontrol_poll();assert(!client && !authenticated);
 assert(submissions==1);
 inited=true;connect_auth();cmd("ARM\n");cmd("SEND 2 FDFA08FF4121FEA2\n");assert(submissions==2 && busy);
 for(int i=0;i<9;i++){clock_ms+=10000;cmd("STATUS\n");assert(client && busy && !gate.armed && submissions==2);}
 cmd("STOP\n");assert(!busy && !inited && submissions==2);cmd("USBON\n");assert(inited && submissions==2);
 puts("PASS TCP 90s: periodic STATUS prevents idle drop; STOP cancels; USBON never replays");
 puts("PASS TCP/main: fragmented line, no IRQ TX, authentication, busy, disconnect, replay, expiry, reset, pipeline/overflow, idle timeout");
}
