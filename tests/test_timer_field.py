"""Tests du widget de minuteur (ui.timer_field) : stepper + saisie clavier."""

from __future__ import annotations

import pygame

from orapa_mine.ui.timer_field import MAX_MINUTES, TimerField


def _field() -> TimerField:
    tf = TimerField()
    tf.set_rects(
        pygame.Rect(0, 0, 10, 10),   # minus
        pygame.Rect(20, 0, 40, 10),  # value
        pygame.Rect(70, 0, 10, 10),  # plus
    )
    return tf


def _digit(ch: str) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch)


def _key(code: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="")


def test_plus_minus_clamp():
    tf = _field()
    tf.handle_click((5, 5))  # minus at 0 -> stays 0
    assert tf.minutes == 0
    for _ in range(3):
        tf.handle_click((75, 5))  # plus
    assert tf.minutes == 3


def test_plus_clamps_to_max():
    tf = _field()
    for _ in range(MAX_MINUTES + 5):
        tf.handle_click((75, 5))
    assert tf.minutes == MAX_MINUTES


def test_typing_a_custom_number():
    tf = _field()
    tf.handle_click((30, 5))  # focus value box
    tf.handle_key(_digit("4"))
    tf.handle_key(_digit("5"))
    tf.handle_key(_key(pygame.K_RETURN))
    assert tf.minutes == 45 and tf.active is False


def test_typing_rejects_above_max():
    tf = _field()
    tf.handle_click((30, 5))
    tf.handle_key(_digit("9"))
    tf.handle_key(_digit("9"))  # "99" > 60 -> refusé, reste "9"
    tf.handle_key(_key(pygame.K_RETURN))
    assert tf.minutes == 9


def test_first_keystroke_replaces_value():
    tf = TimerField(5)
    tf.set_rects(pygame.Rect(0, 0, 10, 10), pygame.Rect(20, 0, 40, 10), pygame.Rect(70, 0, 10, 10))
    tf.handle_click((30, 5))   # focus : affiche 5
    tf.handle_key(_digit("3"))  # remplace -> "3", pas "53"
    tf.handle_key(_key(pygame.K_RETURN))
    assert tf.minutes == 3


def test_click_elsewhere_commits():
    tf = _field()
    tf.handle_click((30, 5))
    tf.handle_key(_digit("7"))
    assert tf.handle_click((500, 500)) is False  # clic hors champ
    assert tf.minutes == 7 and tf.active is False
