"""Dessin partagé du plateau et des gemmes (utilisé par plusieurs écrans).

Aucune règle de jeu : uniquement du rendu. Isolé ici pour éviter la
duplication entre l'écran de jeu et l'écran de fin.
"""

from __future__ import annotations

import pygame

from orapa_mine.model.gems import GemKind, Piece
from orapa_mine.model.grid import Grid
from orapa_mine.ui import theme


def piece_color(piece: Piece) -> tuple[int, int, int]:
    key = piece.color if piece.kind is GemKind.NORMAL else piece.kind
    return theme.GEM_FILL[key]


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


def draw_gems(surface: pygame.Surface, grid: Grid) -> None:
    """Dessine les gemmes pleines de `grid` (couleur + arêtes visibles)."""
    for gem in grid.gems:
        base = piece_color(gem.piece)
        for pos, half in gem.absolute_cells().items():
            poly = theme.half_cell_polygon(pos, half)
            pygame.draw.polygon(surface, base, poly)
            pygame.draw.polygon(surface, lighten(base, 0.35), poly, width=1)
        for pos, half in gem.absolute_cells().items():
            pygame.draw.polygon(surface, darken(base, 0.4), theme.half_cell_polygon(pos, half), width=1)
