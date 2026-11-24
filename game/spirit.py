"""정령 (적). 종류별 데이터는 SPIRITS, 싸우는 방식은 배틀 AI (psd 4.6).

상태:
    idle ──think──▶ position ──settle──▶ idle            (접근·포위·거리 유지)
    idle/position ──prepare──▶ windup ──strike──▶ attack ──attack_end──▶ backoff ──rest──▶ idle
                     (공격 차례를 얻어야 함)   (머리 위 ❗ 예고)               (물러나며 차례 반납)
    idle/position/backoff ──flee──▶ retreat ──calm──▶ idle      (HP 낮음 + 방어 기술 못 씀 → 거리 벌림)
    idle/position/backoff/retreat ──evade──▶ dodge ──dodge_end──▶ idle  (모아 공격이 날아옴 → 확률로 옆으로 대시, 무적)
    (싸우는 상태) ──hit──▶ hurt ──recover──▶ idle          (짧게 밀려나고, 예고·준비 중인 공격은 취소)
    (어느 상태든) ──faint──▶ faint                        (HP 0 → 기절. 흡수될 때까지 그대로)
    faint ──drain──▶ essence_out ──purify──▶ purified    (모아가 F 로 흡수 → 기운 빠짐 → 원래 색)
    (싸우는 상태) ──hold_on──▶ hold ──release──▶ idle      (튜토리얼 연출·저항: 공격하지 않음, 무적)

배틀 AI (psd 4.6): 위에서부터 확인해 첫 번째로 맞는 기술을 쓴다. 없거나 쿨다운 중인 기술은 건너뛴다.
    1. HP 30% 이하          → 방어 기술 (예고 없이 바로)
    2. 특별 기술 준비 + 사거리 안 → 특별 기술
    3. 플레이어와 가깝다(≤200) → 근접 기술
    4. 그 외                 → 원거리 기술 (모아가 회피 중이면 기다림)
여러 마리일 때:
    · 한 번에 공격하는 정령은 SPIRIT_MAX_ATTACKERS 마리까지. 차례가 없으면 주위를 맴돌며 자리만 잡는다
    · 근접형끼리는 모아 둘레에서 서로 벌어져 포위한다
원거리 기술은 모아가 움직이는 쪽을 SPIRIT_LEAD 만큼 앞서 노린다. 근접 기술은 예고가 시작될 때 방향을 고정한다.
"""
import math
import random

from transitions import Machine

import combat
import skills
from attack import Projectile
from config import (SPIRIT_SPEED, SPIRIT_ATTACK_GAP, SPIRIT_SKILL_WINDUP, SPIRIT_NEAR, SPIRIT_LOW_HP,
                    RANGED_KEEP, SPIRIT_FIRST_DELAY, ENEMY_HURT_TIME, ENEMY_KNOCKBACK_SPEED,
                    SPIRIT_TELEGRAPH, SPIRIT_MAX_ATTACKERS, SPIRIT_BACKOFF_TIME, SPIRIT_RETREAT_TIME,
                    SPIRIT_RETREAT_COOLDOWN, SPIRIT_LEAD, SPIRIT_SPREAD_ANGLE, SPIRIT_WAIT_RING,
                    SPIRIT_DODGE_CHANCE, SPIRIT_DODGE_COOLDOWN, SPIRIT_DODGE_TIME, SPIRIT_DODGE_SPEED)
from effect import Effect
from fighter import Fighter
from moa import face_of
from sprite import SheetSprite

