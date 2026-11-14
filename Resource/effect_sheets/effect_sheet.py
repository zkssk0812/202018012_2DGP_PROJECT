"""이펙트 시트(effects_player.png / effects_monster.png + json)를 pico2d로 그리는 예제.

이펙트는 모두 오른쪽을 향해 그려져 있어서, 쏘는 방향 각도(라디안)를 angle로 넘기면 됩니다.
  오른쪽 0, 위 pi/2, 왼쪽 pi, 아래 -pi/2
"""
import json, math
from pico2d import load_image


class EffectSheet:
    def __init__(self, owner='player'):          # 'player' 또는 'monster'
        self.image = load_image(f'effects_{owner}.png')
        self.meta = json.load(open(f'effects_{owner}.json', encoding='utf-8'))
        self.sheet_h = self.meta['sheet_h']


class Effect:
    def __init__(self, sheet, name, x, y, angle=0.0, scale=0.5):
        self.sheet, self.info = sheet, sheet.meta['effects'][name]
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
        elif 'loop_from' in i:                     # 등장 뒤 일부 구간만 반복 (물방울막, 단단한 털)
            lf = i['loop_from']
            self.index = lf + (k - i['frames']) % (i['frames'] - lf)
        else:
            self.index, self.done = i['frames'] - 1, True

    def draw(self):
        i = self.info
        w, h = i['cell_w'], i['cell_h']
        left = i['x'] + self.index * w
        bottom = self.sheet.sheet_h - i['y'] - h       # 시트 맨 위 기준 y → pico2d 아래 기준
        ox, oy = i['origin']                            # origin이 (x, y)에 오도록 회전해서 옮김
        dx, dy = (w / 2 - ox) * self.scale, (oy - h / 2) * self.scale
        c, s = math.cos(self.angle), math.sin(self.angle)
        cx, cy = self.x + dx * c - dy * s, self.y + dx * s + dy * c
        self.sheet.image.clip_composite_draw(left, bottom, w, h, self.angle, '', cx, cy, w * self.scale, h * self.scale)

# 사용 예)
#   fx = EffectSheet('player')
#   e = Effect(fx, 'dew_shot', moa_x, moa_y, angle=math.pi)   # 왼쪽으로 이슬탄
#   매 프레임 e.update(dt); e.draw(); e.done이면 제거
