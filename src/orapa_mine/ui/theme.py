"""Constantes visuelles et helpers de géométrie écran pour l'UI Pygame.

Aucune règle de jeu ici : uniquement couleurs, dimensions et conversions
case <-> pixel. Isolé pour garder `game_screen.py` lisible et pour pouvoir
retoucher le rendu en un seul endroit.
"""

from __future__ import annotations

import re

import pygame

from orapa_mine.model.gems import Direction, GemColor, GemKind, HalfCell, Position

# --- Dimensions (mise en page adaptative) -----------------------------------
#
# La taille des cases et la position du plateau sont recalculées par
# `configure()` en fonction de la grille ET de la taille de l'écran, pour que la
# fenêtre tienne toujours sur le moniteur. Les valeurs ci-dessous sont des
# défauts (remplacés dès le premier appel à `configure()` / `window_size()`).
# La palette des pièces est une bande **verticale à gauche** du plateau.

CELL = 72          # taille d'une case (px) — dynamique
CELL_MAX = 64      # cases jamais plus grandes (évite des tuiles absurdes)
CELL_MIN = 30      # cases jamais plus petites (grandes grilles / petits écrans)
BOARD_X = 180      # coin haut-gauche du plateau (dynamique)
BOARD_Y = 96

ENTRY_MARGIN = 46  # marge autour du plateau pour les points d'entrée
PANEL_WIDTH = 320  # panneau d'informations à droite
PANEL_MARGIN = 48  # espace entre le plateau et le panneau
PALETTE_WIDTH = 88  # largeur de la bande de palette (à gauche)

_PALETTE_GAP = 20   # espace entre la palette et le plateau
_SLOT_H = 74        # hauteur d'une case de palette (fixe, pour garder des icônes mesurées)
_SLOT_GAP = 8
_LEFT_GUTTER = 22
_RIGHT_GUTTER = 24
_TOP_SPACE = 96     # au-dessus du plateau (= BOARD_Y : titre + entrées du haut)
_BELOW_SPACE = 84   # sous le plateau (entrées du bas + ligne d'indices)
_PANEL_MIN_H = 470  # hauteur minimale du panneau (sinon son contenu déborde)
_SCREEN_MARGIN_W = 40   # marge écran (bords de fenêtre)
_SCREEN_MARGIN_H = 96   # marge écran (barre des tâches + barre de titre)
_FALLBACK_SCREEN = (1366, 768)

# Géométrie calculée par `configure()`.
PANEL = pygame.Rect(0, 0, PANEL_WIDTH, _PANEL_MIN_H)
PALETTE = pygame.Rect(0, 0, PALETTE_WIDTH, _PANEL_MIN_H)
WINDOW = (0, 0)


def board_bottom(rows: int) -> int:
    return BOARD_Y + rows * CELL


def available_screen() -> tuple[int, int]:
    """Taille d'écran utilisable (résolution du **bureau** moins les marges).

    On utilise `get_desktop_sizes()` et non `Info().current_w/h` : ce dernier
    renvoie le *mode vidéo courant* (donc la taille de la fenêtre déjà ouverte,
    p. ex. 760×660 pour le menu), ce qui rapetissait le plateau. Le bureau, lui,
    reste la vraie résolution du moniteur.
    """
    w = h = 0
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            w, h = sizes[0]
    except (pygame.error, AttributeError):
        pass
    if w <= 0 or h <= 0:  # repli : mode courant, puis valeur par défaut
        try:
            info = pygame.display.Info()
            w, h = int(info.current_w), int(info.current_h)
        except pygame.error:
            pass
    if w <= 0 or h <= 0:
        w, h = _FALLBACK_SCREEN
    return max(760, w - _SCREEN_MARGIN_W), max(560, h - _SCREEN_MARGIN_H)


