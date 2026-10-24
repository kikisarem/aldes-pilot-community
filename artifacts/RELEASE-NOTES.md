Version expérimentale privée : portail de configuration Pico W et packaging Home Assistant.

- Les scripts compilent le firmware générique lc00 sans Wi-Fi ni token intégrés pour Pico W (RP2040) et Pico 2 W (RP2350) ; la configuration locale est enregistrée en flash. Les UF2 sont générés localement et ne sont pas inclus dans le ZIP source.
- Les essais récents de communication et de commandes ont été réalisés sur Pico 2 W. Le nouveau portail générique reste à qualifier matériellement ; le portail temporaire est ouvert et doit être configuré dans un lieu de confiance. Lire `firmware/PORTAL.md` avant installation.
- Companion Docker pour HA Container, add-on local pour HA OS, découverte MQTT des modes/consignes et retour réel de l’IHM.
- Compilation générique et historique avec configuration factice réussie. Tests hôte, CRC et coupures flash simulées, MQTT, navigateur et contrôle ingress réussis.
- Non encore testé : nouveau portail sur Pico physique, nouvelle image sous Docker/HA. Ne pas confondre avec le firmware historique et la reprise automatique après coupure PAC, déjà testés séparément.

Le bridge de production n’a pas été remplacé. Préférer un Pico W de test pour qualifier le nouveau firmware. Les instructions complètes sont dans `firmware/PORTAL.md` et `homeassistant/README.md`. Ne partagez ni UF2 personnalisé ni dump de flash configurée.
