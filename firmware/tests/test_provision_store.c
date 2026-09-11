#include "provision_config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
_Alignas(4) unsigned char fake_flash[2*1024*1024];
static int cut;
void flash_range_erase(uint32_t offset,size_t n){assert(offset>=sizeof(fake_flash)-8192&&offset+n<=sizeof fake_flash);memset(fake_flash+offset,255,n);}
void flash_range_program(uint32_t offset,const uint8_t *data,size_t n){if(cut==1)return;if(cut==2)n=33;memcpy(fake_flash+offset,data,n);}
int flash_safe_execute(void (*fn)(void *),void *arg,uint32_t timeout){(void)timeout;fn(arg);return 0;}
#include "../src/provision_store.c"
int main(void){
 memset(fake_flash,255,sizeof fake_flash);wifi_settings a,b,out;const char *token="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
 assert(!provision_load(&out));assert(config_form("nonce=n&ssid=first&password=password&ip=&gateway=","n",token,&a));assert(provision_save(&a));assert(provision_load(&out)&&!memcmp(&a,&out,sizeof a));
 assert(config_form("nonce=n&ssid=second&password=password&ip=&gateway=","n",token,&b));
 for(cut=1;cut<=2;cut++){assert(!provision_save(&b));assert(provision_load(&out)&&!memcmp(&a,&out,sizeof a));}
 cut=0;assert(provision_save(&b));assert(provision_load(&out)&&!memcmp(&b,&out,sizeof b));assert(provision_save(&a));assert(provision_load(&out)&&!memcmp(&a,&out,sizeof a));
 puts("PASS flash journal: blank, alternating writes, interrupted erase/program retains previous configuration");
}
