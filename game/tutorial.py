"""튜토리얼 (오프닝, psd 2.3) 진행.

    intro      [연출] 토리가 검은 기운에 타락해 간다. "도와줘... 도와줘..." → 완전히 타락
    survive    기술이 없어 피하기만 한다. 10초 버티면 (남은 시간은 보여 주지 않음) ↓
    resist     [연출] 토리가 저항 "끄아아... 어두워, 무서워, 도와줘!" → 검은 기운 일부가 토리 앞에 떨어짐
               → 모아 "이건..."
    fragment   토리는 공격하지 않고 저항한다. 모아가 떨어진 기운을 F 로 흡수 → 할퀴기 배우기 창
               (배우지 않으면 다시 묻는다: 토리를 구하려면 힘이 필요하다)
    fight      토리가 다시 덤벼든다. 할퀴기로 쓰러뜨려 흡수 → 토리가 원래 색으로
    ending     [연출] 토리 "...모아? 고마워!" → 모아 "이번엔 내가 지킬 차례야." → 튜토리얼 끝
    done

[연출] 중에는 어떤 입력도 받지 않고, J 로 건너뛸 수 있다.
"""
import math

import combat
import resources
from config import (TUTORIAL_TORI_GAP, TUTORIAL_SURVIVE_TIME, TUTORIAL_FRAGMENT_DIST, SPRITE_SCALE)
from cutscene import Cutscene
from effect import Effect
from essence import Essence

FIRST_SKILL = 'scratch'

active = False
phase = None
scene = None                 # 지금 도는 연출 (Cutscene) 또는 None
survive_time = 0.0
reoffer = False              # 할퀴기를 배우지 않았을 때 다시 묻기
corrupting = 0.0             # intro: 토리 주위를 도는 검은 기운의 세기 (0 이면 안 그림)
B = None                     # battle_mode 모듈


def start(battle):
    global active, B
    B = battle
    active = True
    moa, tori = B.moa, B.enemy
    tori.x, tori.y = moa.x + TUTORIAL_TORI_GAP, moa.y          # 둘 다 화면 안에
    moa.face = 'right'
    moa.on_enter_idle()
    play_intro()


def locked():
    """연출 중이면 True: 플레이어 입력을 받지 않는다 (J 건너뛰기만)."""
    return active and scene is not None and not scene.done


def skip():
    if locked():
        scene.skip()


def camera_target():
    """연출 중에는 모아와 토리 사이를 비춘다."""
    if locked():
        return (B.moa.x + B.enemy.x) / 2, (B.moa.y + B.enemy.y) / 2
    return B.moa.x, B.moa.y


def run(new_phase, cutscene=None):
    global phase, scene
    phase, scene = new_phase, cutscene
    if cutscene:
        B.moa.held.clear()
        if B.moa.state == 'move':
            B.moa.stop()


# ── intro ───────────────────────────────────────────
def play_intro():
    global corrupting
    moa, tori = B.moa, B.enemy
    tori.hold_on()
    tori.look_toward(moa.x)
    tori.show_pure(True)                    # 아직 원래 색, 주위에 검은 기운이 감돈다
    corrupting = 0.3

    def grow():
        global corrupting
        corrupting = 1.0
        tori.shake = 2.0

    def corrupt():
        global corrupting
        corrupting = 0.0
        tori.show_pure(False)               # 완전히 타락
        tori.shake = 6.0
        combat.add_effect(Effect('monster', 'poison_burst', tori.x, tori.y + 10, scale=1.1))
        combat.add_effect(Effect('monster', 'warn_glint', tori.x, tori.y + 40, scale=1.4))

    def calm():
        tori.shake = 0.0

    lines = [(0.3, 2.6, tori, '도와줘... 도와줘...'),
             (2.9, 4.6, tori, '도와... 줘...'),
             (5.4, 6.8, moa, '토리...?'),
             (7.0, 8.4, 'banner', '토리가 완전히 타락했다!')]
    events = [(2.8, grow), (4.8, corrupt), (5.4, calm)]
    run('intro', Cutscene(8.6, events, lines, on_end=start_survive))


def start_survive():
    global survive_time, corrupting
    corrupting = 0.0
    B.enemy.show_pure(False)
    B.enemy.shake = 0.0
    B.enemy.release()
    survive_time = 0.0
    run('survive')
    B.notice('기술이 없다! Space 로 토리의 공격을 피하자', 4.0)


