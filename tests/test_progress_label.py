"""La case « Progression » du jeu se coche en cliquant la case OU le libellé."""

from __future__ import annotations

import pygame

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.grid import Grid
from orapa_mine.ui import theme
from orapa_mine.ui.game_screen import GameScreen


def test_progress_label_click_toggles():
    theme.window_size(10, 8)
    gs = GameScreen(GameState(hidden_grid=Grid(width=10, height=8)), cat.base_set())
    before = gs.save_progress
    # Clic sur le TEXTE (bord droit de la ligne, loin de la petite case).
    label_point = (gs.progress_row.right - 6, gs.progress_row.centery)
    gs.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=label_point))
    assert gs.save_progress is (not before)
