"""공격 판정 (기술을 한 번 쓰면 하나 이상 생긴다).

delay 뒤에 판정이 켜지고 active 동안 유지된다.
한 번 시전에 같은 대상은 1회만 명중한다 (psd 4.4).
Projectile 은 판정 원이 날아가고, 맞히거나 최대 거리에서 사라진다(폭발할 수도 있다).
"""
import math

from collision import Circle


class Attack:
    def __init__(self, owner, shape, power=None, delay=0.0, active=0.1,
                 skill_id=None, dot=None, hit_fx='hit_spark'):
        self.owner = owner
        self.shape = shape
        self.power = power              # None 이면 피해 없이 지속 피해만
        self.delay, self.active = delay, active
        self.skill_id = skill_id
        self.dot = dot                  # (매초 최대 HP 비율, 시간) 또는 None
        self.hit_fx = hit_fx
        self.time = 0.0
        self.already_hit = set()
        self.cancelled = False
        self.on_start = None            # 판정이 켜지는 순간 한 번 부르는 함수
        self.lethal = False             # True 면 맞은 대상은 즉사 (방어 무시)
        self._started = False

    @property
    def started(self):
        return self.time >= self.delay

    @property
    def is_active(self):
        return not self.cancelled and self.delay <= self.time < self.delay + self.active

    @property
    def done(self):
        return self.cancelled or self.time >= self.delay + self.active

    def cancel(self):
        if not self.started:
            self.cancelled = True

    def update(self, dt):
        self.time += dt
        if not self._started and self.started and not self.cancelled:
            self._started = True
            if self.on_start:
                self.on_start(self)

    def source(self):
        """맞은 쪽이 밀려날 기준점."""
        return self.owner.x, self.owner.y

    def try_hit(self, target):
        """판정이 켜져 있고, 아직 안 맞힌 대상의 몸과 겹치면 True. 무적인 대상은 맞지 않는다."""
        if not self.is_active or target is self.owner or id(target) in self.already_hit:
            return False
        if getattr(target, 'team', None) == getattr(self.owner, 'team', None):
            return False                          # 같은 편(정령끼리)은 맞히지 않음
        if target.is_invincible:
            return False
        if self.shape.hits(target.x, target.y, target.radius):
            self.already_hit.add(id(target))
            return True
        return False

    def on_hit(self, target):
        """맞힌 뒤 처리 (투사체는 여기서 사라진다)."""


class Projectile(Attack):
    def __init__(self, owner, x, y, angle, radius, speed, max_dist, power=None, delay=0.0,
                 skill_id=None, dot=None, hit_fx='hit_spark', on_end=None):
        super().__init__(owner, Circle(x, y, radius), power, delay, active=max_dist / speed,
                         skill_id=skill_id, dot=dot, hit_fx=hit_fx)
        self.angle = angle
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.on_end = on_end            # 사라질 때 부르는 함수 (폭발 등), 인자: 이 투사체
        self.fx = None                  # 날아가는 그림 (Effect)

    def update(self, dt):
        was_done = self.done
        super().update(dt)
        if self.started and not self.cancelled:
            self.shape.x += self.vx * dt
            self.shape.y += self.vy * dt
            if self.fx:
                self.fx.x, self.fx.y = self.shape.x, self.shape.y
        if self.done and not was_done and not self.cancelled:
            self._end()

    def source(self):
        return self.shape.x - self.vx, self.shape.y - self.vy

    def on_hit(self, target):
        self.active = self.time - self.delay       # 맞은 순간 끝
        self._end()

    def _end(self):
        if self.fx:
            self.fx.done = True
        if self.on_end:
            fn, self.on_end = self.on_end, None
            fn(self)
