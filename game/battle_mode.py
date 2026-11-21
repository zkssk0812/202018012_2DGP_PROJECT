"""전투 모드: 전투 맵 위에서 모아 혼자 정령 여러 마리와 싸운다.

어떤 전투인지는 world.encounter 가 정한다.
    숲에서 조우: world.encounter = dict(battle_map, spirits=[(종류, 레벨), ...])
    튜토리얼:    tutorial 이 진행을 맡는다 (토리 한 마리, 연출 중 입력 막기, J 건너뛰기)

흡수 흐름 (psd 4.1):
    정령 HP 0 → 기절 → 그 자리에 검은 기운 + 흡수 범위 원
    → 모아 몸이 범위에 닿으면 F 안내 → F → 기운이 모아에게 날아옴, 정령은 기운이 빠지고 원래 색으로
    → 흡수가 끝나면 경험치 + 기술 배우기 창
모두 원래 색으로 돌아오면 숲의 조우한 자리로 돌아간다.
모아가 쓰러지면 숲의 조우한 자리에서 HP 절반으로 다시 시작한다 (psd 4.3). 튜토리얼은 전투 맵에서 다시 시작.
"""
import math
import sys

from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_t, SDLK_u, SDLK_g, SDLK_k, SDLK_f, SDLK_j, SDLK_p

import admin
import combat
import debug_draw
import fade
import game_framework
import hud
import tutorial
import world
from battle_map import BattleMap
from camera import Camera
from collision import separate
from config import (FAINT_RESTART_TIME, ABSORB_TIME, FADE_TIME, BATTLE_END_DELAY,
                    TUTORIAL_BATTLE_MAP, TUTORIAL_TORI_LEVEL)
from essence import Essence
from spirit import Spirit
from stats import exp_reward

battle_map = None
camera = None
moa = None
enemies = []          # 이번 전투의 정령들
enemy = None          # 첫 번째 정령 (튜토리얼은 토리 한 마리라 이것만 씀)
essences = []         # 기절한 자리의 검은 기운들
faint_time = 0.0
end_time = 0.0
ending = False
notice_text, notice_time = '', 0.0     # 화면 가운데 위에 잠깐 띄우는 알림


def init():
    global battle_map, camera
    enc = world.encounter
    battle_map = BattleMap(enc['battle_map'] if enc else TUTORIAL_BATTLE_MAP)
    camera = Camera(battle_map.w, battle_map.h)
    start()


def start():
    global moa, faint_time, end_time, ending
    combat.clear()
    moa = world.get_moa(battle_map, *battle_map.player_start)    # 숲에서 온 그 모아 (HP·기술 유지)
    moa.on_dot_tick = combat.dot_tick_fx
    enc = world.encounter
    spawn(enc['spirits'] if enc else [('tori', TUTORIAL_TORI_LEVEL)])
    faint_time = end_time = 0.0
    ending = False
    if tutorial.active and tutorial.phase == 'to_battle':
        tutorial.attach_battle(sys.modules[__name__])
    elif len(enemies) > 1:
        notice(f'타락한 정령 {len(enemies)}마리가 나타났다!')
    camera.follow(*camera_target())
    fade.in_(FADE_TIME)


def spawn(spirit_list):
    """정령들을 전투 맵 오른쪽(enemy_start 둘레)에 흩어 놓는다."""
    global enemies, enemy
    ex, ey = battle_map.enemy_start
    n = len(spirit_list)
    enemies = []
    for i, (kind, level) in enumerate(spirit_list):
        a = (i - (n - 1) / 2) * 0.9                          # 모아 쪽을 향한 부채꼴 모양으로
        x, y = battle_map.clamp(ex + math.cos(a) * 120 - 120, ey + math.sin(a) * 260, 40)
        s = Spirit(kind, level, x, y, battle_map, moa)
        s.on_dot_tick = combat.dot_tick_fx
        enemies.append(s)
    enemy = enemies[0]
    essences.clear()
    update_target()


def set_essence(e):
    """튜토리얼: 토리가 저항하며 떨어뜨린 기운 조각."""
    essences.append(e)


def finish():
    combat.clear()


