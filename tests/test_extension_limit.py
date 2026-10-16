"""#75 : plafond du nombre d'extensions selon la taille de grille.

Petit → 2, Standard → 4, Grand → 5. Au plafond, on ne peut plus cocher de
nouvelle extension ; passer à une grille plus petite rogne l'excédent. Vaut
pour l'écran de configuration ET le mode créateur.
"""

from __future__ import annotations

import pygame

from orapa_mine.ai.generator import DISALLOWED_EXTENSIONS_BY_SIZE, MAX_EXTENSIONS_BY_SIZE
from orapa_mine.ui.config_screen import ConfigScreen
from orapa_mine.ui.creator_screen import CreatorScreen


def _click(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_mapping_is_small_standard_large():
    assert MAX_EXTENSIONS_BY_SIZE == (2, 4, 5)


def test_rainbow_disallowed_only_on_small_grid():
    assert "rainbow" in DISALLOWED_EXTENSIONS_BY_SIZE[0]       # Petit
    assert "rainbow" not in DISALLOWED_EXTENSIONS_BY_SIZE[1]   # Standard
    assert "rainbow" not in DISALLOWED_EXTENSIONS_BY_SIZE[2]   # Grand


# --- Arc-en-ciel : carré 2×2 interdit sur la petite grille (#75) -------------


def test_config_rainbow_not_selectable_on_small_grid():
    cfg = ConfigScreen()
    cfg.size_index = 0  # Petit
    assert cfg._ext_disabled("rainbow") is True
    cfg.handle_event(_click(cfg.rainbow_row.center))
    assert cfg.rainbow is False
    # Mais sélectionnable dès la grille standard.
    cfg.size_index = 1
    cfg.handle_event(_click(cfg.rainbow_row.center))
    assert cfg.rainbow is True


def test_config_shrinking_grid_unchecks_rainbow():
    cfg = ConfigScreen()
    cfg.size_index = 1  # Standard
    cfg.rainbow = True
    cfg.handle_event(_click(cfg.size_rects[0].center))  # → Petit
    assert cfg.rainbow is False


def test_creator_rainbow_not_selectable_on_small_grid():
    cr = CreatorScreen(size_index=0)  # Petit
    cr.handle_event(_click(cr.rainbow_row.center))
    assert cr.rainbow is False


def test_creator_constructed_with_rainbow_on_small_is_trimmed():
    cr = CreatorScreen(size_index=0, rainbow=True)
    assert cr.rainbow is False


# --- Écran de configuration --------------------------------------------------


def test_config_small_grid_caps_at_two():
    cfg = ConfigScreen()
    cfg.size_index = 0  # Petit
    cfg.handle_event(_click(cfg.diamant_row.center))
    cfg.handle_event(_click(cfg.corps_row.center))
    assert cfg._ext_count() == 2
    # La 3e extension est refusée (plafond atteint).
    cfg.handle_event(_click(cfg.wormhole_row.center))
    assert cfg.wormhole is False
    assert cfg._ext_count() == 2
    # Décocher reste toujours possible.
    cfg.handle_event(_click(cfg.diamant_row.center))
    assert cfg.diamant is False
    # …et libère une place pour une autre extension.
    cfg.handle_event(_click(cfg.wormhole_row.center))
    assert cfg.wormhole is True


def test_config_shrinking_grid_trims_extensions():
    cfg = ConfigScreen()
    cfg.size_index = 2  # Grand : 5 extensions possibles
    for attr in ConfigScreen._EXT_ATTRS:
        setattr(cfg, attr, True)
    assert cfg._ext_count() == 5
    # Passage à la petite grille : plafonné à 2.
    cfg.handle_event(_click(cfg.size_rects[0].center))
    assert cfg.size_index == 0
    assert cfg._ext_count() == 2
    # Les deux premières extensions (ordre d'affichage) sont conservées.
    assert cfg.diamant is True and cfg.corps_noir is True
    assert cfg.wormhole is False and cfg.filter is False and cfg.rainbow is False


# --- Mode créateur -----------------------------------------------------------


def test_creator_small_grid_caps_at_two():
    cr = CreatorScreen(size_index=0)  # Petit
    cr.handle_event(_click(cr.diamant_row.center))
    cr.handle_event(_click(cr.corps_row.center))
    assert cr._ext_count() == 2
    cr.handle_event(_click(cr.wormhole_row.center))
    assert cr.wormhole is False
    assert cr._ext_count() == 2


def test_creator_constructed_over_limit_is_trimmed():
    # Une config reçue avec trop d'extensions pour une petite grille est rognée.
    cr = CreatorScreen(size_index=0, diamant=True, corps_noir=True, wormhole=True)
    assert cr._ext_count() == 2
    assert cr.wormhole is False  # 3e extension retirée