def configure(cols: int, rows: int, panel_width: int | None = None) -> tuple[int, int]:
    """Recalcule la mise en page pour une grille `cols`×`rows` tenant à l'écran.

    Choisit la plus grande taille de case (≤ CELL_MAX) telle que plateau +
    palette (gauche) + panneau (droite) tiennent dans l'écran disponible, puis
    positionne le plateau, la palette et le panneau. `panel_width` permet à un
    écran (p. ex. le mode créateur) d'élargir son panneau ; la fenêtre s'ajuste.
    Renvoie la taille fenêtre.
    """
    global CELL, BOARD_X, BOARD_Y, PANEL, PALETTE, WINDOW
    pw = PANEL_WIDTH if panel_width is None else panel_width
    avail_w, avail_h = available_screen()
    pad = ENTRY_MARGIN  # place pour les points d'entrée de chaque côté

    fixed_w = (
        _LEFT_GUTTER + PALETTE_WIDTH + _PALETTE_GAP + pad
        + pad + PANEL_MARGIN + pw + _RIGHT_GUTTER
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

    PANEL = pygame.Rect(panel_x, BOARD_Y, pw, panel_h)
    PALETTE = pygame.Rect(_LEFT_GUTTER, BOARD_Y, PALETTE_WIDTH, panel_h)
    WINDOW = (panel_x + pw + _RIGHT_GUTTER, BOARD_Y + panel_h + _BELOW_SPACE)
    return WINDOW


def window_size(cols: int, rows: int, panel_width: int | None = None) -> tuple[int, int]:
    """Configure la mise en page pour `cols`×`rows` et renvoie la taille fenêtre."""
    return configure(cols, rows, panel_width)


def palette_slots(count: int) -> list[pygame.Rect]:
    """Rectangles des `count` cases de la palette, empilés verticalement à gauche.

    Les cases ont une hauteur fixe (`_SLOT_H`) pour rester mesurées quelle que
    soit la taille du plateau ; elles ne rétrécissent que si l'espace manque.
    """
    if count <= 0:
        return []
    pad = 6
    inner_h = PALETTE.height - 2 * pad
    slot_h = min(float(_SLOT_H), (inner_h - (count - 1) * _SLOT_GAP) / count)
    slot_w = PALETTE_WIDTH - 6
    rects: list[pygame.Rect] = []
    y = PALETTE.y + pad
    for _ in range(count):
        rects.append(pygame.Rect(PALETTE.x + 3, int(y), slot_w, int(slot_h)))
        y += slot_h + _SLOT_GAP
    return rects


# --- Couleurs (mode sombre / clair) ------------------------------------------
#
# Deux palettes complètes. `set_mode()` recopie l'une d'elles dans les variables
# de module (BACKGROUND, TEXT, GEM_FILL, …) : tout le code continue de lire
# `theme.X` et bascule en direct. Les gemmes ont des teintes adaptées pour
# rester visibles sur fond clair (notamment le blanc, posé sur un plateau gris
# bleuté) ; le corps noir et le trou de ver restent sombres dans les deux modes.

# Couleur de texte/éléments posés SUR l'accent doré (lisible dans les 2 modes).
ON_ACCENT = (26, 28, 36)

_DARK = {
    "BACKGROUND": (16, 18, 27),
    "BOARD_BG": (26, 30, 44),
    "BOARD_BORDER": (70, 80, 110),
    "GRID_LINE": (40, 46, 66),
    "TEXT": (222, 228, 240),
    "TEXT_DIM": (140, 150, 172),
    "ENTRY_IDLE": (58, 66, 92),
    "ENTRY_HOVER": (250, 214, 120),
    "PANEL_BG": (22, 25, 37),
    "SLOT_BG": (30, 34, 50),
    "SLOT_SELECTED": (250, 214, 120),
    "SLOT_USED": (40, 44, 58),
    "GHOST_OK": (120, 220, 150),
    "GHOST_BAD": (224, 96, 96),
    "INPUT_BG": (14, 16, 24),
    "INPUT_ACTIVE": (250, 214, 120),
    "WIN_COLOR": (120, 220, 150),
    "LOSE_COLOR": (232, 110, 110),
    "WORMHOLE_RING": (236, 238, 245),
    "RAY_TRANSPARENT": (170, 210, 235),
    "RAY_ABSORBED": (120, 120, 132),
    "GEM_FILL": {
        GemColor.RED: (206, 66, 68),
        GemColor.YELLOW: (232, 198, 72),
        GemColor.BLUE: (66, 122, 214),
        GemColor.WHITE: (232, 234, 240),
        GemKind.DIAMOND: (150, 205, 220),
        GemKind.BLACK_BODY: (8, 8, 12),
        GemKind.WORMHOLE: (14, 14, 22),
    },
    "RAY_COLORS": {
        "rouge": (224, 74, 74), "bleu": (74, 130, 224), "jaune": (238, 206, 82),
        "blanc": (238, 240, 246), "orange": (234, 146, 58), "vert": (78, 186, 104),
        "violet": (158, 96, 210), "rose": (238, 138, 180), "jaune clair": (240, 226, 150),
        "bleu clair": (150, 200, 238), "vert clair": (168, 222, 160),
        "orange clair": (242, 190, 138), "violet clair": (198, 162, 226),
        "noir": (44, 44, 54), "gris": (150, 156, 170),
    },
}

_LIGHT = {
    "BACKGROUND": (226, 230, 238),
    "BOARD_BG": (205, 212, 226),   # gris bleuté : le blanc des gemmes y ressort
    "BOARD_BORDER": (150, 160, 184),
    "GRID_LINE": (186, 194, 210),
    "TEXT": (30, 36, 52),
    "TEXT_DIM": (96, 106, 128),
    "ENTRY_IDLE": (182, 190, 208),
    "ENTRY_HOVER": (236, 176, 56),
    "PANEL_BG": (236, 239, 245),
    "SLOT_BG": (214, 220, 232),
    "SLOT_SELECTED": (238, 184, 60),
    "SLOT_USED": (196, 202, 216),
    "GHOST_OK": (64, 172, 104),
    "GHOST_BAD": (206, 74, 74),
    "INPUT_BG": (248, 249, 252),
    "INPUT_ACTIVE": (230, 168, 54),
    "WIN_COLOR": (36, 146, 86),
    "LOSE_COLOR": (198, 58, 58),
    "WORMHOLE_RING": (248, 249, 252),
    "RAY_TRANSPARENT": (72, 134, 190),
    "RAY_ABSORBED": (110, 110, 124),
    "GEM_FILL": {
        GemColor.RED: (202, 56, 58),
        GemColor.YELLOW: (222, 168, 32),
        GemColor.BLUE: (46, 104, 200),
        GemColor.WHITE: (250, 251, 254),
        GemKind.DIAMOND: (96, 170, 196),
        GemKind.BLACK_BODY: (22, 22, 30),   # reste « noir »
        GemKind.WORMHOLE: (22, 22, 30),
    },
    "RAY_COLORS": {
        "rouge": (210, 56, 56), "bleu": (48, 108, 206), "jaune": (208, 162, 24),
        "blanc": (120, 128, 146), "orange": (220, 126, 34), "vert": (44, 158, 80),
        "violet": (140, 76, 196), "rose": (222, 104, 158), "jaune clair": (190, 168, 60),
        "bleu clair": (92, 156, 206), "vert clair": (104, 176, 114),
        "orange clair": (222, 158, 92), "violet clair": (166, 126, 204),
        "noir": (40, 40, 52), "gris": (116, 122, 138),
    },
}

_PALETTES = {"dark": _DARK, "light": _LIGHT}
MODE = "dark"


def set_mode(mode: str) -> None:
    """Applique la palette « dark » ou « light » aux variables de module."""
    global MODE
    MODE = "light" if mode == "light" else "dark"
    globals().update(_PALETTES[MODE])


def toggle_mode() -> None:
    set_mode("light" if MODE == "dark" else "dark")


# Palette par défaut (mode sombre) appliquée dès l'import.
set_mode("dark")


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


# --- Étiquetage des cases (« Qu'y a-t-il en A1 ? ») --------------------------
#
# Une case est désignée par « ligne-lettre + colonne-numéro » (A1 = coin
# haut-gauche) : la lettre est la LIGNE (comme les bords gauche A–H), le chiffre
# la COLONNE (comme les bords haut 1–10). Ce format (lettre SUIVIE d'un chiffre)
# est volontairement distinct des libellés de bord — chiffre seul (1–18) ou
# lettre seule (A–R) — pour que les deux espaces de noms ne se recouvrent jamais.

_CELL_LABEL_RE = re.compile(r"([A-Z])([0-9]+)")


def cell_label(pos: Position) -> str:
    """Étiquette « ligne-lettre + colonne-numéro » d'une case (A1 = haut-gauche)."""
    return f"{chr(ord('A') + pos.row)}{pos.col + 1}"


def looks_like_cell_label(text: str) -> bool:
    """Vrai si `text` a la *forme* d'une étiquette de case (lettre + chiffres).

    Ne vérifie pas que la case est dans la grille (voir `parse_cell_label`) :
    sert à router la saisie vers une question de case plutôt qu'un tir de bord.
    """
    return _CELL_LABEL_RE.fullmatch(text.strip().upper()) is not None


def parse_cell_label(text: str, width: int, height: int) -> Position | None:
    """Convertit « A1 » (ligne-lettre + colonne-numéro) en `Position`.

    Renvoie None si le format ne correspond pas ou si la case est hors grille.
    """
    match = _CELL_LABEL_RE.fullmatch(text.strip().upper())
    if match is None:
        return None
    row = ord(match.group(1)) - ord("A")
    col = int(match.group(2)) - 1
    if 0 <= row < height and 0 <= col < width:
        return Position(row, col)
    return None
