"""#79 : historique agrandi + barre de défilement cliquable/glissable.

- Le panneau de jeu s'étire sous le plateau → l'historique est plus grand que
  la simple hauteur du plateau ne le permettrait.
- La barre de défilement se saisit (glissement du pouce) et se clique dans la
  gouttière (saut), en plus de la molette.
"""

from __future__ import annotations

import pygame

from orapa_mine.ui import theme
from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Direction, Position
from orapa_mine.model.grid import Grid
from orapa_mine.ui.game_screen import GameScreen


def _game_with_history(n: int) -> GameScreen:
    hidden = Grid(width=10, height=8)
    hidden.place_gem(cat.YELLOW.at(Position(3, 4)))
    game = GameState(hidden_grid=hidden)
    for i in range(n):
        game.play_shot(Position(i % 8, 0), Direction.RIGHT)
    return GameScreen(game, [*cat.base_set()], timer_minutes=0)


def test_history_panel_extends_below_the_board():
    gs = _game_with_history(0)
    # Le panneau de jeu est plus haut que le panneau « de base » (hauteur du
    # plateau) : il récupère l'espace libre sous lui (#79).
    assert gs.panel.height > theme.PANEL.height
    assert gs.panel.bottom < gs.size[1]  # reste dans la fenêtre (place pour la ligne d'indices)
    # La zone de saisie est ancrée vers le bas, sous l'historique agrandi.
    assert gs.input_rect.bottom < gs.panel.bottom
    assert gs.input_rect.top > gs.history_rect.bottom


def test_no_scrollbar_when_history_fits():
    gs = _game_with_history(1)
    assert gs._history_scrollbar() is None


def test_dragging_thumb_scrolls_history():
    gs = _game_with_history(25)
    sb = gs._history_scrollbar()
    assert sb is not None
    _, thumb, _, max_scroll = sb
    assert max_scroll > 0
    # Saisir le pouce puis le glisser tout en haut -> défilement à 0.
    gs.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=thumb.center))
    assert gs._dragging_scroll is True
    gs.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(thumb.centerx, gs.history_rect.y - 60), rel=(0, 0), buttons=(1, 0, 0)
    ))
    assert gs.history_scroll == 0.0
    # Puis tout en bas.
    gs.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(thumb.centerx, gs.history_rect.bottom + 60), rel=(0, 0), buttons=(1, 0, 0)
    ))
    assert gs.history_scroll == max_scroll
    # Relâcher arrête le glissement.
    gs.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=thumb.center))
    assert gs._dragging_scroll is False


def test_clicking_gutter_jumps_and_starts_drag():
    gs = _game_with_history(25)
    gs.history_scroll = 0.0
    gs.history_stick_bottom = False
    track, _, _, max_scroll = gs._history_scrollbar()
    # Clic en bas de la gouttière -> le pouce saute vers le bas (défilement > 0).
    gs.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=(track.centerx, track.bottom - 4)
    ))
    assert gs._dragging_scroll is True
    assert gs.history_scroll > 0.0
