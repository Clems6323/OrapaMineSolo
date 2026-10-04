"""Internationalisation (FR / EN) de l'interface.

Approche volontairement simple : une langue courante au niveau module (réglée
par le bouton FR/EN du menu) et une fonction `t(fr, en)` qui renvoie la bonne
chaîne. Les traductions sont écrites **à côté** de leur usage (pas de table de
clés centrale), ce qui garantit qu'aucune chaîne n'est oubliée.

Les noms « données » (couleurs du rayon, pièces, tailles) viennent du modèle en
français ; `color()`, `piece()` et `size_name()` en donnent la version affichée.
"""

from __future__ import annotations

LANG = "fr"


def set_language(lang: str) -> None:
    global LANG
    LANG = "en" if lang == "en" else "fr"


def toggle() -> None:
    set_language("fr" if LANG == "en" else "en")


def t(fr: str, en: str) -> str:
    """Chaîne traduite selon la langue courante."""
    return en if LANG == "en" else fr


# Couleurs du rayon (clés = noms français du modèle) + états spéciaux.
_COLORS_EN = {
    "rouge": "red", "bleu": "blue", "jaune": "yellow", "blanc": "white",
    "orange": "orange", "vert": "green", "violet": "purple", "rose": "pink",
    "jaune clair": "light yellow", "bleu clair": "light blue",
    "vert clair": "light green", "orange clair": "light orange",
    "violet clair": "light purple", "noir": "black", "gris": "gray",
    "transparent": "transparent", "absorbé": "absorbed",
}

# Libellés de pièces dans la palette (couleurs + extensions).
_PIECES_EN = {
    "rouge": "red", "jaune": "yellow", "bleu": "blue", "blanc": "white",
    "diamant": "diamond", "corps-noir": "black body", "trou-de-ver": "wormhole",
}

_SIZES_EN = {"Petit": "Small", "Standard": "Standard", "Grand": "Large"}


def color(name: str | None) -> str:
    """Nom affiché d'une couleur de rayon (ou « transparent »)."""
    fr = name or "transparent"
    return _COLORS_EN.get(fr, fr) if LANG == "en" else fr


def piece(label: str) -> str:
    """Nom affiché d'une pièce de palette (à partir de son libellé français)."""
    return _PIECES_EN.get(label, label) if LANG == "en" else label


def size_name(fr: str) -> str:
    """Nom affiché d'une taille de grille (Petit/Standard/Grand)."""
    return _SIZES_EN.get(fr, fr) if LANG == "en" else fr
