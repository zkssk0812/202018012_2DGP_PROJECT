"""숲(필드) 모드: 숲 맵을 걸어 다닌다. 지금 숲은 world.current_field (튜토리얼 숲 → 숲1).

조작: 방향키 이동. (Space · QWER · F 는 전투에서만)
    · 출구에 닿으면 그 숲으로 넘어간다 (튜토리얼 숲의 북쪽 길 → 숲1, 튜토리얼이 끝난 뒤에만)
    · 숲 끝 길목에는 상위 정령(보스)이 서 있다. 가까이 다가가면 대사 뒤 보스전 (구하기 전에는 다음 숲으로 못 감)
    · 수풀의 새 칸에 들어설 때마다 맵의 조우 확률로 타락한 정령 2~3마리를 만난다 (psd 4.3)
      → 수풀이 흔들리고 화면이 어두워지며 전투 맵으로. 전투가 끝나면 조우한 자리로 돌아온다
튜토리얼이 진행 중이면 tutorial 이 연출을 맡고, 토리를 맵에 세워 둔다.
"""
import math
import random
import sys

from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP, SDLK_ESCAPE, SDLK_t, SDLK_u, SDLK_j, SDLK_p, SDLK_i

import admin
import combat
import debug_draw
import fade
import game_framework
import hud
import resources
import tutorial
import ui
import world
from camera import Camera
from collision import separate
from config import (FADE_TIME, FIELD_ENTRY, TUTORIAL, TUTORIAL_TORI_LEVEL, FIELD_FEET_OFFSET,
                    ENCOUNTERS, ENCOUNTER_COOLDOWN, BOSSES, BOSS_TRIGGER_RADIUS,
                    BOSS_REWARD_LEVEL, ADMIN_WARP)
import story
from cutscene import Cutscene
from effect import Effect
from field_map import FieldMap
from moa import DIR_KEYS, face_of
from spirit import Spirit, SPIRITS

ENCOUNTER_SHAKE = 0.7     # 조우: 수풀이 흔들리는 시간 (이동 막힘) 뒤 전투로

field_map = None
camera = None
moa = None
enemy = None              # 튜토리얼의 토리 (숲에 서 있는 정령). 없으면 None
boss = None               # 숲 끝 길목의 상위 정령. 없으면 None
boss_inside = False       # 모아가 보스 범위 안에 있는지 (밖 → 안으로 들어설 때만 보스전)
boss_step = 0.0           # 보스가 길을 비켜 주며 더 움직일 거리 (위로)
BOSS_ASIDE = 110          # 구한 보스가 길을 비켜 서는 거리 (길 위쪽 풀밭)
scene = None              # 숲에서 도는 이야기 연출 (Cutscene). 도는 동안 입력을 막고 J 로 건너뜀
cur_bush = None
on_exit = None
safe_time = 0.0           # 이 시간 동안은 조우하지 않음 (전투에서 막 돌아왔을 때)
encounter_time = None     # 조우해서 전투로 넘어가기를 기다리는 중이면 남은 시간
notice_text, notice_time = '', 0.0


def init():
    global field_map, camera, moa, enemy, cur_bush, on_exit, safe_time, encounter_time
    global boss, boss_inside, scene
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
    scene = None
    place_boss()                                                 # (방금 구한 보스면 여기서 이야기 연출 시작)
    if world.arrive_notice:
        notice(world.arrive_notice, 4.0)
        world.arrive_notice = None
    if world.defeated:
        notice('쓰러졌다… 조우한 자리에서 다시 시작한다 (HP 절반)', 3.0)
    world.defeated = False
    world.encounter = None
    camera.follow(*camera_target())
    fade.in_(FADE_TIME)


def place_boss():
    """숲 끝 길목에 상위 정령을 세운다. 이미 구했으면 원래 색으로 길옆에 비켜서 있다."""
    global boss, boss_inside, boss_step
    boss, boss_inside, boss_step = None, False, 0.0
    info = BOSSES.get(field_map.name)
    if not info or not field_map.boss_pos:
        return
    x, y = field_map.boss_pos
    boss = Spirit(info['kind'], info['level'], x, y, field_map, moa)
    boss.hold_on()
    boss.look_toward(moa.x, moa.y)
    if info['kind'] in world.cleared:
        boss.show_pure(True)
        boss.pure_sprite.play('joy', boss.face)
        if world.boss_saved == info['kind']:                     # 방금 구함: 이야기를 나눈 뒤 길을 비켜 줌
            world.boss_saved = None
            play_after_story()
        else:
            boss.y += BOSS_ASIDE                                 # 이미 비켜 서 있음
    boss_inside = near_boss()                                    # 범위 안에서 돌아왔으면 다시 나갔다 와야 보스전


