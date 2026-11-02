# Relevés communautaires : pages 0x23 à 0x28

Source publique : [RD13, HACF, message 619 du 1 novembre 2026](https://forum.hacf.fr/t/aldes-t-one-air-aquaair/42974/619).
Crédit : RD13. Observations déclarées sur son installation, pas des captures
indépendamment revérifiées ici. Les offsets partent de zéro dans la trame
complète. Ce document n'autorise ni écriture, ni parcours actif de pages.

## 0x23 — programmation, 119 octets

Quatre programmes A/B chauffage, C/D clim ; sept jours depuis lundi.
Quatre octets little endian par jour, départ offset 5 ; bit 0 = 0 h,
un bit par heure, 1 = Confort. Cela occupe 112 octets (5–116), hors en-tête
et fin de trame. Valeur des huit bits supérieurs de chaque mot non établie.
L'alignement jour/semaine reste à vérifier sur chaque PAC : l'installation
de référence a déjà présenté un décalage calendrier. Aucune écriture de
grille implémentée à partir de ce seul relevé.

## 0x24 — sondes, 87 octets

Selon RD13, mots LE16 signés /100 comparés à l'IHM :

| Offset | Attribution rapportée |
|---|---|
| 45 | Extérieur ThoA |
| 47 / 49 | ECS haut / bas |
| 57 | Ligne gaz Th3 |
| 61 | Échangeur extérieur ThoR1 |
| 75 | Sortie compresseur |

- Offset 63 : pression échangeur ECS probable (12,15 contre 12,10 bar IHM),
  pas une température validée.
- Offset 29 : angle vanne trois voies, valeur brute 45 ; ne pas appliquer /100.
- Offset 65 : −40 °C rapporté avec sonde absente ; ne pas l'afficher comme
  température physique confirmée ni généraliser ce marqueur à tous les champs.
- Th4/Th5/Th6 non attribués parmi 51/53/55/59/69/71.
- Offsets 79/81 non attribués ; EEV1 non identifié dans cette page.

L'extérieur à 45 avait également été comparé à l'IHM sur l'installation
de référence. Les autres attributions ne bénéficient pas de cette vérification.

## 0x25–0x28 — énergie

Longueurs rapportées : 175 / 175 / 151 / 127 octets. Blocs de 24 octets,
départ offset 5 : six LE32, trois compteurs ECS/clim/chauffage en kWh puis
trois valeurs pondérées par le tarif, interprétées en milli-euros par RD13.
L'interprétation monétaire reste bornée à ses comparaisons ; l'échelle globale
et les variantes de pages ne sont pas toutes requalifiées ici.

- Page 26, bloc offset 149 : compteurs courants comparés à l'IHM.
- Page 27 : totaux archivés ; datation avant remise à zéro seulement supposée.
- Pages 25/26/28 : quinze blocs d'historique supposés mensuels, sans date établie.

## Fraîcheur et blocage — limite déterminante

Chez RD13 ces pages ne sont chargées qu'au démarrage ; ses entités deviennent
indisponibles après trois heures. Ses tentatives de navigation aboutissent
à un blocage sur 4A. Aucun mécanisme fiable de rafraîchissement n'est fourni.
Ne pas ajouter de cycle automatique, de reset, ni déclarer ces mesures fraîches
sans nouvelle trame complète réellement reçue et horodatée. Attendre le diff
annoncé et une capture de dialogue natif pour établir la séquence.
