# Utilisation expérimentale et limites

Ce projet personnel partage une démarche d’interopérabilité et des essais réalisés sur une installation de référence. Il ne constitue ni un produit officiel Aldes, ni une prestation d’installation ou de maintenance, ni une certification de compatibilité ou de sécurité.

## Périmètre des résultats

Le fait qu’une fonction ait été observée sur l’installation de référence ne garantit pas son fonctionnement ailleurs. Les versions de matériel, de firmware et de logiciel, ainsi que les essais et leurs limites, sont décrits dans REPRODUCTION.md et VALIDATION.md. Une qualification logicielle simulée ne remplace pas un essai matériel. Les éléments marqués expérimentaux ou non qualifiés ne doivent pas être présentés comme validés.

Le firmware générique avec portail Wi-Fi reste à qualifier sur matériel. Le parcours Home Assistant REST dispose d’une lecture vérifiée sur l’installation de référence ; les commandes HA et la reprise après redémarrage complet du Pi restent à vérifier. Les autres parcours de déploiement ont leurs propres limites.

## Effets possibles et précautions

Le logiciel peut modifier les consignes et les modes de chauffage, climatisation et eau chaude, et annuler une période de vacances ou de hors gel. Une erreur de décodage, une incompatibilité ou une panne peut entraîner un réglage indésirable, une absence de chauffage ou d’eau chaude, une consommation accrue ou des dommages. Des informations affichées peuvent être incomplètes ou périmées malgré les contrôles prévus.

Avant un premier essai, relever les réglages et versions, conserver l’accès à l’IHM et vérifier le moyen de revenir au fonctionnement habituel. Tester une fonction à la fois, en présence d’une personne pouvant contrôler son effet sur l’installation. Ne pas désactiver les protections constructeur ni utiliser ce projet comme dispositif de sécurité, d’alarme ou de protection antigel. Respecter les prescriptions du fabricant et faire intervenir un professionnel si une manipulation matérielle l’exige.

Ne pas exposer directement les ports du bridge à Internet. Garder les identifiants, jetons, captures privées et dumps de flash configurée hors des publications. Un seul collecteur doit piloter la connexion au Pico.

## Absence d’engagement contractuel

Le projet est fourni en l’état, sans garantie contractuelle de fonctionnement, de disponibilité, de compatibilité ou d’adéquation à un usage particulier, dans la mesure permise par le droit applicable. Aucun engagement de support, de mise à jour ou de correction dans un délai déterminé n’est pris. Le partage ne constitue pas un engagement à intervenir sur les installations des utilisateurs.

Ces mentions ne suppriment aucun droit impératif et ne prétendent pas exclure une responsabilité qui ne peut légalement l’être. Elles ne constituent pas une renonciation générale des utilisateurs à tout recours. L’incidence d’une utilisation sur une garantie constructeur ou un contrat d’entretien doit être examinée au cas par cas ; aucune conclusion automatique n’est annoncée ici.

## Droits et marques

Aldes et les noms de produits sont cités pour identifier le matériel concerné. Aucune affiliation, approbation ou certification par le fabricant n’est revendiquée. Les droits sur les marques et les composants tiers restent à leurs titulaires ; voir THIRD_PARTY.md.

Une licence du code original, lorsqu’elle sera choisie, encadrera sa réutilisation. Elle ne donnera aucun droit sur les logiciels propriétaires, les marques ou les droits de tiers. Ce document n’accorde pas à lui seul une licence du code original.

Avant diffusion publique, vérifier l’origine et les licences de chaque composant et de chaque binaire, les autorisations relatives aux contributions et captures de tiers, l’absence de secrets et la précision des affirmations de compatibilité. Faire examiner le dépôt et les conditions de diffusion par un avocat en propriété intellectuelle et responsabilité logicielle si une appréciation juridique propre au projet est recherchée.
