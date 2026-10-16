"""Écran de fin : révèle la solution et propose de rejouer.

Deux issues :
- `won=True`  : victoire (proposition correcte) + score (nombre de tirs/questions) ;
- `won=False` : partie abandonnée — on révèle quand même la solution.

Signale son choix à l'app via `self.restart` / `self.quit`.
"""

from __future__ import annotations

import math

import pygame

from orapa_mine.model.gems import Piece
from orapa_mine.model.grid import Grid
from orapa_mine.model import serialization
from orapa_mine.ui import board_render, dialogs, i18n, lang_toggle, theme, theme_toggle


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
        distance=None,
    ) -> None:
        self.won = won
        self.score = score
        self.distance = distance  # Score (model.distance) : proximité à la vérité (#45)
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

        self.font_big = theme.font(32, bold=True)
        self.font = theme.font(20)
        self.font_small = theme.font(16)

        s = theme.s
        self.panel = theme.PANEL.copy()
        inner = self.panel.x + s(18)
        bw = theme.PANEL_WIDTH - s(36)
        self.save_rect = pygame.Rect(inner, self.panel.bottom - s(164), bw, s(40))
        self.replay_rect = pygame.Rect(inner, self.panel.bottom - s(108), bw, s(44))
        self.quit_rect = pygame.Rect(inner, self.panel.bottom - s(56), bw, s(40))

    # --- Événements --------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if theme_toggle.hit(event.pos):  # bascule mode sombre / clair
            theme_toggle.toggle()
        elif lang_toggle.handle_click(event.pos, self.size[0]):  # drapeaux FR / UK
            pass
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

    def _is_perfect(self) -> bool:
        """Vrai si l'hypothèse finale colle exactement à la vérité (distance nulle)."""
        return self.distance is not None and self.distance.total == 0.0

    def _distance_text(self) -> str:
        """Valeur de la distance à la vérité (Earth Mover, en cases)."""
        if self.distance is None:
            return "—"
        total = self.distance.total
        if math.isinf(total):  # au moins une gemme non posée : distance non finie
            return "∞"
        return f"{total:.2f} " + i18n.t("cases", "cells")

    def _distance_note(self) -> str | None:
        """Précision affichée sous la distance quand elle est infinie."""
        if self.distance is None or not math.isinf(self.distance.total):
            return None
        n = self.distance.missing
        return i18n.t(f"{n} gemme(s) non posée(s)", f"{n} gem(s) not placed")

    def update(self, dt: float) -> None:  # noqa: D401 - rien à animer
        pass

    # --- Rendu -------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(theme.BACKGROUND)
        theme_toggle.draw(surface)
        lang_toggle.draw(surface)
        board_render.draw_board(surface, self.grid)
        board_render.draw_gems(surface, self.grid)  # solution révélée

        caption = self.font.render(i18n.t("Voici la solution :", "Here is the solution:"), True, theme.TEXT_DIM)
        surface.blit(caption, (theme.BOARD_X, theme.BOARD_Y - theme.s(34)))

        pygame.draw.rect(surface, theme.PANEL_BG, self.panel, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.panel, width=1, border_radius=8)
        x = self.panel.x + theme.s(18)

        if self.won:
            banner, color = i18n.t("Gagné !", "You win!"), theme.WIN_COLOR
        elif self.timed_out:
            banner, color = i18n.t("Temps écoulé !", "Time's up!"), theme.LOSE_COLOR
        else:
            banner, color = i18n.t("Partie abandonnée", "Game abandoned"), theme.LOSE_COLOR
        title = self.font_big.render(banner, True, color)
        surface.blit(title, (x, self.panel.top + theme.s(20)))

        # Deux scores (plus bas = meilleur), #45 : requêtes pondérées + distance.
        score_line = i18n.t(f"Score requêtes : {self.score}", f"Request score: {self.score}")
        surface.blit(self.font.render(score_line, True, theme.TEXT), (x, self.panel.top + theme.s(60)))
        dist_line = i18n.t(f"Distance à la vérité : {self._distance_text()}",
                           f"Distance to truth: {self._distance_text()}")
        dist_color = theme.WIN_COLOR if self._is_perfect() else theme.TEXT
        surface.blit(self.font.render(dist_line, True, dist_color), (x, self.panel.top + theme.s(86)))

        y = self.panel.top + theme.s(112)
        note = self._distance_note()
        if note is not None:  # ex. « 1 gemme non posée » quand la distance est infinie
            surface.blit(self.font_small.render(note, True, theme.TEXT_DIM), (x, y))
            y += theme.s(22)
        spent = self.font_small.render(
            i18n.t(f"Temps passé : {_duration(self.elapsed_seconds)}",
                   f"Time spent: {_duration(self.elapsed_seconds)}"), True, theme.TEXT_DIM)
        surface.blit(spent, (x, y))

        # Bouton « Sauvegarder la configuration » (partage de l'énigme jouée).
        pygame.draw.rect(surface, theme.BTN_SAVE, self.save_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.save_rect, width=1, border_radius=8)
        sv = self.font_small.render(
            i18n.t("Sauvegarder la configuration", "Save configuration"), True, theme.BTN_TEXT)
        surface.blit(sv, sv.get_rect(center=self.save_rect.center))
        if self.message:
            msg = self.font_small.render(self.message, True, self.message_color)
            surface.blit(msg, (x, self.save_rect.top - theme.s(24)))

        pygame.draw.rect(surface, theme.BTN_BLUE, self.replay_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.replay_rect, width=1, border_radius=8)
        r = self.font.render(i18n.t("Retour au menu", "Back to menu"), True, theme.BTN_TEXT)
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
