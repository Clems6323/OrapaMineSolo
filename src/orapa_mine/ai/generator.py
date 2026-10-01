"""Génération aléatoire d'une grille cachée valide (rôle du « maître du jeu »).

C'est ici que vivent les **contraintes de placement** (docs/RULES.md,
section « Les gemmes ») :

- bornes de la grille et non-chevauchement (déléguées à `Grid`),
- règle d : deux gemmes ne peuvent pas être **côte à côte**. Dans notre
  discrétisation en cases, on l'applique de façon sûre en interdisant toute
  **adjacence orthogonale** entre cases de gemmes différentes (le contact par
  un coin — cases en diagonale — reste autorisé). Légèrement conservateur mais
  jamais illégal.
- règle e : aucune gemme **entièrement cachée** derrière une autre — chaque
  gemme doit avoir au moins une ligne de vue droite (haut/bas/gauche/droite)
  vers un bord, sans autre gemme sur le trajet.

Le placement sur une case de bordure est autorisé (règle c).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from orapa_mine.model.gems import Direction, Piece, PlacedGem, Position
from orapa_mine.model.grid import Grid
from orapa_mine.model import gems_catalog as cat

_MAX_ATTEMPTS = 5000
_DIRECTIONS = (Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT)


@dataclass
class Difficulty:
    """Paramètres de génération : quelles pièces, sur quelle grille.

    Utiliser les fabriques `base()` / `full()` ou construire une liste de
    pièces sur mesure (pour un écran de configuration de difficulté).
    """

    pieces: list[Piece] = field(default_factory=cat.base_set)
    width: int = 10
    height: int = 8
    name: str = "base"

    @staticmethod
    def base() -> Difficulty:
        """Version de base : 5 gemmes (1 R, 1 J, 1 B, 2 blanches)."""
        return Difficulty(pieces=cat.base_set(), name="base")

    @staticmethod
    def full() -> Difficulty:
        """Set complet : 7 pièces (base + Diamant + Corps noir)."""
        return Difficulty(pieces=cat.full_set(), name="complet")


def generate_hidden_grid(
    width: int | None = None,
    height: int | None = None,
    difficulty: Difficulty | None = None,
    rng: random.Random | None = None,
) -> Grid:
    """Génère une grille cachée valide selon `difficulty`.

    `rng` permet de rendre la génération déterministe (tests). Lève
    `RuntimeError` si aucun placement valide n'est trouvé après plusieurs
    milliers d'essais (ne devrait pas arriver avec les réglages par défaut).
    """
    difficulty = difficulty or Difficulty.base()
    grid_w = width if width is not None else difficulty.width
    grid_h = height if height is not None else difficulty.height
    rng = rng or random.Random()

    for _ in range(_MAX_ATTEMPTS):
        grid = Grid(width=grid_w, height=grid_h)
        if _try_fill(grid, difficulty.pieces, rng) and _all_gems_visible(grid):
            return grid
    raise RuntimeError(
        "Impossible de générer une grille valide : trop de pièces pour la grille ?"
    )


def _try_fill(grid: Grid, pieces: list[Piece], rng: random.Random) -> bool:
    """Tente de poser toutes les `pieces` (ordre aléatoire). True si réussi."""
    order = list(pieces)
    rng.shuffle(order)
    for piece in order:
        placement = _random_valid_placement(grid, piece, rng)
        if placement is None:
            return False
        grid.place_gem(placement)
    return True


def _random_valid_placement(
    grid: Grid, piece: Piece, rng: random.Random
) -> PlacedGem | None:
    """Choisit au hasard un placement valide de `piece`, ou None si aucun."""
    occupied = set(grid.surface)
    candidates: list[PlacedGem] = []
    for orientation in piece.orientations():
        max_row = max(p.row for p, _ in orientation)
        max_col = max(p.col for p, _ in orientation)
        for row in range(grid.height - max_row):
            for col in range(grid.width - max_col):
                gem = PlacedGem(piece=piece, anchor=Position(row, col), orientation=orientation)
                if grid.can_place(gem) and not _touches_orthogonally(gem, occupied):
                    candidates.append(gem)
    if not candidates:
        return None
    return rng.choice(candidates)


def _touches_orthogonally(gem: PlacedGem, occupied: set[Position]) -> bool:
    """Vrai si une case de `gem` est orthogonalement adjacente à `occupied`."""
    for cell in gem.absolute_cells():
        for direction in _DIRECTIONS:
            if (cell + direction) in occupied:
                return True
    return False


def _all_gems_visible(grid: Grid) -> bool:
    """Vrai si aucune gemme n'est entièrement cachée derrière une autre."""
    return all(_gem_visible(grid, gem) for gem in grid.gems)


# --- Validation d'une configuration existante (mode créateur) ----------------


def _gem_label(gem: PlacedGem) -> str:
    """Nom lisible d'une gemme posée (pour les messages de validation)."""
    return gem.color.value if gem.color is not None else gem.piece.name


def _shares_flat_face(grid: Grid, gem: PlacedGem) -> bool:
    """Vrai si `gem` touche une autre gemme par une **face plate** partagée.

    Contrairement à `_touches_orthogonally` (adjacence de cases, volontairement
    conservatrice pour la génération), on tient compte de la géométrie des
    demi-cases : deux triangles qui ne se rejoignent que par leur hypoténuse ou
    par un coin ne sont **pas** considérés côte à côte (contact autorisé).
    """
    own = gem.absolute_cells()
    for cell, half in own.items():
        for direction in _DIRECTIONS:
            neighbor = cell + direction
            if neighbor in own:
                continue
            other_half = grid.surface.get(neighbor)
            if other_half is None:
                continue
            # Face partagée pleine des deux côtés -> vrai contact « côte à côte ».
            if direction in half.flat_faces() and direction.reverse() in other_half.flat_faces():
                return True
    return False


def configuration_problems(grid: Grid) -> list[str]:
    """Liste les violations des règles de placement dans `grid`.

    Mêmes règles que le jeu : deux gemmes ne peuvent pas être côte à côte (face
    plate partagée ; le contact en diagonale ou par un coin reste autorisé) et
    aucune gemme n'est entièrement cachée. Retourne une liste vide si la
    configuration est valide. Logique pure et testable, pour le mode créateur.
    """
    problems: list[str] = []
    for gem in grid.gems:
        if _shares_flat_face(grid, gem):
            problems.append(f"La gemme {_gem_label(gem)} touche une autre gemme.")
    for gem in grid.gems:
        if not _gem_visible(grid, gem):
            problems.append(f"La gemme {_gem_label(gem)} est entièrement cachée.")
    return problems


def configuration_is_valid(grid: Grid) -> bool:
    """Vrai si `grid` respecte toutes les règles de placement."""
    return not configuration_problems(grid)


def _gem_visible(grid: Grid, gem: PlacedGem) -> bool:
    """Vrai si `gem` a au moins une ligne de vue droite vers un bord."""
    own_cells = set(gem.absolute_cells())
    blockers = set(grid.surface) - own_cells
    for cell in own_cells:
        for direction in _DIRECTIONS:
            position = cell
            clear = True
            while True:
                position = position + direction
                if not grid.is_inside(position):
                    break  # atteint le bord sans obstacle
                if position in blockers:
                    clear = False
                    break
            if clear:
                return True
    return False
