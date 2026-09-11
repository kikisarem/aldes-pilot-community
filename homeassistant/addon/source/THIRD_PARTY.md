# Composants tiers

Le firmware utilise Raspberry Pi Pico SDK 2.3.1 (BSD-3-Clause), TinyUSB (MIT), lwIP et CYW43 via les sous-modules du SDK. Le SDK se récupère séparément ; conserver ses licences lors de toute redistribution binaire.

Le fichier pico_sdk_import.cmake provient du SDK. Ses notices sont conservées ; copie de la licence SDK dans licenses/PICO_SDK.txt. TinyUSB commit de référence : 86ad6e56c1700e85f1c5678607a762cfe3aa2f47.

Ce projet indépendant n’est ni un produit Aldes ni une distribution officielle. Aucun firmware propriétaire de PAC ni capture privée d’un tiers n’est inclus. Les références communautaires ayant aidé les recherches sont TOUG (djtef), Open-connect-box (YannDoublet), aldes-bridge (saniho) et le fil HACF Aldes T.One Air/AquaAIR.

## Portail générique

`firmware/vendor/dhcpserver` et `dnsserver` : raspberrypi/pico-examples, commit `0d62f75bafc2c8120d3276c3343d1a9195e909e9`, sous-dossier `pico_w/wifi/access_point_wifi_provisioning`. DHCP : licence MIT embarquée. DNS : BSD-3-Clause, licence Raspberry Pi dans `licenses/`. Modifications locales : bornes des options DHCP, longueurs DNS, type de question, alignement. Ne pas réécraser ces contrôles lors d’une mise à jour.

Le compagnon HA utilise paho-mqtt 2.1.0 (EPL-2.0 / EDL-1.0), installé à la construction de l’image ; aucun identifiant MQTT dans les sources.
