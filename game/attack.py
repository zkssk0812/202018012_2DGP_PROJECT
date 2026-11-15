"""공격 판정 하나 (기술을 한 번 쓰면 하나 생긴다).

delay 뒤에 판정이 켜지고 active 동안 유지된다.
한 번 시전에 같은 대상은 1회만 명중한다 (psd 4.4).
"""


class Attack:
    def __init__(self, owner, shape, power, delay=0.0, active=0.1):
        self.owner = owner
        self.shape = shape
        self.power = power
        self.delay, self.active = delay, active
        self.time = 0.0
        self.already_hit = set()

    @property
    def is_active(self):
        return self.delay <= self.time < self.delay + self.active

    @property
    def done(self):
        return self.time >= self.delay + self.active

    def update(self, dt):
        self.time += dt

    def try_hit(self, target):
        """판정이 켜져 있고, 아직 안 맞힌 대상의 몸과 겹치면 True. 무적인 대상은 맞지 않는다."""
        if not self.is_active or target is self.owner or id(target) in self.already_hit:
            return False
        if target.is_invincible:
            return False
        if self.shape.hits(target.x, target.y, target.radius):
            self.already_hit.add(id(target))
            return True
        return False
