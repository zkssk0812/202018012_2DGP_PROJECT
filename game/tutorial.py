"""튜토리얼 (오프닝, psd 2.3) 진행. 숲 맵과 전투 맵을 오간다.

  [숲 · 튜토리얼 맵]
    intro      [연출] 토리가 검은 기운에 타락해 간다. "도와줘... 도와줘..." → 완전히 타락
    to_battle  화면이 어두워지며 전투 맵으로
  [전투 맵]
    survive    기술이 없어 피하기만 한다. 10초 버티면 (남은 시간은 보여 주지 않음) ↓
    resist     [연출] 토리가 저항 "끄아아... 어두워, 무서워, 도와줘!" → 검은 기운 일부가 토리 앞에 떨어짐
               → 모아 "이건..."
    fragment   토리는 공격하지 않고 저항한다. 떨어진 기운을 F 로 흡수 → 할퀴기 배우기 창
               (배우지 않으면 다시 묻는다)
    fight      토리가 다시 덤벼든다. 할퀴기로 쓰러뜨려 흡수 → 토리가 원래 색으로
    to_field   잠시 뒤 화면이 어두워지며 숲으로 돌아감
  [숲 · 튜토리얼 맵]
    ending     [연출] 토리 "...모아? 고마워!" → 모아 "이번엔 내가 지킬 차례야." → 튜토리얼 끝
    done       숲을 자유롭게 걸어 다닌다 (원래 색의 토리가 서 있음)

[연출] 중에는 어떤 입력도 받지 않고, J 로 건너뛸 수 있다.
H 는 지금 튜토리얼이 붙어 있는 모드 모듈 (field_mode 또는 battle_mode).
H 에 필요한 것: moa, enemy, notice(), (숲) go_battle(), (전투) go_field(), battle_map, set_essence()
"""
import math

import combat
import resources
from config import (TUTORIAL_SURVIVE_TIME, TUTORIAL_FRAGMENT_DIST, SPRITE_SCALE)
from cutscene import Cutscene
from effect import Effect
from essence import Essence
from moa import face_of

FIRST_SKILL = 'scratch'
RETURN_DELAY = 1.5           # 토리가 원래 색으로 돌아오고 숲으로 돌아가기까지

active = False
phase = None
scene = None                 # 지금 도는 연출 (Cutscene) 또는 None
survive_time = 0.0
wait_time = 0.0
reoffer = False              # 할퀴기를 배우지 않았을 때 다시 묻기
corrupting = 0.0             # intro: 토리 주위를 도는 검은 기운의 세기 (0 이면 안 그림)
H = None


def running():
    """튜토리얼이 아직 끝나지 않았으면 True (끝난 뒤에는 숲을 자유롭게 다닌다)."""
    return active and phase != 'done'


def locked():
    """연출 중이면 True: 플레이어 입력을 받지 않는다 (J 건너뛰기만)."""
    return active and scene is not None and not scene.done


def skip():
    if locked():
        scene.skip()


def camera_target():
    """연출 중에는 모아와 토리 사이를 비춘다."""
    if locked() and H.enemy:
        return (H.moa.x + H.enemy.x) / 2, (H.moa.y + H.enemy.y) / 2
    return H.moa.x, H.moa.y


def run(new_phase, cutscene=None):
    global phase, scene
    phase, scene = new_phase, cutscene
    if cutscene:
        H.moa.held.clear()
        if H.moa.state == 'move':
            H.moa.stop()


def face_each_other():
    moa, tori = H.moa, H.enemy
    dx, dy = tori.x - moa.x, tori.y - moa.y
    moa.face = face_of(dx, dy)
    moa.on_enter_idle()
    tori.look_toward(moa.x, moa.y)


# ── 숲: intro ───────────────────────────────────────
def start_intro(field):
    global active, H, corrupting
    H, active = field, True
    moa, tori = H.moa, H.enemy
    tori.show_pure(True)                    # 아직 원래 색, 주위에 검은 기운이 감돈다
    face_each_other()
    corrupting = 0.3

    def grow():
        global corrupting
        corrupting = 1.0
        tori.shake = 2.0

    def corrupt():
        global corrupting
        corrupting = 0.0
        tori.show_pure(False)               # 완전히 타락
        tori.sprite.play('idle', tori.face)
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
    run('intro', Cutscene(8.6, events, lines, on_end=to_battle))


