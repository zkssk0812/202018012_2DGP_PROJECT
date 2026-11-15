"""주인공 모아.

상태는 transitions 의 Machine 으로 관리한다.
    idle ──walk──▶ move
    move ──stop──▶ idle
    idle/move/cast ──dodge_start──▶ dodge ──dodge_end──▶ idle   (쿨다운이 끝났을 때만)
    idle/move ──cast_start──▶ cast ──cast_end──▶ idle           (QWER 기술, 쓰는 동안 못 움직임)
    idle/move/cast/hurt ──hit──▶ hurt ──recover──▶ idle          (넉백 뒤 0.5초 무적)
    (어느 상태든) ──faint──▶ faint                                (HP 0, 전투 모드가 다시 시작시킴)
x, y 는 몸 원의 중심(맵 좌표)이다.
"""
import math

from sdl2 import (SDL_KEYDOWN, SDL_KEYUP, SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN, SDLK_SPACE,
                  SDLK_q, SDLK_w, SDLK_e, SDLK_r)
from transitions import Machine

import skills
from config import (MOA_SPEED, MOA_BODY_RADIUS, MOA_SPRITE_OFFSET_Y,
                    DODGE_TIME, DODGE_SPEED, DODGE_COOLDOWN,
                    HURT_TIME, KNOCKBACK_SPEED, HIT_INVINCIBLE,
                    MOA_BASE_STATS, MOA_LEVEL, MOA_SKILL_WINDUP,
                    SLOT_KEYS, SLOT_UNLOCK_LEVELS, MOA_START_SKILLS)
from fighter import Fighter
from sprite import SheetSprite

# 방향키 → (dx, dy, 그림 방향)
DIR_KEYS = {
    SDLK_LEFT: (-1, 0, 'left'),
    SDLK_RIGHT: (1, 0, 'right'),
    SDLK_UP: (0, 1, 'up'),
    SDLK_DOWN: (0, -1, 'down'),
}
SKILL_KEYS = {SDLK_q: 0, SDLK_w: 1, SDLK_e: 2, SDLK_r: 3}


def face_of(vx, vy):
    """방향 벡터 → 그림 방향 (더 큰 축 쪽)."""
    if abs(vx) >= abs(vy):
        return 'right' if vx > 0 else 'left'
    return 'up' if vy > 0 else 'down'


class Slot:
    """기술 칸 하나 (Q W E R)."""
    def __init__(self, key, unlock_level, skill_id=None):
        self.key = key
        self.unlock_level = unlock_level
        self.skill_id = skill_id
        self.cooldown = 0.0
        self.forced = False            # 관리자 모드에서 잠긴 칸에 넣은 기술


