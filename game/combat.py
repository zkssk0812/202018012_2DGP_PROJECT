"""전투 중 살아 있는 공격 판정과 이펙트를 모아 두고, 명중을 처리한다."""
from effect import Effect
from stats import damage

attacks = []
effects = []


def clear():
    attacks.clear()
    effects.clear()


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
