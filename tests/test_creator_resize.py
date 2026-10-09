"""Régression #38 : (dé)cocher une extension ne doit pas recréer la fenêtre.

Recréer la fenêtre (set_mode) à chaque bascule d'extension provoquait un bref
flash noir. Seul un vrai changement de taille de grille doit demander un resize.
"""

from __future__ import annotations

from orapa_mine.ui.creator_screen import CreatorScreen


def test_toggling_extension_keeps_same_window():
    cr = CreatorScreen(size_index=1)
    cr.pending_resize = False
    before = cr.size
    cr.diamant = not cr.diamant          # (dé)coche le diamant
    cr._rebuild(clear_gems=False)
    assert cr.size == before             # même fenêtre
    assert cr.pending_resize is False    # aucun set_mode demandé -> pas de flash


def test_changing_grid_size_requests_resize():
    cr = CreatorScreen(size_index=1)     # Standard 10×8
    cr.pending_resize = False
    cr.size_index = 2                    # Grand 12×10
    cr._rebuild(clear_gems=True)
    assert cr.pending_resize is True     # la fenêtre change vraiment de taille
