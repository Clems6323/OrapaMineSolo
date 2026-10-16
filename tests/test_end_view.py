"""Écran de fin : bascule entre la solution et le plateau proposé par le joueur."""

from __future__ import annotations

import pygame

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.ui.end_screen import EndScreen


def _click(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def _truth() -> Grid:
    g = Grid(width=10, height=8)
    g.place_gem(cat.YELLOW.at(Position(2, 2)))
    return g


def test_view_toggle_switches_between_solution_and_guess():
    guess = Grid(width=10, height=8)
    guess.place_gem(cat.YELLOW.at(Position(2, 3)))
    es = EndScreen(won=False, score=5, hidden_grid=_truth(), palette_pieces=[cat.YELLOW], guess_grid=guess)
    assert es.show_solution is True  # par défaut, on montre la solution
    es.handle_event(_click(es.guess_rect.center))
    assert es.show_solution is False
    es.handle_event(_click(es.solution_rect.center))
    assert es.show_solution is True


def test_no_toggle_without_a_guess_board():
    es = EndScreen(won=True, score=3, hidden_grid=_truth(), palette_pieces=[cat.YELLOW], guess_grid=None)
    # Cliquer là où serait le bouton « Ta proposition » ne change rien.
    es.handle_event(_click(es.guess_rect.center))
    assert es.show_solution is True
