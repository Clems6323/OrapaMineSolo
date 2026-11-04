"""Correspondance entre les identifiants « fil » (ASCII, stables) et le modèle.

Les identifiants exposés aux participants sont des chaînes ASCII minuscules
stables (issue #90), indépendantes des noms internes (français) des pièces et
des couleurs. Ce module est l'**unique source de vérité** de cette traduction,
utilisée à la frontière du protocole (session, arbitre, SDK).
"""

from __future__ import annotations

from orapa_mine.model import gems_catalog as cat
from orapa_mine.model.gems import GemColor, GemKind, Piece

# --- Pièces : id fil (ASCII) <-> Piece.name (interne, français) --------------

PIECE_ID_TO_NAME: dict[str, str] = {
    "red": "rouge",
    "yellow": "jaune",
    "blue": "bleu",
    "white-big": "blanc-grand",
    "white-small": "blanc-petit",
    "diamond": "diamant",
    "filter": "filtre",
    "black-body": "corps-noir",
    "wormhole": "trou-de-ver",
    "mystery": "mystère",
}
NAME_TO_PIECE_ID: dict[str, str] = {name: wid for wid, name in PIECE_ID_TO_NAME.items()}

# Garde-fou : la table couvre exactement les pièces du catalogue (détecte toute
# dérive si une pièce est ajoutée/renommée côté modèle).
assert set(NAME_TO_PIECE_ID) == set(cat.ALL_PIECES), (
    "La table des identifiants de pièces diverge du catalogue : "
    f"{set(NAME_TO_PIECE_ID) ^ set(cat.ALL_PIECES)}"
)


def piece_id(piece_name: str) -> str:
    """Identifiant fil (ASCII) d'un `Piece.name` interne."""
    return NAME_TO_PIECE_ID[piece_name]


def piece_by_id(wire_id: str) -> Piece | None:
    """Pièce du catalogue pour un identifiant fil, ou None si inconnu."""
    name = PIECE_ID_TO_NAME.get(wire_id)
    return cat.ALL_PIECES[name] if name is not None else None


# --- Couleurs : GemColor <-> token ASCII -------------------------------------

COLOR_TO_ASCII: dict[GemColor, str] = {
    GemColor.RED: "red",
    GemColor.YELLOW: "yellow",
    GemColor.BLUE: "blue",
    GemColor.WHITE: "white",
}
ASCII_TO_COLOR: dict[str, GemColor] = {tok: c for c, tok in COLOR_TO_ASCII.items()}

# Couleur d'un rayon : le moteur renvoie un **nom français** (table de mélange),
# qu'on traduit en token ASCII stable pour le fil.
RAY_COLOR_TO_ASCII: dict[str, str] = {
    "rouge": "red",
    "bleu": "blue",
    "jaune": "yellow",
    "blanc": "white",
    "orange": "orange",
    "vert": "green",
    "violet": "purple",
    "rose": "pink",
    "jaune clair": "light-yellow",
    "bleu clair": "light-blue",
    "noir": "black",
    "vert clair": "light-green",
    "orange clair": "light-orange",
    "violet clair": "light-purple",
    "gris": "gray",
}


def color_to_ascii(color: GemColor) -> str:
    """Token ASCII d'une `GemColor` (question de case, gemme révélée)."""
    return COLOR_TO_ASCII[color]


def ascii_to_color(token: str) -> GemColor | None:
    """`GemColor` d'un token ASCII, ou None si invalide (couleur mystère devinée)."""
    return ASCII_TO_COLOR.get(token)


def ray_color_to_ascii(name: str | None) -> str | None:
    """Token ASCII de la couleur annoncée d'un rayon (None si transparent)."""
    if name is None:
        return None
    return RAY_COLOR_TO_ASCII.get(name, name)


# --- Extensions : GemKind -> token ASCII (réponse à une question de case) -----

# Seules les extensions « révélées par leur nature » apparaissent : le diamant,
# le filtre, le corps noir et le trou de ver. La gemme mystère révèle sa
# COULEUR (comme une gemme normale), pas sa nature (issue #77).
EXTENSION_KIND_TO_ASCII: dict[GemKind, str] = {
    GemKind.DIAMOND: "diamond",
    GemKind.FILTER: "filter",
    GemKind.BLACK_BODY: "black-body",
    GemKind.WORMHOLE: "wormhole",
}


def kind_to_ascii(kind: GemKind) -> str | None:
    """Token ASCII d'une extension révélée par une question de case, sinon None."""
    return EXTENSION_KIND_TO_ASCII.get(kind)
