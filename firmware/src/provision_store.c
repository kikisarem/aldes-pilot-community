#include "provision_config.h"
#include "hardware/flash.h"
#include "pico/flash.h"
#include <string.h>
#define CONFIG_BASE (2u*1024u*1024u-2u*FLASH_SECTOR_SIZE)
_Static_assert(sizeof(config_record)<=FLASH_PAGE_SIZE,"configuration must fit a page");
static const config_record *slot(unsigned i){return (const config_record *)(XIP_BASE+CONFIG_BASE+i*FLASH_SECTOR_SIZE);}
static int current(void){bool a=config_valid(slot(0)),b=config_valid(slot(1));if(!a&&!b)return -1;if(!a)return 1;if(!b)return 0;return (int32_t)(slot(1)->sequence-slot(0)->sequence)>0?1:0;}
bool provision_load(wifi_settings *w){int i=current();if(i<0)return false;*w=slot(i)->wifi;return true;}
static struct {uint32_t offset;uint8_t data[FLASH_PAGE_SIZE];} pending;
static void write_flash(void *unused){(void)unused;flash_range_erase(pending.offset,FLASH_SECTOR_SIZE);flash_range_program(pending.offset,pending.data,FLASH_PAGE_SIZE);}
bool provision_save(const wifi_settings *w){int old=current(),next=old==0?1:0;config_record r={0};r.magic=CONFIG_MAGIC;r.version=1;r.sequence=old<0?1:slot(old)->sequence+1;r.wifi=*w;r.crc=config_crc(&r,offsetof(config_record,crc));r.seal=CONFIG_SEAL;if(!config_valid(&r))return false;memset(pending.data,255,sizeof pending.data);memcpy(pending.data,&r,sizeof r);pending.offset=CONFIG_BASE+next*FLASH_SECTOR_SIZE;
 if(flash_safe_execute(write_flash,NULL,2000)!=PICO_OK)return false;
 return config_valid(slot(next))&&!memcmp(slot(next),&r,sizeof r);
}
