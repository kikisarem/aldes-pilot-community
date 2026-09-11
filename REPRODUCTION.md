# Reproduire l’installation expérimentale

## Matériel et versions de référence

| Élément | Référence observée |
|---|---|
| PAC | Aldes T.One AquaAIR, chauffage + rafraîchissement + ECS |
| Interface PAC | Version IHM **181**, lue à l’écran |
| Version complète du régulateur | Non identifiée avec certitude ; ne pas confondre avec IHM 181 ou un firmware V17 téléchargé pour analyse |
| Zones | Quatre thermostats radio Aldes **35001151** |
| Bridge | **Raspberry Pi Pico W, RP2040** ; pas un Pico sans Wi-Fi ni un Pico 2 W validé |
| Câble | USB de données entre le port USB hôte de la PAC et le micro-USB du Pico W ; un câble charge seule ne convient pas |
| Réseau | Wi-Fi 2,4 GHz ; adresse IPv4 fixe libre, passerelle dans le même /24 dans le code de référence |
| Firmware Pico utilisé | TXDIAG v1.2 TX90 + diagnostic de fin des transferts de contrôle ; variante **lc00**, `CB_RX_EARLY_REARM=0` |
| SDK de compilation | Raspberry Pi Pico SDK **2.3.1**, commit `079c6f39023649b154152db30f1d781e884879bc` |
| Compilateur ARM vérifié | Arm GNU Toolchain **14.2.Rel1**, cible `arm-none-eabi` avec newlib |
| Hôte de référence | Mac, Python **3.14.6**, FastAPI **0.141.1**, Uvicorn **0.52.4** |

Le serveur doit rester allumé pour servir la page et collecter les logs. Aucun compte Aldes ni ConnectBox ne sont nécessaires dans cette installation. Aucune ouverture de PAC, soudure ou liaison radio supplémentaire.

## 1. Préparer le firmware personnel

Installer Git, Python 3, CMake, un compilateur C natif et **la chaîne Arm complète avec newlib**. Sur le Mac de référence, le simple paquet Homebrew `arm-none-eabi-gcc` échouait avec `cannot find -lg/-lc` ; la distribution Arm GNU complète fonctionne.

```sh
git clone --branch 2.3.1 --recurse-submodules https://github.com/raspberrypi/pico-sdk.git
export PICO_SDK_PATH="$PWD/pico-sdk"
export PICO_TOOLCHAIN_PATH=/chemin/vers/arm-gnu-toolchain-14.2.rel1
cd aldes-pilot-community
python3 firmware/configure.py
python3 firmware/build-local.py
```

`configure.py` demande SSID, mot de passe, IPv4 et passerelle. Il génère un jeton aléatoire et des headers sous `firmware/private/`, ignorés par Git. Le build produit `firmware/build/cbclone_lc00.uf2`. Ce fichier contient **vos** identifiants : ne pas le partager. Aucun binaire personnalisé de l’installation de référence n’est fourni.

Le SSID entre dans le cache CMake ; le mot de passe est dans le header privé et le binaire. Conserver ces fichiers localement, permissions restrictives. La configuration réseau est statique /24 ; d’autres topologies demandent une adaptation du source, pas un changement de firmware PAC.

## 2. Flasher le Pico, jamais la PAC

Débrancher le Pico de la PAC. Maintenir BOOTSEL en branchant le Pico à l’ordinateur, puis copier l’UF2 sur le volume **RPI-RP2**. Après redémarrage, contrôler l’accès au bridge :

```sh
python3 firmware/workbench.py --host ADRESSE_PICO status
```

Attendu : protocole `WORKBENCH 1`, authentification acceptée, `tx_timeout_ms=90000`, désarmé (`armed=0`). L’état USB monté dépend de l’hôte auquel le Pico est branché. Ensuite relier le Pico à la PAC et démarrer **un seul** collecteur.

