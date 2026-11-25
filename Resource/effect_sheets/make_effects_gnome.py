"""노움(바위의 상위 정령) 전용 이펙트 시트 effects_gnome.png + effects_gnome.json 을 만든다.

effects_boss 와 같은 방식 · 형식. 바위는 갈색, 타락한 노움처럼 자홍 수정 빛을 섞는다.
    python make_effects_gnome.py      (이 폴더에서 실행)

이펙트:
    crack_tile      대지 균열 예고: 바닥 칸이 점점 갈라짐 (4프레임: 금 → 깊은 금)
    rock_pillar     대지 균열: 칸에서 솟는 바위 기둥 (6프레임, 한 번)
    boulder         대지의 분노: 떨어지는 큰 바위 (1프레임)
    quake_wave      대지의 분노: 맵 전체 흙빛 충격파 (8프레임, 한 번, 크게 늘려 그림)
    life_stone_N    생명석 (N = 0 빨강 · 1 파랑 · 2 초록 · 3 노랑). 4프레임 = 맞은 수 0 · 1 · 2 · 부서지기 직전
    life_orb_N      생명석과 같은 색 기운 (6프레임 반복)
"""
import json
import math
import random

from make_effects_boss import Canvas, mix, smooth

OUT = 'effects_gnome'

OUTLINE = (40, 22, 18)
ROCK_DARK = (78, 56, 46)
ROCK = (122, 92, 72)
ROCK_LIGHT = (176, 146, 118)
CRYSTAL = (214, 66, 160)
CRYSTAL_LIGHT = (255, 170, 225)
EMBER = (255, 150, 90)
LIFE = [(235, 70, 70), (80, 140, 255), (90, 210, 110), (250, 205, 60)]


def lighten(c, k):
    return mix(c, (255, 255, 255), k)


def darken(c, k):
    return mix(c, (0, 0, 0), k)


def poly_inside(px, py, pts):
    """점이 다각형 안인지 (짝홀 규칙)."""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def draw_line(c, x1, y1, x2, y2, width, color, a=1.0):
    steps = int(max(abs(x2 - x1), abs(y2 - y1))) + 1
    for k in range(steps + 1):
        t = k / steps
        c.dot(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, width / 2, color, a)


def rock_blob(c, cx, cy, rx, ry, seed, light_dir=(-0.6, -0.8), crystals=3):
    """울퉁불퉁한 바위 덩어리 (테두리 + 명암 + 수정)."""
    rnd = random.Random(seed)
    bumps = [(rnd.uniform(0.85, 1.12), rnd.uniform(0, math.tau)) for _ in range(5)]

    def radius_at(th):
        r = 1.0
        for k, (amp, ph) in enumerate(bumps):
            r += (amp - 1) * math.sin(th * (k + 2) + ph) * 0.5
        return r

    for y in range(int(cy - ry - 6), int(cy + ry + 6)):
        for x in range(int(cx - rx - 6), int(cx + rx + 6)):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            d = math.hypot(dx, dy)
            th = math.atan2(dy, dx)
            edge = radius_at(th)
            if d > edge + 0.1:
                continue
            if d > edge - 0.04:
                c.blend(x, y, OUTLINE, 0.95)
                continue
            shade = 0.5 - 0.5 * (dx * light_dir[0] + dy * light_dir[1]) / max(d, 0.2) * min(1, d * 1.6)
            facet = 0.5 + 0.5 * math.sin(dx * 7 + dy * 5 + seed)
            col = mix(ROCK_LIGHT, ROCK_DARK, shade * 0.8 + facet * 0.15)
            c.blend(x, y, col, 1.0)
    for k in range(crystals):                               # 박힌 자홍 수정
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0.2, 0.6)
        x0, y0 = cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr
        s = rnd.uniform(0.12, 0.2) * min(rx, ry)
        pts = [(x0, y0 - s * 1.6), (x0 + s, y0), (x0, y0 + s * 0.8), (x0 - s, y0)]
        for y in range(int(y0 - s * 2), int(y0 + s * 2)):
            for x in range(int(x0 - s * 2), int(x0 + s * 2)):
                if poly_inside(x + 0.5, y + 0.5, pts):
                    t = (y + 0.5 - (y0 - s * 1.6)) / (s * 2.4)
                    c.blend(x, y, mix(CRYSTAL_LIGHT, CRYSTAL, t), 0.95)


# ── 대지 균열: 갈라지는 바닥 ─────────────────────────
CRACK_W, CRACK_H, CRACK_FRAMES = 240, 240, 4


