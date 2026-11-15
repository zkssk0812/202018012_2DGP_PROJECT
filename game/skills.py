"""기술 데이터와 시전 (psd 5.2, 5.3, 6.3, 6.4).

수치는 모두 psd 의 임시값이다. 판정 크기는 5.3, 위력·쿨다운은 5.2 / 6.3 / 6.4.
cast(skill_id, caster) 가 판정·이펙트를 combat 에 넣고, 시전자가 할 일(동작, 묶이는 시간, 돌진)을 돌려준다.

caster 에 필요한 것: x, y, aim_angle(), opponent, skill_windup, fx_owner, add_guard()
"""
import math

import combat
from config import FX_SKIP
from attack import Attack, Projectile
from collision import Circle, Sector, Capsule
from effect import Effect

# 기술 id → 데이터
#   kind: melee / melee_dot / ranged / ranged_dot / guard / special
#   shape: sector / multi_sector / capsule / dash / self_circle / projectile / slam / guard
SKILLS = {
    # ── 일반 정령 · 숲1 ──
    'scratch':      dict(name='할퀴기', kind='melee', shape='sector', r=120, angle=90,
                         power=40, cooldown=1.0, fx='scratch'),
    'thorn_stab':   dict(name='가시찌르기', kind='melee_dot', shape='sector', r=140, angle=60,
                         power=20, dot=(0.03, 4), cooldown=5.0, fx='thorn'),
    'dew_shot':     dict(name='이슬탄', kind='ranged', shape='projectile', r=16, speed=600, dist=700,
                         power=30, cooldown=1.5, fx='dew_shot', hit_fx='dew_hit'),
    'water_shield': dict(name='물방울막', kind='guard', shape='guard', guard=(0.7, 1.0),
                         cooldown=6.0, fx='water_shield'),
    # ── 일반 정령 · 숲2 (강화형) ──
    'dash_claw':    dict(name='돌진 할퀴기', kind='melee', shape='dash', length=250, r=35, dash_time=0.2,
                         power=55, cooldown=3.0, fx='dash_claw'),
    'shadow_mist':  dict(name='그림자 안개', kind='melee_dot', shape='self_circle', r=150,
                         dot=(0.04, 4), cooldown=7.0, fx='shadow_mist'),
    'hard_fur':     dict(name='단단한 털', kind='guard', shape='guard', guard=(0.8, 1.5),
                         cooldown=6.0, fx='hard_fur'),
    'light_beam':   dict(name='빛줄기', kind='ranged', shape='capsule', length=700, r=25, active=0.2,
                         power=50, cooldown=3.0, fx='light_beam'),
    'poison_shot':  dict(name='독가루탄', kind='ranged_dot', shape='projectile', r=18, speed=500, dist=600,
                         explode_r=120, dot=(0.04, 4), cooldown=7.0, fx='poison_shot',
                         explode_fx='poison_burst'),
    # ── 실프 ──
    'wind_shot':    dict(name='바람탄', kind='ranged', shape='projectile', r=18, speed=650, dist=800,
                         power=35, cooldown=1.5, fx='wind_shot', hit_fx='wind_hit'),
    'venom_wind':   dict(name='독바람탄', kind='ranged_dot', shape='projectile', r=18, speed=550, dist=800,
                         dot=(0.04, 4), cooldown=6.0, fx='venom_wind', hit_fx='wind_hit'),
    'triple_gust':  dict(name='세 갈래 바람', kind='special', shape='projectile', r=18, speed=600, dist=800,
                         count=3, spread=30, power=30, cooldown=6.0, fx='wind_shot', hit_fx='wind_hit',
                         cast_fx='triple_gust'),
    'wind_blade':   dict(name='바람 칼날', kind='special', shape='capsule', length=900, r=30, active=0.2,
                         power=70, cooldown=8.0, fx='wind_blade'),
    # ── 노움 ──
    'rock_charge':  dict(name='돌진 박치기', kind='melee', shape='dash', length=300, r=50, dash_time=0.25,
                         power=60, cooldown=3.0, fx='rock_charge'),
    'dust_whirl':   dict(name='흙먼지 회오리', kind='melee_dot', shape='self_circle', r=180,
                         dot=(0.04, 4), cooldown=7.0, fx='dust_whirl'),
    'rapid_punch':  dict(name='연속 주먹', kind='special', shape='multi_sector', r=160, angle=60,
                         hits=3, interval=0.25, power=30, cooldown=6.0, fx='rapid_punch'),
    'slam':         dict(name='내려찍기', kind='special', shape='slam', r=200, max_dist=400, warn=0.5,
                         power=100, cooldown=12.0, fx='slam_impact', warn_fx='slam_warn'),
}

