"""Petit stepper numérique « − valeur + » (sans saisie clavier).

Widget léger partagé (écran de configuration, mode créateur) pour régler un
entier borné via deux boutons. L'appelant fournit le **texte affiché** dans la
case (p. ex. « ∞ » pour 0), ce qui garde le widget générique.
"""

from __future__ import annotations

import pygame

from orapa_mine.ui import theme


class StepperField:
    """Stepper − valeur + pour un entier dans [min_value, max_value]."""

    def __init__(self, value: int = 0, min_value: int = 0, max_value: int = 99) -> None:
        self.min_value = min_value
        self.max_value = max_value
        self.value = max(min_value, min(max_value, int(value)))
        self.minus_rect = pygame.Rect(0, 0, 0, 0)
        self.value_rect = pygame.Rect(0, 0, 0, 0)
        self.plus_rect = pygame.Rect(0, 0, 0, 0)

    def set_rects(self, minus: pygame.Rect, value: pygame.Rect, plus: pygame.Rect) -> None:
        self.minus_rect, self.value_rect, self.plus_rect = minus, value, plus

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Traite un clic gauche ; renvoie True s'il concernait le − ou le +."""
        if self.minus_rect.collidepoint(pos):
            self.value = max(self.min_value, self.value - 1)
            return True
        if self.plus_rect.collidepoint(pos):
            self.value = min(self.max_value, self.value + 1)
            return True
        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, text: str) -> None:
        """Dessine − valeur +, avec `text` (calculé par l'appelant) dans la case."""
        for rect, glyph in ((self.minus_rect, "−"), (self.plus_rect, "+")):
            pygame.draw.rect(surface, theme.SLOT_BG, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            g = font.render(glyph, True, theme.TEXT)
            surface.blit(g, g.get_rect(center=rect.center))
        pygame.draw.rect(surface, theme.INPUT_BG, self.value_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BOARD_BORDER, self.value_rect, width=1, border_radius=8)
        val = font.render(text, True, theme.TEXT)
        surface.blit(val, val.get_rect(center=self.value_rect.center))
