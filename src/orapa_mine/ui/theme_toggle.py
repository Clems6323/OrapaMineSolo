"""Bouton de bascule mode sombre / clair (soleil / lune), partagé par les écrans.

Placé en haut à gauche de chaque écran. Il montre l'icône du mode vers lequel il
fait basculer : en mode sombre un **soleil** (clic -> clair), en mode clair une
**lune** (clic -> sombre).
"""

from __future__ import annotations

import math

import pygame

from orapa_mine.ui import theme

RECT = pygame.Rect(16, 16, 34, 34)


def hit(pos: tuple[int, int]) -> bool:
    """Vrai si `pos` est sur le bouton (à appeler avant la bascule)."""
    return RECT.collidepoint(pos)


def toggle() -> None:
    theme.toggle_mode()


def draw(surface: pygame.Surface) -> None:
    pygame.draw.rect(surface, theme.SLOT_BG, RECT, border_radius=8)
    pygame.draw.rect(surface, theme.BOARD_BORDER, RECT, width=1, border_radius=8)
    cx, cy = RECT.center
    if theme.MODE == "dark":  # propose de passer en clair -> soleil
        sun = (245, 200, 70)
        pygame.draw.circle(surface, sun, (cx, cy), 6)
        for i in range(8):
            a = i * math.pi / 4
            p1 = (cx + 9 * math.cos(a), cy + 9 * math.sin(a))
            p2 = (cx + 13 * math.cos(a), cy + 13 * math.sin(a))
            pygame.draw.line(surface, sun, p1, p2, 2)
    else:  # propose de passer en sombre -> lune (croissant)
        moon = (70, 84, 128)
        pygame.draw.circle(surface, moon, (cx, cy), 9)
        pygame.draw.circle(surface, theme.SLOT_BG, (cx + 4, cy - 3), 8)
