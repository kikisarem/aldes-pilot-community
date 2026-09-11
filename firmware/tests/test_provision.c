#include "provision_config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 const char *token="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
 wifi_settings w;assert(config_form("nonce=n&ssid=test+wifi&password=p%26ssword123&ip=&gateway=","n",token,&w));
 assert(!strcmp(w.ssid,"test wifi")&&!strcmp(w.password,"p&ssword123")&&w.ip[0]==0);
 assert(config_form("nonce=n&ssid=test&password=password&ip=192.168.1.50&gateway=192.168.1.1","n",token,&w));
 const char *bad[]={"nonce=x&ssid=t&password=password&ip=&gateway=","nonce=n&ssid=t&ssid=other&password=password&ip=&gateway=","nonce=n&ssid=t%00evil&password=password&ip=&gateway=","nonce=n&ssid=t&password=short&ip=&gateway=","nonce=n&ssid=t&password=password&ip=192.168.1.1&gateway=192.168.1.1","nonce=n&ssid=t&password=password&ip=192.168.1.50&gateway=192.168.2.1","nonce=n&ssid=t&password=password&ip=999.1.1.1&gateway=1.1.1.1","nonce=n&ssid=t%ZZ&password=password&ip=&gateway="};
 for(unsigned i=0;i<sizeof bad/sizeof bad[0];i++)assert(!config_form(bad[i],"n",token,&w));
 assert(config_form("nonce=n&ssid=test&password=password&ip=&gateway=","n",token,&w));
 config_record r={0};r.magic=CONFIG_MAGIC;r.version=1;r.sequence=4;r.wifi=w;r.seal=CONFIG_SEAL;r.crc=config_crc(&r,offsetof(config_record,crc));assert(config_valid(&r));
 for(size_t i=0;i<sizeof r;i++){config_record broken=r;((unsigned char*)&broken)[i]^=1;assert(!config_valid(&broken));}
 memset(&r,255,sizeof r);assert(!config_valid(&r));puts("PASS provisioning: form bounds, duplicates, null injection, IP validation, CRC corruption/erased record");
}
