# Aldes Pilot dans Home Assistant

Deux parcours : **HA OS avec add-on** ou **Home Assistant Container avec un conteneur compagnon**. Le Pico reste local. Home Assistant offre l’interface web et l’application mobile ; l’accès distant utilise votre accès HA existant (ou HA Cloud/Tailscale). Aucun port du Pico ne doit être redirigé vers Internet. Aucun cloud Aldes n’est nécessaire.

État : parcours REST installé sur un Raspberry Pi ARM64 avec Home Assistant Container 2026.6.4. Image Docker construite, configuration HA vérifiée, lecture réelle et entités contrôlées après migration depuis le Mac. Le parcours MQTT/add-on et le nouveau portail Wi-Fi restent à qualifier sur matériel.

**Compatibilité des cartes :** le code et les scripts de compilation prennent en charge le Pico W (RP2040) et le Pico 2 W (RP2350). Les essais matériels récents de communication et de commandes ont été réalisés sur le Pico 2 W. Le nouveau portail Wi-Fi générique, lui, reste à qualifier matériellement. Les UF2 ne sont pas inclus dans le ZIP source GitHub : il faut les compiler (ou les obtenir d’une publication officielle) avant le flash. L’installation du serveur HA elle-même ne nécessite pas le SDK Pico.

## Installation simple du Pico

Effectuez ces étapes une fois par PAC ; chaque PAC a besoin de son propre Pico et d’un serveur/bridge configuré pour cette carte.

