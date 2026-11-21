"""숲(필드) 모드: 숲 맵을 걸어 다닌다. 지금 숲은 world.current_field (튜토리얼 숲 → 숲1).

조작: 방향키 이동. (Space · QWER · F 는 전투에서만)
    · 출구에 닿으면 그 숲으로 넘어간다 (튜토리얼 숲의 북쪽 길 → 숲1, 튜토리얼이 끝난 뒤에만)
    · 수풀의 새 칸에 들어설 때마다 맵의 조우 확률로 타락한 정령 2~3마리를 만난다 (psd 4.3)
      → 수풀이 흔들리고 화면이 어두워지며 전투 맵으로. 전투가 끝나면 조우한 자리로 돌아온다
튜토리얼이 진행 중이면 tutorial 이 연출을 맡고, 토리를 맵에 세워 둔다.
"""
import random
import sys

from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP, SDLK_ESCAPE, SDLK_t, SDLK_u, SDLK_j

import admin
import combat
import debug_draw
import fade
import game_framework
import hud
import resources
import tutorial
import world
from camera import Camera
from collision import separate
from config import (FADE_TIME, FIELD_ENTRY, TUTORIAL, TUTORIAL_TORI_LEVEL, FIELD_FEET_OFFSET,
                    ENCOUNTERS, ENCOUNTER_COOLDOWN)
from field_map import FieldMap
from moa import DIR_KEYS
from spirit import Spirit

ENCOUNTER_SHAKE = 0.7     # 조우: 수풀이 흔들리는 시간 (이동 막힘) 뒤 전투로

field_map = None
camera = None
moa = None
enemy = None              # 튜토리얼의 토리 (숲에 서 있는 정령). 없으면 None
cur_bush = None
on_exit = None
safe_time = 0.0           # 이 시간 동안은 조우하지 않음 (전투에서 막 돌아왔을 때)
encounter_time = None     # 조우해서 전투로 넘어가기를 기다리는 중이면 남은 시간
notice_text, notice_time = '', 0.0


def init():
    global field_map, camera, moa, enemy, cur_bush, on_exit, safe_time, encounter_time
    field_map = FieldMap(world.current_field)
    camera = Camera(field_map.w, field_map.h)
    pos = world.field_return or FIELD_ENTRY.get(world.current_field, field_map.start)
    moa = world.get_moa(field_map, *pos)
    moa.on_dot_tick = combat.dot_tick_fx
    enemy = None
    on_exit = field_map.exit_at(moa.x, moa.y)          # 출구 위에서 시작하면 바로 넘어가지 않게
    cur_bush = field_map.bush_at(moa.x, moa.y)         # 수풀 위로 돌아와도 바로 다시 조우하지 않게
    encounter_time = None
    safe_time = ENCOUNTER_COOLDOWN if world.encounter else 0.0
    combat.clear()
    me = sys.modules[__name__]
    if TUTORIAL and field_map.tori_pos and tutorial.phase in (None, 'to_field', 'done'):
        enemy = Spirit('tori', TUTORIAL_TORI_LEVEL, *field_map.tori_pos, field_map, moa)
        enemy.hold_on()
        if tutorial.phase == 'done':
            enemy.x += tutorial.TORI_STEP_ASIDE          # 이미 끝났으면 길옆에 서 있음
        if tutorial.phase is None:
            tutorial.start_intro(me)          # 숲에서 토리가 타락해 가는 연출
        else:
            tutorial.attach_field(me)         # 전투에서 돌아옴 → 마무리 / 이미 끝남
    if world.defeated:
        notice('쓰러졌다… 조우한 자리에서 다시 시작한다 (HP 절반)', 3.0)
    world.defeated = False
    world.encounter = None
    camera.follow(*camera_target())
    fade.in_(FADE_TIME)


def finish():
    combat.clear()


def go_battle():
    """화면을 어둡게 하고 전투 맵으로. 돌아올 자리는 지금 자리."""
    import battle_mode
    world.field_return = (moa.x, moa.y)
    fade.out(FADE_TIME, lambda: game_framework.change_mode(battle_mode))


