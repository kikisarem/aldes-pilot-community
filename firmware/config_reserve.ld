/* Keep the physical flash size at 2 MiB for SDK erase bounds.
   Reserve its last two sectors by rejecting any overlapping program image. */
ASSERT(__flash_binary_end <= 0x101fe000, "Firmware overlaps provisioning sectors")
