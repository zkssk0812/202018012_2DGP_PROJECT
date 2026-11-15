"""기술 배우기 창 (psd 4.1): 흡수로 기술을 얻을 수 있을 때 뜬다. 열려 있는 동안 게임은 멈춘다.

    offer   기술 설명 + [배운다] [배우지 않는다]
              배운다 → 빈칸이 있으면 바로 배움 / 꽉 찼으면 full 로
    full    "기술 칸이 꽉 차서 더 배울 수 없다. 기술을 하나 버리겠습니까?" + [버린다] [버리지 않는다]
              버린다 → choose 로 / 버리지 않는다 → 배우지 않고 닫기
    choose  버릴 칸 고르기 → 그 칸에 새 기술

조작: ← → 고르기, Enter · Space · F 결정, Esc 한 단계 뒤로 (offer 에서는 배우지 않기)
"""
from pico2d import get_events, draw_rectangle
from sdl2 import (SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_LEFT, SDLK_RIGHT,
                  SDLK_RETURN, SDLK_KP_ENTER, SDLK_SPACE, SDLK_f)

import battle_mode
import game_framework
import skills
import ui
from config import SCREEN_W, SCREEN_H

PANEL_W, PANEL_H = 640, 330
CONFIRM_KEYS = (SDLK_RETURN, SDLK_KP_ENTER, SDLK_SPACE, SDLK_f)
WRAP = 34                     # 설명 한 줄 글자 수

new_skill = None              # 이번에 배울 수 있는 기술 id
step = 'offer'
cursor = 0                    # 버튼 또는 칸 고르기 위치


def open_for(skill_id):
    global new_skill
    new_skill = skill_id
    game_framework.push_mode(__import__('skill_learn_mode'))


def init():
    go('offer')


def finish():
    battle_mode.moa.held.clear()      # 창이 열린 동안 뗀 방향키가 눌린 채로 남지 않게


def go(s):
    global step, cursor
    step, cursor = s, 0
    if s == 'choose':                 # 첫 번째 열린 칸부터
        cursor = open_slots()[0]


def open_slots():
    moa = battle_mode.moa
    return [i for i in range(len(moa.slots)) if moa.slot_open(i)]


def name(skill_id):
    return skills.info(skill_id)['name']


def close(message):
    battle_mode.notice(message)
    game_framework.pop_mode()


# ── 입력 ────────────────────────────────────────────
def handle_events():
    global cursor
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
            return
        if e.type != SDL_KEYDOWN:
            continue
        if e.key in (SDLK_LEFT, SDLK_RIGHT):
            move_cursor(-1 if e.key == SDLK_LEFT else 1)
        elif e.key in CONFIRM_KEYS:
            confirm()
            return
        elif e.key == SDLK_ESCAPE:
            back()
            return


def move_cursor(d):
    global cursor
    if step == 'choose':
        slots = open_slots()
        cursor = slots[(slots.index(cursor) + d) % len(slots)]
    else:
        cursor = (cursor + d) % 2


def confirm():
    moa = battle_mode.moa
    if step == 'offer':
        if cursor == 1:
            close(f'{ui.eul(name(new_skill))} 배우지 않았다')
            return
        where = moa.learn(new_skill)
        if where == 'full':
            go('full')
        else:
            close(f'{ui.eul(name(new_skill))} 배웠다!  ({moa.slots[where].key})')
    elif step == 'full':
        if cursor == 0:
            go('choose')
        else:
            close(f'{ui.eul(name(new_skill))} 배우지 않았다')
    elif step == 'choose':
        old = moa.slots[cursor].skill_id
        moa.set_slot(cursor, new_skill)
        old_text = f'{ui.eul(name(old))} 잊고 ' if old else ''
        close(f'{old_text}{ui.eul(name(new_skill))} 배웠다!  ({moa.slots[cursor].key})')


def back():
    if step == 'offer':
        close(f'{ui.eul(name(new_skill))} 배우지 않았다')
    elif step == 'full':
        go('offer')
    elif step == 'choose':
        go('full')
        global cursor
        cursor = 0


def update(dt):
    pass                              # 멈춤


# ── 그리기 ──────────────────────────────────────────
def wrap(text, width=WRAP):
    lines, line = [], ''
    for word in text.split(' '):
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}' if line else word
    if line:
        lines.append(line)
    return lines


