# Architecture technique — Orapa Mine solo

## Choix technique : Python + Pygame + uv

- **Pygame** est retenu pour l'interface graphique : le cœur du jeu est un
  rayon qui traverse une grille, dévie sur des gemmes et change de couleur
  — c'est fondamentalement du dessin/animation (halo lumineux, gemmes
  stylisées, rayon qui progresse case par case) plutôt que des formulaires.
  Un toolkit de widgets classique (Tkinter, Qt) rendrait cette partie très
  contrainte visuellement ; Pygame donne un contrôle pixel-perfect sur le
  rendu et une boucle de jeu adaptée à l'animation.
- **uv** gère l'environnement virtuel, les dépendances et le lockfile
  (`uv.lock`). Ne pas utiliser `pip`/`venv` manuellement — voir `CLAUDE.md`
  pour les commandes.

## Séparation des responsabilités (important : logique de jeu = testable
sans GUI)

```
src/orapa_mine/
├── model/              # Logique pure, sans dépendance UI, 100% testable
│   ├── gems.py         # Gem, GemShape, GemColor
│   ├── grid.py         # Grid, placement, validation
│   ├── beam.py         # Simulation de trajectoire + couleur du rayon
│   └── game.py         # État de partie, tours, historique, victoire
├── ai/
│   └── generator.py    # Génération aléatoire d'une grille valide (le "Directeur")
├── ui/
│   └── app.py           # Pygame : boucle de jeu, rendu, animation du rayon,
│                        # gestion des événements clavier/souris
└── main.py              # Point d'entrée (lance la boucle Pygame)
```

Règle d'or : **`model/` ne doit jamais importer `pygame`**. Ça garantit que
toute la logique du jeu (la partie intéressante et risquée : tracé du rayon,
règles de déviation, mélange des couleurs) peut être testée unitairement
sans ouvrir de fenêtre, avec `pytest`.

## Flux de données

1. `ai/generator.py` crée un `Grid` caché (les vraies positions/gemmes).
2. L'utilisateur clique sur un point d'entrée dans la fenêtre Pygame.
3. `ui/app.py` traduit ce clic en `(Position, Direction)` et appelle
   `model/beam.py` (`fire_beam`), qui retourne un `BeamResult` (point de
   sortie ou `None` si absorbé, couleur finale, chemin complet pour
   l'animation).
4. `model/game.py` enregistre le coup dans l'historique et vérifie une
   éventuelle proposition de victoire.
5. `ui/app.py` anime le rayon le long de `BeamResult.path` (case par case,
   à une vitesse contrôlée) puis affiche le résultat sur la grille de
   déduction du joueur (jamais la grille cachée, sauf mode debug explicite).

## Modélisation suggérée (point de départ, à affiner par Claude Code)

```python
from dataclasses import dataclass
from enum import Enum

class GemColor(Enum):
    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"
    WHITE = "white"

class GemShape(Enum):
    OBLIQUE = "oblique"   # dévie à 90°
    STRAIGHT = "straight" # mur, renvoie à 180°
    DIAMOND = "diamond"   # dévie sans changer la couleur (extension)
    BLACK_BODY = "black_body"  # absorbe tout (extension)

@dataclass(frozen=True)
class Gem:
    color: GemColor | None  # None pour DIAMOND / BLACK_BODY
    shape: GemShape
    orientation: int  # 0/90/180/270, sens du miroir

@dataclass(frozen=True)
class Position:
    row: int
    col: int
```

## Tests

- `tests/test_beam.py` : cas de trajectoire simples (ligne droite sans
  gemme, une déviation, deux déviations, absorption, sortie par le point
  d'entrée).
- `tests/test_grid.py` : validation du placement (pas de chevauchement, pas
  sur une case interdite, etc.).
- Approche recommandée : **TDD**. Écrire les tests de `beam.py` à partir des
  scénarios documentés dans `docs/RULES.md` AVANT d'écrire la logique, car
  c'est la partie la plus sujette à erreurs d'interprétation des règles.
- Les tests de `model/` ne nécessitent aucune fenêtre Pygame (pas d'appel à
  `pygame.init()`), ils tournent donc aussi bien en CI/headless.

## Interface graphique (`ui/app.py`)

Boucle Pygame standard :

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        # TODO: clic sur une case de bordure -> jouer un tir
        # TODO: clic sur la grille de déduction -> poser une hypothèse

    # TODO: mettre à jour l'animation du rayon en cours (si applicable)
    screen.fill(BACKGROUND_COLOR)
    # TODO: dessiner la grille, les hypothèses du joueur, le rayon animé
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

Écrans nécessaires :
1. Écran de configuration de partie (taille grille, nombre de gemmes,
   extensions activées, difficulté) — peut être un simple menu Pygame ou
   des rectangles cliquables, pas besoin d'un framework de widgets.
2. Écran de jeu :
   - grille de déduction cliquable (le joueur y note ses hypothèses),
   - zone pour choisir un point d'entrée (clic sur une case de bordure),
   - animation du rayon qui progresse et dévie en temps réel,
   - historique des tirs (entrée → sortie, couleur),
   - bouton "Proposer une solution".
3. Écran de fin (victoire + score = nombre de tirs, ou défaite).

### Pistes pour un rendu "joli"

- Dégradés radiaux / halo autour du rayon (`pygame.gfxdraw` ou surfaces
  avec alpha) plutôt qu'une simple ligne.
- Gemmes dessinées comme des polygones colorés avec un léger effet de
  brillance (triangle clair superposé) plutôt que des carrés pleins.
- Police custom (`pygame.font.Font(chemin_ttf, taille)`) plutôt que la
  police système par défaut.
- Anti-aliasing sur les cercles/lignes via `pygame.gfxdraw.aacircle` /
  `aapolygon`.
- Transition douce (easing) sur l'apparition du résultat d'un tir plutôt
  qu'un affichage instantané.

## Commandes

```bash
# installer les dépendances
uv sync

# lancer le jeu
uv run python -m orapa_mine.main

# lancer les tests
uv run pytest

# lancer les tests avec couverture
uv run pytest --cov=orapa_mine
```