# 정령 종류 (psd 6.2). radius · offset 은 그림의 몸통에 맞춘 피격 원 (offset = 원 중심에서 그림 중심까지)
# folder: 그림 시트 폴더 (보스는 boss_sprites). dodge: 회피를 하는지 (튜토리얼 토리는 처음 배운 할퀴기를 맞혀 보는 단계라 피하지 않음)
SPIRITS = {
    'tori':  dict(name='토리', sheet='tori_corrupt_sheet', pure='tori_sheet', base=(40, 10, 8),
                  skills=('scratch',), drop=1.0, radius=30, offset=5, style='melee', dodge=False),
    'thorn': dict(name='가시몽', sheet='thorn_corrupt1_sheet', pure='thorn_pure_sheet', base=(40, 10, 8),
                  skills=('scratch', 'thorn_stab'), drop=0.3, radius=30, offset=5, style='melee', dodge=True),
    'dew':   dict(name='이슬방울', sheet='dew_corrupt1_sheet', pure='dew_pure_sheet', base=(34, 11, 9),
                  skills=('dew_shot', 'water_shield'), drop=0.3, radius=26, offset=8, style='ranged', dodge=True),
    # 숲2: 숲1 정령을 어둡게 색만 바꾼 개체 (그림 · 피격 원은 같고, 능력치와 기술은 강화형. psd 6.2)
    'dark_thorn': dict(name='어둠가시몽', sheet='thorn_corrupt2_sheet', pure='thorn_pure_sheet', base=(46, 14, 10),
                       skills=('dash_claw', 'shadow_mist', 'hard_fur'), drop=0.3, radius=30, offset=5,
                       style='melee', dodge=True),
    'dark_dew':   dict(name='어둠이슬방울', sheet='dew_corrupt2_sheet', pure='dew_pure_sheet', base=(40, 15, 9),
                       skills=('light_beam', 'poison_shot'), drop=0.3, radius=26, offset=8,
                       style='ranged', dodge=True),
    # 상위 정령 (보스). 움직임은 원거리형 AI + 특별 패턴 (boss.py). 이기면 특별 기술 1개 확정 (reward)
    'sylph': dict(name='실프', sheet='sylph_corrupt_sheet', pure='sylph_pure_sheet', folder='boss_sprites',
                  base=(80, 13, 11), skills=('wind_shot', 'venom_wind', 'triple_gust', 'wind_blade'),
                  reward=('triple_gust', 'wind_blade'), drop=1.0, radius=38, offset=20, style='ranged',
                  dodge=True, boss=True),
}

MELEE_KINDS = ('melee', 'melee_dot')
RANGED_KINDS = ('ranged', 'ranged_dot')
FIGHTING = ['idle', 'position', 'windup', 'attack', 'backoff', 'retreat', 'dodge', 'hurt']
GHOST_GAP = 0.05             # 회피 잔상을 남기는 간격
GHOST_LIFE = 0.25


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


def angle_diff(a, b):
    """a - b 를 -π ~ π 로."""
    return (a - b + math.pi) % math.tau - math.pi


