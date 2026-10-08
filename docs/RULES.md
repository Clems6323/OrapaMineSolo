# Règles d'Orapa Mine — synthèse pour l'implémentation

> ✅ **Mise à jour (2026-08-31)** : ce document a été **révisé à partir du vrai
> livret officiel** (`docs/ORAPA MINE_REGLES_WEB.pdf`, édition française
> Miraludo, jeu de Junghee Choi & Wanjin Gill, © Gameology 2024). Les points
> auparavant incertains (dimensions de grille, table de couleurs, nombre de
> gemmes, question « qu'y a-t-il en X ? ») sont désormais **confirmés** et
> marqués ✅. Les seuls points encore ouverts sont :
>
> Tous les points auparavant ouverts sont désormais **résolus** :
> - ✅ formes des 7 pièces « tangram » confirmées (photos
>   `docs/tangram_pictures.jpeg` + mesures utilisateur), encodées dans
>   `model/gems_catalog.py` ;
> - ✅ table de mélange des couleurs complète (livret + carte « aide de jeu »).

## Principe général ✅

Orapa Mine est un jeu de déduction spatiale proche de *Black Box*. Un joueur
(le « maître du jeu ») place secrètement des gemmes sur un plateau caché
derrière un paravent. L'autre joueur (le « prospecteur ») envoie des rayons
(ondes supersoniques) depuis le bord du plateau pour déduire la position et
l'état exact de toutes les gemmes.

Dans le jeu physique, les **deux joueurs jouent simultanément les deux rôles**
(chacun maître du jeu pour l'adversaire et prospecteur pour lui-même), et
c'est une **course** : le premier à identifier la disposition adverse gagne.

Dans **notre version solo**, l'ordinateur joue le maître du jeu : il génère un
plateau aléatoire valide, et l'utilisateur joue le prospecteur. Il n'y a pas
de rival ; **le score = le nombre de rayons envoyés** avant une proposition
correcte (voir « Variantes solo »).

## Plateau ✅

- Grille **10 × 8 cases** (confirmé par le livret : « La feuille de solutions
  représente une grille de 10x8 cases »).
- Points d'entrée/sortie du rayon sur le **bord** du plateau, repérés par un
  **nombre (1 à 18)** ou une **lettre (A à R)** — comme à la Bataille Navale.
  Note : 10 colonnes + 8 lignes = 18, ce qui est cohérent avec un rayon qui se
  déplace de case en case (une « piste » par ligne et par colonne).
- La taille reste **configurable** dans le code (`Grid(width, height)`), mais
  la **valeur par défaut est désormais 10×8** (et non plus 8×8).

## Les gemmes ✅ (formes exactes `TODO-PHOTOS`)

- **7 gemmes par ensemble.** La **version de base n'en utilise que 5** :
  **1 rouge, 1 jaune, 1 bleue, 2 blanches.**
- Les 2 gemmes restantes de l'ensemble sont les **extensions** (voir plus
  bas) : le **Diamant** (transparent) et le **Corps noir** (absorbant).
- Chaque gemme est une **pièce géométrique de type « tangram »** (triangle
  rectangle ou parallélogramme), pas une simple case. Ses **arêtes visibles à
  la surface** jouent le rôle de **miroir** : le rayon se réfléchit sur
  l'arête diagonale.
- **Contraintes de placement (confirmées par le livret)** :
  - a. Les lignes de surface des gemmes doivent être **visibles**.
  - b. Chaque **coin de gemme correspond à un coin de la grille**, et les
    lignes visibles s'alignent sur la grille (pas de placement « de travers » :
    orientations limitées à 0/90/180/270°). ✅ **Le retournement (symétrie) est
    autorisé** — vérifié par l'utilisateur ; en pratique cela n'ajoute des
    orientations qu'au parallélogramme rouge (les autres pièces sont
    symétriques).
  - c. Une gemme **peut toucher le bord** du plateau mais **ne peut pas en
    dépasser**.
  - d. **Deux gemmes ne peuvent pas être côte à côte** : elles ne peuvent se
    toucher que **par un coin ou par une ligne** (pas d'adjacence par une
    face pleine).
  - e. **Aucune gemme ne doit être entièrement cachée** derrière une autre
    vue depuis un bord du plateau (chaque gemme doit être atteignable par au
    moins un rayon).
  - ✅ **Formes confirmées** (photos + mesures utilisateur), isolées dans
    `model/gems_catalog.py` :
    - Rouge : parallélogramme, aire 2 (côtés longs plats, bouts à 45°).
    - Bleu / Blanc #1 : triangle isocèle base 4 / hauteur 2, aire 4.
    - Jaune : triangle rectangle isocèle, cathètes de 2 cases, aire 2.
    - Blanc #2 : carré tourné à 45° (losange, boîte 2×2), aire 2.
    - Diamant : triangle base 2 / hauteur 1, aire 1.
    - Corps noir : **rectangle plein 1×2**, aire 2.

## Trajectoire du rayon ✅

1. Le prospecteur annonce un point d'entrée sur le bord (nombre ou lettre).
2. Le rayon avance **en ligne droite**, case par case (horizontal ou
   vertical), jusqu'à rencontrer une gemme.