def go_field():
    """화면을 어둡게 하고 숲으로 돌아간다 (돌아갈 자리는 world.field_return)."""
    import field_mode
    fade.out(FADE_TIME, lambda: game_framework.change_mode(field_mode))


# ── 입력 ─────────────────────────────────────────────
def handle_events():
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE:   # 임시: 일시정지 화면이 생기기 전까지는 종료
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_p and not fade.busy():
            tutorial.skip_tutorial()                               # 튜토리얼 전체 건너뛰기
        elif tutorial.locked() or fade.busy():                   # 연출·화면 전환 중: J 건너뛰기 말고는 받지 않음
            if e.type == SDL_KEYDOWN and e.key == SDLK_j:
                tutorial.skip()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_t:
            admin.toggle()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_u:
            admin.toggle_hurtbox()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_g and admin.enabled:
            for s in enemies:                                    # 관리자: 정령 모두 즉사 → 기절
                s.kill()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_k and admin.enabled:
            import skill_select_mode                             # 관리자: 기술 선택 창 (게임 멈춤)
            game_framework.push_mode(skill_select_mode)
            return
        elif e.type == SDL_KEYDOWN and e.key == SDLK_f:
            try_absorb()
        else:
            moa.handle_event(e)


def absorbable():
    """모아가 지금 F 로 흡수할 수 있는 기운 (가장 가까운 것). 없으면 None."""
    if not moa.can_absorb:
        return None
    near = [e for e in essences if e.in_range(moa)]
    return min(near, key=lambda e: math.hypot(e.x - moa.x, e.y - moa.y)) if near else None


def can_absorb():
    return absorbable() is not None


def try_absorb():
    """범위 밖이나 다른 동작 중에 F 를 누르면 아무 일도 없다."""
    e = absorbable()
    if e is None:
        return
    moa.start_absorb(e)
    e.fly_to_target(moa, ABSORB_TIME)
    if e.drains_source:                           # 튜토리얼의 떨어진 조각은 토리를 정화하지 않음
        e.source.drain()


# ── 매 프레임 ────────────────────────────────────────
def update(dt):
    global notice_time
    if ending:                                    # 숲으로 넘어가는 중: 전투는 멈추고 화면만 어두워짐
        fade.update(dt)
        notice_time = max(0.0, notice_time - dt)
        return
    moa.update(dt)
    for s in enemies:
        s.update(dt)
    update_target()
    push_bodies()
    combat.update(dt, [moa] + enemies)
    update_essences(dt)
    update_faint(dt)
    update_end(dt)
    tutorial.update(dt)
    fade.update(dt)
    notice_time = max(0.0, notice_time - dt)
    camera.follow_smooth(*camera_target(), dt)


def update_target():
    """모아의 '상대'(내려찍기가 떨어질 곳) = 가장 가까운 쓰러지지 않은 정령."""
    alive = [s for s in enemies if not s.is_down]
    moa.opponent = min(alive, key=lambda s: math.hypot(s.x - moa.x, s.y - moa.y)) if alive else None


def push_bodies():
    """몸끼리 밀어내기. 회피·돌진 중인 모아와 기절한 정령은 통과한다."""
    moa_passing = moa.state == 'dodge' or (moa.cast_info and moa.cast_info['dash'])
    standing = [s for s in enemies if not s.is_down]
    if not moa_passing:
        for s in standing:
            separate(moa, s, b_fixed=s.state == 'hold')      # 연출로 붙잡힌 토리는 밀리지 않음
    for i, a in enumerate(standing):
        for b in standing[i + 1:]:
            separate(a, b)
    for f in [moa] + standing:
        f.x, f.y = battle_map.clamp(f.x, f.y, f.radius)


def camera_target():
    return tutorial.camera_target() if tutorial.locked() else (moa.x, moa.y)


def update_essences(dt):
    for s in enemies:                             # 새로 기절한 정령 자리에 검은 기운
        if s.state == 'faint' and not any(e.source is s and e.drains_source for e in essences):
            essences.append(Essence(s, on_absorbed=lambda s=s: reward(s)))
    for e in list(essences):
        was_done = e.done
        e.update(dt)
        if e.done and not was_done:               # 흡수 완료
            if not e.drains_source:               # 조각은 흡수하면 끝 (다음에 기절하면 새 기운이 생기게)
                essences.remove(e)
            if e.on_absorbed:
                e.on_absorbed()


