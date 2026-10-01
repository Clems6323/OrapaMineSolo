"""Objets de valeur et primitives géométriques du jeu.

Modèle **tangram fidèle** (confirmé par le vrai livret, voir docs/RULES.md) :
les gemmes sont des pièces géométriques (triangles rectangles,
parallélogrammes) dont les arêtes servent de miroir. Pour simuler le rayon on
décompose chaque pièce en **demi-cases** (`HalfCell`) : une case peut être
pleine (`FULL`) ou coupée par une diagonale à 45° en un triangle rectangle
occupant un coin (`RA_NW`, `RA_NE`, `RA_SW`, `RA_SE`, d'après le coin où se
trouve l'angle droit).

La réflexion du rayon se calcule ici (`HalfCell.reflect`) pour rester une seule
source de vérité, indépendante de l'UI (aucun import pygame).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GemColor(Enum):
    """Couleurs de base des gemmes."""

    RED = "rouge"
    BLUE = "bleu"
    YELLOW = "jaune"
    WHITE = "blanc"


class GemKind(Enum):
    """Nature de la gemme, qui détermine son effet sur la couleur du rayon.

    - NORMAL : gemme colorée classique (teinte le rayon).
    - DIAMOND : extension. Dévie comme une gemme normale mais ne teinte jamais.
    - BLACK_BODY : extension. Absorbe le rayon (aucune sortie).
    """

    NORMAL = "normal"
    DIAMOND = "diamond"
    BLACK_BODY = "black_body"


@dataclass(frozen=True)
class Position:
    """Coordonnée de case sur la grille (0-indexée, ligne vers le bas)."""

    row: int
    col: int

    def __add__(self, direction: Direction) -> Position:
        drow, dcol = direction.value
        return Position(self.row + drow, self.col + dcol)

    def __sub__(self, direction: Direction) -> Position:
        drow, dcol = direction.value
        return Position(self.row - drow, self.col - dcol)


class Direction(Enum):
    """Direction de déplacement du rayon (delta ligne, delta colonne)."""

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    def reverse(self) -> Direction:
        return _REVERSE[self]


_REVERSE: dict[Direction, Direction] = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

# Déviation sur une arête diagonale à 45°, exprimée en direction de trajet.
# '/'  (miroir anti-slash visuel inverse) : DROITE<->HAUT, GAUCHE<->BAS.
# '\\' : DROITE<->BAS, GAUCHE<->HAUT.
_DEFLECT_SLASH: dict[Direction, Direction] = {
    Direction.RIGHT: Direction.UP,
    Direction.UP: Direction.RIGHT,
    Direction.LEFT: Direction.DOWN,
    Direction.DOWN: Direction.LEFT,
}
_DEFLECT_BACKSLASH: dict[Direction, Direction] = {
    Direction.RIGHT: Direction.DOWN,
    Direction.DOWN: Direction.RIGHT,
    Direction.LEFT: Direction.UP,
    Direction.UP: Direction.LEFT,
}


class HalfCell(Enum):
    """Contenu géométrique d'une case occupée par une gemme.

    `FULL` : case pleine (4 faces plates). Les `RA_*` sont des triangles
    rectangles occupant un coin de la case, nommés d'après le coin de l'angle
    droit (NW = haut-gauche, NE = haut-droit, SW = bas-gauche, SE = bas-droit).
    L'hypoténuse (à 45°) est le miroir ; les deux cathètes sont des faces
    plates (renvoi à 180°).
    """

    FULL = "full"
    RA_NW = "ra_nw"
    RA_NE = "ra_ne"
    RA_SW = "ra_sw"
    RA_SE = "ra_se"

    def reflect(self, incoming: Direction) -> Direction:
        """Direction de sortie du rayon entrant dans cette demi-case.

        Renvoi à 180° si le rayon frappe une face plate (cathète ou face d'une
        case pleine), sinon déviation à 90° sur l'hypoténuse.
        """
        if incoming in _BOUNCE_DIRS[self]:
            return incoming.reverse()
        if self in (HalfCell.RA_NW, HalfCell.RA_SE):
            return _DEFLECT_SLASH[incoming]
        return _DEFLECT_BACKSLASH[incoming]

    def flat_faces(self) -> frozenset[Direction]:
        """Côtés de la case entièrement pleins (faces plates à 180°).

        Une face est « pleine » quand toute l'arête de la case est de la
        matière (face d'une case pleine, ou cathète d'un triangle rectangle).
        Les côtés absents correspondent à l'hypoténuse (contact en diagonale) ou
        à un simple coin. Utilisé pour détecter un vrai contact « côte à côte »
        entre gemmes, par opposition à un contact ponctuel autorisé.
        """
        return _FLAT_FACES[self]

    def rotated_cw(self) -> HalfCell:
        """La même demi-case après rotation de 90° dans le sens horaire."""
        return _ROTATE_CW[self]

    def mirrored_h(self) -> HalfCell:
        """La même demi-case après symétrie horizontale (gauche <-> droite)."""
        return _MIRROR_H[self]


# Directions de trajet qui frappent une **face plate** de la demi-case (donc
# renvoi à 180°). Déduit des cathètes : une case pleine renvoie toujours ;
# sinon selon le coin de l'angle droit.
_BOUNCE_DIRS: dict[HalfCell, frozenset[Direction]] = {
    HalfCell.FULL: frozenset(
        {Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT}
    ),
    HalfCell.RA_NW: frozenset({Direction.DOWN, Direction.RIGHT}),
    HalfCell.RA_NE: frozenset({Direction.DOWN, Direction.LEFT}),
    HalfCell.RA_SW: frozenset({Direction.UP, Direction.RIGHT}),
    HalfCell.RA_SE: frozenset({Direction.UP, Direction.LEFT}),
}

# Côtés pleins de chaque demi-case (une arête complète de matière). Un rayon qui
# frappe cette face rebondit à 180° ; c'est le côté par lequel deux gemmes se
# touchent vraiment « côte à côte ». Déduit de `_BOUNCE_DIRS` : la face frappée
# est à l'opposé du sens de trajet du rayon.
_FLAT_FACES: dict[HalfCell, frozenset[Direction]] = {
    half: frozenset(travel.reverse() for travel in bounces)
    for half, bounces in _BOUNCE_DIRS.items()
}

# Rotation horaire des coins : NW -> NE -> SE -> SW -> NW.
_ROTATE_CW: dict[HalfCell, HalfCell] = {
    HalfCell.FULL: HalfCell.FULL,
    HalfCell.RA_NW: HalfCell.RA_NE,
    HalfCell.RA_NE: HalfCell.RA_SE,
    HalfCell.RA_SE: HalfCell.RA_SW,
    HalfCell.RA_SW: HalfCell.RA_NW,
}

# Symétrie horizontale (gauche <-> droite) : NW <-> NE, SW <-> SE.
_MIRROR_H: dict[HalfCell, HalfCell] = {
    HalfCell.FULL: HalfCell.FULL,
    HalfCell.RA_NW: HalfCell.RA_NE,
    HalfCell.RA_NE: HalfCell.RA_NW,
    HalfCell.RA_SW: HalfCell.RA_SE,
    HalfCell.RA_SE: HalfCell.RA_SW,
}


@dataclass(frozen=True)
class Piece:
    """Définition canonique d'une pièce (indépendante de son placement).

    `cells` associe des offsets de case (ancrés au coin haut-gauche de la boîte
    englobante, min row/col = 0) à leur géométrie `HalfCell`.
    """

    name: str
    color: GemColor | None
    kind: GemKind
    cells: frozenset[tuple[Position, HalfCell]]

    def orientations(self) -> list[frozenset[tuple[Position, HalfCell]]]:
        """Empreintes distinctes obtenues par rotations **et retournements**.

        Le retournement (symétrie) est autorisé (confirmé par l'utilisateur) :
        seul le parallélogramme rouge y gagne de nouvelles orientations, les
        autres pièces étant symétriques. Groupe diédral -> jusqu'à 8 empreintes,
        dédoublonnées.
        """
        result: list[frozenset[tuple[Position, HalfCell]]] = []
        for base in (set(self.cells), _mirror_h(self.cells)):
            current = base
            for _ in range(4):
                normalized = _normalize(current)
                if normalized not in result:
                    result.append(normalized)
                current = {
                    (_rotate_cell_cw(p, current), hc.rotated_cw()) for p, hc in current
                }
        return result

    def at(self, anchor: Position, orientation_index: int = 0) -> PlacedGem:
        """Fabrique une `PlacedGem` ancrée en `anchor` dans une orientation."""
        return PlacedGem(
            piece=self,
            anchor=anchor,
            orientation=self.orientations()[orientation_index],
        )


def _rotate_cell_cw(
    pos: Position, cells: set[tuple[Position, HalfCell]]
) -> Position:
    """Rotation horaire d'une case dans la boîte englobante du groupe `cells`."""
    max_row = max(p.row for p, _ in cells)
    # (r, c) -> (c, max_row - r) pour une rotation horaire de 90°.
    return Position(pos.col, max_row - pos.row)


def _normalize(
    cells: set[tuple[Position, HalfCell]]
) -> frozenset[tuple[Position, HalfCell]]:
    """Recolle l'empreinte contre l'origine (min row/col = 0)."""
    min_row = min(p.row for p, _ in cells)
    min_col = min(p.col for p, _ in cells)
    return frozenset(
        (Position(p.row - min_row, p.col - min_col), hc) for p, hc in cells
    )


def _mirror_h(cells: frozenset[tuple[Position, HalfCell]]) -> set[tuple[Position, HalfCell]]:
    """Symétrie horizontale (miroir gauche/droite) d'une empreinte."""
    max_col = max(p.col for p, _ in cells)
    return {
        (Position(p.row, max_col - p.col), hc.mirrored_h()) for p, hc in cells
    }


@dataclass(frozen=True)
class PlacedGem:
    """Une pièce posée sur la grille : géométrie absolue + métadonnées."""

    piece: Piece
    anchor: Position
    orientation: frozenset[tuple[Position, HalfCell]]

    @property
    def color(self) -> GemColor | None:
        return self.piece.color

    @property
    def kind(self) -> GemKind:
        return self.piece.kind

    def absolute_cells(self) -> dict[Position, HalfCell]:
        """Cases occupées, en coordonnées absolues sur la grille."""
        return {
            Position(self.anchor.row + p.row, self.anchor.col + p.col): hc
            for p, hc in self.orientation
        }
