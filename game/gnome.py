"""바위의 상위 정령 노움 (숲2 보스, psd 6.4). 행동 트리로 싸운다.

평소에는 일반 정령의 근접형 행동 트리를 그대로 쓴다 (돌진 박치기 · 흙먼지 회오리 · 연속 주먹 · 내려찍기).
바위라서 회피는 하지 않는다. 특별 패턴은 Spirit 트리의 '보스 패턴 가지'로 더해진다 (피격보다 우선).
패턴 중에는 맞아도 밀려나지 않는다 (피해는 받음).

    Sequence 대지 균열 : HP 70% 이하가 됐나? (한 번) → 대지 균열
        모아 둘레 바닥 칸(7×5) 중 일부가 붉게 갈라지고, 1초 뒤 그 칸에서 바위 기둥이 솟는다 (즉사급 85%).
        3번. 안전한 칸이 매번 바뀌고 줄어든다 (45% → 30% → 2칸). 모아 바로 옆 칸 하나는 늘 안전.
    Sequence 대지의 분노 : HP 30% 이하가 됐나? (한 번) → 대지의 분노 (노움 무적)
        노움 둘레에 큰 바위 4개가 떨어진다 → "무너져라!" 2.5초 힘 모으기 → 맵 전체 충격파 (즉사급 85%).
        노움 기준으로 바위 뒤(그림자)에 있어야만 안전. 힘을 모으는 동안 흙먼지 회오리 2개가 모아를 쫓아와 밀어낸다.
        충격파가 지나간 바위는 부서진다.
"""
import math
import random

import combat
from attack import Attack
from behavior_tree import Sequence, Action, Condition, SUCCESS, RUNNING
from collision import Rect
from boss import screen_fill
from collision import separate
from config import (HEAVY_HIT, QUAKE_HP, QUAKE_TILE, QUAKE_COLS, QUAKE_ROWS, QUAKE_WAVES, QUAKE_WARN,
                    QUAKE_SAFE, QUAKE_TIME, WRATH_HP, WRATH_ROCKS, WRATH_ROCK_DIST, WRATH_ROCK_R,
                    WRATH_ROCK_DROP, WRATH_CHARGE, WRATH_BLAST_AT, WRATH_TIME, WRATH_WHIRLS,
                    WRATH_WHIRL_SPEED, WRATH_WHIRL_HIT)
from cutscene import bubble
from pico2d import draw_circle
from effect import Effect
from pico2d import draw_rectangle
from sdl2 import SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND
import pico2d
from spirit import Spirit

PILLAR_TIME = 0.6           # 솟은 바위 기둥이 보이는 시간
ROCK_FALL = 0.35            # 바위가 떨어지는 시간 (그림)
SHELTER_MARGIN = 10         # 바위 그림자 판정 여유 (바위 반지름보다 이만큼 안쪽이어야 숨은 것)


class Boulder:
    """대지의 분노 때 떨어지는 큰 바위. 몸을 막고, 노움의 충격파를 가린다."""

    def __init__(self, x, y, delay):
        self.x, self.y = x, y
        self.radius = WRATH_ROCK_R
        self.delay = delay          # 떨어지기 시작할 때까지
        self.time = 0.0
        self.broken = False
        self.done = False

    @property
    def landed(self):
        return self.time >= self.delay + ROCK_FALL

    def update(self, dt):
        self.time += dt
        if self.broken and self.time >= 0.6:
            self.done = True

    def crumble(self):
        self.broken = True
        self.time = 0.0
        combat.add_effect(Effect('monster', 'slam_impact', self.x, self.y, scale=0.9))

    def draw(self, camera):
        if self.time < self.delay and not self.broken:
            return
        sx, sy = camera.to_screen(self.x, self.y)
        if not self.landed and not self.broken:                     # 떨어지는 중: 위에서 내려옴 + 바닥 그림자
            k = (self.time - self.delay) / ROCK_FALL
            draw_circle(int(sx), int(sy), int(self.radius * k), 40, 25, 15)
            sy += (1 - k) * 400
        r = self.radius * (1.0 if not self.broken else max(0.0, 1 - self.time / 0.6))
        if r > 1:
            draw_rectangle(sx - r, sy - r * 0.7, sx + r, sy + r * 0.9, 110, 85, 70, filled=True)
            draw_rectangle(sx - r, sy - r * 0.7, sx + r, sy + r * 0.9, 50, 35, 25)


