"""훈련용 정령 — 판정을 시험하기 위한 임시 적. 그림은 config.DUMMY_SHEET (지금은 타락한 토리).

다가와서 할퀴기만 한다. 배틀 AI(psd 4.6)를 가진 정령으로 바꾸기 전까지 쓴다.
    idle ──chase──▶ move ──reach──▶ attack ──attack_end──▶ idle
    idle/move/attack ──hit──▶ hurt ──recover──▶ idle     (짧게 밀려나고, 예고 중인 공격은 취소)
    (어느 상태든) ──faint──▶ faint                        (HP 0 → 기절. 흡수될 때까지 그대로)
    오프닝 규칙: 토리는 15초가 지나면 스스로를 공격해 기절한다 (psd 2.3, 남은 시간은 보여 주지 않음)
    faint ──drain──▶ essence_out ──purify──▶ purified    (모아가 F 로 흡수 → 기운 빠짐 → 원래 색)
할퀴기는 공격 동작이 시작될 때 상대 쪽으로 방향을 고정한다. 그래서 동작을 보고 피할 수 있다.
"""
import math
import random

from transitions import Machine

import skills
from config import (DUMMY_SHEET, DUMMY_BASE_STATS, DUMMY_LEVEL, DUMMY_BODY_RADIUS, DUMMY_SPEED,
                    DUMMY_SPRITE_OFFSET_Y, DUMMY_ATTACK_RANGE, DUMMY_ATTACK_GAP,
                    DUMMY_SKILL_WINDUP, DUMMY_PURE_SHEET, DUMMY_SKILLS, DUMMY_DROP_CHANCE,
                    DUMMY_SELF_FAINT_TIME,
                    ENEMY_HURT_TIME, ENEMY_KNOCKBACK_SPEED)
from fighter import Fighter
from moa import face_of
from sprite import SheetSprite

SKILL = 'scratch'