def crack_paths(seed):
    """가운데에서 사방으로 뻗는 금 (가지 포함)."""
    rnd = random.Random(seed)
    paths = []
    for k in range(6):
        a = k * math.tau / 6 + rnd.uniform(-0.3, 0.3)
        x, y = CRACK_W / 2, CRACK_H / 2
        pts = [(x, y)]
        for step in range(7):
            a += rnd.uniform(-0.5, 0.5)
            x += math.cos(a) * 16
            y += math.sin(a) * 16
            pts.append((x, y))
            if step == 3 and rnd.random() < 0.7:            # 가지
                b = a + rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.0)
                bx, by = x, y
                branch = [(bx, by)]
                for _ in range(3):
                    b += rnd.uniform(-0.4, 0.4)
                    bx += math.cos(b) * 14
                    by += math.sin(b) * 14
                    branch.append((bx, by))
                paths.append(branch)
        paths.append(pts)
    return paths


def draw_crack(frame):
    c = Canvas(CRACK_W, CRACK_H)
    k = (frame + 1) / CRACK_FRAMES
    # 칸 테두리 (붉게 빛남)
    for y in range(CRACK_H):
        for x in range(CRACK_W):
            e = min(x, y, CRACK_W - 1 - x, CRACK_H - 1 - y)
            if e < 6:
                c.blend(x, y, EMBER, (0.35 + 0.45 * k) * (1 - e / 6))
            else:
                c.blend(x, y, (150, 40, 25), 0.18 + 0.22 * k)
    for path in crack_paths(11):
        n = max(2, int(len(path) * min(1.0, 0.35 + 0.65 * k)))
        pts = path[:n]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            draw_line(c, x1, y1, x2, y2, 3 + 4 * k, EMBER, 0.35 + 0.3 * k)          # 빛
            draw_line(c, x1, y1, x2, y2, 1.5 + 2.5 * k, OUTLINE, 0.95)              # 금
    return c


# ── 솟는 바위 기둥 ──────────────────────────────────
PILLAR_W, PILLAR_H, PILLAR_FRAMES = 160, 240, 6


def draw_pillar(frame):
    c = Canvas(PILLAR_W, PILLAR_H)
    grow = [0.35, 0.75, 1.0, 1.05, 1.0, 0.9][frame]
    fade = 1.0 if frame < 4 else (0.85 if frame == 4 else 0.6)
    base_y = PILLAR_H - 14
    h = 190 * grow
    top = base_y - h
    pts = [(PILLAR_W / 2 - 50, base_y), (PILLAR_W / 2 - 34, top + 40), (PILLAR_W / 2 - 8, top),
           (PILLAR_W / 2 + 20, top + 18), (PILLAR_W / 2 + 36, top + 52), (PILLAR_W / 2 + 52, base_y)]
    for y in range(int(top) - 4, base_y + 4):
        for x in range(PILLAR_W):
            if poly_inside(x + 0.5, y + 0.5, pts):
                near_edge = not all(poly_inside(x + 0.5 + dx, y + 0.5 + dy, pts)
                                    for dx, dy in ((3, 0), (-3, 0), (0, 3), (0, -3)))
                if near_edge:
                    c.blend(x, y, OUTLINE, 0.95 * fade)
                else:
                    t = (x - PILLAR_W / 2 + 50) / 100
                    facet = 0.5 + 0.5 * math.sin(y * 0.15 + x * 0.05)
                    c.blend(x, y, mix(ROCK_LIGHT, ROCK_DARK, t * 0.8 + facet * 0.15), fade)
    for k in range(3):                                      # 기둥의 수정 줄
        y0 = top + 40 + k * h * 0.25
        draw_line(c, PILLAR_W / 2 - 16 + k * 6, y0, PILLAR_W / 2 + 4 + k * 6, y0 + 24, 5, CRYSTAL, 0.9 * fade)
        draw_line(c, PILLAR_W / 2 - 14 + k * 6, y0, PILLAR_W / 2 + 2 + k * 6, y0 + 20, 2, CRYSTAL_LIGHT, fade)
    rnd = random.Random(frame)
    for k in range(10 if frame < 3 else 4):                 # 튀는 흙 조각
        x = PILLAR_W / 2 + rnd.uniform(-70, 70)
        y = base_y - rnd.uniform(0, 60 + 40 * frame)
        c.dot(x, y, rnd.uniform(2.5, 5), OUTLINE, 0.9 * fade)
        c.dot(x, y, rnd.uniform(1.5, 3.5), ROCK_LIGHT, 0.9 * fade)
    return c


# ── 큰 바위 ─────────────────────────────────────────
BOULDER_W, BOULDER_H = 192, 192


