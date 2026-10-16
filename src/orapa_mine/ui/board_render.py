"""Dessin partagé du plateau et des gemmes (utilisé par plusieurs écrans).

Aucune règle de jeu : uniquement du rendu. Isolé ici pour éviter la
duplication entre l'écran de jeu et l'écran de fin.
"""

from __future__ import annotations

import math

import pygame

from orapa_mine.model.gems import GemKind, HalfCell, Piece
from orapa_mine.model.grid import Grid
from orapa_mine.ui import i18n, theme


def piece_color(piece: Piece) -> tuple[int, int, int]:
    key = piece.color if piece.kind is GemKind.NORMAL else piece.kind
    return theme.GEM_FILL[key]


def faded_piece_color(piece: Piece) -> tuple[int, int, int]:
    """Couleur « posée/utilisée » d'une pièce dans la palette.

    On désature vers le gris puis on assombrit : une pièce posée a l'air
    « désactivée » plutôt que colorée en plus terne — ce qui évite notamment
    qu'un diamant posé ressemble au filtre (même teinte translucide) (#66).
    Le corps noir (déjà quasi noir) est au contraire éclairci en gris foncé,
    sinon son état « posé » serait invisible.
    """
    if piece.kind is GemKind.BLACK_BODY:
        return (72, 72, 82)
    return faded_color(piece_color(piece))


def faded_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Version « désactivée » d'une couleur : désaturée vers le gris puis assombrie."""
    r, g, b = rgb
    lum = int(0.299 * r + 0.587 * g + 0.114 * b)
    mix = 0.78  # part de gris (désaturation)
    grey = (
        int(r * (1 - mix) + lum * mix),
        int(g * (1 - mix) + lum * mix),
        int(b * (1 - mix) + lum * mix),
    )
    return darken(grey, 0.35)


