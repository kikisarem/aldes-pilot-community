#include "provision_config.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
uint32_t config_crc(const void *data,size_t n){const uint8_t *p=data;uint32_t c=~0u;while(n--){c^=*p++;for(int b=0;b<8;b++)c=(c>>1)^((0u-(c&1))&0xedb88320u);}return ~c;}
static bool text_ok(const char *s,size_t cap,size_t min){size_t n=0;for(;n<cap&&s[n];n++)if((unsigned char)s[n]<32)return false;return n>=min&&n<cap;}
static bool ip_ok(const uint8_t *a){return a[0]>0&&a[0]<224&&a[0]!=127&&a[3]>0&&a[3]<255;}
static bool settings_ok(const wifi_settings *w){
 if(!text_ok(w->ssid,sizeof w->ssid,1)||!text_ok(w->password,sizeof w->password,8)||strlen(w->token)!=64)return false;
 for(int i=0;i<64;i++)if(!((w->token[i]>='0'&&w->token[i]<='9')||(w->token[i]>='a'&&w->token[i]<='f')))return false;
 const uint8_t zero[4]={0};if(!memcmp(w->ip,zero,4))return !memcmp(w->gateway,zero,4);
 return ip_ok(w->ip)&&ip_ok(w->gateway)&&!memcmp(w->ip,w->gateway,3)&&memcmp(w->ip,w->gateway,4);
}
bool config_valid(const config_record *r){return r->magic==CONFIG_MAGIC&&r->version==1&&r->seal==CONFIG_SEAL&&r->crc==config_crc(r,offsetof(config_record,crc))&&memchr(r->wifi.token,0,65)&&settings_ok(&r->wifi);}
static int hex(char c){if(c>='0'&&c<='9')return c-'0';if(c>='A'&&c<='F')return c-'A'+10;if(c>='a'&&c<='f')return c-'a'+10;return -1;}
static bool decode(const char *s,size_t n,char *out,size_t cap){size_t j=0;for(size_t i=0;i<n;i++){unsigned char c=s[i];if(c=='+')c=' ';else if(c=='%'){if(i+2>=n)return false;int a=hex(s[i+1]),b=hex(s[i+2]);if(a<0||b<0)return false;c=(a<<4)|b;i+=2;}if(c<32||c==127||j+1>=cap)return false;out[j++]=c;}out[j]=0;return true;}
static bool field(const char *body,const char *key,char *out,size_t cap){bool found=false;size_t k=strlen(key);out[0]=0;for(const char *p=body;*p;){const char *end=strchr(p,'&');if(!end)end=p+strlen(p);if((size_t)(end-p)>k&&p[k]=='='&&!memcmp(p,key,k)){if(found||!decode(p+k+1,(size_t)(end-p)-k-1,out,cap))return false;found=true;}p=*end?end+1:end;}return found;}
static bool ip_parse(const char *s,uint8_t *out){if(!*s){memset(out,0,4);return true;}unsigned a,b,c,d;char extra;if(sscanf(s,"%u.%u.%u.%u%c",&a,&b,&c,&d,&extra)!=4||a>255||b>255||c>255||d>255)return false;out[0]=a;out[1]=b;out[2]=c;out[3]=d;return true;}
bool config_form(const char *body,const char *nonce,const char *token,wifi_settings *out){wifi_settings w={0};char n[65],ip[16],gw[16];if(!field(body,"nonce",n,sizeof n)||strcmp(n,nonce)||!field(body,"ssid",w.ssid,sizeof w.ssid)||!field(body,"password",w.password,sizeof w.password)||!field(body,"ip",ip,sizeof ip)||!field(body,"gateway",gw,sizeof gw)||!ip_parse(ip,w.ip)||!ip_parse(gw,w.gateway))return false;if(strlen(token)!=64)return false;memcpy(w.token,token,65);if(!settings_ok(&w))return false;*out=w;return true;}