class TrainingThorn(Fighter):
    states = ['idle', 'move', 'attack', 'hurt', 'faint', 'essence_out', 'purified']

    def __init__(self, x, y, battle_map, target):
        self.x, self.y = x, y
        self.radius = DUMMY_BODY_RADIUS
        self.battle_map = battle_map
        self.opponent = target
        self.sprite = SheetSprite('sprite_sheets', DUMMY_SHEET)
        self.face = 'left'
        self.skill_windup = DUMMY_SKILL_WINDUP
        self.init_fighter(DUMMY_BASE_STATS, DUMMY_LEVEL, 'monster')

        self.state_time = 0.0
        self.cooldown = 1.0            # 시작하자마자 때리지 않도록
        self.attack_angle = 0.0
        self.knock_vx = self.knock_vy = 0.0
        self.pure_sprite = None
        self.skills = DUMMY_SKILLS
        self.drop_chance = DUMMY_DROP_CHANCE
        self.alive_time = 0.0          # 오프닝: 버틴 시간

        self.machine = Machine(model=self, states=TrainingThorn.states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        self.machine.add_transition('chase', 'idle', 'move')
        self.machine.add_transition('reach', ['idle', 'move'], 'attack', conditions='can_attack')
        self.machine.add_transition('lose', 'move', 'idle')
        self.machine.add_transition('attack_end', 'attack', 'idle')
        self.machine.add_transition('hit', ['idle', 'move', 'attack', 'hurt'], 'hurt')
        self.machine.add_transition('recover', 'hurt', 'idle')
        self.machine.add_transition('faint', ['idle', 'move', 'attack', 'hurt'], 'faint')
        self.machine.add_transition('drain', 'faint', 'essence_out')
        self.machine.add_transition('purify', 'essence_out', 'purified')
        self.on_enter_idle()

    @property
    def is_invincible(self):
        return self.state in ('faint', 'essence_out', 'purified')

    @property
    def purify_done(self):
        """원래 색으로 완전히 돌아왔는지 (원래대로 동작까지 끝)."""
        return self.state == 'purified' and self.sprite.done

    def reset_state_time(self):
        self.state_time = 0.0

    def can_attack(self):
        return self.cooldown <= 0

    def aim_angle(self):
        return self.attack_angle

    def distance_to_target(self):
        return math.hypot(self.opponent.x - self.x, self.opponent.y - self.y)

    def angle_to_target(self):
        return math.atan2(self.opponent.y - self.y, self.opponent.x - self.x)

    def look_at_target(self):
        a = self.angle_to_target()
        self.face = face_of(math.cos(a), math.sin(a))

    # ── 맞기 (Fighter) ───────────────────────────────
    def react_to_hit(self, from_x, from_y):
        dx, dy = self.x - from_x, self.y - from_y
        n = math.hypot(dx, dy) or 1
        self.knock_vx, self.knock_vy = dx / n, dy / n
        self.hit()

    def on_zero_hp(self):
        self.faint()

    def roll_skill(self, owned):
        """흡수했을 때 줄 기술 (psd 4.1). 이미 가진 기술은 빼고 고른다. 없으면 None."""
        choices = [s for s in self.skills if s not in owned]
        if choices and random.random() < self.drop_chance:
            return random.choice(choices)
        return None

    def kill(self):
        """관리자 G: 즉사 → 바로 기절."""
        if not self.is_down:
            self.apply_damage(self.hp)

    # ── 상태 진입 ────────────────────────────────────
    def on_enter_idle(self):
        self.sprite.play('idle', self.face)

    def on_enter_move(self):
        self.sprite.play('move', self.face)

    def on_enter_attack(self):
        self.look_at_target()
        self.attack_angle = self.angle_to_target()
        self.cooldown = skills.info(SKILL)['cooldown'] + DUMMY_ATTACK_GAP
        self.sprite.play('attack', self.face, restart=True)
        skills.cast(SKILL, self)

    def on_enter_hurt(self):
        self.sprite.play('idle', self.face, restart=True)    # 가시몽 시트에는 피격 동작이 없음

    def on_enter_faint(self):
        self.sprite.play('faint', self.face, restart=True)

    def on_enter_essence_out(self):
        self.sprite.play('essence_out', self.face, restart=True)

    def on_enter_purified(self):
        self.sprite.play('purify', self.face, restart=True)

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.cooldown = max(0.0, self.cooldown - dt)
        self.update_status(dt)
        if DUMMY_SELF_FAINT_TIME and not self.is_down and self.opponent.state != 'faint':
            self.alive_time += dt
            if self.alive_time >= DUMMY_SELF_FAINT_TIME:   # 오프닝: 모아를 다치게 할까 두려워 스스로를 공격
                self.kill()
                return
        getattr(self, f'update_{self.state}')(dt)
        self.sprite.update(dt)

    def target_ready(self):
        return self.opponent.state != 'faint'

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
        self.move_by(math.cos(a) * DUMMY_SPEED * dt, math.sin(a) * DUMMY_SPEED * dt)

    def update_attack(self, dt):
        if self.sprite.done:
            self.attack_end()

    def update_hurt(self, dt):
        self.move_by(self.knock_vx * ENEMY_KNOCKBACK_SPEED * dt, self.knock_vy * ENEMY_KNOCKBACK_SPEED * dt)
        if self.state_time >= ENEMY_HURT_TIME:
            self.recover()

    def update_faint(self, dt):
        pass                                  # 모아가 흡수할 때까지 기절해 있음

    def update_essence_out(self, dt):
        if self.sprite.done:
            self.purify()

    def update_purified(self, dt):
        # 원래대로 동작이 끝나면 원래 색 그림(정화된 모습)으로 바꿔 기뻐한다
        if self.sprite.done and self.pure_sprite is None:
            self.pure_sprite = SheetSprite('sprite_sheets', DUMMY_PURE_SHEET)
            self.pure_sprite.play('joy', self.face)
        if self.pure_sprite:
            self.pure_sprite.update(dt)

    def move_by(self, dx, dy):
        self.x, self.y = self.battle_map.clamp(self.x + dx, self.y + dy, self.radius)

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        sx, sy = camera.to_screen(self.x, self.y)
        (self.pure_sprite or self.sprite).draw(sx, sy + DUMMY_SPRITE_OFFSET_Y)
