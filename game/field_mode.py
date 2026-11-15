"""숲(필드) 모드: 숲 맵을 걸어 다닌다. (지금은 튜토리얼 숲만)

조작: 방향키 이동. (Space · QWER · F 는 전투에서만)
튜토리얼이 진행 중이면 tutorial 이 연출을 맡고, 토리를 맵에 세워 둔다.
"""
import sys

from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP, SDLK_ESCAPE, SDLK_t, SDLK_u, SDLK_j

import admin
import combat
import debug_draw
import fade
import game_framework
import hud
import tutorial
import world
from camera import Camera
from collision import separate
from config import START_FIELD, FADE_TIME, TUTORIAL, FIELD_FEET_OFFSET
from field_map import FieldMap
from moa import DIR_KEYS
from training_thorn import TrainingThorn

field_map = None
camera = None
moa = None
enemy = None              # 튜토리얼의 토리 (숲에 서 있는 정령). 없으면 None
cur_bush = None
on_exit = False
notice_text, notice_time = '', 0.0


def init():
    global field_map, camera, moa, enemy, cur_bush, on_exit
    field_map = FieldMap(START_FIELD)
    camera = Camera(field_map.w, field_map.h)
    pos = world.field_return or field_map.start
    moa = world.get_moa(field_map, *pos)
    moa.on_dot_tick = combat.dot_tick_fx
    enemy = None
    cur_bush = on_exit = None
    combat.clear()
    me = sys.modules[__name__]
    if TUTORIAL and field_map.tori_pos and tutorial.phase in (None, 'to_field', 'done'):
        enemy = TrainingThorn(*field_map.tori_pos, field_map, moa)
        enemy.hold_on()
        if tutorial.phase is None:
            tutorial.start_intro(me)          # 숲에서 토리가 타락해 가는 연출
        else:
            tutorial.attach_field(me)         # 전투에서 돌아옴 → 마무리 / 이미 끝남
    camera.follow(*camera_target())
    fade.in_(FADE_TIME)


def finish():
    combat.clear()


def go_battle():
    """화면을 어둡게 하고 전투 맵으로."""
    import battle_mode
    world.field_return = (moa.x, moa.y)
    fade.out(FADE_TIME, lambda: game_framework.change_mode(battle_mode))


def notice(text, duration=2.5):
    global notice_text, notice_time
    notice_text, notice_time = text, duration


def handle_events():
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE:   # 임시: 일시정지 화면이 생기기 전까지는 종료
            game_framework.quit()
        elif tutorial.locked() or fade.busy():                 # 연출·화면 전환 중: J 건너뛰기만
            if e.type == SDL_KEYDOWN and e.key == SDLK_j:
                tutorial.skip()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_t:
            admin.toggle()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_u:
            admin.toggle_hurtbox()
        elif e.type in (SDL_KEYDOWN, SDL_KEYUP) and e.key in DIR_KEYS:
            moa.handle_event(e)                                  # 숲에서는 이동만


def camera_target():
    return tutorial.camera_target() if tutorial.active else (moa.x, moa.y)


def update(dt):
    global notice_time
    moa.update(dt)
    if enemy:
        enemy.update(dt)
        separate(moa, enemy, b_fixed=True)                       # 토리는 밀리지 않음
        moa.x, moa.y = field_map.clamp(moa.x, moa.y, moa.radius)
    field_map.update(dt)
    update_field_events()
    combat.update(dt, ())                                        # 이펙트만
    tutorial.update(dt)
    notice_time = max(0.0, notice_time - dt)
    camera.follow_smooth(*camera_target(), dt)
    fade.update(dt)


def update_field_events():
    """수풀 흔들기, 열매 먹기, 출구."""
    global cur_bush, on_exit
    bush = field_map.bush_at(moa.x, moa.y)
    if bush is not cur_bush and bush is not None:
        bush.rustle()                                            # (튜토리얼 숲은 조우 확률 0)
    cur_bush = bush
    for f in field_map.fruits:
        if f.try_eat(moa):
            notice('열매를 먹었다! HP 회복')
    ex = field_map.exit_at(moa.x, moa.y)
    if ex and not on_exit:
        notice('이 길은 숲1 로 이어진다. (숲1 은 아직 준비 중)')
    on_exit = ex is not None


def draw():
    field_map.draw_background(camera)
    things = list(field_map.objects()) + [moa] + ([enemy] if enemy else [])
    for obj in sorted(things, key=sort_y, reverse=True):         # 화면 위쪽(뒤)부터
        obj.draw(camera)
    combat.draw(camera)
    field_map.draw_foreground(camera)
    tutorial.draw_world(camera)
    if tutorial.locked():
        tutorial.draw_overlay()
    else:
        hud.draw_player(moa, slots=False)
        if notice_time > 0:
            hud.draw_notice(notice_text)
    if admin.enabled:
        for w in field_map.walls:
            debug_draw.arena(w, camera)
        admin.draw_label()
    if admin.show_hurtbox:
        debug_draw.hurtbox(moa, camera)
    fade.draw()


def sort_y(obj):
    """그리는 순서: 캐릭터는 발밑, 수풀은 아래쪽, 열매는 가운데."""
    if obj is moa or obj is enemy:
        return obj.y - FIELD_FEET_OFFSET
    return obj.y


def debug_state():
    return (f'FIELD moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} Lv{moa.level} '
            f'exp={moa.exp} | tori {enemy.state if enemy else None} '
            f'tut={tutorial.phase}{"(scene)" if tutorial.locked() else ""}')