def reward(spirit):
    """쓰러뜨린 정령의 기운을 흡수했을 때: 경험치 + 기술."""
    moa.gain_exp(exp_reward(spirit.level))
    give_skill(spirit)


def give_skill(spirit):
    """흡수한 정령에게서 기술을 얻는다 (psd 4.1)."""
    owned = [s.skill_id for s in moa.slots if s.skill_id]
    skill_id = spirit.roll_skill(owned)
    if skill_id is None:
        notice(f'{spirit.name}의 기운을 흡수했다')
        return
    import skill_learn_mode                       # 배울지 묻는 창 (게임 멈춤)
    skill_learn_mode.open_for(skill_id)


def update_end(dt):
    """숲에서 조우한 전투: 모두 원래 색으로 돌아오면 잠시 뒤 숲으로."""
    global end_time, ending
    if tutorial.running() or ending or not enemies:
        return
    if all(s.purify_done for s in enemies):
        end_time += dt
        if end_time >= BATTLE_END_DELAY:
            ending = True
            notice('모두 구했다!', 1.5)
            go_field()


def notice(text, duration=2.5):
    global notice_text, notice_time
    notice_text, notice_time = text, duration


def update_faint(dt):
    """모아가 쓰러지면: 숲의 조우한 자리에서 HP 절반으로 다시 시작 (psd 4.3). 튜토리얼은 전투 맵에서."""
    global faint_time, ending
    if moa.state != 'faint' or ending:
        return
    faint_time += dt
    if faint_time < FAINT_RESTART_TIME:
        return
    faint_time = 0.0
    if tutorial.running():
        combat.clear()
        moa.restart(*battle_map.player_start)
        for s in enemies:
            if not s.is_down:
                s.x, s.y = battle_map.enemy_start
        return
    ending = True
    moa.restart(moa.x, moa.y)                     # HP 절반 (숲으로 돌아가면 조우한 자리에 놓임)
    world.defeated = True
    go_field()


# ── 그리기 ───────────────────────────────────────────
def draw():
    battle_map.draw_background(camera)
    for e in essences:
        e.draw_ground(camera)
    for obj in sorted([moa] + enemies, key=lambda o: -o.y):     # 화면 위쪽(뒤)부터
        obj.draw(camera)
    for e in essences:
        e.draw(camera)
    combat.draw(camera)
    battle_map.draw_foreground(camera)
    tutorial.draw_world(camera)
    if tutorial.locked():                         # 연출 중에는 UI 를 숨기고 위아래 검은 띠
        tutorial.draw_overlay()
    else:
        for s in enemies:
            if s.state not in ('essence_out', 'purified', 'hold'):   # 흡수·연출 중에는 HP 바를 숨김
                hud.draw_enemy(s, camera)
        if can_absorb():
            hud.draw_absorb_prompt(moa, camera)
        hud.draw_player(moa)
        if notice_time > 0:
            hud.draw_notice(notice_text)
    if admin.enabled:
        draw_debug()
        admin.draw_label()
    if admin.show_hurtbox:
        for f in [moa] + enemies:
            debug_draw.hurtbox(f, camera)
    fade.draw()


def draw_debug():
    debug_draw.arena(battle_map.arena, camera)
    for atk in combat.attacks:
        if atk.cancelled:
            continue
        color = debug_draw.HIT_COLOR if atk.is_active else debug_draw.HIT_WAIT_COLOR
        debug_draw.shape(atk.shape, camera, color)


def debug_state():
    """테스트용: 현재 상태를 짧게 돌려준다."""
    es = ' '.join(f'{s.kind}{s.level}:{s.state}:{s.hp}' for s in enemies)
    return (f'moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) hp={moa.hp}/{moa.max_hp} '
            f'Lv{moa.level} exp={moa.exp}/{moa.exp_needed} | {es} | ess={len(essences)} '
            f'absorb_ok={can_absorb()} tut={tutorial.phase}'
            f'{"(scene)" if tutorial.locked() else ""}')
