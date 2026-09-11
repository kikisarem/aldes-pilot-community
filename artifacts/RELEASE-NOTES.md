Version expérimentale privée : portail de configuration Pico W et packaging Home Assistant.

- UF2 générique lc00 sans Wi-Fi ni token de propriétaire compilés ; configuration locale enregistrée en flash.
- Firmware réservé au Pico W RP2040 2 Mo. Portail ouvert temporaire à configurer dans un lieu de confiance ; lire `firmware/PORTAL.md` avant installation.
- Companion Docker pour HA Container, add-on local pour HA OS, découverte MQTT des modes/consignes et retour réel de l’IHM.
- Compilation générique et historique avec configuration factice réussie. Tests hôte, CRC et coupures flash simulées, MQTT, navigateur et contrôle ingress réussis.
- Non encore testé : nouveau portail sur Pico physique, nouvelle image sous Docker/HA. Ne pas confondre avec le firmware historique et la reprise automatique après coupure PAC, déjà testés séparément.

Le bridge de production n’a pas été remplacé. Préférer un Pico W de test pour qualifier le nouveau firmware. Les instructions complètes sont dans `firmware/PORTAL.md` et `homeassistant/README.md`. Ne partagez ni UF2 personnalisé ni dump de flash configurée.
