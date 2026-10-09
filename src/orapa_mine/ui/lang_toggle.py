"""Sélecteur de langue (drapeaux France / Royaume-Uni), partagé par les écrans.

Placé en haut à droite de chaque écran. La langue active est mise en avant
(liseré doré) ; l'inactive est assombrie. Les positions sont calculées à partir
de la largeur de l'écran pour rester collées au bord droit quelle que soit la
taille de la fenêtre.
"""

from __future__ import annotations

import pygame

from orapa_mine.ui import i18n, theme

_FW, _FH, _GAP, _MARGIN, _TOP = 44, 28, 10, 24, 24


def rects(width: int) -> tuple[pygame.Rect, pygame.Rect]:
    """Rectangles des drapeaux FR puis UK, alignés à droite d'une fenêtre `width`."""
    fx = width - 2 * _FW - _GAP - _MARGIN
    fr = pygame.Rect(fx, _TOP, _FW, _FH)
    uk = pygame.Rect(fx + _FW + _GAP, _TOP, _FW, _FH)
    return fr, uk


def handle_click(pos: tuple[int, int], width: int) -> bool:
    """Applique la langue si un drapeau est cliqué. Renvoie True si consommé."""
    fr, uk = rects(width)
    if fr.collidepoint(pos):
        i18n.set_language("fr")
        return True
    if uk.collidepoint(pos):
        i18n.set_language("en")
        return True
    return False


def draw(surface: pygame.Surface) -> None:
    fr, uk = rects(surface.get_width())
    _draw_flag(surface, fr, "fr", active=i18n.LANG == "fr")
    _draw_flag(surface, uk, "uk", active=i18n.LANG == "en")


def _draw_flag(surface: pygame.Surface, rect: pygame.Rect, which: str, active: bool) -> None:
    if which == "fr":
        _draw_france(surface, rect)
    else:
        _draw_uk(surface, rect)
    if not active:
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((10, 12, 18, 150))
        surface.blit(shade, rect.topleft)
        pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1)
    else:
        pygame.draw.rect(surface, theme.SLOT_SELECTED, rect.inflate(6, 6), width=3, border_radius=3)


def _draw_france(surface: pygame.Surface, rect: pygame.Rect) -> None:
    third = rect.width / 3
    pygame.draw.rect(surface, (0, 85, 164), (rect.x, rect.y, third + 1, rect.height))
    pygame.draw.rect(surface, (240, 240, 245), (rect.x + third, rect.y, third + 1, rect.height))
    pygame.draw.rect(surface, (239, 65, 53), (rect.x + 2 * third, rect.y, third + 1, rect.height))


def _draw_uk(surface: pygame.Surface, rect: pygame.Rect) -> None:
    blue, white, red = (1, 33, 105), (240, 240, 245), (200, 16, 46)
    x, y, w, h = rect
    cx, cy = rect.centerx, rect.centery
    tl, tr, bl, br = rect.topleft, rect.topright, rect.bottomleft, rect.bottomright
    pygame.draw.rect(surface, blue, rect)
    clip = surface.get_clip()
    surface.set_clip(rect)
    # Croix de Saint-André (diagonales) : blanc épais puis rouge fin.
    pygame.draw.line(surface, white, tl, br, max(3, h // 5))
    pygame.draw.line(surface, white, tr, bl, max(3, h // 5))
    pygame.draw.line(surface, red, tl, br, max(2, h // 11))
    pygame.draw.line(surface, red, tr, bl, max(2, h // 11))
    # Croix de Saint-Georges : bande blanche puis rouge, horizontale + verticale.
    pygame.draw.rect(surface, white, (x, cy - h // 5, w, 2 * (h // 5)))
    pygame.draw.rect(surface, white, (cx - w // 8, y, w // 4, h))
    pygame.draw.rect(surface, red, (x, cy - h // 9, w, 2 * (h // 9)))
    pygame.draw.rect(surface, red, (cx - w // 13, y, 2 * (w // 13), h))
    surface.set_clip(clip)
