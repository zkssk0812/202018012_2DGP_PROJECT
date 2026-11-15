"""훈련용 가시몽 — 1주차 피격 판정을 시험하기 위한 임시 적.

다가와서 할퀴기만 한다. 2주차에 배틀 AI(psd 4.6)를 가진 정령으로 바꾼다.
    idle ──chase──▶ move ──reach──▶ attack ──attack_end──▶ idle
할퀴기는 공격 동작이 시작될 때 상대 쪽으로 방향을 고정한다. 그래서 동작을 보고 피할 수 있다.
"""
import math

from transitions import Machine

from attack import Attack
from collision import Sector
from config import (DUMMY_BASE_STATS, DUMMY_LEVEL, DUMMY_BODY_RADIUS, DUMMY_SPEED,
                    DUMMY_SPRITE_OFFSET_Y, DUMMY_ATTACK_RANGE, DUMMY_ATTACK_GAP,
                    SCRATCH_POWER, SCRATCH_RADIUS, SCRATCH_ANGLE, SCRATCH_COOLDOWN,
                    SCRATCH_WINDUP, SCRATCH_ACTIVE, SCRATCH_FX_LEAD)
from effect import Effect
from moa import face_of
from sprite import SheetSprite
from stats import stats_at


class TrainingThorn:
    states = ['idle', 'move', 'attack']

    def __init__(self, x, y, battle_map, target):
        self.x, self.y = x, y
        self.radius = DUMMY_BODY_RADIUS
        self.battle_map = battle_map
        self.target = target
        self.sprite = SheetSprite('sprite_sheets', 'thorn_corrupt1_sheet')
        self.face = 'left'

        self.level = DUMMY_LEVEL
        self.max_hp, self.attack, self.defense = stats_at(DUMMY_BASE_STATS, self.level)
        self.hp = self.max_hp

        self.state_time = 0.0
        self.cooldown = 1.0            # 시작하자마자 때리지 않도록
        self.attack_angle = 0.0
        self.new_attacks = []          # 이번 프레임에 만든 공격 (전투 모드가 가져감)
        self.new_effects = []

        self.machine = Machine(model=self, states=TrainingThorn.states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        self.machine.add_transition('chase', 'idle', 'move')
        self.machine.add_transition('reach', ['idle', 'move'], 'attack', conditions='can_attack')
        self.machine.add_transition('lose', 'move', 'idle')
        self.machine.add_transition('attack_end', 'attack', 'idle')
        self.on_enter_idle()

    @property
    def is_invincible(self):
        return False

    def reset_state_time(self):
        self.state_time = 0.0

    def can_attack(self):
        return self.cooldown <= 0

    def distance_to_target(self):
        return math.hypot(self.target.x - self.x, self.target.y - self.y)

    def angle_to_target(self):
        return math.atan2(self.target.y - self.y, self.target.x - self.x)

    def look_at_target(self):
        a = self.angle_to_target()
        self.face = face_of(math.cos(a), math.sin(a))

    # ── 상태 진입 ────────────────────────────────────
    def on_enter_idle(self):
        self.sprite.play('idle', self.face)

    def on_enter_move(self):
        self.sprite.play('move', self.face)

    def on_enter_attack(self):
        self.look_at_target()
        self.attack_angle = self.angle_to_target()
        self.cooldown = SCRATCH_COOLDOWN + DUMMY_ATTACK_GAP
        self.sprite.play('attack', self.face, restart=True)
        shape = Sector(self.x, self.y, SCRATCH_RADIUS, self.attack_angle, math.radians(SCRATCH_ANGLE))
        self.new_attacks.append(Attack(self, shape, SCRATCH_POWER, SCRATCH_WINDUP, SCRATCH_ACTIVE))

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        getattr(self, f'update_{self.state}')(dt)
        self.sprite.update(dt)

    def target_ready(self):
        return self.target.state != 'faint'

    def update_idle(self, dt):
        if not self.target_ready():
            return
        if self.distance_to_target() <= DUMMY_ATTACK_RANGE:
            self.look_at_target()
            self.sprite.play('idle', self.face)
            self.reach()
        else:
            self.chase()

    def update_move(self, dt):
        if not self.target_ready():
            self.lose()
            return
        d = self.distance_to_target()
        if d <= DUMMY_ATTACK_RANGE:
            self.reach()
            if self.state == 'move':          # 쿨다운 중이면 그 자리에서 기다림
                self.lose()
            return
        a = self.angle_to_target()
        self.look_at_target()
        self.sprite.play('move', self.face)
        self.x, self.y = self.battle_map.clamp(self.x + math.cos(a) * DUMMY_SPEED * dt,
                                               self.y + math.sin(a) * DUMMY_SPEED * dt, self.radius)

    def update_attack(self, dt):
        # 판정이 켜질 때 할퀴는 그림이 보이도록 조금 먼저 이펙트를 시작
        fx_time = SCRATCH_WINDUP - SCRATCH_FX_LEAD
        if self.state_time - dt < fx_time <= self.state_time:
            self.new_effects.append(Effect('monster', 'scratch', self.x, self.y, self.attack_angle,
                                           scale=SCRATCH_RADIUS / 136))   # 그림의 앞쪽 길이 136px → 판정 반지름
        if self.sprite.done:
            self.attack_end()

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        sx, sy = camera.to_screen(self.x, self.y)
        self.sprite.draw(sx, sy + DUMMY_SPRITE_OFFSET_Y)