# ── resist ──────────────────────────────────────────
def play_resist():
    moa, tori = B.moa, B.enemy
    combat.clear()                          # 날아오던 공격·이펙트 정리
    tori.hold_on()
    tori.look_toward(moa.x)
    tori.resist(True)

    def drop():
        a = math.atan2(moa.y - tori.y, moa.x - tori.x)            # 토리 앞 (모아 쪽)
        x = tori.x + math.cos(a) * TUTORIAL_FRAGMENT_DIST
        y = tori.y + math.sin(a) * TUTORIAL_FRAGMENT_DIST
        x, y = B.battle_map.clamp(x, y, 40)
        B.set_essence(Essence(tori, x, y, drop_time=0.6, drains_source=False,
                              on_absorbed=on_fragment_absorbed))

    lines = [(0.3, 3.2, tori, '끄아아... 어두워, 무서워, 도와줘!'),
             (3.6, 5.2, moa, '이건...')]
    run('resist', Cutscene(5.4, [(1.6, drop)], lines, on_end=start_fragment))


def start_fragment():
    run('fragment')
    if B.essence is None:                   # 건너뛰기로 drop 이 막 실행된 경우에도 기운은 있음
        return
    B.notice('토리에게서 떨어진 검은 기운… 다가가서 F 로 흡수하자', 5.0)


def on_fragment_absorbed():
    import skill_learn_mode
    skill_learn_mode.open_for(FIRST_SKILL, on_done=on_learn_done)


def on_learn_done(learned):
    global reoffer
    if learned:
        start_fight()
    else:
        reoffer = True                      # 다음 프레임에 다시 묻는다


def start_fight():
    run('fight')
    B.enemy.release()
    B.notice('Q : 할퀴기로 토리를 구하자!', 4.0)


# ── ending ──────────────────────────────────────────
def play_ending():
    moa, tori = B.moa, B.enemy
    lines = [(0.3, 2.4, tori, '...모아? 고마워!'),
             (2.6, 4.6, moa, '이번엔 내가 지킬 차례야.'),
             (4.8, 6.6, 'banner', '튜토리얼 끝')]
    run('ending', Cutscene(6.8, [], lines, on_end=lambda: run('done')))


# ── 매 프레임 ────────────────────────────────────────
def update(dt):
    global survive_time, reoffer
    if not active:
        return
    if scene and not scene.done:
        scene.update(dt)
        return
    if phase == 'survive':
        if B.moa.state != 'faint':
            survive_time += dt
        if survive_time >= TUTORIAL_SURVIVE_TIME and B.moa.state in ('idle', 'move', 'dodge'):
            play_resist()
    elif phase == 'fragment' and reoffer:
        reoffer = False
        B.notice('토리를 구하려면 힘이 필요해…', 3.0)
        import skill_learn_mode
        skill_learn_mode.open_for(FIRST_SKILL, on_done=on_learn_done)
    elif phase == 'fight' and B.enemy.purify_done:
        play_ending()


# ── 그리기 ──────────────────────────────────────────
def draw_world(camera):
    """캐릭터 위에 그리는 것: 타락해 가는 토리 주위의 검은 기운, 말풍선."""
    if not active:
        return
    if corrupting > 0:
        draw_swirl(camera)
    if locked():
        scene.draw_world(camera)


def draw_overlay():
    if locked():
        scene.draw_overlay()


def draw_swirl(camera):
    meta = resources.json_data('sprite_sheets', 'dark_essence.json')
    image = resources.image('sprite_sheets', meta['image'])
    cw, ch = meta['cell_w'], meta['cell_h']
    tori = B.enemy
    t = scene.time if scene else 0.0
    count = 3 if corrupting < 1 else 6
    for k in range(count):
        a = t * (2.0 + corrupting * 2) + k * 2 * math.pi / count
        r = 46 - corrupting * 10
        x = tori.x + math.cos(a) * r
        y = tori.y + 20 + math.sin(a) * r * 0.6
        sx, sy = camera.to_screen(x, y)
        frame = int(t * meta['fps'] + k) % meta['frames']
        size = cw * SPRITE_SCALE * (0.5 + 0.3 * corrupting)
        image.clip_draw(frame * cw, 0, cw, ch, sx, sy, size, size)
