#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef int err_t;typedef uint16_t u16_t;
#define ERR_OK 0
#define ERR_VAL -1
#define ERR_ABRT -2
#define IPADDR_TYPE_V4 0
#define IP_ANY_TYPE NULL
#define TCP_WRITE_FLAG_COPY 1
struct tcp_pcb {int unused;};
struct pbuf {struct pbuf *next;void *payload;u16_t len,tot_len;};
static uint32_t clock_ms;static bool mounted=true,inited=true,busy;
static unsigned submissions,aborts,usbstarts;static uint32_t job;
static const char *state="IDLE";static char response[1024];
static struct tcp_pcb fake;
static uint32_t get_absolute_time(void){return clock_ms;}
static uint32_t to_ms_since_boot(uint32_t v){return v;}
static void cyw43_arch_lwip_begin(void){}
static void cyw43_arch_lwip_end(void){}
#define tcp_arg(...) ((void)0)
#define tcp_err(...) ((void)0)
#define tcp_recv(...) ((void)0)
#define tcp_nagle_disable(...) ((void)0)
#define tcp_output(...) ((void)0)
#define tcp_accept(...) ((void)0)
#define tcp_recved(...) ((void)0)
#define pbuf_free(...) ((void)0)
static void tcp_abort(struct tcp_pcb *p){(void)p;aborts++;}
static err_t tcp_write(struct tcp_pcb *p,const void *s,u16_t n,int flags){(void)p;(void)flags;assert(n<sizeof(response));memcpy(response,s,n);response[n]=0;return ERR_OK;}
static struct tcp_pcb *tcp_new_ip_type(int x){(void)x;return &fake;}
static err_t tcp_bind(struct tcp_pcb *p,void *addr,int port){(void)p;(void)addr;assert(port==8766);return ERR_OK;}
static struct tcp_pcb *tcp_listen_with_backlog(struct tcp_pcb *p,int n){(void)n;return p;}
static void tcp_close(struct tcp_pcb *p){(void)p;}
static bool tud_inited(void){return inited;}
static bool tud_mounted(void){return mounted;}
static bool tud_init(int port){(void)port;usbstarts++;inited=true;return true;}
