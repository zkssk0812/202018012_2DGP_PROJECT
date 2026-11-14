"""숲 맵 + 수풀 + 열매를 pico2d로 돌려 보는 예제.

이 파일과 같은 폴더에 맵 파일(tutorial/forest1/forest2/forest3 의 _bg.png, _fg.png, .json),
bush_forest1/2.png·json, fruit.png·json 을 두고 실행하세요.
moa_sheet.png / moa_sheet.json(모아 한 장짜리 시트)이 있으면 모아로, 없으면 네모로 그립니다.

조작: 방향키 이동, 1~4 맵 바꾸기, F1 충돌 상자 보기, ESC 종료
"""
import json, random, os
from pico2d import (open_canvas, close_canvas, load_image, clear_canvas, update_canvas, get_events,
                    draw_rectangle, delay, get_time)
from sdl2 import (SDL_QUIT, SDL_KEYDOWN, SDL_KEYUP, SDLK_ESCAPE, SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN,
                  SDLK_1, SDLK_2, SDLK_3, SDLK_4, SDLK_F1)

SW, SH = 1280, 720          # 화면 크기
SPEED = 260                 # 이동 속도 (px/초)
FEET_W, FEET_H = 28, 14     # 발밑 충돌 상자


class Sheet:
    """json(rows/cell_w/cell_h) 형식 스프라이트 시트"""
    def __init__(self, png, js):
        self.img = load_image(png); self.meta = json.load(open(js, encoding='utf-8'))
        self.cw, self.ch = self.meta['cell_w'], self.meta['cell_h']; self.total = self.meta['rows_total']

    def frame(self, row_name, t):
        r = self.meta['rows'][row_name]; k = int(t*r['fps'])
        if r['loop']: k %= r['frames']
        else: k = min(k, r['frames']-1)
        return r, k, k >= r['frames']-1 and not r['loop']

    def draw(self, row_name, t, x, y, scale=1.0):
        r, k, _ = self.frame(row_name, t)
        self.img.clip_draw(k*self.cw, (self.total-1-r['row'])*self.ch, self.cw, self.ch, x, y, self.cw*scale, self.ch*scale)


