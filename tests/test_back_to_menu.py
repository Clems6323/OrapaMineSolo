"""Bouton « Retour au menu » du jeu et son popup de sauvegarde."""

from __future__ import annotations

import pygame

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.game import GameState
from orapa_mine.model.grid import Grid
from orapa_mine.ui import dialogs, theme
from orapa_mine.ui.game_screen import GameScreen


def _screen() -> GameScreen:
    theme.window_size(10, 8)
    return GameScreen(GameState(hidden_grid=Grid(width=10, height=8)), cat.base_set())


def _click(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_menu_button_opens_prompt():
    gs = _screen()
    gs.handle_event(_click(gs.menu_rect.center))
    assert gs.show_leave_prompt is True
    assert gs.back_to_menu is False


def test_cancel_closes_prompt_and_stays():
    gs = _screen()
    gs.show_leave_prompt = True
    rects = gs._leave_prompt_layout(gs.size)["rects"]
    gs.handle_event(_click(rects[3].center))  # Annuler
    assert gs.show_leave_prompt is False
    assert gs.back_to_menu is False


def test_leave_without_saving_goes_to_menu():
    gs = _screen()
    gs.show_leave_prompt = True
    rects = gs._leave_prompt_layout(gs.size)["rects"]
    gs.handle_event(_click(rects[2].center))  # Quitter sans sauvegarder
    assert gs.back_to_menu is True
    assert gs.show_leave_prompt is False


def test_save_with_progress_then_menu(monkeypatch):
    written: dict = {}
    monkeypatch.setattr(dialogs, "ask_save_path", lambda: "unused.json")
    monkeypatch.setattr(dialogs, "write_json", lambda path, data: written.update(data))
    gs = _screen()
    gs.show_leave_prompt = True
    rects = gs._leave_prompt_layout(gs.size)["rects"]
    gs.handle_event(_click(rects[0].center))  # Sauvegarder (avec progression)
    assert written.get("progress") is True
    assert gs.back_to_menu is True


def test_save_cancelled_stays_in_game(monkeypatch):
    monkeypatch.setattr(dialogs, "ask_save_path", lambda: None)  # annule le sélecteur
    gs = _screen()
    gs.show_leave_prompt = True
    rects = gs._leave_prompt_layout(gs.size)["rects"]
    gs.handle_event(_click(rects[1].center))  # Sauvegarder (configuration seule)
    assert gs.back_to_menu is False       # pas de sauvegarde -> on reste
    assert gs.show_leave_prompt is False  # le popup se ferme
