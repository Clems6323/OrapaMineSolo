"""Écran de fin : révèle la solution et propose de rejouer.

Deux issues :
- `won=True`  : victoire (proposition correcte) + score (nombre de tirs/questions) ;
- `won=False` : partie abandonnée — on révèle quand même la solution.

Signale son choix à l'app via `self.restart` / `self.quit`.
"""

from __future__ import annotations

import pygame

from orapa_mine.model.gems import Piece
from orapa_mine.model.grid import Grid
from orapa_mine.model import serialization
from orapa_mine.ui import board_render, dialogs, i18n, theme, theme_toggle


class EndScreen:
    """Écran de fin de partie (plateau révélé + bandeau résultat)."""

    def __init__(
        self,
        won: bool,
        score: int,
        hidden_grid: Grid,
        palette_pieces: list[Piece],
        elapsed_seconds: float = 0.0,
        timed_out: bool = False,
        timer_minutes: int = 0,
    ) -> None:
        self.won = won
        self.score = score
        self.grid = hidden_grid
        self.palette_pieces = palette_pieces
        self.elapsed_seconds = max(0.0, elapsed_seconds)
        self.timed_out = timed_out
        self.timer_minutes = max(0, int(timer_minutes))
        self.restart = False
        self.quit = False
        self.message: str | None = None
        self.message_color = theme.TEXT_DIM
        self.size = theme.window_size(hidden_grid.width, hidden_grid.height)

        pygame.font.init()
        self.font_big = pygame.font.SysFont("arial", 32, bold=True)
        self.font = pygame.font.SysFont("arial", 20)
        self.font_small = pygame.font.SysFont("arial", 16)

        self.panel = theme.PANEL.copy()
        inner = self.panel.x + 18
        bw = theme.PANEL_WIDTH - 36
        self.save_rect = pygame.Rect(inner, self.panel.bottom - 164, bw, 40)
        self.replay_rect = pygame.Rect(inner, self.panel.bottom - 108, bw, 44)
        self.quit_rect = pygame.Rect(inner, self.panel.bottom - 56, bw, 40)

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if theme_toggle.hit(event.pos):  # bascule mode sombre / clair
            theme_toggle.toggle()
        elif self.save_rect.collidepoint(event.pos):
            self._save()
        elif self.replay_rect.collidepoint(event.pos):
            self.restart = True
        elif self.quit_rect.collidepoint(event.pos):
            self.quit = True

    def _save(self) -> None:
        """Sauvegarde la configuration jouée (sans progression) pour la partager."""
        path = dialogs.ask_save_path()
        if not path:
            return
        data = serialization.to_dict(
            width=self.grid.width,
            height=self.grid.height,
            palette_pieces=self.palette_pieces,
            hidden_grid=self.grid,
            include_progress=False,
            timer_minutes=self.timer_minutes,
        )
        try:
            dialogs.write_json(path, data)
        except OSError as exc:
            self.message = i18n.t("Échec de la sauvegarde : ", "Save failed: ") + str(exc)
            self.message_color = theme.LOSE_COLOR
            return
        self.message = i18n.t("Configuration enregistrée.", "Configuration saved.")
        self.message_color = theme.WIN_COLOR

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        theme_toggle.draw(surface)
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.grid)  # solution révélée

        caption = self.font.render(i18n.t("Voici la solution :", "Here is the solution:"), True, theme.TEXT_DIM)
        surface.blit(caption, (theme.BOARD_X, theme.BOARD_Y - 34))

        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel.x + 18

        if self.won:
            banner, color = i18n.t("Gagné !", "You win!"), theme.WIN_COLOR
            detail = i18n.t(f"Résolu en {self.score} tir(s)/question(s).",
                            f"Solved in {self.score} shot(s)/question(s).")
        elif self.timed_out:
            banner, color = i18n.t("Temps écoulé !", "Time's up!"), theme.LOSE_COLOR
            detail = i18n.t(f"{self.score} tir(s)/question(s) joués.",
                            f"{self.score} shot(s)/question(s) played.")
        else:
            banner, color = i18n.t("Partie abandonnée", "Game abandoned"), theme.LOSE_COLOR
            detail = i18n.t(f"{self.score} tir(s)/question(s) joués.",
                            f"{self.score} shot(s)/question(s) played.")
        title = self.font_big.render(banner, True, color)
        surface.blit(title, (x, self.panel.top + 20))
        surface.blit(self.font.render(detail, True, theme.TEXT), (x, self.panel.top + 64))
        spent = self.font.render(
            i18n.t(f"Temps passé : {_duration(self.elapsed_seconds)}",
                   f"Time spent: {_duration(self.elapsed_seconds)}"), True, theme.TEXT_DIM)
        surface.blit(spent, (x, self.panel.top + 92))

        # Bouton « Sauvegarder la configuration » (partage de l'énigme jouée).
        pygame.draw.rect(surface, (54, 96, 120), self.save_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.save_rect, width=1, border_radius=8)
        sv = self.font_small.render(
            i18n.t("Sauvegarder la configuration", "Save configuration"), True, theme.TEXT)
        surface.blit(sv, sv.get_rect(center=self.save_rect.center))
        if self.message:
            msg = self.font_small.render(self.message, True, self.message_color)
            surface.blit(msg, (x, self.save_rect.top - 24))

        pygame.draw.rect(surface, (54, 120, 90), self.replay_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.replay_rect, width=1, border_radius=8)
        r = self.font.render(i18n.t("Rejouer", "Replay"), True, theme.TEXT)
        surface.blit(r, r.get_rect(center=self.replay_rect.center))

        pygame.draw.rect(surface, theme.SLOT_BG, self.quit_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.quit_rect, width=1, border_radius=8)
        q = self.font.render(i18n.t("Quitter", "Quit"), True, theme.TEXT)
        surface.blit(q, q.get_rect(center=self.quit_rect.center))


def _duration(seconds: float) -> str:
    """Durée lisible « M min S s » (ou « S s » sous une minute)."""
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    if minutes:
        return i18n.t(f"{minutes} min {secs} s", f"{minutes} min {secs} s")
    return i18n.t(f"{secs} s", f"{secs} s")
