---
name: orapa-mine-rules
description: Référence rapide des règles de déviation/couleur du rayon pour Orapa Mine. À consulter dès qu'on écrit ou modifie la simulation de trajectoire (model/beam.py) ou la génération de grille (ai/generator.py), pour éviter de réinventer/oublier une règle déjà documentée dans docs/RULES.md.
---

# Skill : règles de simulation du rayon — Orapa Mine

Cette skill résume, pour un accès rapide pendant le codage, les règles
détaillées dans `docs/RULES.md` (source de vérité — à relire si un doute
subsiste, notamment sur les points `TODO-VALIDATION`).

## Géométrie des gemmes (⚠️ modèle "tangram", confirmé par le vrai livret)

- Les gemmes ne sont **pas** de simples cases : ce sont des pièces
  géométriques (triangles rectangles, parallélogrammes) dont l'**arête
  visible** sert de **miroir**. Formes exactes : `TODO-PHOTOS` (isolées dans
  `model/gems_catalog.py`).
- Coins alignés sur les coins de grille ; orientations limitées à
  0/90/180/270° (pas de placement "de travers").

## Directions et déviations

- Le rayon se déplace en ligne droite, case par case, dans une des 4
  directions cardinales (haut/bas/gauche/droite).
- **Arête diagonale** (`/` ou `\`) : dévie le rayon de 90°.
  - `/` : haut↔droite, bas↔gauche
  - `\` : haut↔gauche, bas↔droite
- **Face pleine perpendiculaire** : renvoie le rayon à 180° — il repart vers
  sa case d'entrée (conséquence géométrique, pas une "pièce mur" dédiée).
- **Diamant (extension)** : dévie comme une arête diagonale, mais **ne teinte
  jamais le rayon**.
- **Corps noir (extension)** : absorbe le rayon. Pas de case de sortie, pas
  de couleur — résultat "absorbé" (`exit_point = None`). Toujours posé base
  rectangulaire, pointe vers le haut.
- **Trou de ver (extension)** : paire de cases 1×1. Le rayon qui entre dans
  un trou **ressort de l'autre dans la même direction** (téléportation), sans
  teinter. Géré dans `beam.fire_beam` avant les autres interactions ; le
  segment de liaison est marqué `TELEPORT_SEGMENT` (non dessiné). `Piece.quantity
  = 2` : la pièce se pose en deux exemplaires.

## Couleur du rayon

- Le rayon commence "transparent" (aucune couleur).
- À chaque gemme colorée touchée pour la **première fois** (par couleur
  distincte), sa couleur s'ajoute à l'ensemble des couleurs "collectées".
  Retoucher une couleur déjà collectée ne change rien.
- À la sortie de la grille, la couleur finale est déterminée par
  `COLOR_MIX_TABLE` (constante isolée en tête de `model/beam.py`), à partir
  de l'ensemble des couleurs collectées. Ne jamais faire ce calcul de
  manière dispersée dans le code — toujours passer par cette table.
- Table confirmée par le vrai livret (mélange façon peinture, le blanc
  éclaircit ; voir `docs/RULES.md` pour la table complète et les rares combos
  `TODO-AIDE-JEU`) :
  - {Rouge} → Rouge ; {Bleu} → Bleu ; {Jaune} → Jaune ; {Blanc} → Blanc
  - {Rouge, Jaune} → Orange ; {Jaune, Bleu} → Vert ; {Rouge, Bleu} → Violet
  - {Rouge, Blanc} → Rose ; {Jaune, Blanc} → Jaune clair ;
    {Bleu, Blanc} → Bleu clair
  - {Rouge, Jaune, Bleu} → Noir ; {Jaune, Bleu, Blanc} → Vert clair
  - {Rouge, Jaune, Blanc} → Orange clair ; {Rouge, Bleu, Blanc} → Violet clair
  - {Rouge, Jaune, Bleu, Blanc} → Gris

## Cas particuliers à couvrir dans les tests

1. Rayon qui traverse la grille sans toucher aucune gemme → sort en face du
   point d'entrée, transparent.
2. Une seule déviation (arête diagonale d'une gemme).
3. Plusieurs déviations en chaîne (2-3 arêtes successives).
4. Face pleine perpendiculaire → le rayon ressort par son point d'entrée (180°).
5. Absorption par un corps noir (extension) → pas de sortie.
6. Rayon qui touche deux fois une gemme de même couleur (chemin en boucle
   improbable mais à ne pas planter dessus) → couleur comptée une fois.
7. Les 4 couleurs réunies sur un même trajet → Gris.

## Où modifier quoi

- Direction/déviation : `model/beam.py::next_direction` (nom indicatif).
- Table de couleurs : `model/beam.py::COLOR_MIX_TABLE`.
- Formes/footprints des 7 pièces (`TODO-PHOTOS`) : `model/gems_catalog.py`.
- Contraintes de placement (adjacence, gemme cachée, bordure) :
  `ai/generator.py` (+ `model/grid.py`).
- Taille de grille par défaut (10×8) : `model/grid.py::DEFAULT_WIDTH` /
  `DEFAULT_HEIGHT`.
