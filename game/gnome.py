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
    Sequence 생명석 (HP 0 기믹) : 생명석 기믹 중인가? → 생명석 (노움 무적, 무릎 꿇음)
        "아직이다...!" — 생명석 4개(빨강·파랑·초록·노랑)가 0.7초 간격으로 떨어진다. 떨어진 순서가 정답.
        같은 색의 기운 4개도 흩어진다 (짝 생명석을 부수기 전에는 흐리고 흡수할 수 없음).
        순서대로 [생명석 부수기(3대) → 같은 색 기운 F 흡수] 4번 → 노움이 쓰러진다 (평소처럼 흡수해 구함).
        틀린 생명석을 부수면 큰 피해(60%) + 노움 HP 20% 로 부활. 25초가 지나도 부활. 다음 HP 0 때 다시.
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
from essence import Essence
from config import (LIFE_COLORS, LIFE_FALL_START, LIFE_FALL_GAP, LIFE_STONE_HITS, LIFE_LIMIT, LIFE_FAIL_HIT,
                    LIFE_REVIVE, LIFE_DIST, LIFE_SPACING)
from pico2d import draw_circle
from effect import Effect
from pico2d import draw_rectangle
from sdl2 import SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND
import pico2d
from spirit import Spirit

PILLAR_TIME = 0.6           # 솟은 바위 기둥이 보이는 시간
ROCK_FALL = 0.35            # 바위가 떨어지는 시간 (그림)
SHELTER_MARGIN = 10         # 바위 그림자 판정 여유 (바위 반지름보다 이만큼 안쪽이어야 숨은 것)


def draw_fx(name, frame, sx, sy, scale=0.5, scale_y=None, alpha=1.0):
    """노움 이펙트 시트(effects_gnome)의 한 칸을 화면 (sx, sy) 에 그린다 (origin 기준)."""
    from effect import EffectSheet
    sheet = EffectSheet.get('gnome')
    i = sheet.meta['effects'][name]
    w, h = i['cell_w'], i['cell_h']
    sy_scale = scale if scale_y is None else scale_y
    left = i['x'] + min(frame, i['frames'] - 1) * w
    bottom = sheet.sheet_h - i['y'] - h
    ox, oy = i['origin']
    cx, cy = sx + (w / 2 - ox) * scale, sy + (oy - h / 2) * sy_scale
    if alpha < 1:
        sheet.image.opacify(max(0.0, alpha))
    sheet.image.clip_draw(left, bottom, w, h, cx, cy, w * scale, h * sy_scale)
    if alpha < 1:
        sheet.image.opacify(1.0)


def draw_drop_shadow(sx, sy, r, k):
    """떨어지는 것의 바닥 그림자 (점점 커짐)."""
    SDL_SetRenderDrawBlendMode(pico2d.pico2d.renderer, SDL_BLENDMODE_BLEND)
    w, h = r * k, r * k * 0.35
    draw_rectangle(sx - w, sy - h, sx + w, sy + h, 0, 0, 0, int(90 * k), filled=True)


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
            draw_drop_shadow(sx, sy - 20, self.radius, k)
            sy += (1 - k) * 400
        k = 1.0 if not self.broken else max(0.0, 1 - self.time / 0.6)
        if k > 0.02:
            draw_fx('boulder', 0, sx, sy - 22, scale=self.radius / 78 * k, alpha=k)