def hit(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


class Bush:
    def __init__(self, rect, variant):
        self.rect, self.v = rect, variant
        self.anim, self.t = 'idle', random.random()*2      # 처음 시간이 달라야 다 같이 흔들리지 않음

    def play(self, anim):
        self.anim, self.t = anim, 0.0

    def update(self, dt, sheet):
        self.t += dt
        if self.anim == 'rustle' and sheet.frame(f'rustle_{self.v}', self.t)[2]:
            self.play('idle')

    def draw(self, sheet, cx, cy):
        l, b = self.rect[0], self.rect[1]
        ax, ay = sheet.meta['anchor']                        # 그림 칸 안의 뿌리 위치 (40, 74)
        x = l+32 - cx + (sheet.cw/2-ax); y = b+6 - cy + (ay-sheet.ch/2)
        sheet.draw(f'{self.anim}_{self.v}', self.t, x, y)


class Field:
    def __init__(self, name):
        self.info = json.load(open(f'{name}.json', encoding='utf-8'))
        self.bg = load_image(self.info['background']); self.fg = load_image(self.info['foreground'])
        self.W, self.H = self.info['size']
        bs = self.info.get('bush_sheet')
        self.bush_sheet = Sheet(bs, bs.replace('.png', '.json')) if bs else None
        self.bushes = [Bush(b['rect'], b['variant']) for b in self.info['bushes']]
        self.fruit_sheet = Sheet('fruit.png', 'fruit.json')
        self.fruits = [{'pos': p, 'eaten_at': None} for p in self.info['fruits']]
        self.px, self.py = self.info['start']
        self.cur_bush = None; self.encounter = None

    def feet(self, x, y):
        return (x-FEET_W/2, y, x+FEET_W/2, y+FEET_H)

    def blocked(self, x, y):
        f = self.feet(x, y)
        if f[0] < 0 or f[1] < 0 or f[2] > self.W or f[3] > self.H: return True
        return any(hit(f, w) for w in self.info['walls'])

    def move(self, dx, dy, dt):
        nx = self.px+dx*SPEED*dt
        if not self.blocked(nx, self.py): self.px = nx
        ny = self.py+dy*SPEED*dt
        if not self.blocked(self.px, ny): self.py = ny
        # 수풀: 새 칸에 들어설 때마다 흔들고 조우 판정 (포켓몬처럼 한 걸음마다)
        fx, fy = self.px, self.py+4
        now = None
        for b in self.bushes:
            l, bt, r, t = b.rect
            if l <= fx < r and bt <= fy < t: now = b; break
        if now is not self.cur_bush and now is not None:
            now.play('rustle')
            if random.random() < self.info['encounter_rate']:
                now.play('encounter'); self.encounter = (now, get_time())
        self.cur_bush = now

    def update(self, dt):
        for b in self.bushes:
            if self.bush_sheet: b.update(dt, self.bush_sheet)
        now = get_time()
        for f in self.fruits:   # 닿으면 먹고 60초 뒤 다시 열림
            x, y = f['pos']
            if f['eaten_at'] is None and abs(self.px-x) < 28 and abs(self.py-y) < 28:
                f['eaten_at'] = now; print('열매를 먹었다! (HP 30% 회복)')
            elif f['eaten_at'] is not None and now-f['eaten_at'] > 60:
                f['eaten_at'] = None
        if self.encounter and now-self.encounter[1] > 0.6:
            print('정령과 마주쳤다! → 여기서 전투 맵으로 전환')
            self.encounter[0].play('idle'); self.encounter = None
        for e in self.info.get('exits', []):
            if hit(self.feet(self.px, self.py), e['rect']): return e['to']
        return None

    def draw(self, player_draw, debug=False):
        cx = min(max(self.px-SW/2, 0), self.W-SW); cy = min(max(self.py-SH/2, 0), self.H-SH)
        vw, vh = min(SW, self.W), min(SH, self.H)
        self.bg.clip_draw(int(cx), int(cy), vw, vh, vw/2, vh/2)
        # y가 큰(화면 위쪽) 것부터 그려서 앞뒤가 맞게
        objs = []
        if self.bush_sheet:
            objs += [(b.rect[1], lambda b=b: b.draw(self.bush_sheet, cx, cy)) for b in self.bushes]
        for f in self.fruits:
            x, y = f['pos']; row = 'empty' if f['eaten_at'] else 'ripe'
            objs.append((y-10, lambda x=x, y=y, row=row: self.fruit_sheet.draw(row, get_time(), x-cx, y-cy)))
        objs.append((self.py, lambda: player_draw(self.px-cx, self.py-cy)))
        for _, fn in sorted(objs, key=lambda o: -o[0]): fn()
        self.fg.clip_draw(int(cx), int(cy), vw, vh, vw/2, vh/2)      # 나무 윗부분은 맨 위에
        if debug:
            for w in self.info['walls']: draw_rectangle(w[0]-cx, w[1]-cy, w[2]-cx, w[3]-cy)
            f = self.feet(self.px, self.py); draw_rectangle(f[0]-cx, f[1]-cy, f[2]-cx, f[3]-cy)


def main():
    open_canvas(SW, SH)
    moa = Sheet('moa_sheet.png', 'moa_sheet.json') if os.path.exists('moa_sheet.png') else None
    names = ['tutorial', 'forest1', 'forest2', 'forest3']
    field = Field('tutorial')
    keys = set(); face = 'down'; debug = False; last = get_time(); running = True
    dirs = {SDLK_LEFT: (-1, 0, 'left'), SDLK_RIGHT: (1, 0, 'right'), SDLK_UP: (0, 1, 'up'), SDLK_DOWN: (0, -1, 'down')}

    def draw_player(x, y):
        if moa:   # 모아 시트의 발이 칸 아래쪽 가운데 근처라고 보고 그림 (scale 0.5)
            moa.draw(('move_' if keys else 'idle_')+face, get_time(), x, y+moa.ch*0.5*0.5-12, 0.5)
        else:
            draw_rectangle(x-18, y, x+18, y+52)

    while running:
        now = get_time(); dt = min(now-last, 0.05); last = now
        for e in get_events():
            if e.type == SDL_QUIT or (e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE): running = False
            elif e.type == SDL_KEYDOWN and e.key in dirs: keys.add(e.key)
            elif e.type == SDL_KEYUP and e.key in dirs: keys.discard(e.key)
            elif e.type == SDL_KEYDOWN and SDLK_1 <= e.key <= SDLK_4: field = Field(names[e.key-SDLK_1])
            elif e.type == SDL_KEYDOWN and e.key == SDLK_F1: debug = not debug
        dx = sum(dirs[k][0] for k in keys); dy = sum(dirs[k][1] for k in keys)
        if keys: face = dirs[list(keys)[-1]][2]
        if dx or dy:
            n = (dx*dx+dy*dy)**0.5; field.move(dx/n, dy/n, dt)
        nxt = field.update(dt)
        if nxt: field = Field(nxt)
        clear_canvas(); field.draw(draw_player, debug); update_canvas()
        delay(0.01)
    close_canvas()


if __name__ == '__main__':
    main()
