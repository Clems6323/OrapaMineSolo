"""Constantes visuelles et helpers de géométrie écran pour l'UI Pygame.

Aucune règle de jeu ici : uniquement couleurs, dimensions et conversions
case <-> pixel. Isolé pour garder `game_screen.py` lisible et pour pouvoir
retoucher le rendu en un seul endroit.
"""

from __future__ import annotations

import pygame

from orapa_mine.model.gems import Direction, GemColor, GemKind, HalfCell, Position

# --- Dimensions (mise en page adaptative) -----------------------------------
#
# La taille des cases et la position du plateau sont recalculées par
# `configure()` en fonction de la grille ET de la taille de l'écran, pour que la
# fenêtre tienne toujours sur le moniteur. Les valeurs ci-dessous sont des
# défauts (remplacés dès le premier appel à `configure()` / `window_size()`).
# La palette des pièces est une bande **verticale à gauche** du plateau.

CELL = 64          # taille d'une case (px) — dynamique
CELL_MAX = 64      # cases jamais plus grandes (petites grilles)
CELL_MIN = 30      # cases jamais plus petites (grandes grilles / petits écrans)
BOARD_X = 184      # coin haut-gauche du plateau (dynamique)
BOARD_Y = 96

ENTRY_MARGIN = 46  # marge autour du plateau pour les points d'entrée
PANEL_WIDTH = 320  # panneau d'informations à droite
PANEL_MARGIN = 48  # espace entre le plateau et le panneau
PALETTE_WIDTH = 96  # largeur de la bande de palette (à gauche)

_PALETTE_GAP = 20   # espace entre la palette et le plateau
_LEFT_GUTTER = 22
_RIGHT_GUTTER = 24
_TOP_SPACE = 96     # au-dessus du plateau (= BOARD_Y : titre + entrées du haut)
_BELOW_SPACE = 80   # sous le plateau (entrées du bas + ligne d'indices)
_PANEL_MIN_H = 430  # hauteur minimale du panneau (sinon son contenu déborde)
_SCREEN_MARGIN_W = 48   # marge écran (bords de fenêtre)
_SCREEN_MARGIN_H = 120  # marge écran (barre des tâches + barre de titre)
_FALLBACK_SCREEN = (1366, 768)

# Géométrie calculée par `configure()`.
PANEL = pygame.Rect(0, 0, PANEL_WIDTH, _PANEL_MIN_H)
PALETTE = pygame.Rect(0, 0, PALETTE_WIDTH, _PANEL_MIN_H)
WINDOW = (0, 0)


def board_bottom(rows: int) -> int:
    return BOARD_Y + rows * CELL


def available_screen() -> tuple[int, int]:
    """Taille d'écran utilisable (résolution du bureau moins les marges)."""
    try:
        info = pygame.display.Info()
        w, h = int(info.current_w), int(info.current_h)
        if w <= 0 or h <= 0:
            raise ValueError
    except (pygame.error, ValueError):
        w, h = _FALLBACK_SCREEN
    return max(760, w - _SCREEN_MARGIN_W), max(560, h - _SCREEN_MARGIN_H)


def configure(cols: int, rows: int) -> tuple[int, int]:
    """Recalcule la mise en page pour une grille `cols`×`rows` tenant à l'écran.

    Choisit la plus grande taille de case (≤ CELL_MAX) telle que plateau +
    palette (gauche) + panneau (droite) tiennent dans l'écran disponible, puis
    positionne le plateau, la palette et le panneau. Renvoie la taille fenêtre.
    """
    global CELL, BOARD_X, BOARD_Y, PANEL, PALETTE, WINDOW
    avail_w, avail_h = available_screen()
    pad = ENTRY_MARGIN  # place pour les points d'entrée de chaque côté

    fixed_w = (
        _LEFT_GUTTER + PALETTE_WIDTH + _PALETTE_GAP + pad
        + pad + PANEL_MARGIN + PANEL_WIDTH + _RIGHT_GUTTER
    )
    fixed_h = _TOP_SPACE + _BELOW_SPACE
    cell_w = (avail_w - fixed_w) / cols if cols else CELL_MAX
    cell_h = (avail_h - fixed_h) / rows if rows else CELL_MAX
    CELL = int(max(CELL_MIN, min(CELL_MAX, cell_w, cell_h)))

    BOARD_Y = _TOP_SPACE
    BOARD_X = _LEFT_GUTTER + PALETTE_WIDTH + _PALETTE_GAP + pad
    board_w, board_h = cols * CELL, rows * CELL
    panel_h = max(board_h, _PANEL_MIN_H)
    panel_x = BOARD_X + board_w + pad + PANEL_MARGIN

    PANEL = pygame.Rect(panel_x, BOARD_Y, PANEL_WIDTH, panel_h)
    PALETTE = pygame.Rect(_LEFT_GUTTER, BOARD_Y, PALETTE_WIDTH, panel_h)
    WINDOW = (panel_x + PANEL_WIDTH + _RIGHT_GUTTER, BOARD_Y + panel_h + _BELOW_SPACE)
    return WINDOW


def window_size(cols: int, rows: int) -> tuple[int, int]:
    """Configure la mise en page pour `cols`×`rows` et renvoie la taille fenêtre."""
    return configure(cols, rows)


def palette_slots(count: int) -> list[pygame.Rect]:
    """Rectangles des `count` cases de la palette, empilés verticalement à gauche."""
    if count <= 0:
        return []
    pad, gap = 8, 8
    inner_h = PALETTE.height - 2 * pad
    slot_h = min(float(PALETTE_WIDTH), (inner_h - (count - 1) * gap) / count)
    slot_w = PALETTE_WIDTH - 6
    rects: list[pygame.Rect] = []
    y = PALETTE.y + pad
    for _ in range(count):
        rects.append(pygame.Rect(PALETTE.x + 3, int(y), slot_w, int(slot_h)))
        y += slot_h + gap
    return rects


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


def point_px(row: float, col: float) -> tuple[float, float]:
    """Pixel d'un point en coordonnées de case flottantes (ligne, colonne)."""
    return (BOARD_X + col * CELL + CELL / 2, BOARD_Y + row * CELL + CELL / 2)


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
