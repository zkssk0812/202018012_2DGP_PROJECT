"""정령 (적). 종류별 데이터는 SPIRITS, 싸우는 방식은 배틀 AI (psd 4.6).

상태:
    idle ──chase──▶ move ──reach──▶ attack ──attack_end──▶ idle
    idle/move/attack ──hit──▶ hurt ──recover──▶ idle     (짧게 밀려나고, 예고 중인 공격은 취소)
    (어느 상태든) ──faint──▶ faint                        (HP 0 → 기절. 흡수될 때까지 그대로)
    faint ──drain──▶ essence_out ──purify──▶ purified    (모아가 F 로 흡수 → 기운 빠짐 → 원래 색)
    idle/move/attack/hurt ──hold_on──▶ hold ──release──▶ idle   (튜토리얼 연출·저항: 공격하지 않음, 무적)

배틀 AI (psd 4.6): 위에서부터 확인해 첫 번째로 맞는 기술을 쓴다. 없거나 쿨다운 중인 기술은 건너뛴다.
    1. HP 30% 이하          → 방어 기술
    2. 특별 기술 준비 + 사거리 안 → 특별 기술
    3. 플레이어와 가깝다(≤200) → 근접 기술
    4. 그 외                 → 원거리 기술
움직임: 근접형은 다가가고, 원거리형은 일정 거리를 유지한다.
기술은 공격 동작이 시작될 때 상대 쪽으로 방향을 고정한다. 그래서 동작을 보고 피할 수 있다.
"""
import math
import random

from transitions import Machine

import skills
from config import (SPIRIT_SPEED, SPIRIT_ATTACK_GAP, SPIRIT_SKILL_WINDUP, SPIRIT_NEAR, SPIRIT_LOW_HP,
                    RANGED_KEEP, SPIRIT_FIRST_DELAY, ENEMY_HURT_TIME, ENEMY_KNOCKBACK_SPEED)
from fighter import Fighter
from moa import face_of
from sprite import SheetSprite

# 정령 종류 (psd 6.2). radius · offset 은 그림의 몸통에 맞춘 피격 원 (offset = 원 중심에서 그림 중심까지)
SPIRITS = {
    'tori':  dict(name='토리', sheet='tori_corrupt_sheet', pure='tori_sheet', base=(40, 10, 8),
                  skills=('scratch',), drop=1.0, radius=30, offset=5, style='melee'),
    'thorn': dict(name='가시몽', sheet='thorn_corrupt1_sheet', pure='thorn_pure_sheet', base=(40, 10, 8),
                  skills=('scratch', 'thorn_stab'), drop=0.3, radius=30, offset=5, style='melee'),
    'dew':   dict(name='이슬방울', sheet='dew_corrupt1_sheet', pure='dew_pure_sheet', base=(34, 11, 9),
                  skills=('dew_shot', 'water_shield'), drop=0.3, radius=26, offset=8, style='ranged'),
}

MELEE_KINDS = ('melee', 'melee_dot')
RANGED_KINDS = ('ranged', 'ranged_dot')


def reach_of(skill_id):
    """기술 판정이 시전자 중심에서 닿는 거리."""
    s = skills.info(skill_id)
    shape = s['shape']
    if shape in ('sector', 'multi_sector', 'self_circle'):
        return s['r']
    if shape in ('dash', 'capsule'):
        return s['length']
    if shape == 'projectile':
        return s['dist']
    if shape == 'slam':
        return s['max_dist']
    return 0


