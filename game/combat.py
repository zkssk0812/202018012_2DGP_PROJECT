"""전투 중 살아 있는 공격 판정과 이펙트를 모아 두고, 명중을 처리한다."""
import math

from effect import Effect
from stats import damage

attacks = []
effects = []
timers = []           # [남은 시간, 부를 함수, 주인] — 연출을 시간차로 띄울 때


def clear():
    attacks.clear()
    effects.clear()
    timers.clear()


def schedule(delay, fn, owner=None):
    timers.append([delay, fn, owner])


def cancel_timers(owner):
    """주인이 맞아서 기술이 끊기면 남은 연출도 지운다."""
    timers[:] = [t for t in timers if t[2] is not owner]


def add_attack(atk):
    attacks.append(atk)
    if not atk.started:
        atk.owner.pending.append(atk)
    return atk


def add_effect(fx):
    effects.append(fx)
    return fx


def dot_tick_fx(target):
    """지속 피해가 들어갈 때 머리 위에 표시."""
    add_effect(Effect('player', 'dot_tick', target.x, target.y + 30, follow=target, offset_y=30,
                      lifetime=0.6))


def update(dt, fighters):
    for t in list(timers):
        t[0] -= dt
        if t[0] <= 0:
            timers.remove(t)
            t[1]()

    for atk in list(attacks):
        atk.update(dt)
        for target in fighters:
            if atk.try_hit(target):
                hit(atk, target)
    attacks[:] = [a for a in attacks if not a.done]

    for fx in effects:
        fx.update(dt)
    effects[:] = [fx for fx in effects if not fx.done]


def hit(atk, target):
    owner = atk.owner
    if getattr(atk, 'lethal', False):                # 즉사 공격 (실프 즉사 패턴): 방어도 무시하고 HP 0
        target.guard_time = 0.0
        target.apply_damage(target.hp)
        add_effect(Effect(owner.fx_owner, atk.hit_fx, target.x, target.y))
        atk.on_hit(target)
        return
    if getattr(atk, 'ratio', None):                  # 즉사급 공격 (노움 패턴): 최대 HP 의 비율만큼 (방어 기술로 줄일 수 있음)
        sx, sy = atk.source()
        target.take_hit(max(1, math.ceil(target.max_hp * atk.ratio)), sx, sy)
        add_effect(Effect(owner.fx_owner, atk.hit_fx, target.x, target.y))
        atk.on_hit(target)
        return
    if atk.power:
        sx, sy = atk.source()
        target.take_hit(damage(atk.power, owner.attack, target.defense), sx, sy)
        add_effect(Effect(owner.fx_owner, atk.hit_fx, target.x, target.y))
    if atk.dot:
        target.add_dot(atk.skill_id, *atk.dot)
    atk.on_hit(target)


def draw(camera):
    for fx in effects:
        fx.draw(camera)