class Spirit(Fighter):
    states = ['idle', 'position', 'windup', 'attack', 'backoff', 'retreat', 'dodge', 'hurt',
              'faint', 'essence_out', 'purified', 'hold']

    def __init__(self, kind, level, x, y, area, target):
        data = SPIRITS[kind]
        self.kind, self.name = kind, data['name']
        self.team = 'spirit'
        self.x, self.y = x, y
        self.radius = data['radius']
        self.sprite_offset = data['offset']
        self.pure_sheet = data['pure']
        self.folder = data.get('folder', 'sprite_sheets')
        self.boss = data.get('boss', False)
        self.reward_skills = data.get('reward', data['skills'])
        self.notify = None             # 알림을 띄우는 함수 (battle_mode.notice). 보스 패턴 안내에 씀
        self.style = data['style']
        self.can_dodge = data['dodge']
        self.battle_map = area
        self.opponent = target
        self.allies = [self]           # 같은 전투의 정령들 (battle_mode 가 채움). 공격 차례·포위에 씀
        self.sprite = SheetSprite(self.folder, data['sheet'])
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
        self.move_vx = self.move_vy = 0.0      # backoff · retreat · dodge 중 움직이는 방향
        self.dodge_cd = 0.0
        self.retreat_cd = 0.0
        self.seen_attacks = set()              # 피할지 이미 정한 모아의 공격 (한 공격에 한 번만 굴림)
        self.ghosts = []                       # 회피 잔상 [x, y, 행 이름, 프레임, 남은 시간]
        self.ghost_time = 0.0
        self.warn_fx = None
        self.target_v = (0.0, 0.0)             # 모아의 이동 속도 (예측 사격용)
        self.target_prev = None
        self.pure_sprite = None
        self.resisting = False         # 튜토리얼: 검은 기운에 저항 중 (기운 빠짐 동작 반복 + 떨림)
        self.shake = 0.0               # 그림 떨림 세기 (px)
        self.shake_time = 0.0
        self.wander = random.uniform(0, math.tau)   # 원거리형이 옆으로 도는 방향

        self.machine = Machine(model=self, states=type(self).states, initial='idle',
                               ignore_invalid_triggers=True, after_state_change='reset_state_time')
        add = self.machine.add_transition
        add('think', 'idle', 'position')
        add('settle', 'position', 'idle')
        add('prepare', ['idle', 'position'], 'windup')
        add('strike', 'windup', 'attack')
        add('attack_end', 'attack', 'backoff')
        add('rest', 'backoff', 'idle')
        add('flee', ['idle', 'position', 'backoff'], 'retreat')
        add('calm', 'retreat', 'idle')
        add('evade', ['idle', 'position', 'backoff', 'retreat'], 'dodge')
        add('dodge_end', 'dodge', 'idle')
        add('hit', [s for s in FIGHTING if s != 'dodge'], 'hurt')
        add('recover', 'hurt', 'idle')
        add('faint', FIGHTING, 'faint')
        add('drain', 'faint', 'essence_out')
        add('purify', 'essence_out', 'purified')
        add('hold_on', FIGHTING, 'hold')
        add('release', 'hold', 'idle')
        self.on_enter_idle()

    @property
    def is_invincible(self):
        return self.state in ('faint', 'essence_out', 'purified', 'hold', 'dodge')

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

    def others(self):
        return [s for s in self.allies if s is not self and not s.is_down and s.state != 'purified']

    # ── 배틀 AI (psd 4.6) ────────────────────────────
    def ready(self, skill_id):
        return self.skill_cd[skill_id] <= 0

    def low_hp(self):
        return self.hp <= self.max_hp * SPIRIT_LOW_HP

    def choose_skill(self):
        """지금 쓸 기술. 없으면 None."""
        if self.gap > 0:
            return None
        d = self.distance_to_target() - self.opponent.radius
        by_kind = lambda kinds: [s for s in self.skills if skills.info(s)['kind'] in kinds and self.ready(s)]
        if self.low_hp():                                                # 1. 방어
            for s in by_kind(('guard',)):
                return s
        for s in by_kind(('special',)):                                  # 2. 특별 기술
            if d <= reach_of(s):
                return s
        if d + self.opponent.radius <= SPIRIT_NEAR:                      # 3. 가까우면 근접
            near = [s for s in by_kind(MELEE_KINDS) if d <= reach_of(s)]
            if near:
                return max(near, key=lambda s: skills.info(s).get('power') or 0)
        if self.opponent.state == 'dodge':                               # 회피 중(무적)에는 쏘지 않고 기다림
            return None
        far = [s for s in by_kind(RANGED_KINDS) if d <= reach_of(s)]     # 4. 그 외 원거리
        if far:
            return random.choice(far)
        return None

    def cooldown_rate(self):
        """기술 쿨다운 배율 (보스 광폭화 때 줄어든다)."""
        return 1.0

    def has_turn(self):
        """공격 차례: 지금 예고·공격 중인 다른 정령이 SPIRIT_MAX_ATTACKERS 보다 적으면."""
        busy = sum(1 for s in self.others() if s.state in ('windup', 'attack'))
        return busy < SPIRIT_MAX_ATTACKERS

    def try_attack(self):
        skill_id = self.choose_skill()
        if skill_id is None:
            return False
        self.next_skill = skill_id
        if skills.info(skill_id)['kind'] == 'guard':    # 방어는 예고 없이 바로 (차례도 필요 없음)
            self.prepare()
            self.strike()
            return True
        if not self.has_turn():
            return False
        self.prepare()
        return True

    def should_flee(self):
        """HP 가 낮은데 방어 기술을 못 쓰고 모아가 가까우면 거리를 벌린다."""
        if self.retreat_cd > 0 or not self.low_hp():
            return False
        if any(skills.info(s)['kind'] == 'guard' and self.ready(s) for s in self.skills):
            return False
        return self.distance_to_target() < SPIRIT_NEAR + 100

    def melee_angle(self):
        """근접형이 모아에게 다가갈 각도 (모아 → 나). 다른 정령과 SPIRIT_SPREAD_ANGLE 보다 붙지 않게 벌린다."""
        ox, oy = self.opponent.x, self.opponent.y
        mine = math.atan2(self.y - oy, self.x - ox)
        spread = math.radians(SPIRIT_SPREAD_ANGLE)
        for s in self.others():
            diff = angle_diff(mine, math.atan2(s.y - oy, s.x - ox))
            if abs(diff) < spread:
                push = (spread - abs(diff)) * 0.6
                mine += push if diff >= 0 else -push
        return mine

    def wants_to_move(self):
        """움직일 방향 (단위 벡터, 느리면 더 짧게) 또는 None."""
        d = self.distance_to_target()
        a = self.angle_to_target()
        if self.style == 'melee':
            reach = (self.melee_reach or 120) + self.opponent.radius - 24   # 사거리 안쪽으로 여유 있게
            stop = reach if self.has_turn() else reach + SPIRIT_WAIT_RING   # 차례가 없으면 바깥에서 맴돎
            ring = self.melee_angle()                    # 포위할 자리 (모아 둘레의 한 점)
            ox, oy = self.opponent.x, self.opponent.y
            tx, ty = ox + math.cos(ring) * stop, oy + math.sin(ring) * stop
            dx, dy = tx - self.x, ty - self.y
            n = math.hypot(dx, dy)
            if n < 8:
                return None
            if d < stop - 30:                            # 너무 붙어 있으면 (차례 대기) 천천히
                return dx / n * 0.6, dy / n * 0.6
            return dx / n, dy / n
        near, far = RANGED_KEEP
        if d < near:                                    # 너무 가까우면 물러남
            return -math.cos(a), -math.sin(a)
        if d > far:                                     # 너무 멀면 다가감
            return math.cos(a), math.sin(a)
        side = a + math.pi / 2 * (1 if math.sin(self.wander) > 0 else -1)
        return math.cos(side) * 0.5, math.sin(side) * 0.5   # 사이에서는 천천히 옆으로

    def aim(self):
        """공격 방향. 원거리 기술은 모아가 움직이는 쪽을 조금 앞서 노린다."""
        s = skills.info(self.next_skill)
        ox, oy = self.opponent.x, self.opponent.y
        if s['shape'] == 'projectile':
            lead = (math.hypot(ox - self.x, oy - self.y) / s['speed'] + SPIRIT_SKILL_WINDUP) * SPIRIT_LEAD
            ox += self.target_v[0] * lead
            oy += self.target_v[1] * lead
        return math.atan2(oy - self.y, ox - self.x)

    # ── 회피 ─────────────────────────────────────────
    def threat_of(self, atk):
        """모아의 공격이 곧 나를 맞힐 것 같으면 (피할 기준 방향 x, y), 아니면 None."""
        if atk.done or atk.owner is None or getattr(atk.owner, 'team', None) == self.team:
            return None
        if isinstance(atk, Projectile):
            px, py = atk.shape.x, atk.shape.y
            vx, vy = atk.vx, atk.vy
            dx, dy = self.x - px, self.y - py
            v2 = vx * vx + vy * vy or 1
            t = (dx * vx + dy * vy) / v2 - max(0.0, atk.delay - atk.time)
            if not 0 <= t <= 0.45:
                return None
            cx, cy = dx - vx * t, dy - vy * t
            if math.hypot(cx, cy) > self.radius + atk.shape.r + 10:
                return None
            return px, py
        if atk.shape.hits(self.x, self.y, self.radius + 12):
            return atk.owner.x, atk.owner.y
        return None

    def check_dodge(self):
        if not self.can_dodge or self.dodge_cd > 0:
            return False
        for atk in combat.attacks:
            if id(atk) in self.seen_attacks:
                continue
            src = self.threat_of(atk)
            if src is None:
                continue
            self.seen_attacks.add(id(atk))
            if random.random() >= SPIRIT_DODGE_CHANCE:
                continue
            # 공격이 오는 쪽의 옆 + 살짝 뒤로. 벽에 막히는 쪽이면 반대쪽
            away = math.atan2(self.y - src[1], self.x - src[0])
            for side in random.sample((1, -1), 2):
                a = away + side * math.radians(65)
                vx, vy = math.cos(a), math.sin(a)
                nx, ny = self.battle_map.move(self.x, self.y, vx * 60, vy * 60, self.radius)
                if math.hypot(nx - self.x, ny - self.y) > 40:
                    break
            self.move_vx, self.move_vy = vx, vy
            self.evade()
            return True
        return False

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
        choices = [s for s in self.reward_skills if s not in owned]
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

    def on_enter_position(self):
        self.sprite.play('move', self.face)

    def on_enter_windup(self):
        self.look_at_target()
        self.attack_angle = self.angle_to_target()      # 근접: 예고가 시작될 때 방향 고정
        self.sprite.play('idle', self.face)
        if skills.info(self.next_skill)['kind'] != 'guard':
            self.warn_fx = combat.add_effect(Effect('monster', 'warn_glint', self.x, self.y + 60, scale=0.9,
                                                    follow=self, offset_y=60, lifetime=SPIRIT_TELEGRAPH))

    def on_exit_windup(self):
        if self.warn_fx:
            self.warn_fx.done = True
            self.warn_fx = None

    def on_enter_attack(self):
        skill_id = self.next_skill
        s = skills.info(skill_id)
        if s['kind'] in RANGED_KINDS or s['shape'] == 'projectile':
            self.attack_angle = self.aim()                # 원거리: 쏘는 순간 예측해서 조준
        self.face = face_of(math.cos(self.attack_angle), math.sin(self.attack_angle))
        self.skill_cd[skill_id] = s['cooldown'] * self.cooldown_rate()
        self.gap = SPIRIT_ATTACK_GAP
        self.sprite.play('attack', self.face, restart=True)
        skills.cast(skill_id, self)

    def on_enter_backoff(self):
        a = self.angle_to_target()
        if self.style == 'melee':                         # 뒤로
            self.move_vx, self.move_vy = -math.cos(a), -math.sin(a)
        else:                                             # 옆으로
            side = a + math.pi / 2 * random.choice((1, -1))
            self.move_vx, self.move_vy = math.cos(side), math.sin(side)
        self.sprite.play('move', self.face)

    def on_enter_retreat(self):
        self.retreat_cd = SPIRIT_RETREAT_COOLDOWN
        self.sprite.play('move', self.face)

    def on_enter_dodge(self):
        self.dodge_cd = SPIRIT_DODGE_COOLDOWN
        self.face = face_of(self.move_vx, self.move_vy)
        self.sprite.play('dodge', self.face, restart=True, duration=SPIRIT_DODGE_TIME)
        self.ghost_time = 0.0

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
            self.pure_sprite = SheetSprite(self.folder, self.pure_sheet)
            self.pure_sprite.play('idle', self.face)
        else:
            self.pure_sprite = None

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        self.state_time += dt
        self.gap = max(0.0, self.gap - dt)
        self.dodge_cd = max(0.0, self.dodge_cd - dt)
        self.retreat_cd = max(0.0, self.retreat_cd - dt)
        for s in self.skill_cd:
            self.skill_cd[s] = max(0.0, self.skill_cd[s] - dt)
        self.track_target(dt)
        self.update_status(dt)
        self.shake_time += dt
        getattr(self, f'update_{self.state}')(dt)
        self.update_ghosts(dt)
        self.sprite.update(dt)

    def track_target(self, dt):
        """모아의 이동 속도를 잰다 (예측 사격용, 부드럽게)."""
        o = self.opponent
        if o is None or dt <= 0:
            self.target_prev = None
            return
        if self.target_prev and self.target_prev[0] is o:
            vx = (o.x - self.target_prev[1]) / dt
            vy = (o.y - self.target_prev[2]) / dt
            self.target_v = (self.target_v[0] * 0.8 + vx * 0.2, self.target_v[1] * 0.8 + vy * 0.2)
        self.target_prev = (o, o.x, o.y)
        live = {id(a) for a in combat.attacks}
        self.seen_attacks &= live

    def target_ready(self):
        return self.opponent is not None and self.opponent.state != 'faint'

    def think_next(self):
        """idle · position 에서: 회피 → 후퇴 → 공격 → 움직임 순서로 판단. 상태를 바꿨으면 True."""
        if self.check_dodge():
            return True
        if self.should_flee():
            self.flee()
            return True
        return self.try_attack()

    def update_idle(self, dt):
        if not self.target_ready():
            return
        if self.think_next():
            return
        if self.wants_to_move():
            self.think()
        else:
            self.look_at_target()
            self.sprite.play('idle', self.face)

    def update_position(self, dt):
        if not self.target_ready():
            self.settle()
            return
        if self.think_next():
            return
        v = self.wants_to_move()
        if v is None:
            self.settle()
            return
        self.wander += dt * 0.4
        self.look_at_target()
        self.sprite.play('move', self.face)
        self.move_by(v[0] * SPIRIT_SPEED * dt, v[1] * SPIRIT_SPEED * dt)

    def update_windup(self, dt):
        if self.state_time >= SPIRIT_TELEGRAPH or skills.info(self.next_skill)['kind'] == 'guard':
            self.strike()

    def update_attack(self, dt):
        if self.sprite.done:
            self.attack_end()

    def update_backoff(self, dt):
        if self.check_dodge():
            return
        k = 1 - self.state_time / SPIRIT_BACKOFF_TIME           # 점점 느려짐
        self.move_by(self.move_vx * SPIRIT_SPEED * 1.3 * k * dt, self.move_vy * SPIRIT_SPEED * 1.3 * k * dt)
        if self.state_time >= SPIRIT_BACKOFF_TIME:
            self.rest()

    def update_retreat(self, dt):
        if self.check_dodge():
            return
        if self.target_ready():
            a = self.angle_to_target()
            self.move_vx, self.move_vy = -math.cos(a), -math.sin(a)
            self.face = face_of(self.move_vx, self.move_vy)
            self.sprite.play('move', self.face)
        self.move_by(self.move_vx * SPIRIT_SPEED * 1.2 * dt, self.move_vy * SPIRIT_SPEED * 1.2 * dt)
        if self.state_time >= SPIRIT_RETREAT_TIME:
            self.calm()

    def update_dodge(self, dt):
        self.move_by(self.move_vx * SPIRIT_DODGE_SPEED * dt, self.move_vy * SPIRIT_DODGE_SPEED * dt)
        self.ghost_time += dt
        if self.ghost_time >= GHOST_GAP:
            self.ghost_time -= GHOST_GAP
            self.ghosts.append([self.x, self.y, self.sprite.key, self.sprite.index, GHOST_LIFE])
        if self.state_time >= SPIRIT_DODGE_TIME:
            self.dodge_end()

    def update_ghosts(self, dt):
        for g in self.ghosts:
            g[4] -= dt
        self.ghosts = [g for g in self.ghosts if g[4] > 0]

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
            self.pure_sprite = SheetSprite(self.folder, self.pure_sheet)
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
        self.draw_ghosts(camera)
        sx, sy = camera.to_screen(self.x, self.y)
        if self.shake:
            sx += math.sin(self.shake_time * 55) * self.shake
        elif self.state == 'windup':                       # 예고: 살짝 떤다
            sx += math.sin(self.shake_time * 70) * 2
        (self.pure_sprite or self.sprite).draw(sx, sy + self.sprite_offset)

    def draw_ghosts(self, camera):
        """회피 잔상: 지나온 자리에 반투명한 그림."""
        if not self.ghosts:
            return
        spr = self.sprite
        key, index = spr.key, spr.index
        for x, y, k, i, life in self.ghosts:
            spr.key, spr.index = k, i
            spr.image.opacify(0.45 * life / GHOST_LIFE)
            sx, sy = camera.to_screen(x, y)
            spr.draw(sx, sy + self.sprite_offset)
        spr.image.opacify(1.0)
        spr.key, spr.index = key, index
