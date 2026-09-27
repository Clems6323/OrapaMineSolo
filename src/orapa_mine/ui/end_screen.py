"""Écran de fin : révèle la solution et propose de rejouer.

Deux issues :
- `won=True`  : victoire (proposition correcte) + score (nombre de tirs/questions) ;
- `won=False` : partie abandonnée — on révèle quand même la solution.

Signale son choix à l'app via `self.restart` / `self.quit`.
"""

from __future__ import annotations

import pygame

from orapa_mine.model.grid import Grid
from orapa_mine.ui import board_render, theme


class EndScreen:
    """Écran de fin de partie (plateau révélé + bandeau résultat)."""

    def __init__(self, won: bool, score: int, hidden_grid: Grid) -> None:
        self.won = won
        self.score = score
        self.grid = hidden_grid
        self.restart = False
        self.quit = False
        self.size = theme.window_size(hidden_grid.width, hidden_grid.height)

        pygame.font.init()
        self.font_big = pygame.font.SysFont("arial", 32, bold=True)
        self.font = pygame.font.SysFont("arial", 20)
        self.font_small = pygame.font.SysFont("arial", 16)

        px = theme.BOARD_X + hidden_grid.width * theme.CELL + theme.PANEL_MARGIN
        self.panel = pygame.Rect(px, theme.BOARD_Y, theme.PANEL_WIDTH, hidden_grid.height * theme.CELL)
        inner = px + 18
        self.replay_rect = pygame.Rect(inner, self.panel.bottom - 108, theme.PANEL_WIDTH - 36, 44)
        self.quit_rect = pygame.Rect(inner, self.panel.bottom - 56, theme.PANEL_WIDTH - 36, 40)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.replay_rect.collidepoint(event.pos):
            self.restart = True
        elif self.quit_rect.collidepoint(event.pos):
            self.quit = True

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.grid)  # solution révélée

        caption = self.font.render("Voici la solution :", True, theme.TEXT_DIM)
        surface.blit(caption, (theme.BOARD_X, theme.BOARD_Y - 34))

        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel.x + 18

        if self.won:
            banner, color = "Gagné !", theme.WIN_COLOR
            detail = f"Résolu en {self.score} tir(s)/question(s)."
        else:
            banner, color = "Partie abandonnée", theme.LOSE_COLOR
            detail = f"{self.score} tir(s)/question(s) joués."
        title = self.font_big.render(banner, True, color)
        surface.blit(title, (x, theme.BOARD_Y + 20))
        surface.blit(self.font.render(detail, True, theme.TEXT), (x, theme.BOARD_Y + 64))

        pygame.draw.rect(surface, (54, 120, 90), self.replay_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.replay_rect, width=1, border_radius=8)
        r = self.font.render("Rejouer", True, theme.TEXT)
        surface.blit(r, r.get_rect(center=self.replay_rect.center))

        pygame.draw.rect(surface, theme.SLOT_BG, self.quit_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.quit_rect, width=1, border_radius=8)
        q = self.font.render("Quitter", True, theme.TEXT)
        surface.blit(q, q.get_rect(center=self.quit_rect.center))
