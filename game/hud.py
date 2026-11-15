"""전투 화면 UI: HP 막대, 회피 쿨다운, QWER 기술 칸. (그림이 나오기 전 임시)"""
from pico2d import draw_rectangle

import skills
import ui
from config import DODGE_COOLDOWN, SCREEN_W

SLOT_W, SLOT_H, SLOT_GAP = 96, 56, 10


def bar(x, y, w, h, ratio, color, back=(40, 40, 40)):
    draw_rectangle(x, y, x + w, y + h, *back, filled=True)
    if ratio > 0:
        draw_rectangle(x, y, x + w * ratio, y + h, *color, filled=True)
    draw_rectangle(x, y, x + w, y + h, 230, 230, 230)


def draw_player(moa):
    bar(20, 20, 260, 18, moa.hp / moa.max_hp, (90, 220, 120))
    ui.text(26, 29, f'{moa.hp} / {moa.max_hp}', 13)
    ready = 1 - moa.dodge_cooldown / DODGE_COOLDOWN
    bar(20, 44, 120, 8, ready, (120, 180, 255) if ready >= 1 else (90, 110, 150))
    if moa.guard_time > 0:
        ui.text(150, 48, f'방어 {int(moa.guard_rate * 100)}%', 13, (150, 220, 255))
    draw_slots(moa)


def draw_slots(moa):
    total = 4 * SLOT_W + 3 * SLOT_GAP
    x0 = (SCREEN_W - total) / 2
    y = 16
    for i, slot in enumerate(moa.slots):
        x = x0 + i * (SLOT_W + SLOT_GAP)
        opened = moa.slot_open(i)
        draw_rectangle(x, y, x + SLOT_W, y + SLOT_H, *((30, 40, 50) if opened else (20, 20, 20)), filled=True)
        if slot.skill_id and slot.cooldown > 0:            # 쿨다운: 남은 비율만큼 아래부터 어둡게
            ratio = slot.cooldown / skills.info(slot.skill_id)['cooldown']
            draw_rectangle(x, y, x + SLOT_W, y + SLOT_H * ratio, 10, 10, 10, filled=True)
        edge = (255, 200, 80) if slot.forced else (200, 200, 200) if opened else (90, 90, 90)
        draw_rectangle(x, y, x + SLOT_W, y + SLOT_H, *edge)
        ui.text(x + 6, y + SLOT_H - 12, slot.key, 14, (255, 230, 120))
        if slot.skill_id:
            ui.text(x + 6, y + 18, skills.info(slot.skill_id)['name'], 13,
                    (255, 255, 255) if opened else (120, 120, 120))
            if slot.cooldown > 0:
                ui.text(x + SLOT_W - 34, y + SLOT_H - 12, f'{slot.cooldown:.1f}', 12, (200, 200, 200))
        elif not opened:
            ui.text(x + 6, y + 18, f'Lv{slot.unlock_level}', 13, (120, 120, 120))


def draw_enemy(enemy, camera):
    sx, sy = camera.to_screen(enemy.x, enemy.y)
    bar(sx - 40, sy + 70, 80, 8, enemy.hp / enemy.max_hp, (230, 80, 80))
    if enemy.state == 'faint':
        ui.text(sx - 16, sy + 88, '기절', 14, (255, 230, 120))
