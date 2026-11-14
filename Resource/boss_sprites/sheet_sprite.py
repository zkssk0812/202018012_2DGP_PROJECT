"""한 장짜리 스프라이트 시트(*_sheet.png + *_sheet.json)를 pico2d로 재생하는 예제.

행 이름은 '동작_방향' 형식입니다. 예) idle_down, move_left, melee_up, faint_right
방향: down / left / right / up  (왼쪽도 시트에 그려져 있어서 반전할 필요 없음)
"""
import json
from pico2d import open_canvas, close_canvas, load_image, clear_canvas, update_canvas, get_events, delay
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE, SDLK_UP, SDLK_DOWN, SDLK_LEFT, SDLK_RIGHT, SDLK_SPACE


class SheetSprite:
    def __init__(self, name):                      # name 예: 'moa_sheet', 'dew_corrupt1_sheet'
        self.image = load_image(f'{name}.png')
        meta = json.load(open(f'{name}.json', encoding='utf-8'))
        self.cw, self.ch, self.total = meta['cell_w'], meta['cell_h'], meta['rows_total']
        self.rows = meta['rows']
        self.action, self.dir, self.key = 'idle', 'down', None
        self.play('idle', 'down')

    def row_name(self, action, d):
        k = f'{action}_{d}'
        if k in self.rows:
            return k
        # faint/absorb/emote처럼 좌우만 있는 동작은 가까운 쪽으로
        return f'{action}_{"left" if d == "left" else "right"}'

    def play(self, action, d=None, restart=False):
        d = d or self.dir
        key = self.row_name(action, d)
        if key == self.key and not restart:
            return
        self.action, self.dir, self.key = action, d, key
        self.time, self.done = 0.0, False

    def update(self, dt):
        self.time += dt
        r = self.rows[self.key]
        k = int(self.time * r['fps'])
        if r['loop']:
            self.index = k % r['frames']
        elif k < r['frames']:
            self.index = k
        elif 'loop_from' in r:                     # 등장 뒤 일부 구간만 반복
            lf = r['loop_from']
            self.index = lf + (k - r['frames']) % (r['frames'] - lf)
        else:
            self.index, self.done = r['frames'] - 1, True

    def draw(self, x, y, scale=0.5):
        r = self.rows[self.key]
        left = self.index * self.cw
        bottom = (self.total - 1 - r['row']) * self.ch   # 이미지 맨 위가 row 0
        self.image.clip_draw(left, bottom, self.cw, self.ch, x, y, self.cw * scale, self.ch * scale)


if __name__ == '__main__':
    # 방향키: 이동 / Space: 근접 공격 / ESC: 종료
    open_canvas(800, 600)
    moa = SheetSprite('moa_sheet')
    keys = {SDLK_UP: 'up', SDLK_DOWN: 'down', SDLK_LEFT: 'left', SDLK_RIGHT: 'right'}
    held, running = [], True
    while running:
        for e in get_events():
            if e.type == SDL_QUIT or (e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE):
                running = False
            elif e.type == SDL_KEYDOWN and e.key in keys:
                held.append(keys[e.key])
            elif e.type == 769 and e.key in keys and keys[e.key] in held:   # SDL_KEYUP
                held.remove(keys[e.key])
            elif e.type == SDL_KEYDOWN and e.key == SDLK_SPACE:
                moa.play('melee', restart=True)
        if moa.action in ('idle', 'move') or moa.done:
            moa.play('move' if held else 'idle', held[-1] if held else moa.dir)
        moa.update(1 / 60)
        clear_canvas()
        moa.draw(400, 300)
        update_canvas()
        delay(1 / 60)
    close_canvas()
