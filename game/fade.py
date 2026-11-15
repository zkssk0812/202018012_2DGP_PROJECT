"""화면 전환: 검게 어두워졌다가(out) 밝아진다(in).

    fade.out(시간, 끝나면 부를 함수)   어두워지고 나서 함수를 부른다 (보통 모드 바꾸기)
    fade.in_(시간)                     검은 화면에서 밝아진다
모드마다 update(dt) 와 draw() 를 불러 준다. 어두워지는 동안은 busy() 가 True (입력 막기용).
"""
import pico2d
from pico2d import draw_rectangle
from sdl2 import SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND

from config import SCREEN_W, SCREEN_H

alpha = 0.0           # 0 = 투명, 1 = 완전히 검음
_from, _to, _time, _total = 0.0, 0.0, 0.0, 0.0
_then = None


def out(duration, then=None):
    _start(alpha, 1.0, duration, then)


def in_(duration):
    _start(1.0, 0.0, duration, None)


def _start(a, b, duration, then):
    global alpha, _from, _to, _time, _total, _then
    alpha, _from, _to, _time, _total, _then = a, a, b, 0.0, max(duration, 1e-6), then


def busy():
    return _time < _total and _to == 1.0


def update(dt):
    global alpha, _time, _then
    if _time >= _total:
        return
    _time = min(_total, _time + dt)
    alpha = _from + (_to - _from) * (_time / _total)
    if _time >= _total and _then:
        fn, _then = _then, None
        fn()


def draw():
    if alpha <= 0.001:
        return
    SDL_SetRenderDrawBlendMode(pico2d.pico2d.renderer, SDL_BLENDMODE_BLEND)
    draw_rectangle(0, 0, SCREEN_W, SCREEN_H, 0, 0, 0, int(255 * alpha), filled=True)