1. Débranchez le Pico de la PAC et utilisez un câble USB de données pour le relier à un ordinateur.
2. Téléchargez l’UF2 générique depuis une release GitHub publiée, ou suivez [les étapes de compilation](../firmware/PORTAL.md#compiler-luf2-générique). Maintenez **BOOTSEL** en branchant le Pico, puis copiez le fichier correspondant à la carte sur le volume `RPI-RP2`. Après publication, les deux UF2 et `SHA256SUMS` sont joints par l’action GitHub ; attendez que cette action réussisse avant de télécharger le firmware.
3. Sur un téléphone, connectez-vous au Wi-Fi temporaire `Aldes-Setup-…`, restez connecté malgré l’absence d’Internet, puis ouvrez `http://192.168.4.1/`.
4. Saisissez le Wi-Fi de la maison (2,4 GHz) et notez le token de contrôle dans un endroit sûr. Le portail de configuration est ouvert et non chiffré : faites cette étape chez vous, dans un lieu de confiance.
5. Après le redémarrage, trouvez l’adresse IP du Pico dans la liste DHCP du routeur et créez une réservation DHCP. La page « reçue » ne garantit pas que le Pico a rejoint le Wi-Fi.
6. Gardez le Pico débranché de la PAC jusqu’à ce que le serveur correspondant soit configuré. Pour les cas de dépannage, lisez le guide complet [Configuration du Pico](../firmware/PORTAL.md).

Si le Pico est déjà configuré, ne le reflashez pas : relevez son IP et son token existants. Le guide complet documente aussi la récupération en cas de changement Wi-Fi ou de token perdu.

## Prérequis communs

- Home Assistant sur une machine allumée, connectée au même réseau que le Pico.
- Pour le parcours MQTT seulement : un broker MQTT configuré dans l’intégration **MQTT** de Home Assistant, avec découverte activée. Mosquitto convient ; le broker doit imposer une authentification.
- Adresse du Pico et token de contrôle, depuis le portail ou votre configuration privée historique.
- **Un seul collecteur par Pico** : arrêtez le bridge Mac avant de démarrer celui de HA. Gardez son installation intacte pour revenir en arrière si nécessaire. Ne laissez pas deux services de reprise se concurrencer.

## Home Assistant OS

Le parcours add-on reste expérimental. Téléchargez le ZIP du projet depuis GitHub et décompressez-le. Avec Samba ou SSH, copiez **le dossier `homeassistant/addon` entier** vers le dossier local des add-ons de Home Assistant sous le nom `aldes_pilot`. Il contient son Dockerfile, sa configuration et les sources générées. Dans Home Assistant, ouvrez **Paramètres → Modules complémentaires → Boutique → menu ⋮ → Recharger**, puis actualisez la page.

1. Rechargez la boutique d’apps/add-ons ; installez **Aldes Pilot** dans les applications locales. La première construction télécharge Python et les dépendances ; **elle n’exige pas le SDK Pico**.
2. Dans la configuration de l’add-on, donnez un nom clair à cette PAC, par exemple `PAC rez-de-chaussée`, puis renseignez `pico_host` et `control_token`. Ces options sont privées.
3. Démarrez Mosquitto et l’intégration MQTT. L’add-on récupère les identifiants du service MQTT auprès du Supervisor, sans les écrire dans l’image.
4. Arrêtez l’ancien bridge, puis démarrez cet add-on. Activez son démarrage automatique.
5. Ouvrez son interface via Home Assistant. L’ingress gère l’accès à la page ; aucun port web n’est publié sur le réseau par défaut. Les requêtes web sont limitées au proxy ingress du Supervisor et à la boucle locale.
6. Dans MQTT, cherchez l’appareil **Aldes Pilot** et ajoutez ses entités à votre tableau de bord.

## Home Assistant Container

Les add-ons nécessitent le Supervisor ; pour HA Container, utilisez le compagnon Docker sur la machine HA :

```sh
cd homeassistant/docker
python3 configure.py
docker compose up -d --build
```

Le configurateur demande adresse/token Pico. REST est le choix par défaut ; MQTT reste facultatif. Pour MQTT, il demande les accès à votre broker existant. Saisissez une adresse de broker accessible **depuis un conteneur** ; `localhost` désignerait le conteneur Aldes, pas celui de Mosquitto. Les données restent dans `private/` et `logs/`, persistées hors de l’image. Ces dossiers sont exclus de Git.

Pour REST, si HA utilise le réseau hôte (`network_mode: host`), copiez `homeassistant/rest/aldes_pilot.yaml` dans `/config/packages/` et ajoutez `packages: !include_dir_named packages` sous le bloc `homeassistant:` existant de `configuration.yaml`. Ne créez pas un second bloc `homeassistant`. Vérifiez la configuration avant de redémarrer HA. Aucun broker MQTT n’est requis.

Si HA n’utilise pas le réseau hôte, `127.0.0.1` ne désigne pas le compagnon : adaptez le réseau Docker et les URL du package sans exposer le port à Internet. Les commandes REST utilisent l’API locale, sans PIN configuré ; seuls les utilisateurs locaux et les services ayant accès à ce port doivent être considérés comme autorisés.

## Plusieurs PAC / plusieurs bridges

Chaque PAC doit avoir **son Pico, son token, son instance serveur et son identifiant MQTT**. Ne configurez jamais deux instances pour la même adresse Pico : un seul collecteur peut lire les logs de chaque Pico. Pour distinguer les appareils dans Home Assistant, attribuez un nom unique à chaque PAC. Le parcours multi-bridge documenté ci-dessous utilise MQTT ; le package REST fourni est destiné à une seule PAC et peut créer des entités en collision.

### Plusieurs instances Docker (Home Assistant Container ou Mac)

Créez la première instance comme indiqué ci-dessus. Pour chaque PAC supplémentaire, restez dans `homeassistant/docker` et créez une configuration distincte :

```sh
python3 configure.py --instance pac2
INSTANCE_DIR=instances/pac2 WEB_PORT=8772 docker compose -p aldes-pac2 up -d --build
```

Dans les questions du configurateur, choisissez MQTT et donnez un nom unique, par exemple `PAC étage`. Pour une troisième PAC, utilisez un identifiant tel que `pac3`, un autre port (`8773`) et un nom différent. Gardez `INSTANCE_DIR` et `WEB_PORT` identiques aux valeurs utilisées au démarrage. Chaque instance a ses propres secrets, journaux et identité MQTT, dans `homeassistant/docker/instances/<identifiant>/`; ces fichiers sont privés et ne doivent pas être partagés. Configurez chaque Pico avec l’adresse/token affichés au préalable et lancez un seul conteneur par Pico.

### Plusieurs PAC sous Home Assistant OS

Le Supervisor ne lance pas deux fois le même add-on. Pour une deuxième PAC, copiez le dossier d’add-on sous un **nouveau slug** (par exemple `/addons/aldes_pilot_pac2`), puis modifiez `config.yaml` dans cette copie : `slug: aldes_pilot_pac2`, `name: Aldes Pilot PAC 2`, `panel_title: PAC 2` et la valeur par défaut `bridge_name: PAC 2`. Rechargez les add-ons locaux et installez les deux add-ons. Dans chacun, définissez un `bridge_name`, une adresse Pico et un token distincts. Les données et l’identité MQTT sont isolées par le Supervisor. Pour mettre à jour le code, régénérez/copiez les sources dans chaque dossier ; ne remplacez pas les options privées.

Dans les deux parcours, démarrez Mosquitto et l’intégration MQTT, puis vérifiez que Home Assistant affiche un appareil par nom de PAC. Les identifiants MQTT sont générés séparément et conservés avec les données privées de chaque instance ; ne copiez pas le dossier `private` d’une instance vers une autre.

### Lancer le serveur Docker depuis macOS

Le même compagnon peut héberger l’interface et le collecteur sur un Mac avec Docker Desktop. Le Pico doit être joignable depuis le Mac sur le réseau local ; gardez un seul collecteur actif pour ce Pico.

```sh
cd homeassistant/docker
python3 configure.py
docker compose up -d --build
docker compose ps
```

Saisissez l’adresse réseau du Pico et son token. REST est le choix par défaut ; n’activez MQTT que si vous avez déjà un broker accessible depuis Docker Desktop. Ouvrez ensuite `http://127.0.0.1:8771/` sur le Mac. Compose ne publie le port que sur la boucle locale et persiste la configuration et les journaux dans `homeassistant/docker/private/` et `homeassistant/docker/logs/`. Pour arrêter le serveur, utilisez `docker compose down`. Arrêtez d’abord le collecteur lancé ailleurs afin d’éviter deux lecteurs concurrents du port de logs du Pico.

Le package crée deux sélecteurs, quatre consignes et un bouton d’annulation des vacances. Le capteur `sensor.aldes_pilot_rapport` doit conserver cet identifiant, utilisé par les templates. En cas de collision avec une installation existante, adaptez le générateur. Les commandes ne changent pas l’état affiché avant confirmation par le rapport PAC.

Pour MQTT, les entités découvertes apparaissent dans HA. Le diagnostic web est limité à `127.0.0.1:8771` sur l’hôte ; votre tableau de bord HA est l’interface distante. Si nécessaire, ouvrez un tunnel SSH local pour accéder au diagnostic. Aucun second portail cloud à installer.

## Entités et comportement

- Sélecteur mode air : OFF, chauffage Confort/Éco/Programmes A/B, clim Confort/Boost/Programmes C/D.
- Sélecteur ECS : OFF, ON, Boost.
- Nombres : consignes K1–K4 actives, Off (0), 16–24 °C en chauffage ou 22–31 °C en climatisation, par pas de 1 °C. Lorsque le mode air global est Arrêt, 16–31 °C sont acceptés. La configuration MQTT adapte le maximum au mode ; le serveur refuse les consignes hors plage.
- Capteurs MQTT : températures des zones actives K1–K9 ; consignes K5–K9 actives en lecture seule. Leur association aux pièces reste à confirmer. K1–K4 restent pilotables ; l’écriture de K5–K9 n’est pas validée.
- Bouton : annuler les vacances / hors gel. La création de nouvelles dates n’est pas proposée.

Les états viennent exclusivement du rapport21. Modifier l’IHM se répercute sur HA après réception du rapport (cadence observée proche de 20 secondes). Pas d’état optimiste ni de réconciliation automatique. Les températures candidates du rapport sont publiées sous des noms explicitement provisoires, sans présumer de leur correspondance aux pièces.

La découverte MQTT ne crée les entités d’une zone que lorsque le rapport la signale active. Si une zone n’est plus remontée, le bridge efface sa configuration de découverte MQTT retenue : ses entités sont retirées de Home Assistant et seront recréées si la zone réapparaît. Les entités actives portent les identifiants `sensor.aldes_pilot_temperature_k1` à `sensor.aldes_pilot_temperature_k9`, `sensor.aldes_pilot_setpoint_k5` à `sensor.aldes_pilot_setpoint_k9` et `number.aldes_pilot_k1` à `number.aldes_pilot_k4`. Home Assistant peut adapter le préfixe en cas de collision.

La page `/logs` affiche les zones actives présentes dans les données décodées, jusqu’à neuf, et le détail des champs reconnus du rapport local `0x21` avec leurs offsets et formats, ainsi que les autres rapports complets détectés. Le rapport `0x21` porte les consignes K1–K9 aux offsets 13–30 et les températures K1–K9 aux offsets 53–70. Les zones sans valeur sont omises. Pour les rapports dont le format n’est pas encore identifié, le journal RAW reste disponible sans interprétation hasardeuse.

Les commandes MQTT sont QoS0, sans rétention ; les messages reçus avec rétention sont refusés. MQTT remet les commandes directement à la file mémoire unique du serveur, partagée avec l’interface web, au lieu d’attendre séparément le cooldown dans le bridge MQTT. Le serveur accepte jusqu’à 16 commandes distinctes en attente et les traite séquentiellement. Les commandes de mode air et ECS arrivant ensemble dans la fenêtre de 2 secondes sont assemblées en une seule trame USB ; cette écriture combinée est expérimentale et doit être surveillée sur l’IHM PAC. Les changements de consigne attendent 5 secondes après la dernière modification ; les valeurs de plusieurs zones consécutives sont alors assemblées dans une seule trame USB. Les valeurs successives d’une même zone sont remplacées par la plus récente. L’écriture multi-zone est elle aussi expérimentale : la trame mono-zone est validée, mais la prise en charge de plusieurs consignes dans la même trame n’a pas encore été confirmée sur la PAC. La file centralisée attend la fin de l’envoi et du cooldown avant de passer à la suivante ; son état est visible dans **Logs → File de commandes**, pas comme entité Home Assistant.

Les commandes MQTT sont acceptées tant que la lecture PAC est saine, même pendant l’envoi ou le cooldown. L’accusé MQTT confirme uniquement l’ajout à la file serveur, pas l’écriture USB ni l’application par la PAC. Une commande déjà acceptée reste dans la file si le broker se déconnecte ; en revanche, une perte de lecture PAC vide les commandes en attente. La file est en mémoire, ni persistée ni rejouée après redémarrage du serveur. Une commande déjà en cours lors d’une coupure peut avoir été envoyée, mais n’est jamais retentée automatiquement. Le résultat de livraison ne remplace jamais la lecture réelle. La reprise bornée utilise le même `recovery.py` que sur Mac.

L’interface web et MQTT utilisent la même file de commandes côté serveur : les actions sont acceptées rapidement, sans attendre la fin de l’écriture USB. Les commandes sont sérialisées ; le mode air et l’ECS reçus dans une fenêtre de 2 secondes partagent une trame expérimentale, et les consignes K1–K4 arrivent dans une fenêtre commune de 5 secondes puis sont incluses dans une seule trame si plusieurs zones sont en attente. Ces assemblages évitent plusieurs cycles d’écriture/cooldown, mais doivent être validés sur le modèle de PAC utilisé. Pour le premier essai mode air + ECS, envoyer les deux changements à moins de 2 secondes d’intervalle puis vérifier séparément les deux valeurs sur le rapport PAC et l’IHM avant de considérer la fonction comme validée. Les contrôles restent utilisables pendant l’envoi ou le cooldown. Les commandes en attente sont annulées si la lecture PAC devient indisponible ; elles ne sont pas persistées au redémarrage.

Le broker et ses clients autorisés peuvent envoyer des commandes : protégez leurs identifiants et les ACL du broker. La découverte MQTT est conservée, les valeurs sont republiées toutes les quatre secondes à partir de la capture fraîche ; les configurations des zones inactives sont effacées. Le Last Will signale la déconnexion du bridge.

## Test de réception avant migration définitive

1. Vérifier les réglages actuels sur l’IHM et le rapport reçu dans HA.
2. Modifier un mode sur l’IHM et observer l’entité HA correspondante.
3. Envoyer une commande explicite dans HA et vérifier l’IHM, puis revenir au réglage choisi.
4. Vérifier une perte de réseau et l’état indisponible, sans rejouer d’anciennes commandes.
5. Tester une coupure PAC, puis un redémarrage de l’hôte HA ; relever les commandes et le retour de trois rapports21. Cela reste à faire pour ce packaging.

Les sources de l’add-on sont régénérées par `python3 homeassistant/package.py`. Ne les modifiez pas manuellement : `source/SOURCE-HASHES.json` contient les SHA256 des fichiers canoniques de la racine.

Références : [configuration des apps HA](https://developers.home-assistant.io/docs/apps/configuration/), [ingress](https://developers.home-assistant.io/docs/apps/presentation/), [découverte MQTT](https://www.home-assistant.io/integrations/mqtt/).

Sur l’installation de référence, l’API confirme HA Container 2026.6.4 et MQTT absent au moment de la préparation. Le parcours REST évite d’ajouter un broker ; MQTT demeure une alternative. L’add-on HA OS ne s’installe pas dans cette instance Container.

### Latence et disponibilité REST

La lecture reste visible pendant une commande ou le délai de 45 secondes entre deux envois, tant que le rapport est frais. Ce délai interdit seulement une nouvelle commande ; il ne retarde pas volontairement l’affichage. Le capteur binaire « Aldes Pilot Commandes disponibles » expose cette distinction. Une nouvelle commande pendant ce délai est refusée explicitement, sans mise en file. La cadence PAC observée est proche de 20 secondes, puis REST ajoute jusqu’à environ cinq secondes de polling en fonctionnement normal. Ce n’est pas un délai maximal garanti en cas de reconnexion ou de rapport manquant.


## Diagnostic après coupure

Après redémarrage du Pi ou retour du réseau, le collecteur se reconnecte et
établit une nouvelle référence du compteur cumulatif `log perdus`. Deux STATUS
stables et un rapport complet récent sont nécessaires. L’interface reste
indisponible pendant cette vérification ; elle ne réutilise pas les valeurs
antérieures à la reconnexion. Aucune commande utilisateur n’est rejouée.

- Vérifier que le compagnon tourne (`docker compose ps`) et qu’un seul collecteur
  utilise le port de logs du Pico.
- Vérifier l’adresse du Pico dans la configuration privée et sa joignabilité depuis
  l’hôte. Une réservation DHCP ou une adresse fixe cohérente évite les changements
  d’adresse ; ne pas modifier le réseau sans en vérifier les paramètres.
- Examiner `private/usbguard.json`, `private/usbguard-events.jsonl` et
  `private/recovery.json` localement. Ils restent hors Git. `usbguard` ne rallume
  l’USB que si le STATUS indique `usb=0`, sans interrompre un TX PENDING, et avec
  trois essais maximum par heure. Un réseau absent est retenté au tour suivant.
- Vérifier `sensor.aldes_pilot_rapport` à `online`, les valeurs réellement relues
  et le capteur « Commandes disponibles ». `ready` dans recovery seul ne prouve
  pas que la lecture est fraîche.

Pour mettre à jour les sources du compagnon : `git pull --ff-only`, puis
`docker compose up -d --build` depuis `homeassistant/docker`. Conserver les
répertoires privés persistants et une image de retour arrière. Les tests Python
se lancent depuis la racine avec `python3 -m unittest discover -v`.

La reprise après reconnexion du compagnon a été vérifiée sur l’installation de
référence. Aucun nouveau redémarrage complet du Pi ni flash du Pico n’a été
réalisé pour qualifier ce correctif.
