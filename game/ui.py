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


def eul(word):
    """받침이 있으면 '을', 없으면 '를' 을 붙인다. 예) 할퀴기를, 이슬탄을"""
    last = word[-1]
    if '가' <= last <= '힣':
        return word + ('을' if (ord(last) - 0xAC00) % 28 else '를')
    return word + '을(를)'


def i_ga(word):
    """받침이 있으면 '이', 없으면 '가' 를 붙인다. 예) 노움이, 실프가"""
    last = word[-1]
    if '가' <= last <= '힣':
        return word + ('이' if (ord(last) - 0xAC00) % 28 else '가')
    return word + '이(가)'


def text(x, y, s, size=16, color=(255, 255, 255)):
    f = font(size)
    if f:
        f.draw(x, y, s, color)
