"""디버깅용 관리자 모드 (psd 4.8).

T 로 켜고 끈다. 켜져 있으면 화면 구석에 ADMIN 을 띄우고 판정 도형을 그린다.
G(전투 중 즉사)와 K(기술 선택)는 기술·흡수가 생기는 2주차에 붙인다.
"""
import os

from pico2d import load_font, draw_rectangle

from config import SCREEN_H

enabled = False
_font = None
FONT_PATHS = [r'C:\Windows\Fonts\malgun.ttf', r'C:\Windows\Fonts\arial.ttf']


def toggle():
    global enabled
    enabled = not enabled


def _get_font():
    global _font
    if _font is None:
        for p in FONT_PATHS:
            if os.path.exists(p):
                _font = load_font(p, 18)
                break
    return _font


def draw_label():
    font = _get_font()
    if font:
        font.draw(14, SCREEN_H - 20, 'ADMIN', (255, 230, 0))
    else:                                  # 글꼴이 없으면 노란 네모로 표시
        draw_rectangle(10, SCREEN_H - 30, 80, SCREEN_H - 10, 255, 230, 0)