def draw_boulder(frame):
    c = Canvas(BOULDER_W, BOULDER_H)
    for y in range(BOULDER_H):                              # 바닥 그림자
        for x in range(BOULDER_W):
            d = math.hypot((x - BOULDER_W / 2) / 80, (y - BOULDER_H + 30) / 18)
            if d < 1:
                c.blend(x, y, (0, 0, 0), 0.35 * (1 - d))
    rock_blob(c, BOULDER_W / 2, BOULDER_H / 2 + 10, 78, 70, seed=5, crystals=4)
    return c


# ── 맵 전체 흙빛 충격파 ─────────────────────────────
WAVE_W, WAVE_H, WAVE_FRAMES = 512, 512, 8


def draw_wave(frame):
    c = Canvas(WAVE_W, WAVE_H)
    t = frame / (WAVE_FRAMES - 1)
    ease = 1 - (1 - t) ** 3
    cx, cy = WAVE_W / 2, WAVE_H / 2
    ring = 26 + 222 * ease
    thick = 40 * (1 - t) + 8
    alpha_all = 1 - smooth(0.55, 1.0, t)
    rnd = random.Random(frame)
    for y in range(WAVE_H):
        for x in range(WAVE_W):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            if r > 255:
                continue
            if r < ring:
                fill = (1 - t) ** 1.5 * 0.5 * (1 - r / max(ring, 1)) + 0.15 * (1 - t)
                c.blend(x, y, (200, 160, 110), fill * alpha_all)
            d = abs(r - ring)
            if d < thick + 4:
                k = d / thick
                if k > 1:
                    c.blend(x, y, OUTLINE, 0.7 * (1 - (d - thick) / 4) * alpha_all)
                else:
                    c.blend(x, y, mix((255, 230, 190), (150, 100, 60), k), (1 - k * k) * 0.95 * alpha_all)
    for k in range(40):                                     # 고리에 실려 날아가는 돌조각
        a = rnd.uniform(0, math.tau)
        r = ring + rnd.uniform(-thick, thick * 0.5)
        c.dot(cx + math.cos(a) * r, cy + math.sin(a) * r, rnd.uniform(2, 5) * (1 - t * 0.5), OUTLINE, alpha_all)
        c.dot(cx + math.cos(a) * r, cy + math.sin(a) * r, rnd.uniform(1, 3), ROCK_LIGHT, alpha_all)
    return c


# ── 생명석 ──────────────────────────────────────────
STONE_W, STONE_H, STONE_FRAMES = 96, 128, 4


def draw_stone(color, frame):
    c = Canvas(STONE_W, STONE_H)
    cx = STONE_W / 2
    for y in range(STONE_H):                                # 바닥 그림자
        for x in range(STONE_W):
            d = math.hypot((x - cx) / 36, (y - STONE_H + 14) / 9)
            if d < 1:
                c.blend(x, y, (0, 0, 0), 0.35 * (1 - d))
    rock_blob(c, cx, STONE_H - 34, 38, 22, seed=3, crystals=0)          # 받침돌
    gem = [(cx, 10), (cx + 26, 44), (cx + 18, 88), (cx, 100), (cx - 18, 88), (cx - 26, 44)]   # 빛나는 큰 보석
    glow = lighten(color, 0.5)
    for y in range(4, 106):
        for x in range(STONE_W):
            inside = poly_inside(x + 0.5, y + 0.5, gem)
            if inside:
                edge = not all(poly_inside(x + 0.5 + dx, y + 0.5 + dy, gem)
                               for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)))
                if edge:
                    c.blend(x, y, darken(color, 0.65), 1.0)
                else:
                    side = (x - cx) / 26
                    t = (y - 10) / 90
                    col = mix(lighten(color, 0.55), darken(color, 0.35), max(0, side) * 0.7 + t * 0.4)
                    if side < -0.2 and t < 0.6:
                        col = mix(col, (255, 255, 255), 0.35)
                    c.blend(x, y, col, 1.0)
            else:
                d = min(math.hypot(x - px, y - py) for px, py in gem)
                if d < 6:
                    c.blend(x, y, glow, 0.25 * (1 - d / 6))
    rnd = random.Random(21)                                 # 맞은 만큼 금 (frame 1~3)
    cracks = [[(cx - 4, 30), (cx + 6, 48), (cx - 2, 62), (cx + 8, 78)],
              [(cx + 14, 40), (cx + 2, 56), (cx + 12, 70)],
              [(cx - 16, 52), (cx - 4, 66), (cx - 12, 86), (cx + 2, 96)]]
    for k in range(min(frame, 3)):
        pts = cracks[k]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            draw_line(c, x1, y1, x2, y2, 3, (255, 255, 255), 0.5)
            draw_line(c, x1, y1, x2, y2, 1.6, darken(color, 0.8), 1.0)
    if frame == 3:                                          # 부서지기 직전: 빛이 새어 나옴
        for k in range(6):
            a = rnd.uniform(0, math.tau)
            draw_line(c, cx, 55, cx + math.cos(a) * 40, 55 + math.sin(a) * 40, 2, lighten(color, 0.7), 0.6)
    return c