# 기술 목록 순서 (관리자 기술 선택 창)
ORDER = ['scratch', 'thorn_stab', 'dew_shot', 'water_shield',
         'dash_claw', 'shadow_mist', 'hard_fur', 'light_beam', 'poison_shot',
         'wind_shot', 'venom_wind', 'triple_gust', 'wind_blade',
         'rock_charge', 'dust_whirl', 'rapid_punch', 'slam']

KIND_NAMES = {'melee': '근접', 'melee_dot': '근접 지속', 'ranged': '원거리', 'ranged_dot': '원거리 지속',
              'guard': '방어', 'special': '특별'}

CAST_LOCK = 0.3          # 기술을 쓰는 동안 움직이지 못하는 기본 시간


def info(skill_id):
    return SKILLS[skill_id]


def anim_of(skill_id):
    s = SKILLS[skill_id]
    if s['kind'] in ('ranged', 'ranged_dot') or s['shape'] in ('projectile', 'capsule'):
        return 'ranged'
    return 'melee'


def cast(skill_id, caster):
    """기술을 쓴다. 돌려주는 값: dict(anim, lock, dash=(dx, dy, speed, time, windup) 또는 None)."""
    s = SKILLS[skill_id]
    shape = s['shape']
    angle = caster.aim_angle()
    windup = caster.skill_windup
    x, y = caster.x, caster.y
    owner = caster.fx_owner
    result = dict(anim=anim_of(skill_id), lock=CAST_LOCK, dash=None)

    def fx_at(name, fx_x, fx_y, a=0.0, scale=0.5, scale_y=None, **kw):
        """이펙트를 띄우는 함수를 만든다. 판정의 on_start 에 걸면 판정이 켜지는 순간 뜬다."""
        def spawn(_atk=None):
            combat.add_effect(Effect(owner, name, fx_x, fx_y, a, scale, scale_y, **kw))
        return spawn

    def attack(shape_obj, delay, active=0.1, **kw):
        return combat.add_attack(Attack(caster, shape_obj, s.get('power'), delay, active,
                                        skill_id=skill_id, dot=s.get('dot'),
                                        hit_fx=s.get('hit_fx', 'hit_spark'), **kw))

    if shape == 'sector':
        atk = attack(Sector(x, y, s['r'], angle, math.radians(s['angle'])), windup)
        atk.on_start = fx_at(s['fx'], x, y, angle, scale=s['r'] / 136, skip=FX_SKIP)

    elif shape == 'multi_sector':                       # 연속 주먹: 타마다 따로 판정
        for k in range(s['hits']):
            d = windup + k * s['interval']
            atk = attack(Sector(x, y, s['r'], angle, math.radians(s['angle'])), d)
            atk.on_start = fx_at(s['fx'], x, y, angle, scale=s['r'] / 120, skip=FX_SKIP)
        result['lock'] = windup + s['hits'] * s['interval']

    elif shape == 'capsule':                            # 빔: 즉시 판정, active 동안 유지
        cap = Capsule.from_origin(x, y, angle, s['length'], s['r'])
        cell = combat_fx_length(owner, s['fx'])
        atk = attack(cap, windup, active=s['active'])
        atk.on_start = fx_at(s['fx'], x, y, angle, scale=s['length'] / cell, scale_y=0.8, skip=FX_SKIP)

    elif shape == 'dash':                               # 돌진: 지나갈 경로 전체가 판정
        cap = Capsule.from_origin(x, y, angle, s['length'], s['r'])
        cell = combat_fx_length(owner, s['fx'])
        atk = attack(cap, windup, active=s['dash_time'])
        atk.on_start = fx_at(s['fx'], x, y, angle, scale=s['length'] / cell, skip=FX_SKIP)
        speed = s['length'] / s['dash_time']
        result['dash'] = (math.cos(angle), math.sin(angle), speed, s['dash_time'], windup)
        result['lock'] = windup + s['dash_time'] + 0.05

    elif shape == 'self_circle':                        # 자기 중심 원
        atk = attack(Circle(x, y, s['r']), windup)
        atk.on_start = fx_at(s['fx'], x, y, scale=s['r'] * 2 / 192, lifetime=0.8)

    elif shape == 'projectile':
        count = s.get('count', 1)
        spread = math.radians(s.get('spread', 0))
        if 'cast_fx' in s:
            fx_at(s['cast_fx'], x, y, angle, scale=0.5)()
        for k in range(count):
            a = angle + (k - (count - 1) / 2) * spread
            launch(caster, skill_id, s, a, windup)

    elif shape == 'slam':                               # 내려찍기: 상대 위치를 착지 지점으로 고정
        tx, ty = slam_target(caster, s['max_dist'], angle)
        fx_at(s['warn_fx'], tx, ty, scale=s['r'] * 2 / 192, lifetime=s['warn'])()
        atk = attack(Circle(tx, ty, s['r']), s['warn'])
        atk.on_start = fx_at(s['fx'], tx, ty, scale=s['r'] * 2 / 224)
        result['lock'] = s['warn'] + 0.1

    elif shape == 'guard':                              # 방어: 판정 없음, 몸에 막
        rate, duration = s['guard']
        caster.add_guard(rate, duration)
        fx_at(s['fx'], x, y, scale=0.5, follow=caster, lifetime=duration)()
        result['lock'] = 0.15

    return result


