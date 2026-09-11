cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico_w CACHE STRING "Board type")

include(pico_sdk_import.cmake)

project(cbclone C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()
option(CB_PROVISIONING "Generic firmware with first-boot WiFi portal" OFF)
set(CB_RX_EARLY_REARM 0 CACHE STRING "RX rearm A/B")

# Le SSID n'est pas un secret : il reste un -D classique.
set(WIFI_SSID "" CACHE STRING "SSID du WiFi maison")

# Le mot de passe, lui, n'entre JAMAIS dans cmake. On ne reçoit que le chemin
# d'un répertoire temporaire (0700) contenant wifi_config.h en 0600, écrit par
# tools/bin/wifi-secret depuis le Trousseau et effacé sitôt le build terminé.
# Conséquence : rien dans CMakeCache.txt, rien dans les flags.make, rien dans ps.
set(WIFI_CONFIG_DIR "" CACHE PATH "Répertoire temporaire contenant wifi_config.h")

# Deux variantes, une seule variable expérimentale : la réponse à GET_LINE_CODING.
#   lc00     -> 00 00 00 00 00 00 00  (comme la vraie ConnectBox)  = test
#   lc115200 -> 00 C2 01 00 00 00 08  (défaut TinyUSB)             = témoin
foreach(VARIANT lc00 lc115200)
    if(VARIANT STREQUAL "lc00")
        set(LC_ZERO 1)
    else()
        set(LC_ZERO 0)
    endif()

    add_executable(cbclone_${VARIANT}
        src/main.c
        src/usb_descriptors.c
        src/cb_cdc_driver.c
        src/netlog.c
        src/netcontrol.c
        src/control_protocol.c
    )

    if(CB_PROVISIONING)
        target_sources(cbclone_${VARIANT} PRIVATE src/provision.c src/provision_config.c src/provision_store.c vendor/dhcpserver/dhcpserver.c vendor/dnsserver/dnsserver.c)
        target_include_directories(cbclone_${VARIANT} PRIVATE vendor/dhcpserver vendor/dnsserver)
        target_link_libraries(cbclone_${VARIANT} pico_flash hardware_flash hardware_watchdog pico_rand pico_unique_id)
        target_compile_definitions(cbclone_${VARIANT} PRIVATE CB_PROVISIONING=1)
        target_link_options(cbclone_${VARIANT} PRIVATE "-Wl,-T,${CMAKE_CURRENT_LIST_DIR}/config_reserve.ld")
    else()
        target_include_directories(cbclone_${VARIANT} PRIVATE ${CMAKE_CURRENT_LIST_DIR}/private ${WIFI_CONFIG_DIR})
        target_compile_definitions(cbclone_${VARIANT} PRIVATE CB_PROVISIONING=0 WIFI_SSID=\"${WIFI_SSID}\")
    endif()

    target_include_directories(cbclone_${VARIANT} PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}/include
        ${CMAKE_CURRENT_LIST_DIR}/src
    )

    target_compile_definitions(cbclone_${VARIANT} PRIVATE
        CB_LINE_CODING_ZERO=${LC_ZERO}
        CB_RX_EARLY_REARM=${CB_RX_EARLY_REARM}
    )

    target_link_libraries(cbclone_${VARIANT}
        pico_stdlib
        tinyusb_device
        pico_cyw43_arch_lwip_threadsafe_background
    )

    pico_enable_stdio_usb(cbclone_${VARIANT} 0)
    pico_enable_stdio_uart(cbclone_${VARIANT} 1)
    pico_add_extra_outputs(cbclone_${VARIANT})
endforeach()
