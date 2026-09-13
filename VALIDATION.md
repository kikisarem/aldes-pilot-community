# Qualification au 11 septembre 2026

## Zone K2 sans consigne — confirmation du 13 septembre 2026

Observation passive sur l'installation de référence le 12 septembre, puis
confirmation de l'utilisateur le 13 septembre : la zone K2 était **sans consigne**.

- Le champ K2 du rapport `0x21` (offsets 15–16, little endian) est passé de
  `98 08` (2200 / 100 = 22 °C) à `00 00`.
- La valeur nulle a été retrouvée dans 178 rapports complets avec somme de
  contrôle valide ; les trois autres consignes sont restées à 22 °C.
- Le bridge et HA affichaient tous deux cette valeur : elle n'était pas créée
  par la présentation HA. Aucune commande K2 correspondante n'apparaît dans
  le journal d'opérations consulté ; l'origine du changement n'est pas établie.
- Le champ candidat de température K2 restait voisin de 22,1 °C. Cela ne
  constitue pas une validation physique de l'identité de cette sonde.

**Interprétation bornée :** dans ce cas, zéro représente l'absence de consigne,
pas une température mesurée de 0 °C. La désactivation du chauffage/refroidissement
de la zone n'a pas été mesurée séparément : ne pas assimiler automatiquement
« sans consigne » à un arrêt matériel confirmé.

Cette qualification concerne la **lecture** de K2 sur une seule installation.
Écriture à zéro, réactivation depuis cet état et équivalence pour K1/K3/K4 ou
d'autres versions non testées. Aucun réglage ni firmware modifié pendant le
diagnostic. Documentation seule : le code et les interfaces n'ont pas encore
été adaptés pour afficher « Sans consigne ».

## Résultats antérieurs

- 13 tests Python réussis : framing, ruptures, checksum, fraîcheur, rotation/troncature, changements IHM sans connexion réseau, erreurs historiques distinctes de l’état actuel et masques de commandes.
- Tests C/clients du firmware réussis, incluant expiration, désarmement, replay refusé et simulations de livraison à 20 / 89,5 secondes.
- Compilation depuis les sources du dépôt avec secrets factices réussie : SDK 2.3.1 + Arm GNU 14.2.Rel1. Aucun flash matériel lors de cette préparation.
- Navigateur mobile : état extérieur mis à jour, brouillon conservé, perte HTTP signalée, commandes bloquées, zéro POST pendant les tests.
- Changement IHM réel observé : chauffage Confort et K1 à 24 °C, confirmé par l’utilisateur sur la page web.
- Serveur et collecteur sous lanceur macOS autorisé au Réseau local ; venv et capture hors /tmp.
- Arrêt contrôlé des deux enfants : reprise avec rapport frais en 14,2 s. Arrêt du lanceur : recréation par LaunchAgent et rapport frais en 16,3 s. Ce ne sont pas des mesures après reboot matériel.

## Limites conservées

Une seule installation de référence. Reprise automatique après coupure PAC validée sur une occurrence avec le firmware historique ; nouveau firmware générique à qualifier. Démarrage Mac à l’ouverture de session, veille et FileVault à considérer. Températures physiques, écriture de nouvelles dates et des grilles horaires, et persistance prolongée d’une nouvelle consigne non qualifiées. Aucune correction automatique des réglages extérieurs.


## Coupure PAC de 30 secondes — 11 septembre 2026

Après la coupure et la remise de l’horloge sur l’IHM, Pico et collecteur se reconnectent. La PAC émet 20 ; la page invalide correctement les anciennes valeurs. La lecture 21 ne reprend pas seule dans la fenêtre observée.

Reprise supervisée sans écriture de réglage : 40/20 → 25, 45/25 → 26, 46/26 → 27, 47/27 → 28, 48/28 → **21 directement**. Cinq envois uniques, chacun suivi de STOP confirmé. Au moins trois rapports21 successifs vérifient quatre consignes22, airOFF et ECS ON, conformes à la référence avant coupure. Une tentative préparée pour23 a été bloquée avant émission parce que21 était déjà actif.

La séquence diffère du premier déblocage nocturne : ne pas coder une liste aveugle ni imposer un passage par23/24. Cette reprise après coupure est démontrée sur une occurrence et demeure manuelle ; aucun réamorçage USB automatique n’est activé dans le service. Les champs de températures candidates peuvent encore être nuls pendant le retour des informations de sondes ; ne pas les afficher comme des températures physiques nulles.