class LifeStone:
    """생명석: 모아의 공격으로 부순다 (LIFE_STONE_HITS 대). 떨어진 순서대로 부숴야 한다."""
    team = 'spirit'                 # 노움의 공격에는 맞지 않음
    defense = 1

    def __init__(self, owner, order, ci, x, y, delay):
        self.owner, self.order, self.ci = owner, order, ci
        self.color = LIFE_COLORS[ci][1]
        self.x, self.y = x, y
        self.radius = 34
        self.delay = delay
        self.time = 0.0
        self.hits = 0
        self.broken = False
        self.flash = 0.0
        self.done = False

    @property
    def landed(self):
        return self.time >= self.delay + ROCK_FALL

    @property
    def is_invincible(self):
        return self.broken or not self.landed

    def take_hit(self, amount, from_x, from_y):
        if self.is_invincible:
            return
        self.hits += 1
        self.flash = 0.12
        if self.hits >= LIFE_STONE_HITS:
            self.broken = True
            self.time = 0.0
            combat.add_effect(Effect('monster', 'slam_impact', self.x, self.y, scale=0.7))
            self.owner.stone_broken(self)

    def add_dot(self, *args):
        pass

    def update(self, dt):
        self.time += dt
        self.flash = max(0.0, self.flash - dt)
        if self.broken and self.time >= 0.5:
            self.done = True

    def draw(self, camera):
        if self.time < self.delay and not self.broken:
            return
        sx, sy = camera.to_screen(self.x, self.y)
        if not self.landed and not self.broken:
            k = (self.time - self.delay) / ROCK_FALL
            draw_drop_shadow(sx, sy - 22, self.radius, k)
            sy += (1 - k) * 450
        k = 1.0 if not self.broken else max(0.0, 1 - self.time / 0.5)
        if k <= 0.02:
            return
        scale = 0.72 * k * (1.1 if self.flash > 0 else 1.0)          # 맞으면 살짝 커짐
        draw_fx(f'life_stone_{self.ci}', min(self.hits, 3), sx, sy - 22, scale=scale, alpha=k)


