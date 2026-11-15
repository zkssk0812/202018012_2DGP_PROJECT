"""주인공 모아.

상태는 transitions 의 Machine 으로 관리한다.
    idle ──walk──▶ move
    move ──stop──▶ idle
    idle/move ──dodge_start──▶ dodge ──dodge_end──▶ idle   (쿨다운이 끝났을 때만)
    idle/move ──hit──▶ hurt ──recover──▶ idle             (넉백 뒤 0.5초 무적)
    hurt ──faint──▶ faint                                  (HP 0, 전투 모드가 다시 시작시킴)
x, y 는 몸 원의 중심(맵 좌표)이다.
"""
import math

from sdl2 import SDL_KEYDOWN, SDL_KEYUP, SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN, SDLK_SPACE
from transitions import Machine

from config import (MOA_SPEED, MOA_BODY_RADIUS, MOA_SPRITE_OFFSET_Y,
                    DODGE_TIME, DODGE_SPEED, DODGE_COOLDOWN,
                    HURT_TIME, KNOCKBACK_SPEED, HIT_INVINCIBLE,
                    MOA_BASE_STATS, MOA_LEVEL)
from sprite import SheetSprite
from stats import stats_at

# 방향키 → (dx, dy, 그림 방향)
DIR_KEYS = {
    SDLK_LEFT: (-1, 0, 'left'),
    SDLK_RIGHT: (1, 0, 'right'),
    SDLK_UP: (0, 1, 'up'),
    SDLK_DOWN: (0, -1, 'down'),
}


def face_of(vx, vy):
    """방향 벡터 → 그림 방향 (더 큰 축 쪽)."""
    if abs(vx) >= abs(vy):
        return 'right' if vx > 0 else 'left'
    return 'up' if vy > 0 else 'down'


class Moa:
    states = ['idle', 'move', 'dodge', 'hurt', 'faint']

    def __init__(self, x, y, battle_map):
        self.x, self.y = x, y
        self.radius = MOA_BODY_RADIUS
        self.battle_map = battle_map
        self.sprite = SheetSprite('sprite_sheets', 'moa_sheet')

        self.held = []                 # 누르고 있는 방향키 (누른 순서)
        self.face = 'down'             # 그림 방향 (4방향)
        self.dir_x, self.dir_y = 0.0, -1.0   # 바라보는 방향 (8방향, 단위 벡터) — 기술이 나가는 방향

        self.state_time = 0.0          # 지금 상태에 들어온 뒤 흐른 시간
        self.dodge_cooldown = 0.0      # 0 이 되면 다시 회피 가능
        self.invincible = 0.0          # 0 보다 크면 무적 (남은 시간)
        self.dodge_vx = self.dodge_vy = 0.0
        self.knock_vx = self.knock_vy = 0.0

        self.level = MOA_LEVEL
        self.max_hp, self.attack, self.defense = stats_at(MOA_BASE_STATS, self.level)
        self.hp = self.max_hp

        self.machine = Machine(model=self, states=Moa.states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        self.machine.add_transition('walk', 'idle', 'move')
        self.machine.add_transition('stop', 'move', 'idle')
        self.machine.add_transition('dodge_start', ['idle', 'move'], 'dodge', conditions='can_dodge')
        self.machine.add_transition('dodge_end', 'dodge', 'idle')
        self.machine.add_transition('hit', ['idle', 'move', 'hurt'], 'hurt')
        self.machine.add_transition('recover', 'hurt', 'idle')
        self.machine.add_transition('faint', 'hurt', 'faint')
        self.on_enter_idle()

    def reset_state_time(self):
        self.state_time = 0.0

    def can_dodge(self):
        return self.dodge_cooldown <= 0

    @property
    def is_invincible(self):
        return self.invincible > 0 or self.state == 'faint'

    def take_hit(self, amount, from_x, from_y):
        """피해를 받는다. 공격한 쪽(from)의 반대 방향으로 밀려난다."""
        self.hp = max(0, self.hp - amount)
        dx, dy = self.x - from_x, self.y - from_y
        n = math.hypot(dx, dy) or 1
        self.knock_vx, self.knock_vy = dx / n, dy / n
        self.invincible = HURT_TIME + HIT_INVINCIBLE
        self.hit()

    def restart(self, x, y):
        """쓰러진 뒤 다시 시작: HP 절반 (psd 4.3)."""
        self.x, self.y = x, y
        self.hp = max(1, self.max_hp // 2)
        self.invincible = HIT_INVINCIBLE
        self.dodge_cooldown = 0.0
        self.machine.set_state('idle')
        self.reset_state_time()
        self.on_enter_idle()

    # ── 입력 ────────────────────────────────────────
    def handle_event(self, e):
        if e.type == SDL_KEYDOWN and e.key == SDLK_SPACE:
            self.dodge_start()
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
        self.sprite.play('dodge', self.face, restart=True, duration=DODGE_TIME)

    def on_enter_hurt(self):
        self.sprite.play('hurt', self.face, restart=True)

    def on_enter_faint(self):
        self.sprite.play('faint', self.face, restart=True)

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.dodge_cooldown = max(0.0, self.dodge_cooldown - dt)
        self.invincible = max(0.0, self.invincible - dt)
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

    def update_hurt(self, dt):
        self.move_by(self.knock_vx * KNOCKBACK_SPEED * dt, self.knock_vy * KNOCKBACK_SPEED * dt)
        if self.state_time >= HURT_TIME:
            if self.hp <= 0:
                self.faint()
            else:
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
