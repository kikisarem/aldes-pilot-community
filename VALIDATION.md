# Qualification au 11 septembre 2026

- 13 tests Python réussis : framing, ruptures, checksum, fraîcheur, rotation/troncature, changements IHM sans connexion réseau, erreurs historiques distinctes de l’état actuel et masques de commandes.
- Tests C/clients du firmware réussis, incluant expiration, désarmement, replay refusé et simulations de livraison à 20 / 89,5 secondes.
- Compilation depuis les sources du dépôt avec secrets factices réussie : SDK 2.3.1 + Arm GNU 14.2.Rel1. Aucun flash matériel lors de cette préparation.
- Navigateur mobile : état extérieur mis à jour, brouillon conservé, perte HTTP signalée, commandes bloquées, zéro POST pendant les tests.
- Changement IHM réel observé : chauffage Confort et K1 à 24 °C, confirmé par l’utilisateur sur la page web.
- Serveur et collecteur sous lanceur macOS autorisé au Réseau local ; venv et capture hors /tmp.
- Arrêt contrôlé des deux enfants : reprise avec rapport frais en 14,2 s. Arrêt du lanceur : recréation par LaunchAgent et rapport frais en 16,3 s. Ce ne sont pas des mesures après reboot matériel.

## Limites conservées

Une seule installation de référence. Reprise après coupure complète PAC à qualifier. Démarrage Mac à l’ouverture de session, veille et FileVault à considérer. Températures physiques, écriture de nouvelles dates et des grilles horaires, et persistance prolongée d’une nouvelle consigne non qualifiées. Aucune correction automatique des réglages extérieurs.


## Coupure PAC de 30 secondes — 11 septembre 2026

Après la coupure et la remise de l’horloge sur l’IHM, Pico et collecteur se reconnectent. La PAC émet 20 ; la page invalide correctement les anciennes valeurs. La lecture 21 ne reprend pas seule dans la fenêtre observée.

Reprise supervisée sans écriture de réglage : 40/20 → 25, 45/25 → 26, 46/26 → 27, 47/27 → 28, 48/28 → **21 directement**. Cinq envois uniques, chacun suivi de STOP confirmé. Au moins trois rapports21 successifs vérifient quatre consignes22, airOFF et ECS ON, conformes à la référence avant coupure. Une tentative préparée pour23 a été bloquée avant émission parce que21 était déjà actif.

La séquence diffère du premier déblocage nocturne : ne pas coder une liste aveugle ni imposer un passage par23/24. Cette reprise après coupure est démontrée sur une occurrence et demeure manuelle ; aucun réamorçage USB automatique n’est activé dans le service. Les champs de températures candidates peuvent encore être nuls pendant le retour des informations de sondes ; ne pas les afficher comme des températures physiques nulles.
