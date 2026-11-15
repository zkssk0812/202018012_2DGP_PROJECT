"""기술 교체 창 (psd 4.1): 흡수로 기술을 얻었는데 열린 칸이 꽉 찼을 때 뜬다.

전투 위에 겹쳐 뜨고, 열려 있는 동안 게임은 멈춘다.
    Q W E R   그 칸의 기술을 버리고 새 기술을 넣는다 (열린 칸만)
    Esc / X   버리지 않기 (새 기술을 받지 않음)
"""
from pico2d import get_events, draw_rectangle
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_x, SDLK_q, SDLK_w, SDLK_e, SDLK_r

import battle_mode
import game_framework
import skills
import ui
from config import SCREEN_W, SCREEN_H

SLOT_KEYS = {SDLK_q: 0, SDLK_w: 1, SDLK_e: 2, SDLK_r: 3}
PANEL_W, PANEL_H = 560, 230

new_skill = None          # 이번에 얻은 기술 id (열기 전에 정해 둔다)


def open_for(skill_id):
    global new_skill
    new_skill = skill_id
    game_framework.push_mode(__import__('skill_swap_mode'))


def init():
    pass


def finish():
    battle_mode.moa.held.clear()


def handle_events():
    moa = battle_mode.moa
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type != SDL_KEYDOWN:
            continue
        elif e.key in (SDLK_ESCAPE, SDLK_x):
            battle_mode.notice(f'{ui.eul(skills.info(new_skill)["name"])} 받지 않았다')
            game_framework.pop_mode()
            return
        elif e.key in SLOT_KEYS and moa.slot_open(SLOT_KEYS[e.key]):
            i = SLOT_KEYS[e.key]
            old = moa.slots[i].skill_id
            moa.set_slot(i, new_skill)
            old_name = skills.info(old)['name'] if old else '빈칸'
            battle_mode.notice(f'{old_name} 대신 {ui.eul(skills.info(new_skill)["name"])} {moa.slots[i].key}에 넣었다')
            game_framework.pop_mode()
            return


def update(dt):
    pass


def draw():
    battle_mode.draw()
    moa = battle_mode.moa
    x0, y0 = (SCREEN_W - PANEL_W) / 2, (SCREEN_H - PANEL_H) / 2 + 40
    draw_rectangle(x0, y0, x0 + PANEL_W, y0 + PANEL_H, 18, 22, 30, filled=True)
    draw_rectangle(x0, y0, x0 + PANEL_W, y0 + PANEL_H, 200, 150, 255)

    info = skills.info(new_skill)
    top = y0 + PANEL_H
    ui.text(x0 + 20, top - 26, '새 기술을 얻었다!', 20, (230, 210, 255))
    ui.text(x0 + 20, top - 58, f'{info["name"]}  ·  {skills.KIND_NAMES[info["kind"]]}  ·  '
                               f'위력 {info.get("power") or "-"}  ·  쿨다운 {info["cooldown"]:g}초', 16)
    ui.text(x0 + 20, top - 90, '칸이 꽉 찼다. 버릴 기술의 칸을 누르세요.', 15, (200, 200, 200))

    for i, s in enumerate(moa.slots):
        bx, by = x0 + 20 + i * 132, top - 170
        opened = moa.slot_open(i)
        draw_rectangle(bx, by, bx + 120, by + 56, *((30, 40, 50) if opened else (20, 20, 20)), filled=True)
        draw_rectangle(bx, by, bx + 120, by + 56, *((200, 200, 200) if opened else (90, 90, 90)))
        ui.text(bx + 6, by + 44, s.key, 14, (255, 230, 120) if opened else (110, 110, 110))
        name = skills.info(s.skill_id)['name'] if s.skill_id else ('빈칸' if opened else f'Lv{s.unlock_level}')
        ui.text(bx + 6, by + 18, name, 14, (255, 255, 255) if opened else (110, 110, 110))

    ui.text(x0 + 20, y0 + 22, 'Esc · X : 버리지 않기 (새 기술을 받지 않음)', 14, (170, 170, 170))
