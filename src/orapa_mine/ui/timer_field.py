"""Champ de saisie du minuteur : stepper − valeur + **et** saisie au clavier.

Widget partagé par l'écran de configuration et le mode créateur. La valeur est
en minutes, bornée à [0, MAX] (0 = minuteur désactivé). On peut l'ajuster avec
les boutons − / + ou en cliquant la case centrale puis en tapant un nombre.
"""

from __future__ import annotations

import pygame

from orapa_mine.ui import theme

MAX_MINUTES = 60


class TimerField:
    """Stepper éditable pour un minuteur en minutes (0 = désactivé)."""

    def __init__(self, minutes: int = 0) -> None:
        self.minutes = max(0, min(MAX_MINUTES, int(minutes)))
        self.active = False  # saisie clavier en cours
        self._text = ""
        self._fresh = False  # True juste après la prise de focus (1re frappe = remplace)
        self.minus_rect = pygame.Rect(0, 0, 0, 0)
        self.value_rect = pygame.Rect(0, 0, 0, 0)
        self.plus_rect = pygame.Rect(0, 0, 0, 0)

    def set_rects(self, minus: pygame.Rect, value: pygame.Rect, plus: pygame.Rect) -> None:
        self.minus_rect, self.value_rect, self.plus_rect = minus, value, plus

    # --- Interaction -------------------------------------------------------

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Traite un clic gauche. Renvoie True si le clic concernait le champ.

        Un clic en dehors des trois rectangles valide et ferme la saisie en
        cours (mais renvoie False pour laisser l'appelant traiter ce clic).
        """
        if self.minus_rect.collidepoint(pos):
            self._commit()
            self.minutes = max(0, self.minutes - 1)
            return True
        if self.plus_rect.collidepoint(pos):
            self._commit()
            self.minutes = min(MAX_MINUTES, self.minutes + 1)
            return True
        if self.value_rect.collidepoint(pos):
            self.active = True
            self._fresh = True  # la 1re frappe remplace la valeur affichée
            self._text = str(self.minutes) if self.minutes else ""
            return True
        self._commit()  # clic ailleurs : on valide la saisie éventuelle
        return False

    def handle_key(self, event: pygame.event.Event) -> bool:
        """Traite une touche quand la saisie est active. Renvoie True si consommée."""
        if not self.active:
            return False
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self._commit()
        elif event.key == pygame.K_BACKSPACE:
            self._fresh = False
            self._text = self._text[:-1]
        elif event.unicode.isdigit():
            base = "" if self._fresh else self._text
            self._fresh = False
            candidate = base + event.unicode
            if len(candidate) <= 2 and int(candidate) <= MAX_MINUTES:
                self._text = candidate
        return True

    def _commit(self) -> None:
        if self.active:
            self.minutes = min(MAX_MINUTES, int(self._text or 0))
            self.active = False

    # --- Rendu -------------------------------------------------------------

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, off_label: str) -> None:
        for rect, glyph in ((self.minus_rect, "−"), (self.plus_rect, "+")):
            pygame.draw.rect(surface, theme.SLOT_BG, rect, border_radius=8)
            pygame.draw.rect(surface, theme.BOARD_BORDER, rect, width=1, border_radius=8)
            g = font.render(glyph, True, theme.TEXT)
            surface.blit(g, g.get_rect(center=rect.center))
        pygame.draw.rect(surface, theme.INPUT_BG, self.value_rect, border_radius=8)
        edge = theme.INPUT_ACTIVE if self.active else theme.BOARD_BORDER
        pygame.draw.rect(surface, edge, self.value_rect,
                         width=2 if self.active else 1, border_radius=8)
        if self.active:
            text = (self._text or "") + "|"
        elif self.minutes <= 0:
            text = off_label
        else:
            text = f"{self.minutes} min"
        val = font.render(text, True, theme.TEXT)
        surface.blit(val, val.get_rect(center=self.value_rect.center))
