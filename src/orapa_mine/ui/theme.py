"""Constantes visuelles et helpers de géométrie écran pour l'UI Pygame.

Aucune règle de jeu ici : uniquement couleurs, dimensions et conversions
case <-> pixel. Isolé pour garder `game_screen.py` lisible et pour pouvoir
retoucher le rendu en un seul endroit.
"""

from __future__ import annotations

from orapa_mine.model.gems import Direction, GemColor, GemKind, HalfCell, Position

# --- Dimensions --------------------------------------------------------------

CELL = 64
ENTRY_MARGIN = 46  # marge autour du plateau pour les points d'entrée
BOARD_X = 60
BOARD_Y = 96
PANEL_MARGIN = 56  # espace entre le plateau et le panneau de droite
PANEL_WIDTH = 320
PALETTE_HEIGHT = 104  # bande de sélection des pièces sous le plateau


def board_bottom(rows: int) -> int:
    return BOARD_Y + rows * CELL


def palette_top(rows: int) -> int:
    return board_bottom(rows) + ENTRY_MARGIN + 26


def window_size(cols: int, rows: int) -> tuple[int, int]:
    """Taille de fenêtre pour une grille de `cols`×`rows`."""
    width = BOARD_X + cols * CELL + PANEL_MARGIN + PANEL_WIDTH + 40
    height = palette_top(rows) + PALETTE_HEIGHT + 20
    return width, height


# --- Couleurs ----------------------------------------------------------------

BACKGROUND = (16, 18, 27)
BOARD_BG = (26, 30, 44)
BOARD_BORDER = (70, 80, 110)
GRID_LINE = (40, 46, 66)
TEXT = (222, 228, 240)
TEXT_DIM = (140, 150, 172)
ENTRY_IDLE = (58, 66, 92)
ENTRY_HOVER = (250, 214, 120)
PANEL_BG = (22, 25, 37)
SLOT_BG = (30, 34, 50)
SLOT_SELECTED = (250, 214, 120)
SLOT_USED = (40, 44, 58)
GHOST_OK = (120, 220, 150)
GHOST_BAD = (224, 96, 96)
INPUT_BG = (14, 16, 24)
INPUT_ACTIVE = (250, 214, 120)
WIN_COLOR = (120, 220, 150)
LOSE_COLOR = (232, 110, 110)

# Couleurs des gemmes (remplissage) et de leur brillance.
GEM_FILL: dict[object, tuple[int, int, int]] = {
    GemColor.RED: (206, 66, 68),
    GemColor.YELLOW: (232, 198, 72),
    GemColor.BLUE: (66, 122, 214),
    GemColor.WHITE: (232, 234, 240),
    GemKind.DIAMOND: (150, 205, 220),
    GemKind.BLACK_BODY: (34, 34, 42),
}

# Couleur finale annoncée du rayon -> RGB, pour dessiner le rayon et l'historique.
RAY_COLORS: dict[str, tuple[int, int, int]] = {
    "rouge": (224, 74, 74),
    "bleu": (74, 130, 224),
    "jaune": (238, 206, 82),
    "blanc": (238, 240, 246),
    "orange": (234, 146, 58),
    "vert": (78, 186, 104),
    "violet": (158, 96, 210),
    "rose": (238, 138, 180),
    "jaune clair": (240, 226, 150),
    "bleu clair": (150, 200, 238),
    "vert clair": (168, 222, 160),
    "orange clair": (242, 190, 138),
    "violet clair": (198, 162, 226),
    "noir": (44, 44, 54),
    "gris": (150, 156, 170),
}
RAY_TRANSPARENT = (170, 210, 235)  # rayon sans couleur (aucune gemme touchée)
RAY_ABSORBED = (120, 120, 132)


def ray_rgb(color_name: str | None) -> tuple[int, int, int]:
    """RGB d'affichage pour une couleur de rayon (None = transparent)."""
    if color_name is None:
        return RAY_TRANSPARENT
    return RAY_COLORS.get(color_name, RAY_TRANSPARENT)


# --- Conversions case <-> pixel ---------------------------------------------


def cell_rect(pos: Position) -> tuple[int, int, int, int]:
    """Rectangle pixel (x, y, w, h) de la case `pos`."""
    return (BOARD_X + pos.col * CELL, BOARD_Y + pos.row * CELL, CELL, CELL)


def cell_center(pos: Position) -> tuple[float, float]:
    """Centre pixel de la case `pos`."""
    return (BOARD_X + pos.col * CELL + CELL / 2, BOARD_Y + pos.row * CELL + CELL / 2)


# Polygone (liste de coins) à remplir pour une demi-case donnée.
_HALF_POLY = {
    HalfCell.FULL: ("NW", "NE", "SE", "SW"),
    HalfCell.RA_NW: ("NW", "NE", "SW"),
    HalfCell.RA_NE: ("NW", "NE", "SE"),
    HalfCell.RA_SW: ("NW", "SW", "SE"),
    HalfCell.RA_SE: ("NE", "SE", "SW"),
}


def half_cell_polygon_at(
    pos: Position, half: HalfCell, origin_x: float, origin_y: float, size: float
) -> list[tuple[float, float]]:
    """Sommets pixel d'une demi-case, à une origine et une taille quelconques.

    Sert au plateau (origine = coin du plateau, `size=CELL`) comme aux icônes de
    la palette et à l'aperçu fantôme (origine et taille arbitraires).
    """
    x0 = origin_x + pos.col * size
    y0 = origin_y + pos.row * size
    x1, y1 = x0 + size, y0 + size
    corners = {"NW": (x0, y0), "NE": (x1, y0), "SE": (x1, y1), "SW": (x0, y1)}
    return [corners[name] for name in _HALF_POLY[half]]


def half_cell_polygon(pos: Position, half: HalfCell) -> list[tuple[float, float]]:
    """Sommets pixel d'une demi-case sur le plateau."""
    return half_cell_polygon_at(pos, half, BOARD_X, BOARD_Y, CELL)


# --- Étiquetage des bords (points d'entrée/sortie) ---------------------------
#
# Schéma confirmé avec l'utilisateur, cohérent avec le vrai plateau (1–18 /
# A–R) : chiffres en haut (1..larg) et à droite (larg+1..), lettres à gauche
# (A..) et en bas dans la continuité (…après la dernière lettre de gauche).

_ENTRY_EDGE = {
    Direction.DOWN: "top",
    Direction.UP: "bottom",
    Direction.RIGHT: "left",
    Direction.LEFT: "right",
}
_EXIT_EDGE = {
    Direction.UP: "top",
    Direction.DOWN: "bottom",
    Direction.LEFT: "left",
    Direction.RIGHT: "right",
}


def _edge_label(edge: str, row: int, col: int, width: int, height: int) -> str:
    if edge == "top":
        return str(col + 1)
    if edge == "right":
        return str(width + row + 1)
    if edge == "left":
        return chr(ord("A") + row)
    return chr(ord("A") + height + col)  # bottom : continue les lettres


def entry_label(pos: Position, direction: Direction, width: int, height: int) -> str:
    """Étiquette du point d'entrée (bord opposé au sens de trajet)."""
    return _edge_label(_ENTRY_EDGE[direction], pos.row, pos.col, width, height)


def exit_label(pos: Position, direction: Direction, width: int, height: int) -> str:
    """Étiquette du point de sortie (bord dans le sens de trajet)."""
    return _edge_label(_EXIT_EDGE[direction], pos.row, pos.col, width, height)
