#pragma once
#include <stdint.h>
#define PICO_OK 0
int flash_safe_execute(void (*fn)(void *),void *,uint32_t);
