#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define CONFIG_MAGIC 0x414c4431u
#define CONFIG_SEAL 0xc04f19a2u
typedef struct {char ssid[33],password[64],token[65];uint8_t ip[4],gateway[4];} wifi_settings;
typedef struct {uint32_t magic,version,sequence;wifi_settings wifi;uint32_t crc,seal;} config_record;
uint32_t config_crc(const void *,size_t);
bool config_valid(const config_record *);
bool config_form(const char *,const char *,const char *,wifi_settings *);
bool provision_load(wifi_settings *);
void provision_run(void);
extern wifi_settings runtime_wifi;
