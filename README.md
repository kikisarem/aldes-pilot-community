# Pilotage local Aldes T.One AquaAIR

Interface web expérimentale pour un bridge USB Pico W. Elle affiche les consignes et modes **relus sur la PAC**, y compris les changements effectués sur l’IHM. Les commandes partent uniquement sur action utilisateur.

## Fonctionnalités validées sur l’installation de référence

- Quatre consignes de zone : lecture et écriture.
- Air : arrêt, chauffage Confort / Éco / programmes A et B, climatisation Confort / Boost / programmes C et D.
- ECS : arrêt, marche, Boost.
- Vacances : lecture des dates de départ et retour, annulation de la période. Hors gel : observation et annulation ; activation USB non validée.
- Affichage indisponible quand le rapport est trop ancien, incomplet, corrompu ou issu d’une session interrompue.

Les températures candidates ne sont pas présentées comme des mesures de pièces : leur correspondance physique reste à vérifier. Éditer les plages hebdomadaires ou écrire de nouvelles dates de vacances n’est pas encore pris en charge. La persistance d’une nouvelle consigne sur plusieurs heures reste à qualifier. La compatibilité avec d’autres versions de PAC n’est pas garantie par les essais sur une seule installation.

## Architecture

Le collecteur existant reçoit les logs RAW du bridge. `readback.py` lit une fenêtre bornée du fichier, réassemble les transferts, contrôle la somme puis décode le rapport `0x21`. `GET /api/state` ne se connecte jamais au Pico. La page relit cette API toutes les quatre secondes ; la cadence observée des rapports PAC est d’environ vingt secondes.

`pico.py` sérialise les commandes, journalise l’intention, effectue un seul envoi et vérifie le désarmement. Une livraison USB ne constitue pas une preuve d’application : la valeur relue reste affichée séparément. Une égalité ultérieure indique une correspondance observée, sans attribuer avec certitude l’origine du changement.

Aucune boucle de réconciliation ne réécrit les consignes. Un réglage IHM différent est affiché tel quel. Une erreur d’envoi n’entraîne aucun nouvel essai automatique.

Voir [le guide matériel, versions, compilation, flash et amorçage](REPRODUCTION.md).

## Installation

Ce dépôt couvre l’interface et le lecteur de logs. Il nécessite **un firmware bridge compatible avec le protocole WORKBENCH 1 déjà installé** et un collecteur RAW actif. Les sources du firmware sont incluses ; chacun doit compiler son UF2 avec ses propres identifiants.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PICO_CAPTURE=/chemin/vers/pico.log
export PICO_HOST=adresse-du-bridge
export PICO_TOKEN=/chemin/prive/control.token
export PILOT_PIN=un-code-local
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8771
```

Le jeton du bridge doit contenir 64 caractères hexadécimaux minuscules. Garder les jetons, journaux et sauvegardes hors du dépôt. `PILOT_PIN` protège les écritures, pas les lectures. Ne pas exposer ce serveur directement sur Internet ; utiliser un accès privé ou un proxy authentifié. Un seul collecteur doit consommer le port de logs.

`collector.py --host adresse-du-bridge --log /chemin/vers/pico.log` fournit un collecteur sans limite de durée, avec reconnexion et rotation (32 Mio, trois archives). Arrêter le collecteur précédent avant de lancer celui-ci. Le lancement au démarrage doit être configuré et testé séparément.

La durée de vie du collecteur est indépendante de celle du serveur web. Si le collecteur s’arrête, la page passe en indisponible. Sur macOS, vérifier les permissions Réseau local dans le contexte réel de lancement : un LaunchAgent ne suffit pas à garantir l’accès.

## Tests sans appareil

```sh
python3 -m unittest test_reader test_pilot -v
```

Les tests couvrent le réassemblage, la somme, les ruptures de session, la fraîcheur, la rotation/troncature, les changements extérieurs sans écriture et les masques des commandes.

## Champs documentés

Offsets comptés depuis zéro dans une trame complète. Rapport local `0x21` : 90 octets ; écriture `0x10` : 88 octets. Ne pas recopier un rapport dans une commande.

| Offsets | Champ | Format |
|---|---|---|
| 5–8 | Départ vacances | DOS/FAT 32 bits, little endian ; zéro = absent |
| 9–12 | Retour vacances | Même format |
| 13–20 | Consignes K1 à K4 | Quatre entiers 16 bits little endian / 100 |
| 53–60 | Températures candidates | Identité physique des sondes non validée |
| 77–80 | Horloge PAC | DOS/FAT ; ne pas assimiler au temps hôte |
| 81 | Mode air | 0 à 8, table ci-dessous |
| 82 | Mode ECS | 0 arrêt, 1 marche, 2 Boost |

| Air | Mode |
|---|---|
| 0 | Arrêt |
| 1 | Chauffage Confort |
| 2 | Chauffage Éco |
| 3 | Chauffage Programme A |
| 4 | Chauffage Programme B |
| 5 | Clim Confort |
| 6 | Clim Boost |
| 7 | Clim Programme C |
| 8 | Clim Programme D |

La PAC de référence présente un décalage entre date et jour de semaine. Les dates affichées sont celles reçues ; aucune correction d’horloge n’est appliquée. Le rapport `0x21` doit rester actif : le lecteur ne l’acquitte pas et ne tente pas de reconstruire automatiquement un régime de rapports perdu.

## Avant diffusion

Le dossier communautaire est une sélection de sources anonymisées, sans secrets ni captures privées. La diffusion reste privée pendant la qualification. Licence du code original à choisir avant diffusion publique ; conserver les notices des composants tiers. Des essais sur d’autres installations restent nécessaires.
