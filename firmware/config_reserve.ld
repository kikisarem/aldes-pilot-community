/* Reserve the two sectors at offset 0x1fe000 on both supported boards.
   On Pico 2 W this intentionally leaves the upper half of flash unused. */
ASSERT(__flash_binary_end <= 0x101fe000, "Firmware overlaps provisioning sectors")
