"""바위의 상위 정령 노움 (숲2 보스, psd 6.4). 행동 트리로 싸운다.

평소에는 일반 정령의 근접형 행동 트리를 그대로 쓴다 (돌진 박치기 · 흙먼지 회오리 · 연속 주먹 · 내려찍기).
바위라서 회피는 하지 않는다. 특별 패턴은 Spirit 트리의 '보스 패턴 가지'로 더해진다 (피격보다 우선).
패턴 중에는 맞아도 밀려나지 않는다 (피해는 받음).

    Sequence 대지 균열 : HP 70% 이하가 됐나? (한 번) → 대지 균열
        모아 둘레 바닥 칸(7×5) 중 일부가 붉게 갈라지고, 1초 뒤 그 칸에서 바위 기둥이 솟는다 (즉사급 85%).
        3번. 안전한 칸이 매번 바뀌고 줄어든다 (45% → 30% → 2칸). 모아 바로 옆 칸 하나는 늘 안전.
"""
import math
import random

import combat
from attack import Attack
from behavior_tree import Sequence, Action, Condition, SUCCESS, RUNNING
from collision import Rect
from config import (HEAVY_HIT, QUAKE_HP, QUAKE_TILE, QUAKE_COLS, QUAKE_ROWS, QUAKE_WAVES, QUAKE_WARN,
                    QUAKE_SAFE, QUAKE_TIME)
from effect import Effect
from pico2d import draw_rectangle
from sdl2 import SDL_SetRenderDrawBlendMode, SDL_BLENDMODE_BLEND
import pico2d
from spirit import Spirit

PILLAR_TIME = 0.6           # 솟은 바위 기둥이 보이는 시간


class Gnome(Spirit):
    armor_acts = ('quake',)

    def __init__(self, kind, level, x, y, area, target):
        self.quake_done = False
        super().__init__(kind, level, x, y, area, target)
        self.cells = []             # 바닥 칸: dict(rect, wave, state='warn'|'pillar', time)
        self.waves_done = 0

    def pattern_branches(self):
        return [Sequence('대지 균열', Condition('HP 70% 이하가 됐나', self.want_quake),
                         Action('대지 균열', self.do_quake))]

    def pattern_text(self):
        """HUD 에 보여 줄 지금 패턴 (없으면 None)."""
        if self.act == 'quake':
            return '대지 균열', (255, 170, 90)
        return None

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
