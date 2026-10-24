# Configuration du Pico W / Pico 2 W — version expérimentale

Le firmware générique lc00 compile sans les headers privés. SSID, mot de passe et token de contrôle ne sont pas présents dans le fichier UF2 distribué. Le firmware historique reste disponible via `configure.py` / `build-local.py` : **ne partagez jamais un UF2 issu de cette compilation personnalisée**.

## Première installation

1. Prenez un **Pico W (RP2040)** ou un **Pico 2 W (RP2350)** et un câble USB de données.
2. Obtenez l’UF2 de la carte en suivant [Compiler l’UF2 générique](#compiler-luf2-générique), ou depuis une publication officielle si elle est disponible. Hors connexion à la PAC, maintenez BOOTSEL pendant le branchement à l’ordinateur. Copiez le fichier UF2 sur le volume RPI-RP2.
3. Sur le téléphone, rejoignez `Aldes-Setup-xxxxxxxx`. Acceptez de rester connecté à ce réseau sans Internet. Ouvrez **http://192.168.4.1/**. Le DNS de configuration facilite la navigation mais l’ouverture automatique du portail n’est pas garantie.
4. Copiez le token affiché dans un gestionnaire de mots de passe : il sera demandé par le bridge Home Assistant. Saisissez le Wi-Fi **2,4 GHz**, avec mot de passe de 8 à 63 caractères (WPA2/WPA3 compatible). Les réseaux ouverts ne sont pas pris en charge en mode maison.
5. Laissez les adresses vides pour DHCP. Pour une adresse fixe, indiquez une adresse libre et une passerelle distincte dans le même réseau `/24`. Vérifiez l’absence de conflit sur le routeur. Cette restriction ne s’applique pas au DHCP.
6. Validez. Le Pico écrit la configuration, la relit puis redémarre. La page « reçue » confirme la réception du formulaire, **pas** l’association Wi-Fi. Rejoignez le réseau de la maison et trouvez `aldes-pico-xxxxxxxx` dans la liste DHCP du routeur (ce nom ne garantit pas une résolution `.local`). Réservez son adresse.
7. Configurez le bridge avec cette adresse et le token, puis connectez le Pico à la PAC. Contrôlez la lecture et les modes avant tout essai d’écriture.

Le réseau initial est **ouvert** et le formulaire est en HTTP local : faites l’appairage dans un lieu de confiance, car une personne à portée radio pourrait observer/intercepter cette configuration. Il n’y a ni compte cloud ni mot de passe commun embarqué. Le portail ferme après dix minutes sans redémarrage réussi ; coupez/rétablissez l’alimentation pour recommencer. Les ports de log/commande et l’USB de pilotage ne sont pas lancés dans le portail.

## Wi-Fi changé, mauvais mot de passe ou token perdu

Le portail ne se rouvre **pas** sur une perte de Wi-Fi. Débranchez le Pico de la PAC et de toute alimentation. Reliez **GP15 (broche physique 20) à GND (broche 18)**, alimentez-le depuis l’ordinateur, puis retirez ce pont après apparition du réseau de configuration. Ne reliez jamais une broche d’alimentation à GP15. Le formulaire crée un nouveau token ; mettez aussi à jour le bridge. L’ancienne configuration est conservée jusqu’à validation et écriture réussie de la nouvelle.

Ce geste ouvre le mode configuration, il ne garantit pas l’effacement forensique des anciens secrets. Les deux secteurs à l’offset `0x1fe000` contiennent les configurations ; une lecture complète de la flash les expose. **Ne distribuez pas un dump de votre Pico configuré.** Pour céder le matériel, effacez toute la flash avec l’outil Raspberry Pi approprié puis remettez l’UF2 générique.

## Stockage et compilation

### Compiler l’UF2 générique

Le dépôt source ne contient pas les fichiers UF2 : ils sont générés localement et exclus du ZIP/Git. Installez CMake, le [Pico SDK 2.3.1](https://github.com/raspberrypi/pico-sdk/tree/2.3.1) et la toolchain complète Arm GNU **14.2.Rel1** avec `arm-none-eabi` et newlib. Le guide [Reproduire l’installation](../REPRODUCTION.md#1-préparer-le-firmware-personnel-optionnel) détaille les prérequis et le téléchargement du SDK.

Depuis la racine du dépôt, configurez les chemins de votre installation puis construisez la carte voulue :

```sh
export PICO_SDK_PATH="$HOME/pico-sdk"
export PICO_TOOLCHAIN_PATH="$HOME/arm-gnu-toolchain-14.2.rel1"
python3 firmware/build-generic.py
# Pour un Pico 2 W, au lieu de la commande précédente :
PICO_BOARD=pico2_w python3 firmware/build-generic.py
```

Le script place l’UF2 et son empreinte dans `artifacts/`. Pico W est la cible par défaut ; Pico 2 W doit être sélectionné explicitement. Ce firmware générique ne contient pas le Wi-Fi ni le token : le portail les configure au premier démarrage.

### Télécharger un UF2 depuis une release GitHub

Le workflow [firmware-release.yml](../.github/workflows/firmware-release.yml) compile automatiquement les deux UF2 lorsqu’une release GitHub est publiée et les ajoute à ses fichiers avec `SHA256SUMS`. Ouvrez la release du projet, attendez la réussite de l’action **Build Pico firmware release assets**, puis téléchargez le fichier correspondant à la carte et les sommes. Si l’action échoue, ne flashez pas de fichier partiel : consultez les logs de l’action ou construisez localement avec les étapes ci-dessus. La compilation automatique ne remplace pas les essais matériels indiqués dans la section Qualification.

Deux secteurs alternés de 4 Ko, à l’offset `0x1fe000`, format versionné, compteur de génération et CRC32. Une écriture interrompue laisse l’ancienne copie utilisable si elle existait. L’écriture a lieu dans `flash_safe_execute`, hors callback réseau et avant l’initialisation USB. Le firmware réserve cette plage et le script vérifie que l’UF2 ne la recouvre pas. Sur Pico 2 W, cette réserve reste à la même adresse et la moitié supérieure de la flash n’est pas utilisée. Flasher un firmware différent peut toutefois écraser cette réserve.

Pour compiler : SDK Pico **2.3.1**, toolchain **Arm GNU 14.2.Rel1**, CMake. Définissez `PICO_SDK_PATH` et `PICO_TOOLCHAIN_PATH`. `python3 firmware/build-generic.py` construit pour Pico W par défaut ; pour Pico 2 W, lancez `PICO_BOARD=pico2_w python3 firmware/build-generic.py`. Le résultat et son SHA256 sont dans `artifacts/`. Aucune configuration privée n’est requise.

Pour un firmware personnel avec Wi-Fi configuré à la compilation, choisissez de même la carte avec `PICO_BOARD=pico2_w python3 firmware/build-local.py` après `configure.py`. Les builds des deux cartes utilisent des répertoires séparés.

## Qualification

Les scripts permettent de construire les deux cibles. La communication et les commandes du bridge ont été exercées sur Pico 2 W ; le portail générique reste à qualifier matériellement (configuration Wi-Fi, DHCP et écriture flash). Ne confondez pas les essais de commandes avec la qualification complète de ce nouveau firmware de provisionnement.

Les serveurs DHCP/DNS sont adaptés des [exemples Raspberry Pi](https://github.com/raspberrypi/pico-examples/tree/0d62f75bafc2c8120d3276c3343d1a9195e909e9/pico_w/wifi/access_point_wifi_provisioning). Les vérifications de bornes des paquets ont été renforcées dans cette copie.
