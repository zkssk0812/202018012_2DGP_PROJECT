"""전투 화면 UI: HP 막대, 회피 쿨다운, QWER 기술 칸. (그림이 나오기 전 임시)"""
from pico2d import draw_rectangle

import skills
import ui
from config import DODGE_COOLDOWN, SCREEN_W, MOA_MAX_LEVEL

SLOT_W, SLOT_H, SLOT_GAP = 96, 56, 10


def bar(x, y, w, h, ratio, color, back=(40, 40, 40)):
    draw_rectangle(x, y, x + w, y + h, *back, filled=True)
    if ratio > 0:
        draw_rectangle(x, y, x + w * ratio, y + h, *color, filled=True)
    draw_rectangle(x, y, x + w, y + h, 230, 230, 230)


def draw_player(moa, slots=True):
    # 왼쪽 아래: 레벨 · 회피 쿨다운 / HP / 경험치
    ui.text(20, 72, f'Lv {moa.level}', 20, (255, 230, 120))
    ready = 1 - moa.dodge_cooldown / DODGE_COOLDOWN
    bar(84, 66, 120, 8, ready, (120, 180, 255) if ready >= 1 else (90, 110, 150))
    if moa.guard_time > 0:
        ui.text(214, 70, f'방어 {int(moa.guard_rate * 100)}%', 13, (150, 220, 255))

    bar(20, 34, 260, 18, moa.hp / moa.max_hp, (90, 220, 120))
    ui.text(26, 43, f'{moa.hp} / {moa.max_hp}', 13)

    if moa.level >= MOA_MAX_LEVEL:
        bar(20, 20, 260, 8, 1, (230, 200, 80))
        ui.text(288, 24, 'MAX', 12, (230, 200, 80))
    else:
        bar(20, 20, 260, 8, moa.exp / moa.exp_needed, (230, 200, 80))
        ui.text(288, 24, f'EXP {moa.exp} / {moa.exp_needed}', 12, (230, 200, 80))

    if moa.level_up_time > 0:
        ui.text(20, 100, 'LEVEL UP!', 22, (255, 240, 120))
    if slots:
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


def draw_notice(text):
    """화면 가운데 위 알림 (기술 획득 등)."""
    w = 24 + len(text) * 18                  # 한글 17pt 기준 대략적인 글자 폭
    x, y = (SCREEN_W - w) / 2, 600
    draw_rectangle(x, y, x + w, y + 36, 25, 20, 40, filled=True)
    draw_rectangle(x, y, x + w, y + 36, 200, 150, 255)
    ui.text(x + 12, y + 18, text, 17, (240, 230, 255))


def draw_absorb_prompt(moa, camera):
    """흡수 범위 안에 들어오면 모아 머리 위에 F 안내 (psd 4.1)."""
    sx, sy = camera.to_screen(moa.x, moa.y)
    x, y = sx + 26, sy + 30                  # 모아 오른쪽 위 (상대의 HP 바를 가리지 않게)
    draw_rectangle(x, y, x + 26, y + 26, 30, 20, 45, filled=True)
    draw_rectangle(x, y, x + 26, y + 26, 200, 150, 255)
    ui.text(x + 8, y + 13, 'F', 18, (230, 210, 255))


def draw_enemy(enemy, camera):
    sx, sy = camera.to_screen(enemy.x, enemy.y)
    bar(sx - 40, sy + 70, 80, 8, enemy.hp / enemy.max_hp, (230, 80, 80))
    ui.text(sx - 82, sy + 74, f'Lv{enemy.level}', 14, (255, 230, 120))
    if enemy.state == 'faint':
        ui.text(sx - 16, sy + 88, '기절', 14, (255, 230, 120))
