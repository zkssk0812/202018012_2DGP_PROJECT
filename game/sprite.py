"""한 장짜리 스프라이트 시트(*_sheet.png + *_sheet.json) 재생기.

행 이름은 '동작_방향' 형식이다. 예) idle_down, move_left, faint_right
방향: down / left / right / up. faint·absorb 처럼 좌우만 있는 동작은 가까운 쪽을 쓴다.
"""
import resources
from config import SPRITE_SCALE


class SheetSprite:
    def __init__(self, folder, name):              # 예: ('sprite_sheets', 'moa_sheet')
        meta = resources.json_data(folder, f'{name}.json')
        self.image = resources.image(folder, meta['image'])
        self.cw, self.ch, self.total = meta['cell_w'], meta['cell_h'], meta['rows_total']
        self.rows = meta['rows']
        self.key = None
        self.play('idle', 'down')

    def row_name(self, action, d):
        k = f'{action}_{d}'
        if k in self.rows:
            return k
        k = f'{action}_{"left" if d == "left" else "right"}'
        if k in self.rows:
            return k
        # 방향 없는 시트(수풀 등): 그 동작의 첫 행, 없으면 첫 행
        return next((r for r in self.rows if r.startswith(f'{action}_')), next(iter(self.rows)))

    def play(self, action, d, restart=False, duration=None):
        """동작을 바꾼다. duration 을 주면 그 시간 안에 한 번 다 재생되도록 fps 를 맞춘다."""
        key = self.row_name(action, d)
        if key == self.key and not restart:
            return
        self.key = key
        r = self.rows[key]
        self.fps = r['frames'] / duration if duration else r['fps']
        self.time, self.index, self.done = 0.0, 0, False

    def update(self, dt):
        self.time += dt
        r = self.rows[self.key]
        k = int(self.time * self.fps)
        if r['loop']:
            self.index = k % r['frames']
        elif k < r['frames']:
            self.index = k
        elif 'loop_from' in r:                     # 등장 뒤 일부 구간만 반복 (모아 기절)
            lf = r['loop_from']
            self.index = lf + (k - r['frames']) % (r['frames'] - lf)
            self.done = True
        else:
            self.index, self.done = r['frames'] - 1, True

    def draw(self, x, y, scale=None):
        """(x, y) = 화면 좌표의 그림 중심. scale 을 안 주면 SPRITE_SCALE(0.5)."""
        scale = SPRITE_SCALE if scale is None else scale
        r = self.rows[self.key]
        left = self.index * self.cw
        bottom = (self.total - 1 - r['row']) * self.ch   # 이미지 맨 위가 row 0
        self.image.clip_draw(left, bottom, self.cw, self.ch, x, y,
                             self.cw * scale, self.ch * scale)
