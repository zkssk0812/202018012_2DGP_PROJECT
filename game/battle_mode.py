"""전투 모드: 전투 맵 위에서 1대1 전투를 한다.

모아: 이동·회피·QWER 기술. 상대: 훈련용 가시몽 (배틀 AI 정령으로 바꾸기 전까지).
"""
from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_t, SDLK_u

import admin
import combat
import debug_draw
import game_framework
import hud
from battle_map import BattleMap
from camera import Camera
from collision import separate
from config import FAINT_RESTART_TIME
from moa import Moa
from training_thorn import TrainingThorn

MAP_NAME = 'battle_forest1'

battle_map = None
camera = None
moa = None
enemy = None
faint_time = 0.0


def init():
    global battle_map, camera
    battle_map = BattleMap(MAP_NAME)
    camera = Camera(battle_map.w, battle_map.h)
    start()


def start():
    global moa, enemy, faint_time
    combat.clear()
    moa = Moa(*battle_map.player_start, battle_map)
    enemy = TrainingThorn(*battle_map.enemy_start, battle_map, moa)
    moa.opponent = enemy
    for f in (moa, enemy):
        f.on_dot_tick = combat.dot_tick_fx
    faint_time = 0.0
    camera.follow(moa.x, moa.y)


def finish():
    combat.clear()


def handle_events():
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE:   # 임시: 일시정지 화면이 생기기 전까지는 종료
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_t:
            admin.toggle()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_u:
            admin.toggle_hurtbox()
        else:
            moa.handle_event(e)


def update(dt):
    moa.update(dt)
    enemy.update(dt)

    # 몸끼리 밀어내기: 회피·돌진 중이거나 상대가 기절해 있으면 통과
    passing = moa.state == 'dodge' or (moa.cast_info and moa.cast_info['dash']) or enemy.is_down
    if not passing:
        separate(moa, enemy)
        moa.x, moa.y = battle_map.clamp(moa.x, moa.y, moa.radius)
        enemy.x, enemy.y = battle_map.clamp(enemy.x, enemy.y, enemy.radius)

    combat.update(dt, (moa, enemy))
    update_faint(dt)
    camera.follow(moa.x, moa.y)


def update_faint(dt):
    """모아가 쓰러지면 잠시 뒤 그 자리에서 HP 절반으로 다시 시작 (psd 4.3)."""
    global faint_time
    if moa.state != 'faint':
        return
    faint_time += dt
    if faint_time >= FAINT_RESTART_TIME:
        faint_time = 0.0
        combat.clear()
        moa.restart(*battle_map.player_start)
        enemy.x, enemy.y = battle_map.enemy_start


def draw():
    battle_map.draw_background(camera)
    for obj in sorted((moa, enemy), key=lambda o: -o.y):      # 화면 위쪽(뒤)부터
        obj.draw(camera)
    combat.draw(camera)
    battle_map.draw_foreground(camera)
    hud.draw_enemy(enemy, camera)
    hud.draw_player(moa)
    if admin.enabled:
        draw_debug()
        admin.draw_label()
    if admin.show_hurtbox:
        debug_draw.hurtbox(moa, camera)
        debug_draw.hurtbox(enemy, camera)


def draw_debug():
    debug_draw.arena(battle_map.arena, camera)
    for atk in combat.attacks:
        if atk.cancelled:
            continue
        color = debug_draw.HIT_COLOR if atk.is_active else debug_draw.HIT_WAIT_COLOR
        debug_draw.shape(atk.shape, camera, color)


def debug_state():
    """테스트용: 현재 상태를 짧게 돌려준다."""
    return (f'moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} '
            f'slots={[(s.skill_id, round(s.cooldown, 1)) for s in moa.slots]} | '
            f'enemy {enemy.state} ({enemy.x:.0f},{enemy.y:.0f}) hp={enemy.hp}/{enemy.max_hp} '
            f'dots={ {k: round(v[1], 1) for k, v in enemy.dots.items()} } atk={len(combat.attacks)}')