# ── 생명석과 같은 색 기운 ────────────────────────────
ORB_W, ORB_H, ORB_FRAMES = 64, 64, 6


def draw_orb(color, frame):
    c = Canvas(ORB_W, ORB_H)
    cx, cy = ORB_W / 2, ORB_H / 2
    ph = frame / ORB_FRAMES * math.tau
    for y in range(ORB_H):
        for x in range(ORB_W):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            th = math.atan2(dy, dx)
            wob = 13 + 2.5 * math.sin(th * 3 + ph) + 1.5 * math.sin(th * 5 - ph * 2)
            if r < wob:
                k = r / wob
                c.blend(x, y, mix(lighten(color, 0.85), color, k), 0.95)
            elif r < wob + 2:
                c.blend(x, y, darken(color, 0.6), 0.9)
            elif r < 30:
                c.blend(x, y, color, 0.35 * (1 - (r - wob) / (30 - wob)))
    for k in range(3):                                      # 도는 작은 빛
        a = ph + k * math.tau / 3
        c.dot(cx + math.cos(a) * 22, cy + math.sin(a) * 22, 2.2, lighten(color, 0.7), 0.9)
    return c


def main():
    rows = [('crack_tile', draw_crack, CRACK_W, CRACK_H, CRACK_FRAMES, 4, False, [CRACK_W // 2, CRACK_H // 2],
             '대지 균열 예고', '노움 · 갈라지는 바닥 칸'),
            ('rock_pillar', draw_pillar, PILLAR_W, PILLAR_H, PILLAR_FRAMES, 12, False, [PILLAR_W // 2, PILLAR_H - 14],
             '바위 기둥', '노움 대지 균열 · 칸에서 솟음'),
            ('boulder', draw_boulder, BOULDER_W, BOULDER_H, 1, 1, True, [BOULDER_W // 2, BOULDER_H - 30],
             '큰 바위', '노움 대지의 분노 · 충격파를 가림'),
            ('quake_wave', draw_wave, WAVE_W, WAVE_H, WAVE_FRAMES, 12, False, [WAVE_W // 2, WAVE_H // 2],
             '흙빛 충격파', '노움 대지의 분노 · 맵 전체 (크게 늘려 그림)')]
    for i, col in enumerate(LIFE):
        rows.append((f'life_stone_{i}', lambda f, col=col: draw_stone(col, f), STONE_W, STONE_H, STONE_FRAMES, 1,
                     True, [STONE_W // 2, STONE_H - 24], f'생명석 {i}', '노움 생명석 · 프레임 = 맞은 수'))
    for i, col in enumerate(LIFE):
        rows.append((f'life_orb_{i}', lambda f, col=col: draw_orb(col, f), ORB_W, ORB_H, ORB_FRAMES, 10, True,
                     [ORB_W // 2, ORB_H // 2], f'생명 기운 {i}', '노움 생명석과 같은 색 기운'))
    sheet_w = max(w * n for _, _, w, _, n, *_ in rows)
    sheet_h = sum(h for _, _, _, h, *_ in rows)
    sheet = Canvas(sheet_w, sheet_h)
    meta = {'image': f'{OUT}.png', 'sheet_w': sheet_w, 'sheet_h': sheet_h,
            'note': 'effects_monster 와 같은 형식. 한 줄 = 이펙트 하나. y는 이미지 맨 위 기준. '
                    'origin = 칸 왼쪽 위 기준 중심 위치(y 아래로). make_effects_gnome.py 로 만든 그림.',
            'effects': {}}
    y = 0
    for name, fn, w, h, n, fps, loop, origin, label, use in rows:
        for f in range(n):
            sheet.paste(fn(f), f * w, y)
        print(name)
        meta['effects'][name] = {'x': 0, 'y': y, 'label': label, 'use': use, 'cell_w': w, 'cell_h': h,
                                 'frames': n, 'fps': fps, 'loop': loop, 'origin': origin}
        y += h
    sheet.save_png(f'{OUT}.png')
    with open(f'{OUT}.json', 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print('saved', f'{OUT}.png', sheet_w, 'x', sheet_h)


if __name__ == '__main__':
    main()
