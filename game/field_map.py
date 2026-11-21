"""숲(필드) 맵: Resource/forest_maps/<이름>.json

좌표는 pico2d 기준 (왼쪽 아래 0,0). 사각형은 [left, bottom, right, top].
벽은 발밑 상자로 막는다 (몸 원이 아니라 발밑이 닿는지로 판정 — 나무 줄기 앞을 지나갈 수 있게).
그리는 순서: 배경 → 수풀·열매·캐릭터 (화면 위쪽부터) → 전경(나무 윗부분).
"""
import json
import os

import resources
from config import (SCREEN_W, SCREEN_H, FIELD_FEET_W, FIELD_FEET_H, FIELD_FEET_OFFSET, FRUIT_HEAL, FRUIT_REGROW,
                    GAME_DIR)
from sprite import SheetSprite


def overlap(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def feet_rect(x, y):
    """몸 중심 (x, y) 인 캐릭터의 발밑 상자."""
    fy = y - FIELD_FEET_OFFSET
    return (x - FIELD_FEET_W / 2, fy, x + FIELD_FEET_W / 2, fy + FIELD_FEET_H)


class Bush:
    def __init__(self, rect, variant, sheet_name):
        self.rect, self.variant = rect, str(variant)
        self.sprite = SheetSprite('forest_maps', sheet_name)
        self.sprite.play('idle', self.variant)
        self.y = rect[1]                              # 그리는 순서용

    def rustle(self):
        self.sprite.play('rustle', self.variant, restart=True)

    def shake_encounter(self):
        """조우: 수풀이 크게 흔들린다 (전투로 넘어가기 전까지)."""
        self.sprite.play('encounter', self.variant, restart=True)

    def update(self, dt):
        self.sprite.update(dt)
        if self.sprite.done and self.sprite.key.startswith('rustle'):
            self.sprite.play('idle', self.variant)

    def draw(self, camera):
        sp = self.sprite
        ax, ay = sp.meta_anchor
        l, b = self.rect[0], self.rect[1]
        # 그림 칸의 (ax, ay) 를 격자 칸의 아래 가운데에 맞춘다
        x = l + 32 + (sp.cw / 2 - ax)
        y = b + 6 + (ay - sp.ch / 2)
        sx, sy = camera.to_screen(x, y)
        sp.draw(sx, sy, scale=1.0)


class Fruit:
    """회복 열매 (psd 4.3): 닿으면 최대 HP 30% 회복, 60초 뒤 다시 열림."""
    def __init__(self, pos):
        self.x, self.y = pos
        self.eaten_time = None
        meta = resources.json_data('forest_maps', 'fruit.json')
        self.image = resources.image('forest_maps', meta['image'])
        self.meta = meta
        self.time = 0.0

    @property
    def ripe(self):
        return self.eaten_time is None

    def try_eat(self, body):
        if not self.ripe or body.hp >= body.max_hp:
            return False
        if overlap(feet_rect(body.x, body.y), (self.x - 24, self.y - 24, self.x + 24, self.y + 24)):
            body.hp = min(body.max_hp, body.hp + max(1, int(body.max_hp * FRUIT_HEAL + 0.5)))
            self.eaten_time = 0.0
            return True
        return False

    def update(self, dt):
        self.time += dt
        if self.eaten_time is not None:
            self.eaten_time += dt
            if self.eaten_time >= FRUIT_REGROW:
                self.eaten_time = None

    def draw(self, camera):
        m = self.meta
        r = m['rows']['ripe' if self.ripe else 'empty']
        k = int(self.time * r['fps']) % r['frames']
        cw, ch = m['cell_w'], m['cell_h']
        sx, sy = camera.to_screen(self.x, self.y)
        self.image.clip_draw(k * cw, (m['rows_total'] - 1 - r['row']) * ch, cw, ch, sx, sy)


def extra_bushes(name):
    """game/data/extra_bushes.json 에 적어 둔, 원래 맵에 더하는 수풀."""
    p = os.path.join(GAME_DIR, 'data', 'extra_bushes.json')
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8') as f:
        return json.load(f).get(name, [])


class FieldMap:
    def __init__(self, name):
        info = resources.json_data('forest_maps', f'{name}.json')
        self.name = name
        self.w, self.h = info['size']
        self.walls = info['walls']
        self.start = tuple(info['start'])
        self.tori_pos = tuple(info['tori']['pos']) if 'tori' in info else None
        self.exits = info.get('exits', [])
        self.bg = resources.image('forest_maps', info['background'])
        self.fg = resources.image('forest_maps', info['foreground'])
        self.encounter_rate = info.get('encounter_rate', 0.0)
        sheet = info.get('bush_sheet', '').replace('.png', '')
        bushes = info['bushes'] + extra_bushes(name)
        self.bushes = [Bush(b['rect'], b['variant'], sheet) for b in bushes] if sheet else []
        if sheet:
            anchor = resources.json_data('forest_maps', f'{sheet}.json')['anchor']
            for b in self.bushes:
                b.sprite.meta_anchor = anchor
        self.fruits = [Fruit(p) for p in info.get('fruits', [])]

    # ── 움직임 ──────────────────────────────────────
    def blocked(self, x, y):
        f = feet_rect(x, y)
        if f[0] < 0 or f[1] < 0 or f[2] > self.w or f[3] > self.h:
            return True
        return any(overlap(f, w) for w in self.walls)

    def move(self, x, y, dx, dy, radius):
        """축마다 따로 움직여 본다: 벽에 막힌 쪽만 멈추고 벽을 따라 미끄러진다."""
        if not self.blocked(x + dx, y):
            x += dx
        if not self.blocked(x, y + dy):
            y += dy
        return x, y

    def clamp(self, x, y, radius):
        """맵 밖으로 나가지 않게. 숲은 발밑 기준이라 맵 가장자리의 출구까지 발이 닿는다."""
        half = FIELD_FEET_W / 2
        return (min(max(x, half), self.w - half),
                min(max(y, FIELD_FEET_OFFSET), self.h + FIELD_FEET_OFFSET - FIELD_FEET_H))

    def bush_at(self, x, y):
        fx, fy = x, y - FIELD_FEET_OFFSET + 4
        for b in self.bushes:
            l, bt, r, t = b.rect
            if l <= fx < r and bt <= fy < t:
                return b
        return None

    def exit_at(self, x, y):
        f = feet_rect(x, y)
        for e in self.exits:
            if overlap(f, e['rect']):
                return e
        return None

    # ── 그리기 ──────────────────────────────────────
    def update(self, dt):
        for b in self.bushes:
            b.update(dt)
        for f in self.fruits:
            f.update(dt)

    def _draw_layer(self, image, camera):
        image.clip_draw(int(camera.x), int(camera.y), SCREEN_W, SCREEN_H, SCREEN_W / 2, SCREEN_H / 2)

    def draw_background(self, camera):
        self._draw_layer(self.bg, camera)

    def draw_foreground(self, camera):
        self._draw_layer(self.fg, camera)

    def objects(self):
        """캐릭터와 함께 화면 위쪽부터 그릴 것들."""
        return self.bushes + self.fruits
