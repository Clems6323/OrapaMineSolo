"""Régression #38 : (dé)cocher une extension ne doit pas recréer la fenêtre.

Recréer la fenêtre (set_mode) à chaque bascule d'extension provoquait un bref
flash noir. Seul un vrai changement de taille de grille doit demander un resize.
"""

from __future__ import annotations

from orapa_mine.ui.creator_screen import CreatorScreen


def test_toggling_extension_keeps_same_window():
    # Avec une extension déjà active (palette à 2 colonnes), (dé)cocher une AUTRE
    # extension garde la même fenêtre → aucun set_mode → pas de flash (#38).
    cr = CreatorScreen(size_index=1, diamant=True)
    cr.pending_resize = False
    before = cr.size
    cr.corps_noir = not cr.corps_noir
    cr._rebuild(clear_gems=False)
    assert cr.size == before
    assert cr.pending_resize is False


def test_first_extension_widens_window():
    # Passer de 0 à 1 extension ajoute la 2e colonne de palette : la fenêtre
    # s'élargit vraiment (resize légitime, pas un flash inutile).
    cr = CreatorScreen(size_index=1)
    cr.pending_resize = False
    before_w = cr.size[0]
    cr.diamant = True
    cr._rebuild(clear_gems=False)
    assert cr.size[0] > before_w
    assert cr.pending_resize is True


def test_changing_grid_size_requests_resize():
    cr = CreatorScreen(size_index=1)     # Standard 10×8
    cr.pending_resize = False
    cr.size_index = 2                    # Grand 12×10
    cr._rebuild(clear_gems=True)
    assert cr.pending_resize is True     # la fenêtre change vraiment de taille
