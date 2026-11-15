"""전투 화면 UI: HP 막대, 회피 쿨다운. (그림이 나오기 전 임시 막대)"""
from pico2d import draw_rectangle

from config import DODGE_COOLDOWN


def bar(x, y, w, h, ratio, color, back=(40, 40, 40)):
    draw_rectangle(x, y, x + w, y + h, *back, filled=True)
    if ratio > 0:
        draw_rectangle(x, y, x + w * ratio, y + h, *color, filled=True)
    draw_rectangle(x, y, x + w, y + h, 230, 230, 230)


def draw_player(moa):
    bar(20, 20, 260, 18, moa.hp / moa.max_hp, (90, 220, 120))
    ready = 1 - moa.dodge_cooldown / DODGE_COOLDOWN
    bar(20, 44, 120, 8, ready, (120, 180, 255) if ready >= 1 else (90, 110, 150))


def draw_enemy(enemy, camera):
    sx, sy = camera.to_screen(enemy.x, enemy.y)
    bar(sx - 40, sy + 70, 80, 8, enemy.hp / enemy.max_hp, (230, 80, 80))