def lighten(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(min(255, int(c + (255 - c) * amount)) for c in color)  # type: ignore[return-value]


def darken(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(max(0, int(c * (1 - amount))) for c in color)  # type: ignore[return-value]


def _eye_params(polys: list) -> tuple[tuple[float, float], float, bool]:
    """Centre, taille et orientation de l'œil à partir des polygones de la gemme.

    L'œil suit l'orientation de la pièce : il est **vertical** quand l'empreinte
    est plus haute que large (triangle pointant à gauche/droite), horizontal
    sinon. Sa taille est bornée par la plus petite dimension pour rester à
    l'intérieur quelle que soit la rotation (#77 suivi).
    """
    pts = [pt for poly in polys for pt in poly]
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    short = min(span_x, span_y)
    return (cx, cy), short, span_y > span_x


def draw_eye(
    surface: pygame.Surface, center: tuple[float, float], extent: float,
    *, vertical: bool = False, faded: bool = False,
) -> None:
    """Dessine un petit œil (symbole de la gemme mystère) centré sur `center`.

    `extent` = plus petite dimension de la gemme ; l'œil (plus petit qu'avant)
    s'inscrit dedans et pivote de 90° quand `vertical` est vrai.
    """
    cx, cy = int(center[0]), int(center[1])
    length = max(6, int(extent * 0.78))   # grand axe (un peu plus petit qu'avant)
    thick = max(4, int(extent * 0.46))    # petit axe
    w, h = (thick, length) if vertical else (length, thick)
    white = (208, 210, 220) if faded else (240, 242, 248)
    dark = (72, 74, 84) if faded else (26, 28, 36)
    rect = pygame.Rect(0, 0, w, h)
    rect.center = (cx, cy)
    pygame.draw.ellipse(surface, white, rect)
    pygame.draw.ellipse(surface, dark, rect, width=max(1, int(min(w, h) * 0.12)))
    pupil = max(2, int(thick * 0.4))
    pygame.draw.circle(surface, dark, (cx, cy), pupil)
    glint = max(1, int(pupil * 0.4))
    pygame.draw.circle(surface, white, (cx - glint, cy - glint), glint)


def draw_board(surface: pygame.Surface, grid: Grid) -> None:
    """Dessine le fond du plateau, la grille et son cadre."""
    w, h = grid.width, grid.height
    rect = pygame.Rect(theme.BOARD_X, theme.BOARD_Y, w * theme.CELL, h * theme.CELL)
    pygame.draw.rect(surface, theme.BOARD_BG, rect, border_radius=6)
    for col in range(w + 1):
        x = theme.BOARD_X + col * theme.CELL
        pygame.draw.line(surface, theme.GRID_LINE, (x, theme.BOARD_Y), (x, theme.board_bottom(h)))
    for row in range(h + 1):
        y = theme.BOARD_Y + row * theme.CELL
        pygame.draw.line(surface, theme.GRID_LINE, (theme.BOARD_X, y), (theme.BOARD_X + w * theme.CELL, y))
    pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=2, border_radius=6)


def draw_wormhole(
    surface: pygame.Surface,
    center: tuple[float, float],
    size: float,
    square_color: tuple[int, int, int] | None = None,
    spiral_color: tuple[int, int, int] | None = None,
) -> None:
    """Dessine un trou de ver : un carré noir (comme le corps noir) + spirale blanche."""
    # Résolu à l'appel (et non à la définition) pour suivre le mode sombre/clair.
    if square_color is None:
        square_color = theme.GEM_FILL[GemKind.BLACK_BODY]
    if spiral_color is None:
        spiral_color = theme.WORMHOLE_RING
    cx, cy = center
    side = max(4, int(size))
    rect = pygame.Rect(0, 0, side, side)
    rect.center = (int(cx), int(cy))
    pygame.draw.rect(surface, square_color, rect)

    # Spirale d'Archimède partant du centre vers l'extérieur (le « tourbillon »).
    turns = 2.6
    max_r = size * 0.36
    steps = max(24, int(turns * 24))
    points = [
        (
            cx + max_r * (i / steps) * math.cos(turns * 2 * math.pi * (i / steps)),
            cy + max_r * (i / steps) * math.sin(turns * 2 * math.pi * (i / steps)),
        )
        for i in range(steps + 1)
    ]
    width = max(1, int(size * 0.055))
    if len(points) >= 2:
        pygame.draw.lines(surface, spiral_color, False, points, width)


def draw_palette_slot(
    surface: pygame.Surface,
    rect: pygame.Rect,
    piece: Piece,
    *,
    selected: bool,
    placed: int,
    font: pygame.font.Font,
    override_color=None,
) -> None:
    """Dessine une case de palette (fond, bordure, icône, badge de quantité).

    `placed` = nombre d'exemplaires déjà posés ; la case est grisée quand tous
    le sont, et un badge « ×N » affiche le reste à poser (pièces en plusieurs
    exemplaires, p. ex. le trou de ver). `override_color` ne sert qu'à la gemme
    mystère : il teinte son icône de la couleur en cours de sélection ([C]).
    """
    used = placed >= piece.quantity
    bg = theme.SLOT_USED if used else theme.SLOT_BG
    pygame.draw.rect(surface, bg, rect, border_radius=6)
    border = theme.SLOT_SELECTED if selected else theme.BOARD_BORDER
    pygame.draw.rect(surface, border, rect, width=2 if selected else 1, border_radius=6)
    _draw_slot_icon(surface, rect, piece, faded=used, font=font, override_color=override_color)
    if piece.quantity > 1 and not used:
        # Pastille de quantité dans le coin haut-gauche (hors de l'icône et du
        # nom), sur un fond contrasté pour rester lisible, y compris sur le trou
        # de ver noir (#66).
        text = font.render(f"×{piece.quantity - placed}", True, theme.TEXT)
        pad = theme.s(3)
        pill = pygame.Rect(
            rect.left + theme.s(4), rect.top + theme.s(4),
            text.get_width() + 2 * pad, text.get_height() + pad,
        )
        pygame.draw.rect(surface, theme.SLOT_USED, pill, border_radius=theme.s(5))
        surface.blit(text, (pill.x + pad, pill.y + pad // 2))


def _draw_slot_icon(
    surface: pygame.Surface, rect: pygame.Rect, piece: Piece, faded: bool,
    font: pygame.font.Font, override_color=None,
) -> None:
    # Bande réservée au nom, sous l'icône, dimensionnée au texte réel pour que
    # l'icône ne déborde jamais sur le libellé — quelle que soit la langue (#66).
    top_pad = theme.s(8)
    label_h = font.get_height() + theme.s(8)
    icon_w = rect.width - theme.s(16)
    icon_h = rect.height - top_pad - label_h
    if piece.kind is GemKind.WORMHOLE:
        size = min(icon_w, icon_h)
        center = (rect.centerx, rect.top + top_pad + size / 2)
        square = (72, 72, 82) if faded else theme.GEM_FILL[GemKind.BLACK_BODY]
        spiral = theme.TEXT_DIM if faded else theme.WORMHOLE_RING
        draw_wormhole(surface, center, size, square_color=square, spiral_color=spiral)
    else:
        cells = piece.cells
        rows = max(p.row for p, _ in cells) + 1
        cols = max(p.col for p, _ in cells) + 1
        cell_size = min(icon_w / cols, icon_h / rows)
        ox = rect.centerx - cols * cell_size / 2
        oy = rect.top + top_pad
        if piece.kind is GemKind.MYSTERY:  # gemme grise + œil, teintée par la couleur choisie
            base = theme.GEM_FILL[override_color] if override_color is not None else theme.GEM_FILL[GemKind.MYSTERY]
            if faded:
                base = faded_color(base)
            polys = [theme.half_cell_polygon_at(pos, half, ox, oy, cell_size) for pos, half in cells]
            for poly in polys:
                pygame.draw.polygon(surface, base, poly)
                pygame.draw.polygon(surface, darken(base, 0.4), poly, width=1)
            eye_center, eye_extent, eye_vert = _eye_params(polys)
            draw_eye(surface, eye_center, eye_extent, vertical=eye_vert, faded=faded)
        elif piece.kind is GemKind.FILTER:  # icône translucide
            base = faded_piece_color(piece) if faded else piece_color(piece)
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            for pos, half in cells:
                poly = theme.half_cell_polygon_at(pos, half, ox - rect.x, oy - rect.y, cell_size)
                pygame.draw.polygon(overlay, (*base, theme.FILTER_ALPHA), poly)
            surface.blit(overlay, rect.topleft)
        else:
            base = faded_piece_color(piece) if faded else piece_color(piece)
            for pos, half in cells:
                pygame.draw.polygon(surface, base, theme.half_cell_polygon_at(pos, half, ox, oy, cell_size))
    label = i18n.piece(piece.color.value if piece.color else piece.name)
    # Texte vif quand la pièce est disponible, atténué quand elle est posée :
    # second indice (avec la couleur) de l'état de la pièce (#66). TEXT/TEXT_DIM
    # s'adaptent au mode (clair/sombre) — vif = sombre en mode clair, clair en
    # mode sombre, comme demandé.
    color = theme.TEXT_DIM if faded else theme.TEXT
    name = font.render(label, True, color)
    surface.blit(name, name.get_rect(centerx=rect.centerx, bottom=rect.bottom - theme.s(4)))


def draw_ghost(surface: pygame.Surface, gem, ok: bool, is_inside) -> None:
    """Aperçu translucide d'une pièce en cours de pose.

    Cas général : la pièce entière est teintée en vert (pose légale) ou rouge
    (avertissement). Pour la gemme mystère, on dessine sa **couleur choisie** +
    l'œil — sinon on ne saurait pas quelle couleur on pose — et on la cerne d'un
    liseré vert/rouge pour signaler la légalité (#77).
    """
    edge = theme.GHOST_OK if ok else theme.GHOST_BAD
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    if gem.kind is GemKind.MYSTERY:
        base = theme.GEM_FILL[gem.color] if gem.color is not None else theme.GEM_FILL[GemKind.MYSTERY]
        polys = []
        for pos, half in gem.absolute_cells().items():
            if is_inside(pos):
                poly = theme.half_cell_polygon(pos, half)
                polys.append(poly)
                pygame.draw.polygon(overlay, (*base, 170), poly)
                pygame.draw.polygon(overlay, (*darken(base, 0.4), 170), poly, width=1)
        surface.blit(overlay, (0, 0))
        if polys:
            eye_center, eye_extent, eye_vert = _eye_params(polys)
            draw_eye(surface, eye_center, eye_extent, vertical=eye_vert)
        _outline_footprint(surface, gem, edge, is_inside)
        return
    for pos, half in gem.absolute_cells().items():
        if is_inside(pos):
            pygame.draw.polygon(overlay, (*edge, 120), theme.half_cell_polygon(pos, half))
    surface.blit(overlay, (0, 0))


def _outline_footprint(surface: pygame.Surface, gem, color, is_inside) -> None:
    """Liseré englobant les cases visibles d'une pièce (légalité de l'aperçu)."""
    cells = [pos for pos in gem.absolute_cells() if is_inside(pos)]
    if not cells:
        return
    left = theme.BOARD_X + min(p.col for p in cells) * theme.CELL
    top = theme.BOARD_Y + min(p.row for p in cells) * theme.CELL
    right = theme.BOARD_X + (max(p.col for p in cells) + 1) * theme.CELL
    bottom = theme.BOARD_Y + (max(p.row for p in cells) + 1) * theme.CELL
    box = pygame.Rect(left, top, right - left, bottom - top)
    pygame.draw.rect(surface, color, box, width=max(2, theme.s(3)), border_radius=theme.s(4))


def draw_gems(surface: pygame.Surface, grid: Grid) -> None:
    """Dessine les gemmes pleines de `grid` (couleur + arêtes visibles)."""
    for gem in grid.gems:
        if gem.kind is GemKind.WORMHOLE:
            for pos in gem.absolute_cells():
                draw_wormhole(surface, theme.cell_center(pos), theme.CELL)
            continue
        if gem.kind is GemKind.FILTER:  # couleur du diamant, translucide
            _draw_translucent(surface, gem.absolute_cells(), piece_color(gem.piece), theme.FILTER_ALPHA)
            continue
        if gem.kind is GemKind.MYSTERY:  # gemme grise + œil, teintée par sa couleur (cachée)
            base = theme.GEM_FILL[gem.color] if gem.color is not None else theme.GEM_FILL[GemKind.MYSTERY]
            polys = []
            for pos, half in gem.absolute_cells().items():
                poly = theme.half_cell_polygon(pos, half)
                polys.append(poly)
                pygame.draw.polygon(surface, base, poly)
                pygame.draw.polygon(surface, darken(base, 0.4), poly, width=1)
            eye_center, eye_extent, eye_vert = _eye_params(polys)
            draw_eye(surface, eye_center, eye_extent, vertical=eye_vert)
            continue
        base = piece_color(gem.piece)
        for pos, half in gem.absolute_cells().items():
            poly = theme.half_cell_polygon(pos, half)
            pygame.draw.polygon(surface, base, poly)
            pygame.draw.polygon(surface, lighten(base, 0.35), poly, width=1)
        for pos, half in gem.absolute_cells().items():
            pygame.draw.polygon(surface, darken(base, 0.4), theme.half_cell_polygon(pos, half), width=1)


def _draw_translucent(surface, cells, base, alpha) -> None:
    """Dessine une pièce (demi-cases) translucide sur le plateau (pour le filtre)."""
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for pos, half in cells.items():
        poly = theme.half_cell_polygon(pos, half)
        pygame.draw.polygon(overlay, (*base, alpha), poly)
        pygame.draw.polygon(overlay, (*lighten(base, 0.35), min(255, alpha + 70)), poly, width=1)
    surface.blit(overlay, (0, 0))
