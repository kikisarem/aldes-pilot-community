# Démarrage macOS à l’ouverture de session

Installer les outils de compilation Apple (pour `swiftc`) et créer `.venv` dans le dépôt, jamais dans `/tmp`. Arrêter les anciens processus serveur et collecteur avant installation, afin de ne pas ouvrir deux consommateurs de logs.

```sh
python3 macos/install.py --host ADRESSE_PICO
```

Autoriser **Aldes Pilot** dans Confidentialité et sécurité → Réseau local. Le programme crée une app dans `~/Applications`, un LaunchAgent dans `~/Library/LaunchAgents` et une configuration privée sous `private/`. Le LaunchAgent lance l’app via LaunchServices ; l’app lance le superviseur ; le superviseur relance le serveur ou le collecteur s’ils quittent. Le serveur écoute toutes les interfaces : réserver cet accès au réseau privé.

Vérifier `launchctl list`, les journaux sous `logs/`, puis `http://127.0.0.1:8771/api/state` : `observation.available=true` et âge récent. Une simple connexion réseau du lanceur ne suffit pas : il faut un rapport PAC frais après lancement.

C’est un démarrage **à l’ouverture de session utilisateur**, pas avant déverrouillage FileVault et pas une garantie de fonctionnement pendant la veille du Mac. L’accès Réseau local doit être autorisé dans cette identité ; un Python lancé directement par launchd avait échoué sur la machine de référence.

Pour retirer le démarrage : `launchctl bootout gui/$(id -u)/local.aldes.pilot`, puis quitter l’app Aldes Pilot. Conserver les sources et la configuration dans un chemin stable. Ne pas exécuter cet installateur par-dessus un autre service Aldes actif sans l’arrêter.
