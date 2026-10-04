"""Dessin partagé du plateau et des gemmes (utilisé par plusieurs écrans).

Aucune règle de jeu : uniquement du rendu. Isolé ici pour éviter la
duplication entre l'écran de jeu et l'écran de fin.
"""

from __future__ import annotations

import pygame

from orapa_mine.model.gems import GemKind, Piece
from orapa_mine.model.grid import Grid
from orapa_mine.ui import i18n, theme


def piece_color(piece: Piece) -> tuple[int, int, int]:
    key = piece.color if piece.kind is GemKind.NORMAL else piece.kind
    return theme.GEM_FILL[key]


def faded_piece_color(piece: Piece) -> tuple[int, int, int]:
    """Couleur « posée/utilisée » d'une pièce dans la palette.

    Les pièces colorées sont assombries ; le corps noir (déjà quasi noir) est au
    contraire éclairci en gris foncé, sinon son état « posé » serait invisible.
    """
    if piece.kind is GemKind.BLACK_BODY:
        return (72, 72, 82)
    return darken(piece_color(piece), 0.5)


def lighten(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(min(255, int(c + (255 - c) * amount)) for c in color)  # type: ignore[return-value]


def darken(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(max(0, int(c * (1 - amount))) for c in color)  # type: ignore[return-value]


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
    ring_color: tuple[int, int, int] = theme.WORMHOLE_RING,
) -> None:
    """Dessine un trou de ver : cercle sombre cerné d'un liseré (le « O »)."""
    cx, cy = int(center[0]), int(center[1])
    radius = max(4, int(size * 0.34))
    ring = max(2, int(size * 0.08))
    pygame.draw.circle(surface, theme.GEM_FILL[GemKind.WORMHOLE], (cx, cy), radius)
    pygame.draw.circle(surface, ring_color, (cx, cy), radius, width=ring)


def draw_palette_slot(
    surface: pygame.Surface,
    rect: pygame.Rect,
    piece: Piece,
    *,
    selected: bool,
    placed: int,
    font: pygame.font.Font,
) -> None:
    """Dessine une case de palette (fond, bordure, icône, badge de quantité).

    `placed` = nombre d'exemplaires déjà posés ; la case est grisée quand tous
    le sont, et un badge « ×N » affiche le reste à poser (pièces en plusieurs
    exemplaires, p. ex. le trou de ver).
    """
    used = placed >= piece.quantity
    bg = theme.SLOT_USED if used else theme.SLOT_BG
    pygame.draw.rect(surface, bg, rect, border_radius=6)
    border = theme.SLOT_SELECTED if selected else theme.BOARD_BORDER
    pygame.draw.rect(surface, border, rect, width=2 if selected else 1, border_radius=6)
    _draw_slot_icon(surface, rect, piece, faded=used, font=font)
    if piece.quantity > 1 and not used:
        badge = font.render(f"x{piece.quantity - placed}", True, theme.TEXT)
        surface.blit(badge, (rect.left + 6, rect.bottom - 38))  # au-dessus du nom


def _draw_slot_icon(
    surface: pygame.Surface, rect: pygame.Rect, piece: Piece, faded: bool, font: pygame.font.Font
) -> None:
    if piece.kind is GemKind.WORMHOLE:
        size = min(rect.width, rect.height) - 22
        center = (rect.centerx, rect.top + 8 + size / 2)
        ring = theme.TEXT_DIM if faded else theme.WORMHOLE_RING
        draw_wormhole(surface, center, size, ring_color=ring)
    else:
        cells = piece.cells
        rows = max(p.row for p, _ in cells) + 1
        cols = max(p.col for p, _ in cells) + 1
        area = rect.inflate(-16, -22)
        cell_size = min(area.width / cols, area.height / rows)
        ox = rect.centerx - cols * cell_size / 2
        oy = rect.top + 8
        base = faded_piece_color(piece) if faded else piece_color(piece)
        for pos, half in cells:
            pygame.draw.polygon(surface, base, theme.half_cell_polygon_at(pos, half, ox, oy, cell_size))
    label = i18n.piece(piece.color.value if piece.color else piece.name)
    name = font.render(label, True, theme.TEXT_DIM)
    surface.blit(name, name.get_rect(centerx=rect.centerx, bottom=rect.bottom - 4))


def draw_gems(surface: pygame.Surface, grid: Grid) -> None:
    """Dessine les gemmes pleines de `grid` (couleur + arêtes visibles)."""
    for gem in grid.gems:
        if gem.kind is GemKind.WORMHOLE:
            for pos in gem.absolute_cells():
                draw_wormhole(surface, theme.cell_center(pos), theme.CELL)
            continue
        base = piece_color(gem.piece)
        for pos, half in gem.absolute_cells().items():
            poly = theme.half_cell_polygon(pos, half)
            pygame.draw.polygon(surface, base, poly)
            pygame.draw.polygon(surface, lighten(base, 0.35), poly, width=1)
        for pos, half in gem.absolute_cells().items():
            pygame.draw.polygon(surface, darken(base, 0.4), theme.half_cell_polygon(pos, half), width=1)
