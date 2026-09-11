#pragma once
#include <stdint.h>
#include <stddef.h>
#define FLASH_SECTOR_SIZE 4096
#define FLASH_PAGE_SIZE 256
extern unsigned char fake_flash[];
#define XIP_BASE ((uintptr_t)fake_flash)
void flash_range_erase(uint32_t,size_t);
void flash_range_program(uint32_t,const uint8_t *,size_t);
