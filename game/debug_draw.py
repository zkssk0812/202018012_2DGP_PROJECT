"""관리자 모드에서 몸 원과 기술 판정 도형을 선으로 그린다 (psd 4.8, 5.3)."""
import math

from pico2d import draw_circle, draw_line, draw_rectangle

from collision import Circle, Sector, Capsule

HURTBOX_COLOR = (255, 30, 30)          # 피격 범위 (U)
HURTBOX_OFF_COLOR = (150, 150, 150)    # 무적이라 지금은 맞지 않는 피격 범위
HIT_COLOR = (255, 150, 0)              # 공격 판정이 켜져 있을 때
HIT_WAIT_COLOR = (255, 230, 120)       # 공격 판정이 켜지기 전 (예고)
ARENA_COLOR = (255, 255, 0)


def body(obj, camera, color):
    sx, sy = camera.to_screen(obj.x, obj.y)
    draw_circle(int(sx), int(sy), int(obj.radius), *color)


def hurtbox(obj, camera):
    """피격 범위: 몸 원을 붉은색 두 줄로 그리고 가운데에 점을 찍는다. 무적이면 회색."""
    color = HURTBOX_OFF_COLOR if obj.is_invincible else HURTBOX_COLOR
    sx, sy = camera.to_screen(obj.x, obj.y)
    r = int(obj.radius)
    draw_circle(int(sx), int(sy), r, *color)
    draw_circle(int(sx), int(sy), r - 1, *color)
    draw_circle(int(sx), int(sy), 3, *color, filled=True)


def arena(rect, camera, color=ARENA_COLOR):
    l, b, r, t = rect
    x1, y1 = camera.to_screen(l, b)
    x2, y2 = camera.to_screen(r, t)
    draw_rectangle(x1, y1, x2, y2, *color)


def shape(s, camera, color=HIT_COLOR):
    if isinstance(s, Circle):
        sx, sy = camera.to_screen(s.x, s.y)
        draw_circle(int(sx), int(sy), int(s.r), *color)
    elif isinstance(s, Sector):
        _sector(s, camera, color)
    elif isinstance(s, Capsule):
        _capsule(s, camera, color)


def _sector(s, camera, color, steps=16):
    ox, oy = camera.to_screen(s.x, s.y)
    a0 = s.angle - s.width / 2
    points = [(ox + math.cos(a0 + s.width * i / steps) * s.r,
               oy + math.sin(a0 + s.width * i / steps) * s.r) for i in range(steps + 1)]
    draw_line(ox, oy, *points[0], *color)
    draw_line(ox, oy, *points[-1], *color)
    for p, q in zip(points, points[1:]):
        draw_line(*p, *q, *color)


def _capsule(s, camera, color):
    x1, y1 = camera.to_screen(s.x1, s.y1)
    x2, y2 = camera.to_screen(s.x2, s.y2)
    draw_circle(int(x1), int(y1), int(s.r), *color)
    draw_circle(int(x2), int(y2), int(s.r), *color)
    length = math.hypot(x2 - x1, y2 - y1) or 1
    nx, ny = -(y2 - y1) / length * s.r, (x2 - x1) / length * s.r     # 선분에 수직인 방향
    draw_line(x1 + nx, y1 + ny, x2 + nx, y2 + ny, *color)
    draw_line(x1 - nx, y1 - ny, x2 - nx, y2 - ny, *color)