def launch(caster, skill_id, s, angle, delay):
    x, y = caster.x, caster.y
    owner = caster.fx_owner

    on_end = None
    if 'explode_r' in s:                                # 독가루탄: 맞거나 최대 거리에서 폭발
        def on_end(p):
            px, py = p.shape.x, p.shape.y
            combat.add_attack(Attack(caster, Circle(px, py, s['explode_r']), None, 0.0, 0.1,
                                     skill_id=skill_id, dot=s.get('dot')))
            combat.add_effect(Effect(owner, s['explode_fx'], px, py, scale=s['explode_r'] * 2 / 192))

    p = Projectile(caster, x, y, angle, s['r'], s['speed'], s['dist'],
                   power=s.get('power'), delay=delay, skill_id=skill_id,
                   dot=None if 'explode_r' in s else s.get('dot'),
                   hit_fx=s.get('hit_fx', 'hit_spark'), on_end=on_end)

    def show(_atk):
        p.fx = combat.add_effect(Effect(owner, s['fx'], p.shape.x, p.shape.y, angle,
                                        scale=s['r'] * 2 / 40))
    p.on_start = show
    combat.add_attack(p)


def slam_target(caster, max_dist, angle):
    opp = getattr(caster, 'opponent', None)
    if opp is None or opp.is_down:
        return caster.x + math.cos(angle) * max_dist, caster.y + math.sin(angle) * max_dist
    dx, dy = opp.x - caster.x, opp.y - caster.y
    d = math.hypot(dx, dy)
    if d > max_dist:
        dx, dy = dx / d * max_dist, dy / d * max_dist
    return caster.x + dx, caster.y + dy


def combat_fx_length(owner, name):
    """이펙트 그림에서 시전자 위치(origin)부터 앞쪽 끝까지의 길이."""
    from effect import EffectSheet
    i = EffectSheet.get(owner).meta['effects'][name]
    return i['cell_w'] - i['origin'][0]
