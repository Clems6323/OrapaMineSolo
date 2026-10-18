"""Mapping souris canevas↔fenêtre (ui.app) : sur-échantillonnage macOS et
rétrécissement pour tenir à l'écran (#86) partagent le même pipeline."""

from __future__ import annotations

import pygame

from orapa_mine.ui import app as appmod


def test_scaled_event_maps_mouse_to_canvas():
    # Canevas plein format (200×100) recopié dans une fenêtre réduite (100×50) :
    # les coordonnées souris (fenêtre) sont remises à l'échelle du canevas.
    a = appmod.OrapaMineApp()
    a.screen = pygame.display.set_mode((100, 50))
    a.canvas = pygame.Surface((200, 100))           # rendu plein format 2×
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    out = a._scaled_event(ev)
    assert out.pos == (20, 20)                      # fenêtre → canevas


def test_scaled_event_identity_when_canvas_is_screen():
    # Fenêtre 1:1 (canevas == écran) : l'évènement n'est pas transformé.
    a = appmod.OrapaMineApp()
    a.screen = pygame.display.set_mode((300, 200))
    a.canvas = a.screen
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    assert a._scaled_event(ev) is ev