## Reprise automatique ajoutée

`recovery.py`, lancé par le superviseur, réamorce les rapports à partir des pages fraîches20/25/26/27/28. Il n’envoie que les cinq commandes de contrôle8octets connues, jamais0x10. Il cesse tout envoi dès21 et confirme l’état prêt après trois rapports21 distincts.

Un envoi maximum par page et par épisode, cinq maximum par épisode, dix maximum par heure et dix minutes de reprise. Les réservations sont persistées avant émission afin qu’un plantage ne rejoue pas une commande. Fichier périmé : aucune émission. Page inconnue, délai dépassé ou erreur transport : arrêt signalé. Le verrou est partagé avec les commandes web ; le firmware conserve ses protections ARM/STOP.

La reprise matérielle supervisée avait été validée après une coupure. Cette implémentation automatique est testée en simulation (20 tests Python au total), puis déployée en surveillance sans émission lorsque21 est actif. Un nouveau test de coupure reste nécessaire pour qualifier la reprise automatique de bout en bout.


## Deuxième coupure PAC — reprise entièrement automatique

Le 11 septembre 2026 : observation de 20→25→26→27→28→21, cinq commandes de contrôle émises par le service sans envoi manuel, cinq STOP avec armed=0. Trois rapports21 aux uptimes169407/189407/209406 confirment airOFF, ECS ON, K1=24 et K2–K4=22, comme avant la coupure. Le service revient à ready. Cela qualifie cette occurrence sur l’installation de référence, pas toutes les versions de PAC ni le démarrage de l’hôte Mac.

## Portail et packaging Home Assistant — expérimental

Firmware générique compilé pour Pico W RP2040, sans include privé. Tests de formulaire, limites, doublons, échappement, adresses et CRC corrompu/flash vierge sous ASan/UBSan. 26 tests Python du bridge et de la couche MQTT passent. Les commandes MQTT ont une validation explicite ; aucune valeur reçue de MQTT n’est publiée comme état observé.

Portail AP réel, écriture flash interrompue, association DHCP/statique, compatibilité USB du nouveau firmware et installation Docker/HA restent à tester sur matériel. Le firmware et les services de production n’ont pas été remplacés. Le Pi HA n’était pas joignable en SSH pendant cette préparation.

Tests complémentaires : simulation de coupure après effacement et pendant programmation de la nouvelle copie ; ancienne configuration conservée. Navigateur mobile du portail et GET/POST sous préfixe ingress testés avec serveur simulé. Serveur ASGI isolé : iframe SAMEORIGIN, origine réseau hors ingress refusée, POST sans en-tête refusé. Aucun de ces essais n’émet vers la PAC.

## HA Container / REST — 11 septembre 2026

- Image Python 3.13 ARM64 construite sur Raspberry Pi ; Docker démarre au boot, compagnon avec `restart: unless-stopped`.
- Package REST validé par le vérificateur de configuration HA 2026.6.4, puis chargé après redémarrage de HA.
- Collecteur Mac arrêté et son LaunchAgent désactivé avant démarrage du compagnon : un seul collecteur actif.
- Trois rapports21 reçus, reprise en état ready sans commande automatique pendant la migration.
- Deux modes et quatre consignes lus dans HA identiques à la référence avant migration.
- Tableau de bord natif créé et configuration relue via l’API WebSocket.
- Restent à tester avec l’occupant : commande depuis HA puis contrôle IHM, changement IHM visible dans HA, coupure PAC et reboot complet du Pi avec ce déploiement. Le test de reboot PAC antérieur concernait le service Mac.

## Affichage HA pendant le délai entre commandes

Les templates REST rendaient les entités indisponibles pendant les 45 secondes de cooldown. Correction : disponibilité de lecture fondée sur un rapport frais ; garde d’envoi distincte conservée. Cinq scénarios vérifiés avec Jinja dans le conteneur HA (cooldown, envoi actif, reprise, lecture absente, état prêt). Configuration complète vérifiée puis templates rechargés sans redémarrage HA ni commande PAC. Mesure du délai visible après une nouvelle commande utilisateur encore à effectuer.
