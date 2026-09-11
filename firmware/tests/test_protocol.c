#include "control_protocol.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
int main(void) {
 tx_gate g={0}; uint8_t b[TX_MAX];uint16_t n;uint32_t id;
 assert(!gate_take(&g,0,1));
 gate_arm(&g,100);assert(gate_take(&g,101,1));assert(!gate_take(&g,102,2));
 gate_arm(&g,200);assert(!gate_take(&g,201,1));assert(!gate_take(&g,202,2));
 gate_arm(&g,100);assert(!gate_take(&g,30100,2));
 gate_arm(&g,UINT32_MAX-10);assert(gate_take(&g,10,2));
 gate_arm(&g,30);gate_disarm(&g);assert(!gate_take(&g,31,3));
 assert(parse_send("SEND 3 FDFA08FF4121FEA2",&id,b,&n));assert(n==8 && id==3 && b[7]==0xa2);
 const char *bad[]={"SEND 0 FF","SEND 1 F","SEND -1 FF","SEND 4294967296 FF","SEND 1 ","SEND 1 GG","SEND 1 FF FF","SEND 1 FF\r","SEND 1 FF\nARM","SEND 1","SEND 1FF","SEND 1  FF"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);i++) assert(!parse_send(bad[i],&id,b,&n));
 char big[1100]="SEND 4294967295 ";size_t s=strlen(big);memset(big+s,'F',1024);big[s+1024]=0;
 assert(parse_send(big,&id,b,&n));assert(n==512 && id==UINT32_MAX);
 big[s+1024]='F';big[s+1025]='F';big[s+1026]=0;assert(!parse_send(big,&id,b,&n));
 puts("PASS protocol: one shot, expiry/wrap, disarm, replay, strict hex, bounds/overflow");
}
