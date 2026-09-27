"""Grille de jeu : dimensions, placement des gemmes tangram, validation.

La grille maintient, en plus de la liste des gemmes posées, deux index de
cases (reconstruits à chaque placement) pour que la simulation du rayon reste
en O(1) par pas :

- `surface` : `Position` -> `HalfCell` (géométrie de la case),
- `owner`   : `Position` -> `PlacedGem` (à qui appartient la case).

Les cases sont **à propriétaire unique** : deux gemmes ne partagent jamais une
case (choix d'implémentation, voir docs/RULES.md — légèrement plus strict que
le jeu physique mais garantit des surfaces bien définies).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from orapa_mine.model.gems import HalfCell, PlacedGem, Position

# ✅ Confirmé par le vrai livret : grille 10x8. Reste configurable pour les
# variantes de difficulté.
DEFAULT_WIDTH = 10
DEFAULT_HEIGHT = 8


@dataclass
class Grid:
    """Grille contenant les gemmes cachées (de l'ordinateur, en solo)."""

    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    gems: list[PlacedGem] = field(default_factory=list)
    surface: dict[Position, HalfCell] = field(default_factory=dict)
    owner: dict[Position, PlacedGem] = field(default_factory=dict)

    def is_inside(self, position: Position) -> bool:
        """Vrai si `position` est une case valide de la grille."""
        return 0 <= position.row < self.height and 0 <= position.col < self.width

    def is_border(self, position: Position) -> bool:
        """Vrai si `position` est une case de bordure."""
        if not self.is_inside(position):
            return False
        return (
            position.row == 0
            or position.row == self.height - 1
            or position.col == 0
            or position.col == self.width - 1
        )

    def can_place(self, gem: PlacedGem) -> bool:
        """Vrai si toutes les cases de `gem` sont dans la grille et libres."""
        for position in gem.absolute_cells():
            if not self.is_inside(position) or position in self.surface:
                return False
        return True

    def place_gem(self, gem: PlacedGem) -> None:
        """Pose `gem` sur la grille en validant bornes et chevauchement.

        Lève `ValueError` si une case sort de la grille ou est déjà occupée.
        Les règles d'adjacence (d) et de gemme cachée (e) sont vérifiées côté
        `ai/generator.py`, pas ici.
        """
        cells = gem.absolute_cells()
        for position in cells:
            if not self.is_inside(position):
                raise ValueError(f"Case hors grille : {position}")
            if position in self.surface:
                raise ValueError(f"Case déjà occupée : {position}")
        self.gems.append(gem)
        for position, half in cells.items():
            self.surface[position] = half
            self.owner[position] = gem

    def remove_gem(self, gem: PlacedGem) -> None:
        """Retire `gem` de la grille (sans erreur si elle n'y est pas)."""
        if gem not in self.gems:
            return
        self.gems.remove(gem)
        for position in gem.absolute_cells():
            self.surface.pop(position, None)
            self.owner.pop(position, None)

    def gem_at(self, position: Position) -> PlacedGem | None:
        """Retourne la gemme occupant `position`, ou None."""
        return self.owner.get(position)