3. Il se **réfléchit sur l'arête** de la gemme selon son inclinaison :
   - arête diagonale (`/` ou `\`) → déviation à **90°** ;
   - face pleine perpendiculaire → renvoi à **180°** (le rayon repart vers son
     point d'entrée) ;
   - **Corps noir** → **absorption** (pas de sortie) ;
   - **Diamant** → dévie **comme une arête diagonale** mais **sans teinter**.
4. À chaque gemme colorée touchée, il « prend » la couleur — **seule la
   première interaction avec chaque couleur distincte compte** (retoucher une
   couleur déjà collectée ne change rien).
5. Le rayon sort par un bord : le maître du jeu annonce **la case de sortie**
   et **la couleur finale**. S'il est absorbé, il annonce « Le signal a été
   absorbé » (pas de point de sortie).

## Question alternative « Qu'y a-t-il en [coordonnées] ? » ✅

Au lieu d'envoyer un rayon, le prospecteur peut demander le contenu d'une
case précise (ex. « Qu'y a-t-il en A1 ? »). La case est désignée par
**ligne-lettre + colonne-numéro** (A1 = coin haut-gauche : la lettre reprend le
bord gauche A–H, le chiffre le bord haut 1–10). Réponse :

- case vide → « rien » ;
- gemme colorée (même si la case n'est qu'à moitié occupée par la gemme) → sa
  **couleur** ;
- pièce d'**extension** (diamant, corps noir, trou de ver) → le **nom de la
  pièce** (et non une couleur).

Cette question **consomme aussi un tour** (donc compte dans le score solo).
Côté UI (écran de jeu), elle se pose dans la même zone de saisie que les tirs :
une saisie « lettre + chiffre » (A1) est interprétée comme une question de case,
un libellé de bord (chiffre seul 1–18 ou lettre seule A–R) comme un tir.

## Mélange des couleurs ✅ (quelques combos `TODO-AIDE-JEU`)

Le rayon part **transparent** et se teinte façon **peinture** (mélange
soustractif), le **blanc éclaircissant** la teinte. Confirmés par le texte et
les diagrammes du livret :

| Couleurs collectées            | Résultat        | Source            |
| ------------------------------ | --------------- | ----------------- |
| — (aucune)                     | transparent     | ✅ texte           |
| {Rouge}                        | rouge           | ✅ texte           |
| {Bleu}                         | bleu            | ✅ texte           |
| {Jaune}                        | jaune           | ✅ texte           |
| {Blanc}                        | blanc           | ✅ texte           |
| {Rouge, Jaune}                 | orange          | ✅ diagramme       |
| {Jaune, Bleu}                  | vert            | ✅ diagramme       |
| {Rouge, Bleu}                  | violet          | ✅ diagramme       |
| {Rouge, Blanc}                 | rose            | ✅ texte           |
| {Jaune, Blanc}                 | jaune clair     | ✅ texte           |
| {Bleu, Blanc}                  | bleu clair      | ✅ texte           |
| {Rouge, Jaune, Bleu}           | noir            | ✅ aide de jeu     |
| {Jaune, Bleu, Blanc}           | vert clair      | ✅ diagramme       |
| {Rouge, Jaune, Blanc}          | orange clair    | ✅ aide de jeu     |
| {Rouge, Bleu, Blanc}           | violet clair    | ✅ aide de jeu     |
| {Rouge, Jaune, Bleu, Blanc}    | gris            | ✅ texte           |

> Table **complète et confirmée** (livret + carte « aide de jeu »). Logique :
> mélange peinture (R+J+B = noir), le blanc éclaircit (noir → gris, secondaire
> → « X clair »). Isolée dans `COLOR_MIX_TABLE` en tête de `model/beam.py`.

## Fin de partie ✅

- Le prospecteur peut, pendant son tour, **soumettre une proposition
  complète** (position + forme + couleur + orientation de chaque gemme).
- Dans le jeu physique 2 joueurs : proposition correcte → victoire ;
  **proposition erronée → défaite immédiate**.
- **En solo**, on retient une règle plus douce (voir variantes) : une
  proposition erronée n'élimine pas forcément, mais le score reflète le nombre
  de rayons.

## Extensions ✅

- **Diamant** : gemme transparente. Dévie le rayon comme une arête diagonale
  mais **ne modifie jamais sa couleur** (si le rayon touche le diamant *et*
  d'autres gemmes, la couleur ne dépend que des autres).
- **Corps noir** : **absorbe** le rayon sans le renvoyer. Réponse du maître du
  jeu : « Le signal a été absorbé » (pas de point de sortie ; idem si on
  demande son contenu). Posé sur sa **base rectangulaire 1×2, pointe vers le
  haut** (empreinte = 2 cases pleines).
- **Trou de ver** (extension ajoutée, non officielle) : deux cases **1×1**
  posées par paire. Un rayon qui entre dans l'un des trous **ressort de l'autre
  dans la même direction** (téléportation, par la face opposée), **sans teinter**
  la couleur. Dessin : un carré noir (comme le corps noir) marqué d'une spirale
  blanche. Dans la palette, un
  seul emplacement « ×2 » (puis « ×1 » après la première pose, grisé une fois les
  deux posés).

## Variantes solo (spécifiques à cette implémentation) ✅

- **Score = nombre de rayons** (mode retenu) : rayons illimités, le joueur
  soumet sa solution quand il veut ; le score est le nombre de tirs (et de
  questions « qu'y a-t-il en X ? ») utilisés — moins il y en a, mieux c'est.
- **Difficulté** : contrôle du nombre de gemmes (5 base / 7 complet), de la
  taille de grille, et de l'activation des extensions.
- **Minuteur** (optionnel, 0 = désactivé) : réglable sur l'écran de
  configuration et en mode créateur, et sauvegardé avec la configuration. En
  jeu, le temps restant s'affiche (compte à rebours) ; à 0, la partie se
  termine (« Temps écoulé »). L'écran de fin indique le temps passé.
- **Rival IA** (non retenu pour la v1) : simuler un second prospecteur qui
  déduit en parallèle pour recréer la course du jeu physique.

## Points encore à confirmer

- ✅ Plus aucun point ouvert : formes des 7 pièces et table complète de
  mélange des couleurs confirmées et encodées (`model/gems_catalog.py`,
  `model/beam.py::COLOR_MIX_TABLE`).