class Whirl:
    """대지의 분노 힘 모으기 동안 모아를 쫓는 흙먼지 회오리. 닿으면 조금 아프고 밀려난다."""

    def __init__(self, owner, x, y):
        self.owner = owner
        self.x, self.y = x, y
        self.radius = 40
        self.cool = 0.0
        self.done = False
        self.fx = Effect('monster', 'dust_whirl', x, y, scale=0.45)

    def update(self, dt, moa):
        self.fx.update(dt)
        self.cool = max(0.0, self.cool - dt)
        if moa is None or moa.is_down:
            return
        dx, dy = moa.x - self.x, moa.y - self.y
        d = math.hypot(dx, dy) or 1
        self.x, self.y = self.owner.battle_map.move(self.x, self.y, dx / d * WRATH_WHIRL_SPEED * dt,
                                                    dy / d * WRATH_WHIRL_SPEED * dt, self.radius)
        if d < self.radius + moa.radius and self.cool <= 0 and not moa.is_invincible:
            self.cool = 1.0
            moa.take_hit(max(1, math.ceil(moa.max_hp * WRATH_WHIRL_HIT)), self.x, self.y)

    def vanish(self):
        self.done = True
        combat.add_effect(Effect('monster', 'hit_spark', self.x, self.y, scale=1.0))

    def draw(self, camera):
        self.fx.x, self.fx.y = self.x, self.y
        self.fx.draw(camera)