def to_battle():
    global corrupting
    corrupting = 0.0
    H.enemy.show_pure(False)
    H.enemy.shake = 0.0
    run('to_battle')
    H.go_battle()


# ── 전투: survive → resist → fragment → fight ────────
def attach_battle(battle):
    """전투 맵이 열리면 부른다."""
    global H, survive_time
    H = battle
    survive_time = 0.0
    run('survive')
    H.notice('기술이 없다! Space 로 토리의 공격을 피하자', 4.0)


def play_resist():
    moa, tori = H.moa, H.enemy
    combat.clear()                          # 날아오던 공격·이펙트 정리
    tori.hold_on()
    tori.look_toward(moa.x, moa.y)
    tori.resist(True)

    def drop():
        a = math.atan2(moa.y - tori.y, moa.x - tori.x)            # 토리 앞 (모아 쪽)
        x = tori.x + math.cos(a) * TUTORIAL_FRAGMENT_DIST
        y = tori.y + math.sin(a) * TUTORIAL_FRAGMENT_DIST
        x, y = H.battle_map.clamp(x, y, 40)
        H.set_essence(Essence(tori, x, y, drop_time=0.6, drains_source=False,
                              on_absorbed=on_fragment_absorbed))

    lines = [(0.3, 3.2, tori, '끄아아... 어두워, 무서워, 도와줘!'),
             (3.6, 5.2, moa, '이건...')]
    run('resist', Cutscene(5.4, [(1.6, drop)], lines, on_end=start_fragment))


def start_fragment():
    run('fragment')
    H.notice('토리에게서 떨어진 검은 기운… 다가가서 F 로 흡수하자', 5.0)


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
    H.enemy.release()
    H.notice('Q : 할퀴기로 토리를 구하자!', 4.0)


# ── 숲: ending ──────────────────────────────────────
def attach_field(field):
    """전투에서 숲으로 돌아왔을 때 (또는 튜토리얼이 끝난 뒤 다시 숲에 왔을 때)."""
    global H
    H = field
    tori = H.enemy
    tori.show_pure(True)
    tori.pure_sprite.play('joy', tori.face)
    if phase == 'to_field':
        play_ending()


def play_ending():
    moa, tori = H.moa, H.enemy
    face_each_other()
    tori.pure_sprite.play('joy', tori.face)
    lines = [(0.6, 2.7, tori, '...모아? 고마워!'),
             (2.9, 4.9, moa, '이번엔 내가 지킬 차례야.'),
             (5.1, 6.9, 'banner', '튜토리얼 끝')]
    run('ending', Cutscene(7.1, [], lines, on_end=finish_tutorial))


TORI_STEP_ASIDE = 130       # 튜토리얼이 끝나면 토리가 길옆으로 비켜섬 (숲1 로 가는 길을 막지 않게)


def finish_tutorial():
    run('done')
    H.enemy.x += TORI_STEP_ASIDE
    H.notice('길을 따라 북쪽으로 가면 숲1 이다', 4.0)


# ── 매 프레임 ────────────────────────────────────────
def update(dt):
    global survive_time, reoffer, wait_time
    if not active:
        return
    if scene and not scene.done:
        scene.update(dt)
        return
    if phase == 'survive':
        if H.moa.state != 'faint':
            survive_time += dt
        if survive_time >= TUTORIAL_SURVIVE_TIME and H.moa.state in ('idle', 'move', 'dodge'):
            play_resist()
    elif phase == 'fragment' and reoffer:
        reoffer = False
        H.notice('토리를 구하려면 힘이 필요해…', 3.0)
        import skill_learn_mode
        skill_learn_mode.open_for(FIRST_SKILL, on_done=on_learn_done)
    elif phase == 'fight' and H.enemy.purify_done:
        wait_time += dt
        if wait_time >= RETURN_DELAY:       # 원래 색으로 돌아온 토리를 잠깐 보여 주고 숲으로
            wait_time = 0.0
            run('to_field')
            H.go_field()


# ── 그리기 ──────────────────────────────────────────
def draw_world(camera):
    """캐릭터 위에 그리는 것: 타락해 가는 토리 주위의 검은 기운, 말풍선."""
    if not active:
        return
    if corrupting > 0 and H.enemy:
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
    tori = H.enemy
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
