"""Croix « pas de gemme ici » posée au double-clic (#84).

Double-clic sur une case vide (sans pièce en main) → (dé)pose une croix ; une
gemme posée l'efface ; les croix sont sauvées avec la progression.
"""

from __future__ import annotations

import pygame

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.model.serialization import from_dict, to_dict
from orapa_mine.ui import board_render, theme
from orapa_mine.ui.game_screen import _DOUBLE_CLICK_MS, GameScreen


def _grid() -> Grid:
    g = Grid(width=10, height=8)
    g.place_gem(cat.YELLOW.at(Position(2, 2)))
    return g


def _screen() -> GameScreen:
    game = GameState(hidden_grid=_grid())
    return GameScreen(game, [*cat.base_set()], timer_minutes=0)


def _click_at(cell: Position) -> pygame.event.Event:
    cx, cy = theme.cell_center(cell)
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(int(cx), int(cy)))


# --- Double-clic : (dé)pose la croix -----------------------------------------


def test_double_click_toggles_cross_on_empty_cell():
    gs = _screen()
    cell = Position(1, 1)
    gs.handle_event(_click_at(cell))
    gs.handle_event(_click_at(cell))
    assert cell in gs.crosses  # double-clic -> croix posée
    gs.handle_event(_click_at(cell))
    gs.handle_event(_click_at(cell))
    assert cell not in gs.crosses  # re-double-clic -> croix retirée


def test_single_click_does_not_cross():
    gs = _screen()
    cell = Position(1, 1)
    gs.handle_event(_click_at(cell))
    assert cell not in gs.crosses  # un seul clic ne pose rien


def test_two_slow_clicks_do_not_cross():
    gs = _screen()
    cell = Position(1, 1)
    gs.handle_event(_click_at(cell))
    gs._last_click_ms -= _DOUBLE_CLICK_MS + 100  # simule un délai trop long
    gs.handle_event(_click_at(cell))
    assert cell not in gs.crosses


# --- La croix n'apparaît que sur une case vide, sans pièce en main -----------


def test_no_cross_when_a_piece_is_held():
    gs = _screen()
    gs.selected = cat.YELLOW
    gs.orientation_index = 0
    cell = Position(1, 1)
    gs.handle_event(_click_at(cell))
    gs.handle_event(_click_at(cell))
    assert cell not in gs.crosses  # une pièce en main -> pose, pas de croix


def test_no_cross_on_occupied_cell():
    gs = _screen()
    cell = Position(1, 1)
    gs.hypothesis.place_gem(cat.YELLOW.at(cell))
    gs.handle_event(_click_at(cell))
    gs.handle_event(_click_at(cell))
    assert cell not in gs.crosses  # case occupée -> pas de croix


def test_placing_a_gem_clears_the_cross():
    gs = _screen()
    cell = Position(1, 1)
    gs.crosses.add(cell)
    gs.selected = cat.YELLOW
    gs.orientation_index = 0
    gs._place_or_pick(cell)
    assert gs.hypothesis.gem_at(cell) is not None
    assert cell not in gs.crosses  # la gemme efface la croix


# --- Sérialisation : les croix voyagent avec la progression ------------------


def test_crosses_saved_and_restored_with_progress():
    game = GameState(hidden_grid=_grid())
    hypothesis = Grid(width=10, height=8)
    crosses = {Position(1, 1), Position(3, 4)}
    data = to_dict(
        width=10, height=8, palette_pieces=cat.base_set(), hidden_grid=game.hidden_grid,
        include_progress=True, game=game, hypothesis_grid=hypothesis, crosses=crosses,
    )
    assert sorted(data["crosses"]) == [[1, 1], [3, 4]]
    loaded = from_dict(data)
    assert set(loaded.crosses) == crosses


def test_crosses_absent_without_progress():
    game = GameState(hidden_grid=_grid())
    data = to_dict(
        width=10, height=8, palette_pieces=cat.base_set(), hidden_grid=game.hidden_grid,
        include_progress=False,
    )
    assert "crosses" not in data
    loaded = from_dict(data)
    assert loaded.crosses == []


# --- Rendu : dessiner une croix ne lève pas (headless) -----------------------


def test_draw_cross_headless():
    surface = pygame.Surface(theme.window_size(10, 8))
    board_render.draw_crosses(surface, {Position(1, 1), Position(2, 3)})