def play_after_story():
    """보스를 구하고 숲으로 돌아왔을 때: 원래 색의 보스와 이야기 → 길을 비켜 줌."""
    face_boss()

    def calm():
        boss.pure_sprite.play('idle', boss.face)

    def step_aside():
        global boss_step
        boss_step = BOSS_ASIDE
        boss.pure_sprite.play('move', 'up')

    def done():
        global boss_step
        if boss_step > 0:                                       # 건너뛰었으면 바로 제자리로
            boss.y += boss_step
            boss_step = 0.0
        boss.pure_sprite.play('joy', 'down')

    play_scene(story.BOSS_STORY[boss.kind]['after'], dict(calm=calm, step_aside=step_aside), on_end=done)


def boss_blocking():
    return boss is not None and boss.kind not in world.cleared


def near_boss():
    """보스전을 시작할 거리 안인지. 전투가 아직 없는 보스(fight=False)는 서 있기만 한다."""
    if not boss_blocking() or not BOSSES[field_map.name].get('fight', True):
        return False
    return math.hypot(moa.x - boss.x, moa.y - boss.y) < BOSS_TRIGGER_RADIUS


def start_boss():
    """보스 범위에 들어섬: 멈추고 대사 → 화면이 어두워지며 보스전."""
    info = BOSSES[field_map.name]
    world.encounter = dict(battle_map=info['battle_map'], spirits=[(info['kind'], info['level'])])
    face_boss()

    def shake():
        boss.shake = 3.0

    def glint():
        boss.shake = 5.0
        combat.add_effect(Effect('monster', 'warn_glint', boss.x, boss.y + 70, scale=1.6))

    play_scene(story.BOSS_STORY[boss.kind]['before'], dict(shake=shake, glint=glint), on_end=go_battle)


def face_boss():
    """모아와 보스가 서로 바라본다."""
    moa.face = face_of(boss.x - moa.x, boss.y - moa.y)
    moa.on_enter_idle()
    boss.look_toward(moa.x, moa.y)


def play_scene(script, actions, on_end):
    """이야기 연출을 시작한다 (story.py 의 대본). 도는 동안 입력을 막는다."""
    global scene
    actors = dict(actions, moa=moa, boss=boss)
    lines, events, length = story.build(script, actors)
    scene = Cutscene(length, events, lines, on_end)
    moa.held.clear()
    if moa.state == 'move':
        moa.stop()


def update_boss_step(dt):
    """구한 보스가 길 위쪽으로 천천히 비켜 선다."""
    global boss_step
    if boss and boss_step > 0:
        d = min(boss_step, 120 * dt)
        boss.y += d
        boss_step -= d
        if boss_step <= 0 and boss.pure_sprite:
            boss.pure_sprite.play('joy', 'down')


def scene_locked():
    return scene is not None and not scene.done


def admin_boss_warp():
    """관리자 P (튜토리얼이 끝난 뒤): 바로 Lv10, 가시찌르기 · 이슬탄을 칸에 넣고, 실프 앞(범위 바로 밖)으로 이동."""
    while moa.level < BOSS_REWARD_LEVEL:
        moa.gain_exp(moa.exp_needed - moa.exp)
    for skill_id in ADMIN_WARP['skills']:
        if moa.learn(skill_id) == 'full':                        # 열린 칸이 꽉 찼으면 뒤쪽 칸부터 바꿈
            opened = [i for i in range(len(moa.slots)) if moa.slot_open(i)
                      and moa.slots[i].skill_id not in ADMIN_WARP['skills']]
            moa.set_slot(opened[-1], skill_id)
    moa.hp = moa.max_hp
    world.current_field = ADMIN_WARP['field']
    world.field_return = ADMIN_WARP['pos']
    world.arrive_notice = '[관리자] Lv10 · 가시찌르기 · 이슬탄 — 위로 걸어가면 실프전'
    me = sys.modules[__name__]
    fade.out(FADE_TIME, lambda: game_framework.change_mode(me))


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
        elif e.type == SDL_KEYDOWN and e.key == SDLK_p and not fade.busy():
            if tutorial.running():
                tutorial.skip_tutorial()                         # 튜토리얼 전체 건너뛰기
            elif admin.enabled and not tutorial.locked():
                admin_boss_warp()                                # 관리자: Lv10 + 기술 + 실프 앞으로
        elif tutorial.locked() or scene_locked() or fade.busy():   # 연출·화면 전환 중: J 건너뛰기만
            if e.type == SDL_KEYDOWN and e.key == SDLK_j:
                tutorial.skip()
                if scene_locked():
                    scene.skip()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_t:
            admin.toggle()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_i:
            admin.toggle_god()                                   # 관리자: 무적 켜기/끄기
        elif e.type == SDL_KEYDOWN and e.key == SDLK_u:
            admin.toggle_hurtbox()
        elif e.type in (SDL_KEYDOWN, SDL_KEYUP) and e.key in DIR_KEYS:
            moa.handle_event(e)                                  # 숲에서는 이동만


