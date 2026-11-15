"""전투 모드: 전투 맵 위에서 1대1 전투를 한다.

모아: 이동·회피·QWER 기술·F 흡수. 상대: 훈련용 정령 (지금은 타락한 토리, 배틀 AI 정령으로 바꾸기 전까지).

흡수 흐름 (psd 4.1):
    상대 HP 0 → 기절 → 그 자리에 검은 기운 + 흡수 범위 원
    → 모아 몸이 범위에 닿으면 F 안내 → F → 기운이 모아에게 날아옴, 상대는 기운이 빠지고 원래 색으로
    → 흡수가 끝나면 경험치 + 기술 배우기 창 (배운다/배우지 않는다, 꽉 차면 버릴 기술 고르기)
    → (임시) 잠시 뒤 새 상대가 나옴. 나중엔 여기서 전투 맵을 빠져나가 숲으로 돌아간다.
"""
from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_t, SDLK_u, SDLK_g, SDLK_k, SDLK_f

import admin
import combat
import debug_draw
import game_framework
import hud
from battle_map import BattleMap
from camera import Camera
from collision import separate
from config import FAINT_RESTART_TIME, BATTLE_MAP, ABSORB_TIME, DUMMY_RESPAWN_TIME
from essence import Essence
from moa import Moa
from stats import exp_reward
from training_thorn import TrainingThorn

battle_map = None
camera = None
moa = None
enemy = None
essence = None        # 상대가 기절하면 생기는 검은 기운
faint_time = 0.0
respawn_time = 0.0
notice_text, notice_time = '', 0.0     # 화면 가운데 위에 잠깐 띄우는 알림


def init():
    global battle_map, camera
    battle_map = BattleMap(BATTLE_MAP)
    camera = Camera(battle_map.w, battle_map.h)
    start()


def start():
    global moa, faint_time
    combat.clear()
    moa = Moa(*battle_map.player_start, battle_map)
    moa.on_dot_tick = combat.dot_tick_fx
    spawn_enemy()
    faint_time = 0.0
    camera.follow(moa.x, moa.y)


def spawn_enemy():
    global enemy, essence, respawn_time
    enemy = TrainingThorn(*battle_map.enemy_start, battle_map, moa)
    enemy.on_dot_tick = combat.dot_tick_fx
    moa.opponent = enemy
    essence = None
    respawn_time = 0.0


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
        elif e.type == SDL_KEYDOWN and e.key == SDLK_g and admin.enabled:
            enemy.kill()                                         # 관리자: 상대 즉사 → 기절
        elif e.type == SDL_KEYDOWN and e.key == SDLK_k and admin.enabled:
            import skill_select_mode                             # 관리자: 기술 선택 창 (게임 멈춤)
            game_framework.push_mode(skill_select_mode)
            return
        elif e.type == SDL_KEYDOWN and e.key == SDLK_f:
            try_absorb()
        else:
            moa.handle_event(e)


def can_absorb():
    """F 를 누르면 흡수가 되는 상황인지 (안내 표시에도 쓴다)."""
    return essence is not None and moa.can_absorb and essence.in_range(moa)


def try_absorb():
    """범위 밖이나 다른 동작 중에 F 를 누르면 아무 일도 없다."""
    if not can_absorb():
        return
    moa.start_absorb(enemy)
    essence.fly_to_target(moa, ABSORB_TIME)
    enemy.drain()


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
    update_essence(dt)
    update_faint(dt)
    global notice_time
    notice_time = max(0.0, notice_time - dt)
    camera.follow(moa.x, moa.y)


def update_essence(dt):
    global essence, respawn_time
    if essence is None and enemy.state == 'faint':
        essence = Essence(enemy)                  # 기절한 자리에 검은 기운
    if essence is None:
        return
    was_done = essence.done
    essence.update(dt)
    if essence.done and not was_done:             # 흡수 완료 → 경험치, 기술
        moa.gain_exp(exp_reward(enemy.level))
        give_skill()
    if enemy.purify_done:                         # 임시: 원래 색으로 돌아오고 잠시 뒤 새 상대
        respawn_time += dt
        if respawn_time >= DUMMY_RESPAWN_TIME:
            spawn_enemy()


def give_skill():
    """흡수한 정령에게서 기술을 얻는다 (psd 4.1)."""
    owned = [s.skill_id for s in moa.slots if s.skill_id]
    skill_id = enemy.roll_skill(owned)
    if skill_id is None:
        notice('기운을 흡수했다')
        return
    import skill_learn_mode                       # 배울지 묻는 창 (게임 멈춤)
    skill_learn_mode.open_for(skill_id)


def notice(text, duration=2.5):
    global notice_text, notice_time
    notice_text, notice_time = text, duration


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
        if not enemy.is_down:
            enemy.x, enemy.y = battle_map.enemy_start


def draw():
    battle_map.draw_background(camera)
    if essence:
        essence.draw_ground(camera)
    for obj in sorted((moa, enemy), key=lambda o: -o.y):      # 화면 위쪽(뒤)부터
        obj.draw(camera)
    if essence:
        essence.draw(camera)
    combat.draw(camera)
    battle_map.draw_foreground(camera)
    if enemy.state not in ('essence_out', 'purified'):        # 흡수가 시작되면 HP 바를 숨김
        hud.draw_enemy(enemy, camera)
    if can_absorb():
        hud.draw_absorb_prompt(moa, camera)
    hud.draw_player(moa)
    if notice_time > 0:
        hud.draw_notice(notice_text)
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
            f'Lv{moa.level} exp={moa.exp}/{moa.exp_needed} | '
            f'enemy {enemy.state} ({enemy.x:.0f},{enemy.y:.0f}) hp={enemy.hp}/{enemy.max_hp} '
            f'essence={essence.state if essence else None} absorb_ok={can_absorb()}')
