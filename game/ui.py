"""글꼴 불러오기 (한글이 나오는 맑은 고딕, 없으면 Arial)."""
import os

from pico2d import load_font

FONT_PATHS = [r'C:\Windows\Fonts\malgun.ttf', r'C:\Windows\Fonts\arial.ttf']
_fonts = {}


def font(size=16):
    if size not in _fonts:
        _fonts[size] = None
        for p in FONT_PATHS:
            if os.path.exists(p):
                _fonts[size] = load_font(p, size)
                break
    return _fonts[size]


def text(x, y, s, size=16, color=(255, 255, 255)):
    f = font(size)
    if f:
        f.draw(x, y, s, color)
