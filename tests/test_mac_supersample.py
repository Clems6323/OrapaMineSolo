"""Pipeline de sur-échantillonnage macOS (ui.app) : mapping souris canevas↔fenêtre."""

from __future__ import annotations

import pygame

from orapa_mine.ui import app as appmod


def test_scaled_event_maps_mouse_to_canvas(monkeypatch):
    a = appmod.OrapaMineApp()
    monkeypatch.setattr(appmod, "_MAC_SUPERSAMPLE", True)
    a.screen = pygame.display.set_mode((100, 50))   # fenêtre en « points »
    a.canvas = pygame.Surface((200, 100))           # rendu physique 2×
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    out = a._scaled_event(ev)
    assert out.pos == (20, 20)                      # points → pixels physiques


def test_scaled_event_identity_off_mac():
    # Hors macOS Retina (_MAC_SUPERSAMPLE faux), l'évènement n'est pas transformé.
    a = appmod.OrapaMineApp()
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
    assert a._scaled_event(ev) is ev