class Spirit(Fighter):
    states = ['idle', 'move', 'attack', 'hurt', 'faint', 'essence_out', 'purified', 'hold']

    def __init__(self, kind, level, x, y, area, target):
        data = SPIRITS[kind]
        self.kind, self.name = kind, data['name']
        self.team = 'spirit'
        self.x, self.y = x, y
        self.radius = data['radius']
        self.sprite_offset = data['offset']
        self.pure_sheet = data['pure']
        self.style = data['style']
        self.battle_map = area
        self.opponent = target
        self.sprite = SheetSprite('sprite_sheets', data['sheet'])
        self.face = 'left'
        self.skill_windup = SPIRIT_SKILL_WINDUP
        self.init_fighter(data['base'], level, 'monster')

        self.skills = data['skills']
        self.drop_chance = data['drop']
        self.skill_cd = {s: 0.0 for s in self.skills}
        self.gap = random.uniform(*SPIRIT_FIRST_DELAY)   # 다음 기술까지 쉬는 시간
        self.next_skill = None
        self.melee_reach = min((reach_of(s) for s in self.skills
                                if skills.info(s)['kind'] in MELEE_KINDS), default=None)

        self.state_time = 0.0
        self.attack_angle = 0.0
        self.knock_vx = self.knock_vy = 0.0
        self.pure_sprite = None
        self.resisting = False         # 튜토리얼: 검은 기운에 저항 중 (기운 빠짐 동작 반복 + 떨림)
        self.shake = 0.0               # 그림 떨림 세기 (px)
        self.shake_time = 0.0
        self.wander = random.uniform(0, math.tau)   # 원거리형이 옆으로 도는 방향

        self.machine = Machine(model=self, states=Spirit.states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        self.machine.add_transition('chase', 'idle', 'move')
        self.machine.add_transition('reach', ['idle', 'move'], 'attack')
        self.machine.add_transition('lose', 'move', 'idle')
        self.machine.add_transition('attack_end', 'attack', 'idle')
        self.machine.add_transition('hit', ['idle', 'move', 'attack', 'hurt'], 'hurt')
        self.machine.add_transition('recover', 'hurt', 'idle')
        self.machine.add_transition('faint', ['idle', 'move', 'attack', 'hurt'], 'faint')
        self.machine.add_transition('drain', 'faint', 'essence_out')
        self.machine.add_transition('purify', 'essence_out', 'purified')
        self.machine.add_transition('hold_on', ['idle', 'move', 'attack', 'hurt'], 'hold')
        self.machine.add_transition('release', 'hold', 'idle')
        self.on_enter_idle()

    @property
    def is_invincible(self):
        return self.state in ('faint', 'essence_out', 'purified', 'hold')

    @property
    def purify_done(self):
        """원래 색으로 완전히 돌아왔는지 (원래대로 동작까지 끝)."""
        return self.state == 'purified' and self.sprite.done

    def reset_state_time(self):
        self.state_time = 0.0

    def aim_angle(self):
        return self.attack_angle

    def distance_to_target(self):
        return math.hypot(self.opponent.x - self.x, self.opponent.y - self.y)

    def angle_to_target(self):
        return math.atan2(self.opponent.y - self.y, self.opponent.x - self.x)

    def look_at_target(self):
        a = self.angle_to_target()
        self.face = face_of(math.cos(a), math.sin(a))

    # ── 배틀 AI (psd 4.6) ────────────────────────────
    def ready(self, skill_id):
        return self.skill_cd[skill_id] <= 0

    def choose_skill(self):
        """지금 쓸 기술. 없으면 None."""
        if self.gap > 0:
            return None
        d = self.distance_to_target() - self.opponent.radius
        by_kind = lambda kinds: [s for s in self.skills if skills.info(s)['kind'] in kinds and self.ready(s)]
        if self.hp <= self.max_hp * SPIRIT_LOW_HP:                       # 1. 방어
            for s in by_kind(('guard',)):
                return s
        for s in by_kind(('special',)):                                  # 2. 특별 기술
            if d <= reach_of(s):
                return s
        if d + self.opponent.radius <= SPIRIT_NEAR:                      # 3. 가까우면 근접
            near = [s for s in by_kind(MELEE_KINDS) if d <= reach_of(s)]
            if near:
                return max(near, key=lambda s: skills.info(s).get('power') or 0)
        far = [s for s in by_kind(RANGED_KINDS) if d <= reach_of(s)]     # 4. 그 외 원거리
        if far:
            return random.choice(far)
        return None

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
        """관리자 G: 즉사 → 바로 기절. (연출로 붙잡혀 있을 때는 안 됨)"""
        if not self.is_down and self.state != 'hold':
            self.apply_damage(self.hp)

    # ── 상태 진입 ────────────────────────────────────
    def on_enter_idle(self):
        self.sprite.play('idle', self.face)

    def on_enter_move(self):
        self.sprite.play('move', self.face)

    def on_enter_attack(self):
        skill_id = self.next_skill
        self.look_at_target()
        self.attack_angle = self.angle_to_target()
        self.skill_cd[skill_id] = skills.info(skill_id)['cooldown']
        self.gap = SPIRIT_ATTACK_GAP
        self.sprite.play('attack', self.face, restart=True)
        skills.cast(skill_id, self)

    def on_enter_hurt(self):
        self.sprite.play('idle', self.face, restart=True)    # 정령 시트에는 피격 동작이 없음

    def on_enter_faint(self):
        self.sprite.play('faint', self.face, restart=True)

    def on_enter_essence_out(self):
        self.sprite.play('essence_out', self.face, restart=True)

    def on_enter_purified(self):
        self.sprite.play('purify', self.face, restart=True)

    def on_enter_hold(self):
        self.cancel_pending()
        self.dots.clear()
        self.sprite.play('idle', self.face)

    def on_exit_hold(self):
        self.resist(False)
        self.gap = 1.0                        # 풀려나자마자 때리지 않도록

    # ── 튜토리얼 연출 ─────────────────────────────────
    def resist(self, on):
        """검은 기운에 저항: 기운 빠짐 동작을 되풀이하며 떤다."""
        self.resisting = on
        self.shake = 4.0 if on else 0.0
        self.sprite.play('essence_out' if on else 'idle', self.face, restart=True)

    def look_toward(self, x, y=None):
        self.face = face_of(x - self.x, (self.y if y is None else y) - self.y)
        if self.pure_sprite:
            self.pure_sprite.play(self.pure_sprite.key.rsplit('_', 1)[0], self.face)
        self.sprite.play(self.sprite.key.rsplit('_', 1)[0], self.face)

    def show_pure(self, on):
        """원래 색(타락하기 전) 그림으로 보이기."""
        if on:
            self.pure_sprite = SheetSprite('sprite_sheets', self.pure_sheet)
            self.pure_sprite.play('idle', self.face)
        else:
            self.pure_sprite = None

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.gap = max(0.0, self.gap - dt)
        for s in self.skill_cd:
            self.skill_cd[s] = max(0.0, self.skill_cd[s] - dt)
        self.update_status(dt)
        self.shake_time += dt
        getattr(self, f'update_{self.state}')(dt)
        self.sprite.update(dt)

    def target_ready(self):
        return self.opponent is not None and self.opponent.state != 'faint'

    def try_attack(self):
        skill_id = self.choose_skill()
        if skill_id:
            self.next_skill = skill_id
            self.reach()
            return True
        return False

    def wants_to_move(self):
        """움직일 방향 (단위 벡터) 또는 None. 근접형은 다가가고, 원거리형은 거리를 유지하며 옆으로 돈다."""
        d = self.distance_to_target()
        a = self.angle_to_target()
        if self.style == 'melee':
            stop = (self.melee_reach or 120) + self.opponent.radius - 12
            return (math.cos(a), math.sin(a)) if d > stop else None
        near, far = RANGED_KEEP
        if d < near:                                    # 너무 가까우면 물러남
            return -math.cos(a), -math.sin(a)
        if d > far:                                     # 너무 멀면 다가감
            return math.cos(a), math.sin(a)
        side = a + math.pi / 2 * (1 if math.sin(self.wander) > 0 else -1)
        return math.cos(side) * 0.5, math.sin(side) * 0.5   # 사이에서는 천천히 옆으로

    def update_idle(self, dt):
        if not self.target_ready():
            return
        if self.try_attack():
            return
        if self.wants_to_move():
            self.chase()
        else:
            self.look_at_target()
            self.sprite.play('idle', self.face)

    def update_move(self, dt):
        if not self.target_ready():
            self.lose()
            return
        if self.try_attack():
            return
        v = self.wants_to_move()
        if v is None:
            self.lose()
            return
        self.wander += dt * 0.4
        self.look_at_target()
        self.sprite.play('move', self.face)
        self.move_by(v[0] * SPIRIT_SPEED * dt, v[1] * SPIRIT_SPEED * dt)

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
            self.pure_sprite = SheetSprite('sprite_sheets', self.pure_sheet)
            self.pure_sprite.play('joy', self.face)
        if self.pure_sprite:
            self.pure_sprite.update(dt)

    def update_hold(self, dt):
        if self.resisting and self.sprite.done:          # 기운 빠짐 동작을 계속 되풀이
            self.sprite.play('essence_out', self.face, restart=True)
        if self.pure_sprite:
            self.pure_sprite.update(dt)

    def move_by(self, dx, dy):
        self.x, self.y = self.battle_map.move(self.x, self.y, dx, dy, self.radius)

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        sx, sy = camera.to_screen(self.x, self.y)
        if self.shake:
            sx += math.sin(self.shake_time * 55) * self.shake
        (self.pure_sprite or self.sprite).draw(sx, sy + self.sprite_offset)
