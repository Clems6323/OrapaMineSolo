"""Le libellé du dernier tir de test se traduit quand la langue change.

Avant, `fire()` figeait la chaîne dans la langue courante : basculer FR/EN ne
la retraduisait pas.
"""

from __future__ import annotations

import pygame

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import Position
from orapa_mine.model.grid import Grid
from orapa_mine.ui import i18n, theme
from orapa_mine.ui.beam_test import RayTester


def test_last_test_follows_language_toggle():
    pygame.font.init()
    theme.window_size(10, 8)  # configure la géométrie (point_px, étiquettes…)
    rt = RayTester(10, 8, pygame.font.SysFont("arial", 15))
    grid = Grid(width=10, height=8)
    grid.place_gem(cat.BLACK_BODY.at(Position(3, 3)))
    # Tire jusqu'à obtenir une absorption (résultat « absorbé » / « absorbed »).
    for ep in rt.entries:
        if rt.fire(grid, ep).absorbed:
            break
    else:  # pragma: no cover - devrait toujours trouver une absorption
        raise AssertionError("aucun tir absorbé trouvé")

    try:
        i18n.set_language("fr")
        assert "absorbé" in rt.last_test
        i18n.set_language("en")
        assert "absorbed" in rt.last_test
        assert "absorbé" not in rt.last_test  # bien retraduit, pas figé en FR
    finally:
        i18n.set_language("fr")
