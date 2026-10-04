"""Catalogue des 7 pièces réelles d'Orapa Mine (empreintes exactes).

⚠️ **C'est LE fichier à corriger** si les formes physiques diffèrent : tout le
reste du modèle en dépend. Les formes ci-dessous ont été confirmées par
l'utilisateur à partir des pièces physiques (voir docs/tangram_pictures.jpeg
et l'échange dans docs/RULES.md) :

- Rouge     : parallélogramme, aire 2, côtés longs plats, bouts à 45°.
              Retournement autorisé -> ses 2 chiralités sont jouables.
- Bleu      : triangle isocèle base 4 / hauteur 2, aire 4.
- Blanc #1  : identique au bleu.
- Jaune     : triangle rectangle isocèle, cathètes de 2 cases, aire 2.
- Blanc #2  : carré tourné à 45° (losange, boîte 2×2), aire 2 ; 4 arêtes à
              45°, aucune face plate.
- Diamant   : petit triangle base 2 / hauteur 1, aire 1 (dévie sans teinter).
- Corps noir: rectangle plein 1×2, aire 2 (absorbe le rayon).

Chaque pièce est donnée par le **polygone de son contour** (sommets sur les
coins de la grille, en `(colonne, ligne)`, origine haut-gauche, ligne vers le
bas), puis rastérisée en demi-cases. Les slopes sont toutes à 45°, donc le
contour ne passe que par des coins entiers : la rastérisation par coins est
exacte.
"""

from __future__ import annotations

from orapa_mine.model.gems import (
    GemColor,
    GemKind,
    HalfCell,
    Piece,
    Position,
)

# Coin manquant (quand 3 coins sur 4 sont dans la pièce) -> coin de l'angle
# droit du triangle plein (le coin diagonalement opposé au coin vide).
_OPPOSITE_CORNER = {"NW": "SE", "SE": "NW", "NE": "SW", "SW": "NE"}
_RA_BY_CORNER = {
    "NW": HalfCell.RA_NW,
    "NE": HalfCell.RA_NE,
    "SW": HalfCell.RA_SW,
    "SE": HalfCell.RA_SE,
}


def _inside(polygon: list[tuple[int, int]], point: tuple[int, int]) -> bool:
    """Vrai si `point` est à l'intérieur ou sur le bord du polygone convexe.

    Test par produit vectoriel de chaque arête ; arithmétique entière donc
    exacte. Indépendant du sens de parcours du polygone.
    """
    sign = 0
    n = len(polygon)
    px, py = point
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if cross != 0:
            s = 1 if cross > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
    return True


def _rasterize(polygon: list[tuple[int, int]]) -> frozenset[tuple[Position, HalfCell]]:
    """Décompose un contour en demi-cases (`Position` offset -> `HalfCell`)."""
    cols = [x for x, _ in polygon]
    rows = [y for _, y in polygon]
    cells: set[tuple[Position, HalfCell]] = set()
    for r in range(min(rows), max(rows)):
        for c in range(min(cols), max(cols)):
            corners = {
                "NW": (c, r),
                "NE": (c + 1, r),
                "SE": (c + 1, r + 1),
                "SW": (c, r + 1),
            }
            inside = {name for name, pt in corners.items() if _inside(polygon, pt)}
            hc = _classify(inside)
            if hc is not None:
                cells.add((Position(r, c), hc))
    return frozenset(cells)


def _classify(inside: set[str]) -> HalfCell | None:
    """Traduit l'ensemble des coins « dedans » en géométrie de demi-case."""
    if len(inside) == 4:
        return HalfCell.FULL
    if len(inside) == 3:
        (missing,) = {"NW", "NE", "SE", "SW"} - inside
        return _RA_BY_CORNER[_OPPOSITE_CORNER[missing]]
    return None  # 0/1/2 coins : pas d'aire pleine dans cette case


def _piece(
    name: str,
    color: GemColor | None,
    kind: GemKind,
    polygon: list[tuple[int, int]],
) -> Piece:
    return Piece(name=name, color=color, kind=kind, cells=_rasterize(polygon))


# --- Les 7 pièces (orientation canonique) ------------------------------------

RED = _piece("rouge", GemColor.RED, GemKind.NORMAL, [(0, 1), (2, 1), (3, 0), (1, 0)])
BLUE = _piece("bleu", GemColor.BLUE, GemKind.NORMAL, [(0, 2), (4, 2), (2, 0)])
WHITE_BIG = _piece("blanc-grand", GemColor.WHITE, GemKind.NORMAL, [(0, 2), (4, 2), (2, 0)])
YELLOW = _piece("jaune", GemColor.YELLOW, GemKind.NORMAL, [(0, 0), (2, 0), (0, 2)])
WHITE_SMALL = _piece(
    "blanc-petit", GemColor.WHITE, GemKind.NORMAL, [(0, 1), (1, 2), (2, 1), (1, 0)]
)
DIAMOND = _piece("diamant", None, GemKind.DIAMOND, [(0, 1), (2, 1), (1, 0)])
BLACK_BODY = _piece(
    "corps-noir", None, GemKind.BLACK_BODY, [(0, 0), (2, 0), (2, 1), (0, 1)]
)
# Trou de ver (extension) : une case pleine 1×1, posée par paire (quantity=2).
# Un rayon entrant dans un trou ressort de l'autre dans la même direction.
WORMHOLE = Piece(
    name="trou-de-ver",
    color=None,
    kind=GemKind.WORMHOLE,
    cells=_rasterize([(0, 0), (1, 0), (1, 1), (0, 1)]),
    quantity=2,
)


def base_set() -> list[Piece]:
    """Les 5 pièces de la version de base : 1 R, 1 J, 1 B, 2 blanches."""
    return [RED, YELLOW, BLUE, WHITE_BIG, WHITE_SMALL]


def full_set() -> list[Piece]:
    """Les 7 pièces (base + Diamant + Corps noir)."""
    return base_set() + [DIAMOND, BLACK_BODY]


ALL_PIECES: dict[str, Piece] = {
    p.name: p
    for p in (RED, BLUE, WHITE_BIG, YELLOW, WHITE_SMALL, DIAMOND, BLACK_BODY, WORMHOLE)
}