class Moa(Fighter):
    states = ['idle', 'move', 'dodge', 'cast', 'hurt', 'faint']

    def __init__(self, x, y, battle_map):
        self.x, self.y = x, y
        self.radius = MOA_BODY_RADIUS
        self.battle_map = battle_map
        self.sprite = SheetSprite('sprite_sheets', 'moa_sheet')
        self.opponent = None
        self.skill_windup = MOA_SKILL_WINDUP

        self.held = []                 # 누르고 있는 방향키 (누른 순서)
        self.face = 'down'             # 그림 방향 (4방향)
        self.dir_x, self.dir_y = 0.0, -1.0   # 바라보는 방향 (8방향, 단위 벡터) — 기술이 나가는 방향

        self.state_time = 0.0          # 지금 상태에 들어온 뒤 흐른 시간
        self.dodge_cooldown = 0.0      # 0 이 되면 다시 회피 가능
        self.invincible = 0.0          # 0 보다 크면 무적 (남은 시간)
        self.dodge_vx = self.dodge_vy = 0.0
        self.knock_vx = self.knock_vy = 0.0

        self.init_fighter(MOA_BASE_STATS, MOA_LEVEL, 'player')
        self.slots = [Slot(k, lv, s) for k, lv, s in zip(SLOT_KEYS, SLOT_UNLOCK_LEVELS, MOA_START_SKILLS)]
        self.casting_slot = None
        self.cast_info = None

        self.machine = Machine(model=self, states=Moa.states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        self.machine.add_transition('walk', 'idle', 'move')
        self.machine.add_transition('stop', 'move', 'idle')
        self.machine.add_transition('dodge_start', ['idle', 'move', 'cast'], 'dodge', conditions='can_dodge')
        self.machine.add_transition('dodge_end', 'dodge', 'idle')
        self.machine.add_transition('cast_start', ['idle', 'move'], 'cast')
        self.machine.add_transition('cast_end', 'cast', 'idle')
        self.machine.add_transition('hit', ['idle', 'move', 'cast', 'hurt'], 'hurt')
        self.machine.add_transition('recover', 'hurt', 'idle')
        self.machine.add_transition('faint', ['idle', 'move', 'dodge', 'cast', 'hurt'], 'faint')
        self.on_enter_idle()

    def reset_state_time(self):
        self.state_time = 0.0

    def can_dodge(self):
        return self.dodge_cooldown <= 0

    @property
    def is_invincible(self):
        return self.invincible > 0 or self.state == 'faint'

    def aim_angle(self):
        return math.atan2(self.dir_y, self.dir_x)

    # ── 기술 칸 ──────────────────────────────────────
    def slot_open(self, i):
        s = self.slots[i]
        return self.level >= s.unlock_level or s.forced

    def slot_ready(self, i):
        s = self.slots[i]
        return self.slot_open(i) and s.skill_id is not None and s.cooldown <= 0

    def set_slot(self, i, skill_id, forced=False):
        """칸에 기술을 넣는다. 같은 기술이 다른 칸에 있으면 그 칸은 비운다."""
        for k, s in enumerate(self.slots):
            if k != i and s.skill_id == skill_id:
                s.skill_id, s.cooldown, s.forced = None, 0.0, False
        s = self.slots[i]
        s.skill_id, s.cooldown = skill_id, 0.0
        s.forced = forced and self.level < s.unlock_level

    def use_skill(self, i):
        if self.state in ('idle', 'move') and self.slot_ready(i):
            self.casting_slot = i
            self.cast_start()

    # ── 맞기 (Fighter) ───────────────────────────────
    def react_to_hit(self, from_x, from_y):
        """공격한 쪽(from)의 반대 방향으로 밀려나고 잠시 무적."""
        dx, dy = self.x - from_x, self.y - from_y
        n = math.hypot(dx, dy) or 1
        self.knock_vx, self.knock_vy = dx / n, dy / n
        self.invincible = HURT_TIME + HIT_INVINCIBLE
        self.hit()

    def on_zero_hp(self):
        self.faint()

    def restart(self, x, y):
        """쓰러진 뒤 다시 시작: HP 절반 (psd 4.3)."""
        self.x, self.y = x, y
        self.hp = max(1, self.max_hp // 2)
        self.invincible = HIT_INVINCIBLE
        self.dodge_cooldown = 0.0
        self.dots.clear()
        self.guard_time = 0.0
        for s in self.slots:
            s.cooldown = 0.0
        self.machine.set_state('idle')
        self.reset_state_time()
        self.on_enter_idle()

    # ── 입력 ────────────────────────────────────────
    def handle_event(self, e):
        if e.type == SDL_KEYDOWN and e.key == SDLK_SPACE:
            self.dodge_start()
        elif e.type == SDL_KEYDOWN and e.key in SKILL_KEYS:
            self.use_skill(SKILL_KEYS[e.key])
        elif e.type == SDL_KEYDOWN and e.key in DIR_KEYS:
            if e.key not in self.held:
                self.held.append(e.key)
        elif e.type == SDL_KEYUP and e.key in DIR_KEYS:
            if e.key in self.held:
                self.held.remove(e.key)

    def input_vector(self):
        """누른 방향키를 합친 이동 방향 (단위 벡터). 안 누르면 (0, 0)."""
        dx = sum(DIR_KEYS[k][0] for k in self.held)
        dy = sum(DIR_KEYS[k][1] for k in self.held)
        n = math.hypot(dx, dy)
        return (dx / n, dy / n) if n else (0.0, 0.0)

    def update_facing(self, vx, vy):
        if vx or vy:
            self.dir_x, self.dir_y = vx, vy
        if self.held:                      # 그림은 마지막에 누른 방향을 본다
            self.face = DIR_KEYS[self.held[-1]][2]

    # ── 상태 진입 ────────────────────────────────────
    def on_enter_idle(self):
        self.sprite.play('idle', self.face)

    def on_enter_move(self):
        self.sprite.play('move', self.face)

    def on_enter_dodge(self):
        # 누르고 있는 방향으로, 안 누르면 바라보는 방향으로 대시
        vx, vy = self.input_vector()
        if not (vx or vy):
            vx, vy = self.dir_x, self.dir_y
        self.dodge_vx, self.dodge_vy = vx, vy
        self.dir_x, self.dir_y = vx, vy
        self.face = face_of(vx, vy)
        self.dodge_cooldown = DODGE_COOLDOWN
        self.invincible = max(self.invincible, DODGE_TIME)
        self.cast_info = None
        self.sprite.play('dodge', self.face, restart=True, duration=DODGE_TIME)

    def on_enter_cast(self):
        # 방향키를 누르고 있으면 그쪽으로 쓴다
        vx, vy = self.input_vector()
        self.update_facing(vx, vy)
        self.face = face_of(self.dir_x, self.dir_y)
        slot = self.slots[self.casting_slot]
        self.cast_info = skills.cast(slot.skill_id, self)
        slot.cooldown = skills.info(slot.skill_id)['cooldown']
        self.sprite.play(self.cast_info['anim'], self.face, restart=True,
                         duration=max(self.cast_info['lock'], 0.25))

    def on_enter_hurt(self):
        self.cast_info = None
        self.sprite.play('hurt', self.face, restart=True)

    def on_enter_faint(self):
        self.cast_info = None
        self.sprite.play('faint', self.face, restart=True)

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.dodge_cooldown = max(0.0, self.dodge_cooldown - dt)
        self.invincible = max(0.0, self.invincible - dt)
        for s in self.slots:
            s.cooldown = max(0.0, s.cooldown - dt)
        self.update_status(dt)
        getattr(self, f'update_{self.state}')(dt)
        self.sprite.update(dt)

    def update_idle(self, dt):
        vx, vy = self.input_vector()
        if vx or vy:
            self.walk()

    def update_move(self, dt):
        vx, vy = self.input_vector()
        if not (vx or vy):
            self.stop()
            return
        self.update_facing(vx, vy)
        self.sprite.play('move', self.face)
        self.move_by(vx * MOA_SPEED * dt, vy * MOA_SPEED * dt)

    def update_dodge(self, dt):
        self.move_by(self.dodge_vx * DODGE_SPEED * dt, self.dodge_vy * DODGE_SPEED * dt)
        if self.state_time >= DODGE_TIME:
            self.dodge_end()      # idle 로 돌아가고, 방향키를 누르고 있으면 다음 프레임에 move

    def update_cast(self, dt):
        info = self.cast_info
        if info and info['dash']:                    # 돌진 기술: 판정이 켜진 뒤 그 길이만큼 이동
            dx, dy, speed, dash_time, start = info['dash']
            t0, t1 = self.state_time - dt, self.state_time
            moving = max(0.0, min(t1, start + dash_time) - max(t0, start))
            self.move_by(dx * speed * moving, dy * speed * moving)
        if info is None or self.state_time >= info['lock']:
            self.cast_end()

    def update_hurt(self, dt):
        self.move_by(self.knock_vx * KNOCKBACK_SPEED * dt, self.knock_vy * KNOCKBACK_SPEED * dt)
        if self.state_time >= HURT_TIME:
            self.recover()

    def update_faint(self, dt):
        pass

    def move_by(self, dx, dy):
        self.x, self.y = self.battle_map.clamp(self.x + dx, self.y + dy, self.radius)

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        # 맞은 뒤 무적 시간에는 깜빡인다 (회피 중에는 깜빡이지 않음)
        if self.state in ('idle', 'move') and self.invincible > 0 and int(self.invincible * 16) % 2:
            return
        sx, sy = camera.to_screen(self.x, self.y)
        self.sprite.draw(sx, sy + MOA_SPRITE_OFFSET_Y)
