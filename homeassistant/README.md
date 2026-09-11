# Aldes Pilot dans Home Assistant

Deux parcours : **HA OS avec add-on** ou **Home Assistant Container avec un conteneur compagnon**. Le Pico reste local. Home Assistant offre l’interface web et l’application mobile ; l’accès distant utilise votre accès HA existant (ou HA Cloud/Tailscale). Aucun port du Pico ne doit être redirigé vers Internet. Aucun cloud Aldes n’est nécessaire.

État : sources et tests hôte préparés ; **installation réelle HA et image Docker pas encore validées**. Aucun remplacement du bridge Mac effectué. Le firmware actuel est compatible : le portail générique n’est pas un prérequis pour essayer le bridge HA.

## Prérequis communs

- Home Assistant sur une machine allumée, connectée au même réseau que le Pico.
- Un broker MQTT configuré dans l’intégration **MQTT** de Home Assistant, avec découverte activée. Mosquitto convient ; le broker doit imposer une authentification.
- Adresse du Pico et token de contrôle, depuis le portail ou votre configuration privée historique.
- **Un seul collecteur par Pico** : arrêtez le bridge Mac avant de démarrer celui de HA. Gardez son installation intacte pour revenir en arrière si nécessaire. Ne laissez pas deux services de reprise se concurrencer.

## Home Assistant OS

Le dépôt étant privé, l’ajout public d’un dépôt d’add-ons ne convient pas encore. Téléchargez le projet avec votre accès GitHub, puis copiez **le dossier `homeassistant/addon` entier** vers `/addons/aldes_pilot` sur la machine HA (Samba/SSH). Il contient son Dockerfile, sa configuration et les sources générées.

1. Rechargez la boutique d’apps/add-ons ; installez **Aldes Pilot** dans les applications locales. La première construction télécharge Python et les dépendances ; **elle n’exige pas le SDK Pico**.
2. Dans la configuration de l’add-on, renseignez `pico_host` et `control_token`. Ces options sont privées.
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

Le configurateur demande adresse/token Pico et accès à votre broker MQTT existant. Saisissez une adresse de broker accessible **depuis un conteneur** ; `localhost` désignerait le conteneur Aldes, pas celui de Mosquitto. Les données restent dans `private/` et `logs/`, persistées hors de l’image. Ces dossiers sont exclus de Git.

Les entités MQTT apparaissent dans HA. Le diagnostic web est limité à `127.0.0.1:8771` sur l’hôte ; votre tableau de bord HA est l’interface distante. Si nécessaire, ouvrez un tunnel SSH local pour accéder au diagnostic. Aucun second portail cloud à installer.

## Entités et comportement

- Sélecteur mode air : OFF, chauffage Confort/Éco/Programmes A/B, clim Confort/Boost/Programmes C/D.
- Sélecteur ECS : OFF, ON, Boost.
- Quatre nombres : consignes K1–K4, de 16 à 30 °C par pas de 0,5 °C.
- Bouton : annuler les vacances / hors gel. La création de nouvelles dates n’est pas proposée.

Les états viennent exclusivement du rapport21. Modifier l’IHM se répercute sur HA après réception du rapport (cadence observée proche de 20 secondes). Pas d’état optimiste ni de réconciliation automatique. Températures candidates non exposées tant que les sondes physiques ne sont pas confirmées.

Les commandes MQTT sont QoS0, sans rétention ; les messages reçus avec rétention sont refusés. Une demande n’est pas mise en file hors ligne, ni retentée automatiquement. Bridge indisponible, reprise en cours, commande active ou cooldown : entités indisponibles. Le résultat de livraison ne remplace jamais la lecture réelle. La reprise bornée utilise le même `recovery.py` que sur Mac.

Le broker et ses clients autorisés peuvent envoyer des commandes : protégez leurs identifiants et les ACL du broker. La découverte MQTT est conservée, les valeurs sont republiées toutes les quatre secondes à partir de la capture fraîche ; le Last Will signale la déconnexion du bridge.

## Test de réception avant migration définitive

1. Vérifier les réglages actuels sur l’IHM et le rapport reçu dans HA.
2. Modifier un mode sur l’IHM et observer l’entité HA correspondante.
3. Envoyer une commande explicite dans HA et vérifier l’IHM, puis revenir au réglage choisi.
4. Vérifier une perte de réseau et l’état indisponible, sans rejouer d’anciennes commandes.
5. Tester une coupure PAC, puis un redémarrage de l’hôte HA ; relever les commandes et le retour de trois rapports21. Cela reste à faire pour ce packaging.

Les sources de l’add-on sont régénérées par `python3 homeassistant/package.py`. Ne les modifiez pas manuellement : `source/SOURCE-HASHES.json` contient les SHA256 des fichiers canoniques de la racine.

Références : [configuration des apps HA](https://developers.home-assistant.io/docs/apps/configuration/), [ingress](https://developers.home-assistant.io/docs/apps/presentation/), [découverte MQTT](https://www.home-assistant.io/integrations/mqtt/).

Sur l’installation de référence, l’API confirme HA Container 2026.6.4 et MQTT absent au moment de la préparation. Il faut donc préparer le broker et ajouter l’intégration MQTT avant de transférer le bridge. L’add-on HA OS ne s’installe pas dans cette instance Container.
