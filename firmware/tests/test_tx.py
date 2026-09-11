#!/usr/bin/env python3
"""Execute the exact TX functions and IN callback body with a mocked USB HAL."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'src/cb_cdc_driver.c').read_text()
code=s[s.index('CFG_TUSB_MEM_SECTION static uint8_t tx_buf'):s.index('/* Compteurs')]
start=s.index('    if (tx_busy) {',s.index('} else if (ep_addr == s_ep_in)'))
end=s.index('\n  }\n  return true;',start)
callback=s[start:end]
pre=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include "control_protocol.h"
#include "cb_tx.h"
#define CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_ALIGN
#define XFER_RESULT_SUCCESS 0
static uint8_t s_ep_in=0x81;
static bool initialized=true,mounted=true,claim=true,xfer_ok=true;
static unsigned calls,reset_count;static uint16_t last_len;static uint32_t clock_ms;
static uint32_t get_absolute_time(void){return clock_ms;}
static uint32_t to_ms_since_boot(uint32_t t){return t;}
static bool tud_inited(void){return initialized;}
static bool tud_mounted(void){return mounted;}
static bool usbd_edpt_claim(int p,int ep){assert(p==0 && ep==0x81);return claim;}
static bool usbd_edpt_release(int p,int ep){(void)p;(void)ep;return true;}
static bool usbd_edpt_xfer(int p,int ep,void *b,uint16_t n){(void)b;assert(p==0 && ep==0x81);calls++;last_len=n;return xfer_ok;}
static bool tud_deinit(int p){assert(p==0);initialized=false;reset_count++;return true;}
static void netcontrol_usb_reset(void){}
static struct { struct {uint32_t in,out;} ep_buf_ctrl[16]; } fake_dpram;
#define usb_dpram (&fake_dpram)
static uint32_t time_us_32(void){return clock_ms*1000u;}
static void diag_log(const char *fmt,...){(void)fmt;}
#define netlog_printf(...) diag_log(__VA_ARGS__)
#define netlog_hex(...) ((void)0)
'''
main=r'''
int main(void){
 uint8_t packet[512]={0xfd,0xfa};
 cb_tx_service();cb_tx_diag_loop(4,5);assert(calls==0 && !cb_tx_busy());
 mounted=false;assert(!cb_tx_start(packet,8,1));mounted=true;
 assert(!cb_tx_start(packet,0,1));assert(!cb_tx_start(packet,513,1));
 claim=false;assert(!cb_tx_start(packet,8,1));claim=true;
 assert(cb_tx_start(packet,8,1));assert(calls==1 && last_len==8);
 unsigned diag_before=calls;clock_ms=1100;cb_tx_diag_loop(9,10);assert(calls==diag_before && cb_tx_busy());
 assert(!cb_tx_start(packet,8,2));packet[0]=0;assert(tx_buf[0]==0xfd);
 complete(0,8);assert(!cb_tx_busy() && !strcmp(cb_tx_state(),"USB_DONE"));
 assert(cb_tx_start(packet,64,2));complete(0,64);assert(cb_tx_busy() && last_len==0);
 complete(0,0);assert(!cb_tx_busy() && !strcmp(cb_tx_state(),"USB_DONE"));
 assert(cb_tx_start(packet,8,3));complete(1,0);assert(!cb_tx_busy() && !strcmp(cb_tx_state(),"TRANSFER_FAILED"));
 clock_ms=100;assert(cb_tx_start(packet,512,4));clock_ms=90099;cb_tx_service();assert(cb_tx_busy());
 clock_ms=90100;cb_tx_service();assert(!cb_tx_busy() && !initialized && reset_count==1);
 unsigned before=calls;clock_ms=10000;cb_tx_service();assert(calls==before);assert(!cb_tx_start(packet,8,5));
 initialized=true;clock_ms=100000;assert(cb_tx_start(packet,8,5));
 clock_ms=120000;cb_tx_service();assert(cb_tx_busy());complete(0,8);
 assert(!cb_tx_busy() && !strcmp(cb_tx_state(),"USB_DONE"));
 assert(cb_tx_start(packet,8,6));cb_tx_cancel();assert(!initialized && !cb_tx_busy());
 initialized=true;clock_ms=UINT32_MAX-45000u;assert(cb_tx_start(packet,8,7));
 clock_ms+=89999u;cb_tx_service();assert(cb_tx_busy());clock_ms++;cb_tx_service();assert(!cb_tx_busy());
 initialized=true;xfer_ok=false;assert(!cb_tx_start(packet,8,5));assert(!cb_tx_busy());
 puts("PASS USB TX: idle, mount/busy/claim, buffer lifetime, exact size, ZLP, failure, 90s timeout resets controller, no replay");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.c';p.write_text(pre+code+'\nstatic void complete(unsigned result,uint32_t xferred_bytes){uint8_t rhport=0;\n'+callback+'\n}\n'+main)
 exe=Path(d)/'test'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I',str(root/'src'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
