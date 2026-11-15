"""싸우는 쪽(모아, 정령)이 공통으로 가지는 능력치·지속 피해·방어.

각 클래스는 init_fighter() 를 부르고, 아래를 직접 구현한다.
    react_to_hit(from_x, from_y)  맞았을 때 반응 (넉백, 피격 동작)
    on_zero_hp()                  HP 가 0 이 되었을 때 (쓰러짐/기절)
"""
import math

from stats import stats_at

DOT_TICK = 1.0          # 지속 피해는 1초마다


class Fighter:
    def init_fighter(self, base_stats, level, fx_owner):
        self.level = level
        self.max_hp, self.attack, self.defense = stats_at(base_stats, level)
        self.hp = self.max_hp
        self.fx_owner = fx_owner          # 이펙트 시트: 'player' 또는 'monster'
        self.dots = {}                    # 기술 id → [매초 비율, 남은 시간, 다음 틱까지]
        self.guard_rate, self.guard_time = 0.0, 0.0
        self.pending = []                 # 아직 판정이 켜지지 않은 내 공격 (맞으면 취소)
        self.on_dot_tick = None           # 지속 피해가 들어갈 때 부르는 함수 (이펙트용)

    @property
    def is_down(self):
        return self.hp <= 0

    # ── 피해 ────────────────────────────────────────
    def apply_damage(self, amount):
        if self.is_down:
            return 0
        if self.guard_time > 0:
            amount = max(1, math.floor(amount * (1 - self.guard_rate) + 0.5))
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.dots.clear()
            self.cancel_pending()
            self.on_zero_hp()
        return amount

    def take_hit(self, amount, from_x, from_y):
        """기술에 맞음: 피해 + 반응. 쓰러지면 반응하지 않는다."""
        self.apply_damage(amount)
        if not self.is_down:
            self.cancel_pending()
            self.react_to_hit(from_x, from_y)

    def add_dot(self, skill_id, rate, duration):
        """같은 기술의 지속 피해는 겹치지 않고 시간만 새로 시작한다."""
        if not self.is_down:
            self.dots[skill_id] = [rate, duration, DOT_TICK]

    def add_guard(self, rate, duration):
        self.guard_rate, self.guard_time = rate, duration

    def cancel_pending(self):
        import combat                       # combat 이 fighter 를 쓰지 않도록 여기서 불러옴
        for atk in self.pending:
            atk.cancel()
        self.pending.clear()
        combat.cancel_timers(self)

    def update_status(self, dt):
        self.guard_time = max(0.0, self.guard_time - dt)
        self.pending = [a for a in self.pending if not a.started]
        for skill_id in list(self.dots):
            dot = self.dots.get(skill_id)
            if dot is None:
                continue
            dot[1] -= dt
            dot[2] -= dt
            if dot[2] <= 0:                       # 무적이어도 지속 피해는 계속 (psd 4.4)
                dot[2] += DOT_TICK
                self.apply_damage(max(1, math.floor(self.max_hp * dot[0] + 0.5)))
                if self.on_dot_tick:
                    self.on_dot_tick(self)
            if dot[1] <= 1e-6:
                self.dots.pop(skill_id, None)