class Gnome(Spirit):
    armor_acts = ('quake', 'wrath')

    def __init__(self, kind, level, x, y, area, target):
        self.quake_done = False
        self.wrath_done = False
        super().__init__(kind, level, x, y, area, target)
        self.cells = []             # 바닥 칸: dict(rect, wave, state='warn'|'pillar', time)
        self.waves_done = 0
        self.rocks = []             # 대지의 분노: 바위
        self.whirls = []            # 대지의 분노: 흙먼지 회오리
        self.wrath_step = None      # None → 'charge' → 'blast'
        self.flash = 0.0
        self.speech, self.speech_time = '', 0.0

    def pattern_branches(self):
        # 위에 있을수록 먼저 (HP 가 한 번에 많이 깎여 둘 다 조건이 되면 대지의 분노 먼저)
        return [Sequence('대지의 분노', Condition('HP 30% 이하가 됐나', self.want_wrath),
                         Action('대지의 분노', self.do_wrath)),
                Sequence('대지 균열', Condition('HP 70% 이하가 됐나', self.want_quake),
                         Action('대지 균열', self.do_quake))]

    def world_objects(self):
        return self.rocks + self.whirls

    @property
    def is_invincible(self):
        return super().is_invincible or self.act == 'wrath'

    def pattern_text(self):
        """HUD 에 보여 줄 지금 패턴 (없으면 None)."""
        if self.act == 'quake':
            return '대지 균열', (255, 170, 90)
        if self.act == 'wrath':
            if self.wrath_step == 'charge':
                return f'바위 뒤로!  {max(0.0, WRATH_BLAST_AT - self.state_time):.1f}초', (255, 140, 60)
            return '대지의 분노', (255, 140, 60)
        return None

    def update(self, dt):
        self.flash = max(0.0, self.flash - dt)
        self.speech_time = max(0.0, self.speech_time - dt)
        super().update(dt)
        for r in self.rocks:
            r.update(dt)
        self.rocks = [r for r in self.rocks if not r.done]
        for w in self.whirls:
            w.update(dt, self.opponent)
        self.whirls = [w for w in self.whirls if not w.done]
        moa = self.opponent
        if moa:
            for r in self.rocks:                             # 바위는 모아의 몸을 막는다
                if r.landed and not r.broken:
                    separate(moa, r, b_fixed=True)

    def say(self, text, duration=3.0):
        if self.notify:
            self.notify(text, duration)

    # ── 대지 균열 ────────────────────────────────────
    def want_quake(self):
        return not self.quake_done and not self.held and self.hp <= self.max_hp * QUAKE_HP

    def do_quake(self):
        if self.begin('quake'):
            self.quake_done = True
            self.cancel_pending()
            self.waves_done = 0
            self.cells = []
            self.look_at_target()
            self.say('노움이 땅을 내려친다! 갈라지는 바닥을 피하자', 3.0)
        t = self.state_time
        if self.waves_done < len(QUAKE_WAVES) and t >= QUAKE_WAVES[self.waves_done]:
            self.crack(self.waves_done)
            self.waves_done += 1
        for c in self.cells:
            c['time'] += self.dt
            if c['state'] == 'warn' and c['time'] >= QUAKE_WARN:
                self.raise_pillar(c)
        self.cells = [c for c in self.cells if not (c['state'] == 'pillar' and c['time'] >= PILLAR_TIME)]
        if self.sprite.done:
            self.sprite.play('idle', self.face)
        if t >= QUAKE_TIME and not self.cells:
            return SUCCESS
        return RUNNING

    def exit_quake(self):
        self.cells = []
        self.shake = 0.0

    def crack(self, wave):
        """모아 둘레 칸 중 위험한 칸을 정해 갈라지게 한다."""
        moa = self.opponent
        area = self.battle_map
        left, bottom, right, top = area.arena
        cx, cy = int(moa.x // QUAKE_TILE), int(moa.y // QUAKE_TILE)
        grid = []
        for i in range(-(QUAKE_COLS // 2), QUAKE_COLS // 2 + 1):
            for j in range(-(QUAKE_ROWS // 2), QUAKE_ROWS // 2 + 1):
                l, b = (cx + i) * QUAKE_TILE, (cy + j) * QUAKE_TILE
                r, t = l + QUAKE_TILE, b + QUAKE_TILE
                if r <= left or l >= right or t <= bottom or b >= top:
                    continue
                grid.append(((i, j), (max(l, left), max(b, bottom), min(r, right), min(t, top))))
        near = [g for g in grid if max(abs(g[0][0]), abs(g[0][1])) == 1]       # 모아 바로 옆 칸
        safe = {random.choice(near)[0]} if near else set()
        rule = QUAKE_SAFE[wave]
        count = rule if isinstance(rule, int) else int(len(grid) * rule)
        others = [g[0] for g in grid if g[0] not in safe]
        random.shuffle(others)
        safe |= set(others[:max(0, count - len(safe))])
        for key, rect in grid:
            if key not in safe:
                self.cells.append(dict(rect=rect, wave=wave, state='warn', time=0.0))
        self.sprite.play('attack', self.face, restart=True)
        self.shake = 3.0
        combat.add_effect(Effect('monster', 'slam_impact', self.x, self.y, scale=1.4))

    def raise_pillar(self, cell):
        cell['state'] = 'pillar'
        cell['time'] = 0.0
        atk = Attack(self, Rect(*cell['rect']), power=None, delay=0.0, active=0.25,
                     skill_id='quake_pillar', hit_fx='slam_impact')
        atk.ratio = HEAVY_HIT
        combat.add_attack(atk)
        l, b, r, t = cell['rect']
        combat.add_effect(Effect('monster', 'slam_impact', (l + r) / 2, (b + t) / 2,
                                 scale=(r - l) / 224 * 1.1))
        self.shake = 1.0

    # ── 대지의 분노 ──────────────────────────────────
    def want_wrath(self):
        return not self.wrath_done and not self.held and self.hp <= self.max_hp * WRATH_HP

    def do_wrath(self):
        if self.begin('wrath'):
            self.wrath_done = True
            self.quake_done = True                          # (한꺼번에 깎였으면 균열은 건너뜀)
            self.cancel_pending()
            self.dots.clear()
            self.wrath_step = None
            self.drop_rocks()
            self.look_at_target()
            self.sprite.play('attack', self.face, restart=True)
            self.say('노움이 바위를 불러낸다! 충격파가 오기 전에 바위 뒤로 숨자', 3.5)
        t = self.state_time
        if self.wrath_step is None and t >= WRATH_ROCK_DROP[1] + 0.2:
            self.wrath_step = 'charge'
            self.shake = 3.0
            self.speech, self.speech_time = '무너져라...!', WRATH_CHARGE
            combat.add_effect(Effect('monster', 'charge_orb', self.x, self.y + 20, scale=2.0,
                                     follow=self, offset_y=20, lifetime=WRATH_CHARGE))
            moa = self.opponent
            for k in range(WRATH_WHIRLS):                   # 노움 앞쪽 양옆에서 회오리가 생겨 모아를 쫓는다
                a = self.angle_to_target() + (k * 2 - 1) * math.pi / 4
                self.whirls.append(Whirl(self, self.x + math.cos(a) * 220, self.y + math.sin(a) * 220))
        if self.wrath_step == 'charge' and t >= WRATH_BLAST_AT:
            self.wrath_step = 'blast'
            self.blast()
        if self.sprite.done:
            self.sprite.play('idle', self.face)
        return SUCCESS if t >= WRATH_TIME else RUNNING

    def exit_wrath(self):
        self.shake = 0.0
        for r in self.rocks:
            if not r.broken:
                r.crumble()
        for w in self.whirls:
            w.vanish()
        self.gap = 1.0

    def drop_rocks(self):
        """노움 둘레(맵 안)에 바위를 고르게 떨어뜨린다. 모아 쪽은 바위 사이(빈틈)가 되게 → 움직여서 숨어야 한다."""
        lo, hi = WRATH_ROCK_DIST
        base = self.angle_to_target() + math.pi / WRATH_ROCKS * random.choice((1, -1))
        t0, t1 = WRATH_ROCK_DROP
        self.rocks = []
        for k in range(WRATH_ROCKS):
            a = base + k * math.tau / WRATH_ROCKS
            d = random.uniform(lo, hi)
            x, y = self.battle_map.clamp(self.x + math.cos(a) * d, self.y + math.sin(a) * d, WRATH_ROCK_R + 20)
            self.rocks.append(Boulder(x, y, t0 + (t1 - t0) * k / max(1, WRATH_ROCKS - 1)))

    def sheltered(self, body):
        """노움에서 body 까지 직선을 바위가 가리면 True (바위 뒤 그림자 안)."""
        vx, vy = body.x - self.x, body.y - self.y
        dist = math.hypot(vx, vy)
        if dist < 1:
            return False
        ux, uy = vx / dist, vy / dist
        for r in self.rocks:
            if r.broken or not r.landed:
                continue
            rx, ry = r.x - self.x, r.y - self.y
            along = rx * ux + ry * uy                      # 직선 위에서 바위까지 거리
            side = abs(rx * uy - ry * ux)                   # 직선에서 바위 중심까지 거리
            if 0 < along < dist and side <= r.radius - SHELTER_MARGIN:
                return True
        return False

    def blast(self):
        """맵 전체 충격파: 바위 뒤에 숨지 않았으면 즉사급 피해. 바위는 부서진다."""
        self.shake = 1.5
        self.flash = 0.8
        combat.add_effect(Effect('monster', 'slam_impact', self.x, self.y, scale=5.0))
        moa = self.opponent
        if moa and not moa.is_down and not moa.is_invincible and not self.sheltered(moa):
            moa.take_hit(max(1, math.ceil(moa.max_hp * HEAVY_HIT)), self.x, self.y)
            combat.add_effect(Effect('monster', 'hit_spark', moa.x, moa.y, scale=1.5))
        for r in self.rocks:
            r.crumble()
        for w in self.whirls:
            w.vanish()

    def draw_top(self, camera):
        """앞쪽 나무 위: 힘 모으기 어둠, 충격파 섬광, 말풍선."""
        if self.act == 'wrath' and self.wrath_step == 'charge':
            k = min(1.0, (self.state_time - WRATH_ROCK_DROP[1] - 0.2) / WRATH_CHARGE)
            screen_fill((50, 30, 10), 0.12 + 0.3 * k + 0.06 * math.sin(self.state_time * 12))
        if self.flash > 0:
            screen_fill((255, 235, 200), 0.85 * self.flash / 0.8)
        if self.speech_time > 0 and not self.is_down:
            sx, sy = camera.to_screen(self.x, self.y)
            w = 28 + len(self.speech) * 17
            sx = max(w / 2 + 10, min(1280 - w / 2 - 10, sx))
            bubble(sx, max(80, min(sy + 100, 720 - 190)), self.speech)

    # ── 그리기 ──────────────────────────────────────
    def draw_ground(self, camera):
        """캐릭터 아래 바닥에 그리는 것: 갈라지는 칸."""
        if not self.cells:
            return
        SDL_SetRenderDrawBlendMode(pico2d.pico2d.renderer, SDL_BLENDMODE_BLEND)
        for c in self.cells:
            l, b, r, t = c['rect']
            sl, sb = camera.to_screen(l, b)
            sr, st = camera.to_screen(r, t)
            if c['state'] == 'warn':
                k = c['time'] / QUAKE_WARN
                blink = 0.5 + 0.5 * math.sin(c['time'] * (10 + 20 * k))
                draw_rectangle(sl + 3, sb + 3, sr - 3, st - 3, 200, 60, 40, int(60 + 90 * k * blink), filled=True)
                draw_rectangle(sl + 3, sb + 3, sr - 3, st - 3, 255, 140, 90)
            else:
                draw_rectangle(sl, sb, sr, st, 120, 80, 50, 170, filled=True)
