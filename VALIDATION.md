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
