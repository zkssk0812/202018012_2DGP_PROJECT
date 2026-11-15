"""관리자 기술 선택 창 (K, psd 4.8).

전투 위에 겹쳐 뜨고, 열려 있는 동안 게임은 멈춘다.
    ↑ ↓      기술 고르기
    Q W E R  고른 기술을 그 칸에 넣기 (이미 그 칸에 있으면 빼기). 잠긴 칸(E·R)에도 넣을 수 있다.
    K / Esc  닫기
"""
from pico2d import get_events, draw_rectangle
from sdl2 import (SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_k, SDLK_UP, SDLK_DOWN,
                  SDLK_q, SDLK_w, SDLK_e, SDLK_r)

import battle_mode
import game_framework
import skills
import ui
from config import SCREEN_W, SCREEN_H

SLOT_KEYS = {SDLK_q: 0, SDLK_w: 1, SDLK_e: 2, SDLK_r: 3}
PANEL_W, ROW_H = 640, 26

cursor = 0


def init():
    pass


def finish():
    battle_mode.moa.held.clear()      # 창이 열린 동안 뗀 방향키가 눌린 채로 남지 않게


def handle_events():
    global cursor
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type != SDL_KEYDOWN:
            continue
        elif e.key in (SDLK_ESCAPE, SDLK_k):
            game_framework.pop_mode()
            return
        elif e.key == SDLK_UP:
            cursor = (cursor - 1) % len(skills.ORDER)
        elif e.key == SDLK_DOWN:
            cursor = (cursor + 1) % len(skills.ORDER)
        elif e.key in SLOT_KEYS:
            assign(SLOT_KEYS[e.key], skills.ORDER[cursor])


def assign(i, skill_id):
    moa = battle_mode.moa
    if moa.slots[i].skill_id == skill_id:
        moa.clear_slot(i)
    else:
        moa.set_slot(i, skill_id, forced=True)


def update(dt):
    pass                                  # 멈춤


def draw():
    battle_mode.draw()
    moa = battle_mode.moa
    rows = len(skills.ORDER)
    h = 140 + rows * ROW_H
    x0, y_top = (SCREEN_W - PANEL_W) / 2, SCREEN_H - 44     # ADMIN 글씨 아래, 기술 칸 위
    draw_rectangle(x0, y_top - h, x0 + PANEL_W, y_top, 18, 22, 30, filled=True)
    draw_rectangle(x0, y_top - h, x0 + PANEL_W, y_top, 255, 230, 0)

    ui.text(x0 + 16, y_top - 22, '기술 선택 (관리자)', 20, (255, 230, 0))
    ui.text(x0 + 16, y_top - 48, '↑↓ 고르기   Q W E R 칸에 넣기/빼기   K·Esc 닫기', 14, (200, 200, 200))
    hx = (x0 + 40, x0 + 200, x0 + 310, x0 + 370, x0 + 440)
    for x, label in zip(hx, ('기술', '종류', '위력', '쿨다운', '칸')):
        ui.text(x, y_top - 78, label, 14, (150, 150, 150))

    where = {s.skill_id: s.key for s in moa.slots if s.skill_id}
    for k, sid in enumerate(skills.ORDER):
        info = skills.info(sid)
        y = y_top - 104 - k * ROW_H
        if k == cursor:
            draw_rectangle(x0 + 8, y - 12, x0 + PANEL_W - 8, y + 12, 60, 70, 100, filled=True)
            ui.text(x0 + 16, y, '▶', 14, (255, 230, 0))
        color = (255, 255, 255) if k == cursor else (210, 210, 210)
        power = info.get('power')
        power_text = '-' if power is None else (f'{power} × {info["hits"]}' if 'hits' in info else
                                                f'{power} × {info["count"]}' if 'count' in info else str(power))
        ui.text(hx[0], y, info['name'], 15, color)
        ui.text(hx[1], y, skills.KIND_NAMES[info['kind']], 14, color)
        ui.text(hx[2], y, power_text, 14, color)
        ui.text(hx[3], y, f'{info["cooldown"]:g}초', 14, color)
        if sid in where:
            ui.text(hx[4], y, where[sid], 15, (255, 230, 120))

    # 지금 칸 상태
    y = y_top - h + 16
    for i, s in enumerate(moa.slots):
        name = skills.info(s.skill_id)['name'] if s.skill_id else '-'
        lock = '' if moa.slot_open(i) or not s.skill_id else ' (잠김)'
        tag = ' *' if s.forced else ''
        ui.text(x0 + 16 + i * 155, y, f'{s.key}: {name}{tag}{lock}', 14, (255, 230, 120))
