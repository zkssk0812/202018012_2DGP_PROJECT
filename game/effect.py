"""이펙트 시트(effects_player / effects_monster) 재생.

이펙트는 모두 오른쪽을 향해 그려져 있어서, 방향 각도(라디안)만큼 돌려 그린다.
origin 은 칸 안에서 시전자(또는 중심)가 놓일 자리다.
"""
import math

import resources


class EffectSheet:
    _cache = {}

    def __init__(self, owner):                    # 'player' 또는 'monster'
        self.meta = resources.json_data('effect_sheets', f'effects_{owner}.json')
        self.image = resources.image('effect_sheets', self.meta['image'])
        self.sheet_h = self.meta['sheet_h']

    @classmethod
    def get(cls, owner):
        if owner not in cls._cache:
            cls._cache[owner] = EffectSheet(owner)
        return cls._cache[owner]


class Effect:
    def __init__(self, owner, name, x, y, angle=0.0, scale=0.5):
        self.sheet = EffectSheet.get(owner)
        self.info = self.sheet.meta['effects'][name]
        self.x, self.y, self.angle, self.scale = x, y, angle, scale
        self.time, self.index, self.done = 0.0, 0, False

    def update(self, dt):
        i = self.info
        self.time += dt
        k = int(self.time * i['fps'])
        if i['loop'] and 'loop_from' not in i:
            self.index = k % i['frames']
        elif k < i['frames']:
            self.index = k
        elif 'loop_from' in i:
            lf = i['loop_from']
            self.index = lf + (k - i['frames']) % (i['frames'] - lf)
        else:
            self.index, self.done = i['frames'] - 1, True

    def draw(self, camera):
        i = self.info
        w, h = i['cell_w'], i['cell_h']
        left = i['x'] + self.index * w
        bottom = self.sheet.sheet_h - i['y'] - h
        ox, oy = i['origin']
        dx, dy = (w / 2 - ox) * self.scale, (oy - h / 2) * self.scale
        c, s = math.cos(self.angle), math.sin(self.angle)
        sx, sy = camera.to_screen(self.x + dx * c - dy * s, self.y + dx * s + dy * c)
        self.sheet.image.clip_composite_draw(left, bottom, w, h, self.angle, '', sx, sy,
                                             w * self.scale, h * self.scale)
