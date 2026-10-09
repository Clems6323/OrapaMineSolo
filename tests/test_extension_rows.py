"""#35 : cocher une extension en cliquant la case OU le libellé (config + créateur)."""

from __future__ import annotations

import pygame

from orapa_mine.ui.config_screen import ConfigScreen
from orapa_mine.ui.creator_screen import CreatorScreen


def _click(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_config_label_click_toggles_extension():
    cfg = ConfigScreen()
    assert cfg.diamant is False
    # Clic sur le TEXTE (centre de la ligne, hors de la petite case).
    cfg.handle_event(_click(cfg.diamant_row.center))
    assert cfg.diamant is True
    # La case elle-même fonctionne toujours.
    cfg.handle_event(_click(cfg.diamant_rect.center))
    assert cfg.diamant is False


def test_creator_label_click_toggles_extension():
    cr = CreatorScreen(size_index=1)
    assert cr.wormhole is False
    # Clic sur le libellé (bord droit de la ligne, loin de la case).
    cr.handle_event(_click((cr.wormhole_row.right - 5, cr.wormhole_row.centery)))
    assert cr.wormhole is True


def test_creator_timer_column_not_captured_by_extension_row():
    # La ligne d'extension est bornée avant la colonne minuteur : cliquer le « + »
    # du minuteur n'active pas le diamant.
    cr = CreatorScreen(size_index=1)
    before = cr.diamant
    cr.handle_event(_click(cr.timer.plus_rect.center))
    assert cr.diamant is before          # extension non modifiée
    assert cr.timer.minutes == 1         # minuteur bien incrémenté