def camera_target():
    if scene_locked() and boss:                                  # 보스 연출: 모아와 보스 사이를 비춤
        return (moa.x + boss.x) / 2, (moa.y + boss.y) / 2 + 40
    return tutorial.camera_target() if tutorial.locked() else (moa.x, moa.y)


def update(dt):
    global notice_time, safe_time
    if encounter_time is None and not scene_locked():
        moa.update(dt)
    else:
        moa.sprite.update(dt)                                    # 조우·연출 중: 제자리에 멈춤
    if scene_locked():
        scene.update(dt)
    update_boss_step(dt)
    for npc in (enemy, boss):
        if npc:
            npc.update(dt)
            separate(moa, npc, b_fixed=True)                     # 토리·보스는 밀리지 않음
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
    global cur_bush, on_exit, encounter_time, boss_inside
    if scene_locked() or fade.busy():
        return
    if encounter_time is not None:                               # 수풀이 흔들리는 중 → 시간이 되면 전투로
        encounter_time -= dt
        if encounter_time <= 0 and not fade.busy():
            encounter_time = 0.0
            go_battle()
        return

    inside = near_boss()
    if inside and not boss_inside and not tutorial.running() and not fade.busy():
        boss_inside = True
        start_boss()
        return
    boss_inside = inside

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


def pick_mixed(kinds, n):
    """정령 n 마리를 고른다. 근접형·원거리형이 둘 다 있는 숲이면 각각 적어도 한 마리씩 섞는다."""
    by_style = {}
    for k in kinds:
        by_style.setdefault(SPIRITS[k]['style'], []).append(k)
    picked = [random.choice(group) for group in by_style.values()][:n]   # 종류(근접/원거리)마다 하나씩
    picked += [random.choice(kinds) for _ in range(n - len(picked))]    # 나머지는 아무거나
    random.shuffle(picked)
    return picked


def start_encounter(bush):
    """타락한 정령 2~3마리 (숲마다 정해진 종류와 레벨)."""
    global encounter_time
    enc = ENCOUNTERS[field_map.name]
    lo, hi = enc['levels']
    hi = max(lo, min(hi, moa.level + 2))                         # 모아보다 너무 높은 레벨은 나오지 않게
    n = random.randint(*enc['count'])
    world.encounter = dict(battle_map=enc['battle_map'],
                           spirits=[(kind, random.randint(lo, hi)) for kind in pick_mixed(enc['spirits'], n)])
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
    if boss_blocking():
        notice(f'{ui.i_ga(boss.name)} 길을 막고 있다')
        return
    if not map_exists(target):
        notice(f'이 길은 {target} 로 이어진다. (아직 준비 중)')
        return
    go_field(target)


FIELDS_READY = ('tutorial', 'forest1', 'forest2')   # 지금 갈 수 있는 숲 (숲3 은 아직)


def map_exists(name):
    import os
    return name in FIELDS_READY and os.path.exists(resources.path('forest_maps', f'{name}.json'))


def draw():
    field_map.draw_background(camera)
    things = list(field_map.objects()) + [moa] + [npc for npc in (enemy, boss) if npc]
    for obj in sorted(things, key=sort_y, reverse=True):         # 화면 위쪽(뒤)부터
        obj.draw(camera)
    combat.draw(camera)
    field_map.draw_foreground(camera)
    tutorial.draw_world(camera)
    if scene_locked():
        scene.draw_world(camera)
        scene.draw_overlay()                                     # 연출 중에는 UI 를 숨기고 위아래 검은 띠
    elif tutorial.locked():
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
    if obj is moa or obj is enemy or obj is boss:
        return obj.y - FIELD_FEET_OFFSET
    return obj.y


def debug_state():
    return (f'FIELD[{field_map.name}] moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} '
            f'Lv{moa.level} exp={moa.exp} | tori {enemy.state if enemy else None} '
            f'enc={encounter_time is not None} safe={safe_time:.1f} '
            f'tut={tutorial.phase}{"(scene)" if tutorial.locked() else ""}')