def go_field(name):
    """다른 숲으로 (그 숲의 시작 위치에서)."""
    world.current_field = name
    world.field_return = None
    me = sys.modules[__name__]
    fade.out(FADE_TIME, lambda: game_framework.change_mode(me))


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
    return tutorial.camera_target() if tutorial.locked() else (moa.x, moa.y)


def update(dt):
    global notice_time, safe_time
    if encounter_time is None:
        moa.update(dt)
    else:
        moa.sprite.update(dt)                                    # 조우 중: 제자리에 멈춤
    if enemy:
        enemy.update(dt)
        separate(moa, enemy, b_fixed=True)                       # 토리는 밀리지 않음
        moa.x, moa.y = field_map.clamp(moa.x, moa.y, moa.radius)
    field_map.update(dt)
    safe_time = max(0.0, safe_time - dt)
    update_field_events(dt)
    combat.update(dt, ())                                        # 이펙트만
    tutorial.update(dt)
    notice_time = max(0.0, notice_time - dt)
    camera.follow_smooth(*camera_target(), dt)
    fade.update(dt)


def update_field_events(dt):
    """수풀 흔들기·조우, 열매 먹기, 출구."""
    global cur_bush, on_exit, encounter_time
    if encounter_time is not None:                               # 수풀이 흔들리는 중 → 시간이 되면 전투로
        encounter_time -= dt
        if encounter_time <= 0 and not fade.busy():
            encounter_time = 0.0
            go_battle()
        return

    bush = field_map.bush_at(moa.x, moa.y)
    if bush is not cur_bush and bush is not None:                # 수풀의 새 칸에 들어섬
        bush.rustle()
        if can_encounter() and random.random() < field_map.encounter_rate:
            start_encounter(bush)
    cur_bush = bush

    for f in field_map.fruits:
        if f.try_eat(moa):
            notice('열매를 먹었다! HP 회복')

    ex = field_map.exit_at(moa.x, moa.y)
    if ex and ex is not on_exit:
        use_exit(ex)
    on_exit = ex


def can_encounter():
    return (safe_time <= 0 and field_map.name in ENCOUNTERS
            and not tutorial.running())


def start_encounter(bush):
    """타락한 정령 2~3마리 (숲마다 정해진 종류와 레벨)."""
    global encounter_time
    enc = ENCOUNTERS[field_map.name]
    lo, hi = enc['levels']
    hi = max(lo, min(hi, moa.level + 2))                         # 모아보다 너무 높은 레벨은 나오지 않게
    n = random.randint(*enc['count'])
    world.encounter = dict(battle_map=enc['battle_map'],
                           spirits=[(random.choice(enc['spirits']), random.randint(lo, hi)) for _ in range(n)])
    bush.shake_encounter()
    moa.held.clear()
    if moa.state == 'move':
        moa.stop()
    encounter_time = ENCOUNTER_SHAKE
    notice('수풀 속에서 무언가 튀어나온다!', 1.5)


def use_exit(ex):
    target = ex['to']
    if tutorial.running():
        return                                                   # 튜토리얼 중에는 나갈 수 없음
    if not map_exists(target):
        notice(f'이 길은 {target} 로 이어진다. (아직 준비 중)')
        return
    go_field(target)


FIELDS_READY = ('tutorial', 'forest1')       # 지금 갈 수 있는 숲 (숲2·숲3 은 아직)


def map_exists(name):
    import os
    return name in FIELDS_READY and os.path.exists(resources.path('forest_maps', f'{name}.json'))


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
    return (f'FIELD[{field_map.name}] moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} '
            f'Lv{moa.level} exp={moa.exp} | tori {enemy.state if enemy else None} '
            f'enc={encounter_time is not None} safe={safe_time:.1f} '
            f'tut={tutorial.phase}{"(scene)" if tutorial.locked() else ""}')
