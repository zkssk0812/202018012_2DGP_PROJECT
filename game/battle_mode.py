"""전투 모드: 전투 맵 위에서 1대1 전투를 한다.

1주차: 모아 이동·회피, 훈련용 가시몽의 할퀴기에 맞는 피격 판정까지.
"""
from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_t, SDLK_u

import admin
import debug_draw
import game_framework
import hud
from battle_map import BattleMap
from camera import Camera
from collision import separate
from config import FAINT_RESTART_TIME
from effect import Effect
from moa import Moa
from stats import damage
from training_thorn import TrainingThorn

MAP_NAME = 'battle_forest1'

battle_map = None
camera = None
moa = None
enemy = None
attacks = []          # 지금 살아 있는 공격 판정
effects = []
faint_time = 0.0


def init():
    global battle_map, camera
    battle_map = BattleMap(MAP_NAME)
    camera = Camera(battle_map.w, battle_map.h)
    start()


def start():
    global moa, enemy, faint_time
    moa = Moa(*battle_map.player_start, battle_map)
    enemy = TrainingThorn(*battle_map.enemy_start, battle_map, moa)
    attacks.clear()
    effects.clear()
    faint_time = 0.0
    camera.follow(moa.x, moa.y)


def finish():
    attacks.clear()
    effects.clear()


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
    attacks.extend(enemy.new_attacks)
    effects.extend(enemy.new_effects)
    enemy.new_attacks.clear()
    enemy.new_effects.clear()

    if moa.state != 'dodge':                  # 회피 대시 중에는 적을 통과한다
        separate(moa, enemy)
        moa.x, moa.y = battle_map.clamp(moa.x, moa.y, moa.radius)
        enemy.x, enemy.y = battle_map.clamp(enemy.x, enemy.y, enemy.radius)

    resolve_attacks(dt)

    for fx in effects:
        fx.update(dt)
    effects[:] = [fx for fx in effects if not fx.done]

    update_faint(dt)
    camera.follow(moa.x, moa.y)


def resolve_attacks(dt):
    for atk in attacks:
        atk.update(dt)
        for target in (moa, enemy):
            if atk.try_hit(target):
                owner = atk.owner
                target.take_hit(damage(atk.power, owner.attack, target.defense), owner.x, owner.y)
                effects.append(Effect('monster', 'hit_spark', target.x, target.y))
    attacks[:] = [a for a in attacks if not a.done]


def update_faint(dt):
    """모아가 쓰러지면 잠시 뒤 그 자리에서 HP 절반으로 다시 시작 (psd 4.3)."""
    global faint_time
    if moa.state != 'faint':
        return
    faint_time += dt
    if faint_time >= FAINT_RESTART_TIME:
        faint_time = 0.0
        attacks.clear()
        moa.restart(*battle_map.player_start)
        enemy.x, enemy.y = battle_map.enemy_start


def draw():
    battle_map.draw_background(camera)
    for obj in sorted((moa, enemy), key=lambda o: -o.y):      # 화면 위쪽(뒤)부터
        obj.draw(camera)
    for fx in effects:
        fx.draw(camera)
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
    for atk in attacks:
        color = debug_draw.HIT_COLOR if atk.is_active else debug_draw.HIT_WAIT_COLOR
        debug_draw.shape(atk.shape, camera, color)


def debug_state():
    """테스트용: 현재 상태를 짧게 돌려준다."""
    return (f'moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} '
            f'cd={moa.dodge_cooldown:.2f} inv={moa.invincible:.2f} | '
            f'enemy {enemy.state} ({enemy.x:.0f},{enemy.y:.0f}) atk={len(attacks)}')
