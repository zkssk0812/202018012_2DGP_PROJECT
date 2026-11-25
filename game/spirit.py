"""정령 (적). 종류별 데이터는 SPIRITS, 싸우는 방식은 행동 트리(behavior_tree.py)로 짠 배틀 AI (psd 4.6).

행동 트리 (매 프레임 위에서부터 확인, 높은 가지가 진행 중인 낮은 가지를 끊을 수 있다):
    Selector 정령
    ├ Sequence 쓰러짐      : 쓰러졌나? → 기절 · 기운 빠짐 · 원래 색 (흡수될 때까지)
    ├ Sequence 연출        : 붙잡혔나? → 붙잡혀 있기 (튜토리얼 · 숲에 서 있는 정령. 공격하지 않음, 무적)
    ├ (보스 패턴 가지)      : 보스마다 더해진다 (실프: 즉사 패턴)
    ├ Sequence 피격        : 맞았나? → 밀려나기 (예고 · 준비 중이던 공격은 끊김)
    ├ Sequence 회피        : 공격이 날아오나? (예고·공격 중이 아닐 때, 40%) → 옆으로 대시 (무적, 잔상)
    ├ Sequence 후퇴        : 위험한가? (HP 낮음 + 방어 기술 못 씀) → 거리 벌리기
    ├ Sequence 공격        : 상대가 있나? → 기술 · 차례가 있나? → 예고(❗) → 시전 → 물러나기
    ├ Sequence 자리 잡기    : 상대가 있나? → 갈 곳이 있나? → 이동 (근접형 포위 · 원거리형 거리 유지)
    └ Action 대기
지금 하고 있는 행동 이름은 state (애니메이션 · HUD · 다른 정령이 공격 차례를 셀 때 씀).

기술 고르기 (psd 4.6): 위에서부터 확인해 첫 번째로 맞는 기술을 쓴다. 없거나 쿨다운 중인 기술은 건너뛴다.
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

import combat
import skills
from attack import Projectile
from behavior_tree import BehaviorTree, Selector, Sequence, Action, Condition, SUCCESS, RUNNING
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
                  dodge=True, boss=True, reward_level=10),
    'gnome': dict(name='노움', sheet='gnome_corrupt_sheet', pure='gnome_pure_sheet', folder='boss_sprites',
                  base=(90, 16, 14), skills=('rock_charge', 'dust_whirl', 'rapid_punch', 'slam'),
                  reward=('rapid_punch', 'slam'), drop=1.0, radius=46, offset=5, style='melee',
                  dodge=False, boss=True, reward_level=15),          # 바위라 피하지 않음
}

MELEE_KINDS = ('melee', 'melee_dot')
RANGED_KINDS = ('ranged', 'ranged_dot')
DOWN = ('faint', 'essence_out', 'purified')
BUSY = ('windup', 'attack')       # 공격 중 (이때는 회피 · 후퇴하지 않고, 공격 차례로 센다)
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
    armor_acts = ()                    # 이 행동 중에는 맞아도 밀려나지 않음 (보스 패턴)

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
        self.reward_level = data.get('reward_level', 0)    # 보스: 구하면 적어도 이 레벨 (실프 10 → E 칸, 노움 15 → R 칸)
        self.cast_info = None          # 지금 쓰는 기술의 정보 (돌진 · 동작 시간)
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

        self.act = 'idle'              # 지금 하고 있는 행동 (행동 트리의 Action 이 정함)
        self.dt = 0.0
        self.held = False              # 연출로 붙잡혀 있음 (hold_on / release)
        self.hurt_left = 0.0           # 맞고 밀려나는 남은 시간
        self.move_v = None             # 자리 잡기: 이번 프레임에 움직일 방향
        self.tree = BehaviorTree(self.build_tree())
        self.sprite.play('idle', self.face)

    # ── 행동 트리 ────────────────────────────────────
    def build_tree(self):
        return Selector('정령',
            Sequence('쓰러짐', Condition('쓰러졌나', self.is_out), Action('기절·정화', self.do_down)),
            Sequence('연출', Condition('붙잡혔나', lambda: self.held), Action('붙잡혀 있기', self.do_hold)),
            *self.pattern_branches(),
            Sequence('피격', Condition('맞았나', lambda: self.hurt_left > 0), Action('밀려나기', self.do_hurt)),
            Sequence('회피', Condition('공격이 날아오나', self.want_dodge), Action('옆으로 대시', self.do_dodge)),
            Sequence('후퇴', Condition('위험한가', self.want_flee), Action('거리 벌리기', self.do_retreat)),
            Sequence('공격', Condition('상대가 있나', self.target_ready),
                     Condition('기술·차례가 있나', self.pick_attack),
                     Action('예고', self.do_windup), Action('시전', self.do_attack),
                     Action('물러나기', self.do_backoff)),
            Sequence('자리 잡기', Condition('상대가 있나', self.target_ready),
                     Condition('갈 곳이 있나', self.has_place), Action('이동', self.do_move)),
            Action('대기', self.do_idle))

    def pattern_branches(self):
        """보스가 더하는 특별 패턴 가지 (피격보다 우선). 일반 정령은 없음."""
        return []

    def hit_targets(self):
        """이 정령이 만든 것 중 모아가 공격할 수 있는 것 (노움의 생명석)."""
        return []

    def world_objects(self):
        """이 정령이 맵에 만든 것 (캐릭터와 함께 y 순서로 그림). 보스: 폭풍 · 바위 등."""
        return []

    @property
    def state(self):
        return self.act

    def begin(self, act):
        """행동을 바꾼다: 앞 행동의 정리(exit_<이름>)를 부르고 시간을 0 으로. 새로 시작했으면 True."""
        if act == self.act:
            return False
        leave = getattr(self, f'exit_{self.act}', None)
        if leave:
            leave()
        self.act = act
        self.state_time = 0.0
        return True

    @property
    def is_invincible(self):
        return self.act in DOWN or self.act in ('hold', 'dodge')

    @property
    def purify_done(self):
        """원래 색으로 완전히 돌아왔는지 (원래대로 동작까지 끝)."""
        return self.state == 'purified' and self.sprite.done

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
        busy = sum(1 for s in self.others() if s.state in BUSY)
        return busy < SPIRIT_MAX_ATTACKERS

    def pick_attack(self):
        """쓸 기술을 고른다 (next_skill). 방어 기술은 차례가 필요 없고, 다른 기술은 공격 차례가 있어야 한다."""
        skill_id = self.choose_skill()
        if skill_id is None:
            return False
        if skills.info(skill_id)['kind'] != 'guard' and not self.has_turn():
            return False
        self.next_skill = skill_id
        return True

    def want_flee(self):
        return self.act not in BUSY and self.target_ready() and self.should_flee()

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

    def want_dodge(self):
        """모아의 공격이 날아오면 (공격 하나에 한 번) 확률로 피하기로 하고 방향을 정한다."""
        if not self.can_dodge or self.dodge_cd > 0 or self.act in BUSY or not self.target_ready():
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
            return True
        return False

    # ── 맞기 (Fighter) ───────────────────────────────
    def react_to_hit(self, from_x, from_y):
        dx, dy = self.x - from_x, self.y - from_y
        n = math.hypot(dx, dy) or 1
        if self.act in self.armor_acts:                  # 보스 패턴 중: 피해만 받고 밀려나지 않음
            return
        self.knock_vx, self.knock_vy = dx / n, dy / n
        self.hurt_left = ENEMY_HURT_TIME
        self.begin('hurt')
        self.sprite.play('idle', self.face, restart=True)    # 정령 시트에는 피격 동작이 없음

    def on_zero_hp(self):
        self.hurt_left = 0.0
        self.begin('faint')
        self.sprite.play('faint', self.face, restart=True)

    def drain(self):
        """모아가 F 로 흡수하기 시작: 기운이 빠져나간다."""
        if self.act == 'faint':
            self.begin('essence_out')
            self.sprite.play('essence_out', self.face, restart=True)

    def roll_skill(self, owned):
        """흡수했을 때 줄 기술 (psd 4.1). 이미 가진 기술은 빼고 고른다. 없으면 None."""
        choices = [s for s in self.reward_skills if s not in owned]
        if choices and random.random() < self.drop_chance:
            return random.choice(choices)
        return None

    def kill(self):
        """관리자 G: 즉사 → 바로 기절. (연출로 붙잡혀 있을 때는 안 됨)"""
        if not self.is_down and not self.held:
            self.apply_damage(self.hp)

    # ── 행동 (Action) ─────────────────────────────────
    def is_out(self):
        return self.act in DOWN

    def do_down(self):
        """기절 → (흡수되면) 기운 빠짐 → 원래 색. 흡수될 때까지 계속 RUNNING (다시 일어나면 SUCCESS)."""
        if not self.is_out():
            return SUCCESS
        if self.act == 'essence_out' and self.sprite.done:
            self.begin('purified')
            self.sprite.play('purify', self.face, restart=True)
        elif self.act == 'purified':
            # 원래대로 동작이 끝나면 원래 색 그림(정화된 모습)으로 바꿔 기뻐한다
            if self.sprite.done and self.pure_sprite is None:
                self.pure_sprite = SheetSprite(self.folder, self.pure_sheet)
                self.pure_sprite.play('joy', self.face)
            if self.pure_sprite:
                self.pure_sprite.update(self.dt)
        return RUNNING

    def do_hold(self):
        """연출로 붙잡혀 있는 동안 RUNNING. 풀려나면(release) SUCCESS 로 끝난다."""
        if not self.held:
            return SUCCESS
        self.begin('hold')
        if self.resisting and self.sprite.done:          # 기운 빠짐 동작을 계속 되풀이
            self.sprite.play('essence_out', self.face, restart=True)
        if self.pure_sprite:
            self.pure_sprite.update(self.dt)
        return RUNNING

    def do_hurt(self):
        self.begin('hurt')
        dt = self.dt
        self.move_by(self.knock_vx * ENEMY_KNOCKBACK_SPEED * dt, self.knock_vy * ENEMY_KNOCKBACK_SPEED * dt)
        self.hurt_left = max(0.0, self.hurt_left - dt)
        return RUNNING if self.hurt_left > 0 else SUCCESS

    def do_dodge(self):
        if self.begin('dodge'):
            self.dodge_cd = SPIRIT_DODGE_COOLDOWN
            self.face = face_of(self.move_vx, self.move_vy)
            self.sprite.play('dodge', self.face, restart=True, duration=SPIRIT_DODGE_TIME)
            self.ghost_time = 0.0
        dt = self.dt
        self.move_by(self.move_vx * SPIRIT_DODGE_SPEED * dt, self.move_vy * SPIRIT_DODGE_SPEED * dt)
        self.ghost_time += dt
        if self.ghost_time >= GHOST_GAP:
            self.ghost_time -= GHOST_GAP
            self.ghosts.append([self.x, self.y, self.sprite.key, self.sprite.index, GHOST_LIFE])
        return SUCCESS if self.state_time >= SPIRIT_DODGE_TIME else RUNNING

    def do_retreat(self):
        if self.begin('retreat'):
            self.retreat_cd = SPIRIT_RETREAT_COOLDOWN
        if self.target_ready():
            a = self.angle_to_target()
            self.move_vx, self.move_vy = -math.cos(a), -math.sin(a)
            self.face = face_of(self.move_vx, self.move_vy)
        self.sprite.play('move', self.face)
        dt = self.dt
        self.move_by(self.move_vx * SPIRIT_SPEED * 1.2 * dt, self.move_vy * SPIRIT_SPEED * 1.2 * dt)
        return SUCCESS if self.state_time >= SPIRIT_RETREAT_TIME else RUNNING

    def do_windup(self):
        """공격 예고: 머리 위 ❗ (방어 기술은 예고 없이 바로)."""
        guard = skills.info(self.next_skill)['kind'] == 'guard'
        if self.begin('windup'):
            self.look_at_target()
            self.attack_angle = self.angle_to_target()      # 근접: 예고가 시작될 때 방향 고정
            self.sprite.play('idle', self.face)
            if not guard:
                self.warn_fx = combat.add_effect(Effect('monster', 'warn_glint', self.x, self.y + 60, scale=0.9,
                                                        follow=self, offset_y=60, lifetime=SPIRIT_TELEGRAPH))
        return SUCCESS if guard or self.state_time >= SPIRIT_TELEGRAPH else RUNNING

    def exit_windup(self):
        if self.warn_fx:
            self.warn_fx.done = True
            self.warn_fx = None

    def do_attack(self):
        if self.begin('attack'):
            skill_id = self.next_skill
            s = skills.info(skill_id)
            if s['kind'] in RANGED_KINDS or s['shape'] == 'projectile':
                self.attack_angle = self.aim()                # 원거리: 쏘는 순간 예측해서 조준
            self.face = face_of(math.cos(self.attack_angle), math.sin(self.attack_angle))
            self.skill_cd[skill_id] = s['cooldown'] * self.cooldown_rate()
            self.gap = SPIRIT_ATTACK_GAP
            self.sprite.play('attack', self.face, restart=True)
            self.cast_info = skills.cast(skill_id, self)
        info = self.cast_info
        if info and info['dash']:                       # 돌진 기술: 판정이 켜진 뒤 그 길이만큼 이동
            dx, dy, speed, dash_time, start = info['dash']
            t0, t1 = self.state_time - self.dt, self.state_time
            moving = max(0.0, min(t1, start + dash_time) - max(t0, start))
            self.move_by(dx * speed * moving, dy * speed * moving)
        lock = info['lock'] if info else 0.0
        return SUCCESS if self.sprite.done and self.state_time >= lock else RUNNING

    def exit_attack(self):
        self.cast_info = None

    def do_backoff(self):
        """치고 빠지기: 근접형은 뒤로, 원거리형은 옆으로 (점점 느려짐)."""
        if self.begin('backoff'):
            a = self.angle_to_target() if self.target_ready() else 0.0
            if self.style == 'melee':
                self.move_vx, self.move_vy = -math.cos(a), -math.sin(a)
            else:
                side = a + math.pi / 2 * random.choice((1, -1))
                self.move_vx, self.move_vy = math.cos(side), math.sin(side)
            self.sprite.play('move', self.face)
        k = max(0.0, 1 - self.state_time / SPIRIT_BACKOFF_TIME)
        dt = self.dt
        self.move_by(self.move_vx * SPIRIT_SPEED * 1.3 * k * dt, self.move_vy * SPIRIT_SPEED * 1.3 * k * dt)
        return SUCCESS if self.state_time >= SPIRIT_BACKOFF_TIME else RUNNING

    def has_place(self):
        self.move_v = self.wants_to_move()
        return self.move_v is not None

    def do_move(self):
        self.begin('position')
        v = self.move_v
        self.wander += self.dt * 0.4
        self.look_at_target()
        self.sprite.play('move', self.face)
        self.move_by(v[0] * SPIRIT_SPEED * self.dt, v[1] * SPIRIT_SPEED * self.dt)
        return SUCCESS

    def do_idle(self):
        self.begin('idle')
        if self.target_ready():
            self.look_at_target()
        self.sprite.play('idle', self.face)
        return SUCCESS

    # ── 연출 (튜토리얼 · 숲) ──────────────────────────
    def hold_on(self):
        """연출로 붙잡음: 공격하지 않고 무적. 준비 중이던 공격 · 지속 피해는 정리."""
        self.held = True
        self.cancel_pending()
        self.dots.clear()
        self.hurt_left = 0.0
        self.begin('hold')
        self.sprite.play('idle', self.face)

    def release(self):
        if self.held:
            self.held = False
            self.resist(False)
            self.gap = 1.0                        # 풀려나자마자 때리지 않도록
            self.begin('idle')

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
        self.dt = dt
        self.state_time += dt
        self.gap = max(0.0, self.gap - dt)
        self.dodge_cd = max(0.0, self.dodge_cd - dt)
        self.retreat_cd = max(0.0, self.retreat_cd - dt)
        for s in self.skill_cd:
            self.skill_cd[s] = max(0.0, self.skill_cd[s] - dt)
        self.track_target(dt)
        self.update_status(dt)
        self.shake_time += dt
        self.tree.run()
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

    def update_ghosts(self, dt):
        for g in self.ghosts:
            g[4] -= dt
        self.ghosts = [g for g in self.ghosts if g[4] > 0]

    def move_by(self, dx, dy):
        self.x, self.y = self.battle_map.move(self.x, self.y, dx, dy, self.radius)

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        self.draw_ghosts(camera)
        sx, sy = camera.to_screen(self.x, self.y)
        if self.shake:
            sx += math.sin(self.shake_time * 55) * self.shake
        elif self.act == 'windup':                         # 예고: 살짝 떤다
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