class LifeOrb(Essence):
    """생명석과 같은 색의 기운. 짝 생명석을 부수기 전에는 잠겨 있다 (흐리고 흡수할 수 없음)."""

    def __init__(self, owner, order, ci, x, y, on_absorbed):
        super().__init__(owner, x, y, drop_time=0.9, drains_source=False, on_absorbed=on_absorbed)
        self.order, self.ci = order, ci
        self.color = LIFE_COLORS[ci][1]
        self.locked = True
        self.gone = False           # True 면 전투 모드가 목록에서 뺀다 (기믹이 끝났을 때)

    def in_range(self, body):
        return not self.locked and not self.gone and super().in_range(body)

    def draw_ground(self, camera):
        if self.gone or self.state in ('dropping', 'done'):
            return
        if self.locked:
            return
        sx, sy = camera.to_screen(self.x, self.y)
        draw_circle(int(sx), int(sy), int(self.radius), *self.color)        # 흡수 범위 (검은 기운과 같은 방식)

    def draw(self, camera):
        if self.gone or self.state == 'done':
            return
        x, y = self.position()
        sx, sy = camera.to_screen(x, y)
        scale = 0.75 if self.locked else 1.15 + 0.1 * math.sin(self.time * 6)
        if self.state == 'flying':
            scale *= max(0.2, 1 - self.fly_time / max(self.fly_total, 1e-6))
        frame = int(self.time * 10) % 6
        draw_fx(f'life_orb_{self.ci}', frame, sx, sy + 6 * math.sin(self.time * 3), scale=scale,
                alpha=0.55 if self.locked else 1.0)


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
    armor_acts = ('quake', 'wrath', 'last_stand')

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
        self.stones = []            # 생명석
        self.orbs = []              # 같은 색 기운 (전투 모드의 기운 목록에도 들어감)
        self.next_order = 0         # 다음에 부숴야 할 생명석 순서
        self.need_orb = False       # 생명석을 부쉈고, 그 색 기운을 흡수해야 함
        self.limit_at = 0.0
        self.add_essence = None     # 전투 모드에 기운을 넣는 함수 (battle_mode.set_essence)
        self.stand_result = None    # 기믹 결과: None / 'clear' / 'fail'

    def pattern_branches(self):
        # 위에 있을수록 먼저 (HP 가 한 번에 많이 깎여 둘 다 조건이 되면 대지의 분노 먼저)
        return [Sequence('생명석', Condition('생명석 기믹 중인가', lambda: self.act == 'last_stand'),
                         Action('생명석', self.do_last_stand)),
                Sequence('대지의 분노', Condition('HP 30% 이하가 됐나', self.want_wrath),
                         Action('대지의 분노', self.do_wrath)),
                Sequence('대지 균열', Condition('HP 70% 이하가 됐나', self.want_quake),
                         Action('대지 균열', self.do_quake))]

    def world_objects(self):
        return self.rocks + self.whirls + self.stones

    def hit_targets(self):
        return [st for st in self.stones if not st.broken]

    @property
    def is_invincible(self):
        return super().is_invincible or self.act in ('wrath', 'last_stand')

    def pattern_text(self):
        """HUD 에 보여 줄 지금 패턴 (없으면 None)."""
        if self.act == 'quake':
            return '대지 균열', (255, 170, 90)
        if self.act == 'wrath':
            if self.wrath_step == 'charge':
                return f'바위 뒤로!  {max(0.0, WRATH_BLAST_AT - self.state_time):.1f}초', (255, 140, 60)
            return '대지의 분노', (255, 140, 60)
        if self.act == 'last_stand':
            dots = ''.join('●' if k < self.next_order else '○' for k in range(len(LIFE_COLORS)))
            left = max(0.0, self.limit_at - self.state_time)
            return f'생명석 {dots}  {left:.0f}초', (255, 230, 140)
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
        for st in self.stones:
            st.update(dt)
        self.stones = [st for st in self.stones if not st.done]
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

    # ── 생명석 (HP 0 기믹) ────────────────────────────
    def on_zero_hp(self):
        """쓰러지는 대신 생명석 기믹 (이미 풀었으면 평소처럼 기절)."""
        if self.stand_result == 'clear':
            super().on_zero_hp()
            return
        self.hurt_left = 0.0
        self.begin('last_stand')
        self.start_stand()

    def kill(self):
        """관리자 G: 기믹 중이면 바로 푼 것으로 (기절)."""
        if self.act == 'last_stand':
            self.finish_stand('clear')
            return
        super().kill()

    def do_last_stand(self):
        if self.act != 'last_stand':                        # 풀었거나(기절) 실패해 일어섰으면 끝
            return SUCCESS
        if self.resisting and self.sprite.done:
            self.sprite.play('essence_out', self.face, restart=True)
        if self.stand_result is None and self.state_time >= self.limit_at:
            self.say('시간이 다 됐다... 노움이 다시 일어선다!', 3.0)
            self.finish_stand('fail')
        return RUNNING

    def start_stand(self):
        self.stand_result = None
        self.cancel_pending()
        self.dots.clear()
        self.next_order, self.need_orb = 0, False
        self.resisting = True                               # 무릎 꿇고 기운이 빠져나가는 동작을 되풀이
        self.shake = 2.0
        self.sprite.play('essence_out', self.face, restart=True)
        self.speech, self.speech_time = '아직이다...!', 2.2
        self.say('생명석이 떨어진 순서를 기억하자! 순서대로 부수고 같은 색 기운을 흡수하자', 4.0)
        colors = list(range(len(LIFE_COLORS)))
        random.shuffle(colors)                              # 떨어지는 순서 = 정답 순서 (색은 매번 다름)
        spots = self.free_spots(len(colors) * 2)
        self.stones, self.orbs = [], []
        for order, ci in enumerate(colors):
            _, color = LIFE_COLORS[ci]
            x, y = spots[order]
            self.stones.append(LifeStone(self, order, ci, x, y, LIFE_FALL_START + order * LIFE_FALL_GAP))
        for order, ci in enumerate(colors):
            _, color = LIFE_COLORS[ci]
            x, y = spots[len(colors) + order]
            orb = LifeOrb(self, order, ci, x, y, on_absorbed=lambda o=order: self.orb_absorbed(o))
            self.orbs.append(orb)
            if self.add_essence:
                self.add_essence(orb)
        self.limit_at = LIFE_FALL_START + len(colors) * LIFE_FALL_GAP + 0.5 + LIFE_LIMIT

    def free_spots(self, n):
        """노움 둘레(맵 안)에서 서로 떨어진 자리 n 개 (모아 바로 옆은 피함)."""
        lo, hi = LIFE_DIST
        spots = []
        moa = self.opponent
        for _ in range(400):
            if len(spots) >= n:
                break
            a = random.uniform(0, math.tau)
            d = random.uniform(lo, hi)
            x, y = self.battle_map.clamp(self.x + math.cos(a) * d, self.y + math.sin(a) * d, 60)
            if any(math.hypot(x - px, y - py) < LIFE_SPACING for px, py in spots):
                continue
            if moa and math.hypot(x - moa.x, y - moa.y) < 140:
                continue
            spots.append((x, y))
        while len(spots) < n:                               # (드물게) 자리가 모자라면 가까이라도
            spots.append(self.battle_map.clamp(self.x + random.uniform(-hi, hi), self.y + random.uniform(-hi, hi), 60))
        return spots

    def stone_broken(self, stone):
        if self.stand_result is not None:
            return
        if self.need_orb or stone.order != self.next_order:
            self.say('순서가 틀렸다! 노움의 분노가 터진다!', 3.0)
            moa = self.opponent
            if moa and not moa.is_down:
                moa.take_hit(max(1, math.ceil(moa.max_hp * LIFE_FAIL_HIT)), self.x, self.y)
            combat.add_effect(Effect('monster', 'slam_impact', self.x, self.y, scale=3.0))
            self.finish_stand('fail')
            return
        self.need_orb = True
        orb = self.orbs[stone.order]
        orb.locked = False                                  # 같은 색 기운이 빛난다 → 흡수 가능
        name = next(n for n, c in LIFE_COLORS if c == stone.color)
        self.say(f'{name} 생명석을 부쉈다! {name} 기운을 흡수하자', 2.5)

    def orb_absorbed(self, order):
        if self.stand_result is not None:
            return
        self.need_orb = False
        self.next_order = order + 1
        if self.next_order >= len(LIFE_COLORS):
            self.finish_stand('clear')
        else:
            self.say(f'{self.next_order} / {len(LIFE_COLORS)} — 다음 생명석!', 2.0)

    def finish_stand(self, result):
        """기믹 끝: clear → 쓰러짐 (흡수로 구할 수 있음), fail → HP 20% 로 부활."""
        self.stand_result = result
        self.resisting = False
        self.shake = 0.0
        for st in self.stones:
            if not st.broken:
                st.broken, st.time = True, 0.0
        for orb in self.orbs:
            orb.gone = True
        self.orbs = []
        if result == 'clear':
            self.hp = 0
            self.say('노움의 생명석이 모두 꺼졌다!', 2.5)
            Spirit.on_zero_hp(self)                          # 평소처럼 기절 → 검은 기운
        else:
            self.hp = max(1, int(self.max_hp * LIFE_REVIVE))
            self.speech, self.speech_time = '이 정도로는... 쓰러지지 않는다!', 2.2
            self.begin('idle')
            self.sprite.play('idle', self.face, restart=True)
            self.gap = 1.0
            self.stand_result = None                         # 다음 HP 0 때 다시 기믹

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
        combat.add_effect(Effect('gnome', 'quake_wave', self.x, self.y, scale=6.0))     # 화면을 덮는 흙빛 충격파
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
            cx, cy = (sl + sr) / 2, (sb + st) / 2
            if c['state'] == 'warn':                         # 점점 깊게 갈라지며 깜빡임
                k = c['time'] / QUAKE_WARN
                blink = 0.75 + 0.25 * math.sin(c['time'] * (10 + 20 * k))
                draw_fx('crack_tile', int(k * 4), cx, cy, scale=(sr - sl) / QUAKE_TILE,
                        scale_y=(st - sb) / QUAKE_TILE, alpha=blink)
            else:                                            # 바위 기둥이 솟았다가 가라앉음
                frame = int(c['time'] / PILLAR_TIME * 6)
                draw_fx('crack_tile', 3, cx, cy, scale=(sr - sl) / QUAKE_TILE, scale_y=(st - sb) / QUAKE_TILE,
                        alpha=max(0.0, 1 - c['time'] / PILLAR_TIME))
                draw_fx('rock_pillar', frame, cx, sb + 20, scale=(sr - sl) / 160 * 0.95)