Le firmware reste en mémoire flash après débranchement et redémarrage. Il n’a pas d’expiration 24 h. Les temporisations de 30 s d’armement et 90 s de transfert sont des garde-fous par commande, pas une durée de vie du firmware. Le boot n’envoie aucune commande applicative automatiquement.

## 3. Installer la page et le collecteur

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export PICO_HOST=ADRESSE_PICO
export PICO_TOKEN="$PWD/firmware/private/control.token"
export PICO_CAPTURE="$PWD/private/pico.log"
mkdir -p private
.venv/bin/python collector.py --host "$PICO_HOST" --log "$PICO_CAPTURE"
```

Dans un second terminal, définir les mêmes variables, puis :

```sh
export PILOT_PIN=CODE_LOCAL
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8771
```

Ouvrir `http://127.0.0.1:8771/`. Le lecteur s’appuie sur les RAW : les compteurs internes du firmware ne reconnaissent pas tous les rapports. La page reste indisponible tant qu’aucun `0x21` frais complet n’est reçu. Ce comportement protège contre un état supposé.

## 4. Obtenir le régime de lecture : limite encore expérimentale

**Ce dépôt n’est pas encore une installation universelle en un clic.** Le firmware et l’interface se reconstruisent ; l’amorçage des rapports dépend de l’état de la PAC. Ne pas envoyer toute la liste ci-dessous comme un script aveugle.

Séquence observée sur la référence, en contrôlant un rapport complet entre chaque étape :

| Rapport actif | Message de contrôle, hex | Résultat observé |
|---|---|---|
| 20 (Hello) | `fd fa 08 ff 40 20 fe a4` | Reprise de la page précédemment active, d’abord 26, plus tard 27 ou 21 |
| 26 | `fd fa 08 ff 46 26 fe 98` | 27 |
| 27 | `fd fa 08 ff 47 27 fe 96` | 28 dans un essai émis après réception complète ; un autre essai n’avait pas avancé |
| 28 | `fd fa 08 ff 48 28 fe 94` | 23 |
| 23 | `fd fa 08 ff 43 23 fe 9e` | 24 |
| 24 | Écriture d’une consigne connue, puis retour | Rapport 21 avec consigne correspondante |

Le dernier passage est une vraie modification de consigne, pas une lecture neutre. Il doit être choisi et observé par l’occupant. Les générateurs `frame_setpoint`, `frame_air`, `frame_ecs` dans `pico.py` construisent les champs validés. `firmware/workbench.py --host ADRESSE_PICO send --hex '…'` permet un envoi explicite unique, avec journal et STOP ; aucune commande de cette table n’est déclenchée à l’installation.

Pour observer hors ligne :

```sh
python3 reader.py --log private/pico.log --output private/state.json
```

Garder le `0x21` sans acquittement : `41 21` l’a fait retourner au Hello sur la référence. Un `40 20` a ensuite repris 21. Cela a été vérifié après un retour Hello, **pas après toutes les formes de redémarrage à froid**. En cas d’état inattendu, conserver les RAW, arrêter l’expérience et comparer avant un nouvel envoi. Les délais USB hôte ne prouvent pas à eux seuls l’acceptation applicative.

## 5. Validation chez une autre personne

Relever le modèle exact, toutes les versions accessibles et la référence du Pico. Vérifier d’abord le montage USB et les rapports sans écriture. Une fois 21 disponible, changer un seul réglage sur l’IHM et vérifier sa lecture sur la page. Tester ensuite une commande connue et son retour, avec l’IHM comme témoin. Surveiller une nouvelle consigne sur plusieurs heures : la persistance longue reste à qualifier.

Ne pas extrapoler les températures candidates aux pièces sans test physique. La programmation des plages horaires et l’écriture des dates de vacances ne sont pas validées. L’horloge de référence présente un décalage date/jour ; le dépôt ne la corrige pas.

## Démarrage automatique

Voir `macos/README.md` pour le lanceur macOS. Le démarrage à l’ouverture de session du Mac ne prouve pas la reprise automatique du protocole après une coupure PAC. Garder ces deux sujets séparés.