def button(x, y, w, label, selected):
    h = 40
    if selected:
        draw_rectangle(x, y, x + w, y + h, 70, 55, 110, filled=True)
        draw_rectangle(x, y, x + w, y + h, 230, 200, 255)
        ui.text(x + 12, y + h / 2, '▶', 14, (255, 230, 120))
    else:
        draw_rectangle(x, y, x + w, y + h, 35, 35, 50, filled=True)
        draw_rectangle(x, y, x + w, y + h, 120, 110, 140)
    ui.text(x + 34, y + h / 2, label, 17, (255, 255, 255) if selected else (190, 190, 200))


def draw():
    battle_mode.draw()
    x0, y0 = (SCREEN_W - PANEL_W) / 2, (SCREEN_H - PANEL_H) / 2 + 40
    top = y0 + PANEL_H
    draw_rectangle(x0, y0, x0 + PANEL_W, top, 18, 22, 30, filled=True)
    draw_rectangle(x0, y0, x0 + PANEL_W, top, 200, 150, 255)

    draw_skill_card(x0 + 20, top - 20, new_skill, '새 기술')

    if step == 'offer':
        ui.text(x0 + 20, y0 + 92, f'{ui.eul(name(new_skill))} 배우겠습니까?', 17, (230, 210, 255))
        button(x0 + 20, y0 + 22, 290, '배운다', cursor == 0)
        button(x0 + 330, y0 + 22, 290, '배우지 않는다', cursor == 1)
    elif step == 'full':
        ui.text(x0 + 20, y0 + 100, '기술 칸이 꽉 차서 더 배울 수 없다.', 16, (255, 200, 160))
        ui.text(x0 + 20, y0 + 76, '기술을 하나 버리겠습니까?', 17, (230, 210, 255))
        button(x0 + 20, y0 + 22, 290, '버린다', cursor == 0)
        button(x0 + 330, y0 + 22, 290, '버리지 않는다', cursor == 1)
    elif step == 'choose':
        draw_choose(x0, y0)


def draw_skill_card(x, y_top, skill_id, title):
    info = skills.info(skill_id)
    ui.text(x, y_top - 8, title, 14, (170, 150, 200))
    ui.text(x, y_top - 36, info['name'], 24, (255, 255, 255))
    ui.text(x + 180, y_top - 36, f'{skills.KIND_NAMES[info["kind"]]}   ·   위력 {skills.power_text(skill_id)}'
                                 f'   ·   쿨다운 {info["cooldown"]:g}초', 15, (220, 220, 230))
    for k, line in enumerate(wrap(skills.DESCRIPTIONS[skill_id])):
        ui.text(x, y_top - 72 - k * 24, line, 16, (210, 210, 220))


def draw_choose(x0, y0):
    moa = battle_mode.moa
    ui.text(x0 + 20, y0 + 120, f'어느 기술을 버리고 {ui.eul(name(new_skill))} 배울까요?', 16, (230, 210, 255))
    w, gap = 140, 12
    for i, s in enumerate(moa.slots):
        bx, by = x0 + 20 + i * (w + gap), y0 + 22
        opened = moa.slot_open(i)
        selected = step == 'choose' and i == cursor
        fill = (70, 55, 110) if selected else (30, 40, 50) if opened else (20, 20, 20)
        edge = (230, 200, 255) if selected else (200, 200, 200) if opened else (80, 80, 80)
        draw_rectangle(bx, by, bx + w, by + 76, *fill, filled=True)
        draw_rectangle(bx, by, bx + w, by + 76, *edge)
        ui.text(bx + 8, by + 62, s.key, 15, (255, 230, 120) if opened else (100, 100, 100))
        if not opened:
            ui.text(bx + 8, by + 34, f'Lv{s.unlock_level}', 14, (100, 100, 100))
            continue
        if s.skill_id:
            info = skills.info(s.skill_id)
            ui.text(bx + 8, by + 36, info['name'], 15)
            ui.text(bx + 8, by + 14, f'{skills.KIND_NAMES[info["kind"]]} · {skills.power_text(s.skill_id)}',
                    12, (180, 180, 190))
        if selected:
            ui.text(bx + w - 40, by + 62, '버림', 12, (255, 180, 160))
