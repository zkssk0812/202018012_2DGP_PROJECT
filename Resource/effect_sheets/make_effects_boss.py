"""보스(실프) 전용 이펙트 시트 effects_boss.png + effects_boss.json 을 만든다.

다른 이펙트 시트(effects_monster)와 같은 형식·색감(진한 보라 테두리, 자홍 몸, 분홍빛 하이라이트)으로 그린다.
외부 라이브러리 없이 순수 파이썬으로 픽셀을 계산해 PNG 로 저장한다.
    python make_effects_boss.py      (이 폴더에서 실행)

이펙트:
    storm       폭풍(회오리). 실프 즉사 패턴 동안 실프 둘레를 돈다. 닿으면 모아를 2초 띄워 올림 (무적)
    blade_warn  즉사 바람 칼날 예고선. 칼날이 나갈 방향으로 길게 늘여 그린다
    rage_aura   광폭화 오라. 실프 발밑에서 타오르는 고리
"""
import json
import math
import random
import struct
import zlib

OUT = 'effects_boss'

# 색 (effects_monster 와 맞춤)
OUTLINE = (52, 6, 44)
DARK = (112, 18, 92)
MID = (196, 52, 150)
LIGHT = (255, 160, 222)
WHITE = (255, 232, 246)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(lerp(a, b, t) for a, b in zip(c1, c2))


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[0.0, 0.0, 0.0, 0.0] for _ in range(w * h)]   # 미리 곱하지 않은 RGBA (0~255, 알파 0~1)

    def blend(self, x, y, color, a):
        """(x, y) 에 color 를 알파 a 로 덮어 그린다 (over 합성)."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        a = min(1.0, a)
        p = self.px[y * self.w + x]
        out_a = a + p[3] * (1 - a)
        if out_a <= 0:
            return
        for i in range(3):
            p[i] = (color[i] * a + p[i] * p[3] * (1 - a)) / out_a
        p[3] = out_a

    def dot(self, cx, cy, r, color, a=1.0):
        for y in range(int(cy - r - 1), int(cy + r + 2)):
            for x in range(int(cx - r - 1), int(cx + r + 2)):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                self.blend(x, y, color, a * (1 - smooth(r - 0.8, r + 0.6, d)))

    def paste(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                p = other.px[y * other.w + x]
                if p[3] > 0:
                    q = self.px[(oy + y) * self.w + ox + x]
                    q[:] = p

    def save_png(self, path):
        raw = bytearray()
        for y in range(self.h):
            raw.append(0)
            for x in range(self.w):
                r, g, b, a = self.px[y * self.w + x]
                raw += bytes((int(r + 0.5), int(g + 0.5), int(b + 0.5), int(a * 255 + 0.5)))

        def chunk(tag, data):
            c = struct.pack('>I', len(data)) + tag + data
            return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

        png = b'\x89PNG\r\n\x1a\n'
        png += chunk(b'IHDR', struct.pack('>IIBBBBB', self.w, self.h, 8, 6, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        png += chunk(b'IEND', b'')
        with open(path, 'wb') as f:
            f.write(png)


# ── 폭풍 (회오리) ───────────────────────────────────
STORM_W, STORM_H, STORM_FRAMES = 192, 256, 8
STORM_BASE = 238                      # 발밑 (칸 위에서부터 y)
STORM_TOP = 18


def draw_storm(frame):
    c = Canvas(STORM_W, STORM_H)
    phase = frame / STORM_FRAMES
    span = STORM_BASE - STORM_TOP

    def shape(v):
        """높이 v(0 = 바닥, 1 = 꼭대기) 에서의 중심 x 와 반폭."""
        cx = STORM_W / 2 + math.sin(v * 4.2 + phase * math.tau) * 10 * v + math.sin(v * 9 - phase * math.tau) * 3
        half = 9 + 66 * v ** 1.35
        return cx, half

    # 바닥의 소용돌이 먼지 고리
    for y in range(STORM_BASE - 22, STORM_BASE + 14):
        for x in range(STORM_W):
            ex = (x + 0.5 - STORM_W / 2) / 52
            ey = (y + 0.5 - STORM_BASE) / 11
            d = math.hypot(ex, ey)
            if d < 1.25:
                ang = math.atan2(ey, ex)
                band = 0.5 + 0.5 * math.sin(ang * 3 - phase * math.tau * 2)
                a = (1 - smooth(0.75, 1.25, d)) * (0.25 + 0.35 * band)
                c.blend(x, y, mix(DARK, MID, band), a)

    # 몸통: 위로 갈수록 넓어지는 깔때기에 비스듬한 줄무늬
    for y in range(STORM_TOP - 6, STORM_BASE + 2):
        v = (STORM_BASE - (y + 0.5)) / span
        if v < -0.02 or v > 1.04:
            continue
        cx, half = shape(max(0.0, min(1.0, v)))
        for x in range(int(cx - half - 6), int(cx + half + 7)):
            u = (x + 0.5 - cx) / half
            au = abs(u)
            # 꼭대기는 구름처럼 울퉁불퉁하게 흩어짐
            edge = v + 0.07 * math.sin(u * 7 + phase * math.tau) + 0.05 * au * au
            top_fade = 1 - smooth(0.84, 1.0, edge)
            if au > 1.12:
                continue
            if au > 0.96:                                      # 테두리
                c.blend(x, y, OUTLINE, 0.9 * (1 - smooth(1.02, 1.12, au)) * top_fade)
                continue
            ang = math.asin(max(-1.0, min(1.0, u)))            # 원통 둘레 각
            s = math.sin(ang * 2.2 + v * 19 - phase * math.tau * 2)
            stripe = 0.5 + 0.5 * s
            shade = 0.55 + 0.45 * math.cos(ang)                # 가운데가 밝게
            col = mix(DARK, MID, shade)
            if stripe > 0.78:
                col = mix(col, LIGHT, (stripe - 0.78) / 0.22)
            a = (0.62 + 0.3 * stripe) * (1 - smooth(0.8, 0.96, au) * 0.35) * top_fade
            c.blend(x, y, col, a)

    # 감아 도는 바람 줄기 (밝은 선)
    for k in range(3):
        for i in range(260):
            v = i / 259
            cx, half = shape(v)
            ang = v * 13 + k * math.tau / 3 - phase * math.tau * 2
            if math.cos(ang) < -0.1:                           # 뒤로 돌아간 부분은 안 그림
                continue
            x = cx + math.sin(ang) * half * 0.92
            y = STORM_BASE - v * span
            c.dot(x, y, 1.6 + 1.2 * v, WHITE, 0.7 * math.cos(ang))

    # 날리는 부스러기
    rnd = random.Random(7)
    for k in range(14):
        base_v = rnd.random()
        speed = 0.6 + rnd.random() * 0.8
        v = (base_v + phase * speed * 0.5) % 1.0
        cx, half = shape(v)
        ang = rnd.random() * math.tau + phase * math.tau * speed * 2
        x = cx + math.sin(ang) * (half + 10 + rnd.random() * 12)
        y = STORM_BASE - v * span
        c.dot(x, y, 2.4 + rnd.random() * 1.5, OUTLINE, 0.8)
        c.dot(x, y, 1.4 + rnd.random(), LIGHT, 0.9)
    return c


# ── 즉사 칼날 예고선 ────────────────────────────────
WARN_W, WARN_H, WARN_FRAMES = 256, 40, 4


def draw_warn(frame):
    c = Canvas(WARN_W, WARN_H)
    pulse = 0.5 + 0.5 * math.sin(frame / WARN_FRAMES * math.tau)
    mid = WARN_H / 2
    core = 2.2 + 1.6 * pulse
    glow = 9 + 4 * pulse
    for y in range(WARN_H):
        d = abs(y + 0.5 - mid)
        for x in range(WARN_W):
            dash = 0.75 + 0.25 * math.sin((x / WARN_W) * math.tau * 4 - frame / WARN_FRAMES * math.tau)
            if d < glow:
                c.blend(x, y, MID, 0.28 * (1 - d / glow) * dash)
            if d < core + 1.6:
                c.blend(x, y, OUTLINE, 0.55 * (1 - smooth(core, core + 1.6, d)))
            if d < core:
                c.blend(x, y, mix(LIGHT, WHITE, pulse), 0.9 * dash)
    return c


# ── 광폭화 오라 ─────────────────────────────────────
AURA_W, AURA_H, AURA_FRAMES = 256, 256, 8
RAGE = (232, 32, 84)
RAGE_HOT = (255, 120, 150)


def draw_aura(frame):
    c = Canvas(AURA_W, AURA_H)
    phase = frame / AURA_FRAMES * math.tau
    cx, cy = AURA_W / 2, AURA_H / 2
    inner = 66
    for y in range(AURA_H):
        for x in range(AURA_W):
            dx, dy = x + 0.5 - cx, (y + 0.5 - cy) * 1.0
            r = math.hypot(dx, dy)
            if r > 126:
                continue
            th = math.atan2(dy, dx)
            if r < inner:                                       # 안쪽은 옅게 붉은 빛
                c.blend(x, y, RAGE, 0.16 * smooth(inner * 0.4, inner, r))
                continue
            h = (22 + 16 * (0.5 + 0.5 * math.sin(th * 7 + phase))
                 + 9 * math.sin(th * 13 - phase * 2) + 5 * math.sin(th * 23 + phase * 3))
            t = (r - inner) / max(1.0, h)
            if t > 1.18:
                continue
            if t > 1.0:                                         # 불꽃 테두리
                c.blend(x, y, OUTLINE, 0.85 * (1 - smooth(1.0, 1.18, t)))
                continue
            col = mix(RAGE, RAGE_HOT, 1 - t) if t > 0.35 else mix(RAGE_HOT, WHITE, (0.35 - t) / 0.35 * 0.6)
            c.blend(x, y, col, 0.85 - 0.35 * t)
    # 튀는 불씨
    rnd = random.Random(3)
    for k in range(16):
        a0 = rnd.random() * math.tau
        rise = (rnd.random() + frame / AURA_FRAMES) % 1.0
        r = inner + 20 + rise * 36
        x, y = cx + math.cos(a0) * r, cy + math.sin(a0) * r
        c.dot(x, y, 2.6 * (1 - rise) + 0.8, OUTLINE, 0.7 * (1 - rise))
        c.dot(x, y, 1.8 * (1 - rise) + 0.5, RAGE_HOT, 0.9 * (1 - rise))
    return c


def main():
    rows = [
        ('storm', draw_storm, STORM_W, STORM_H, STORM_FRAMES, 12, True, [STORM_W // 2, STORM_BASE],
         '폭풍', '실프 즉사 패턴 · 닿으면 2초간 띄워 올림 (무적)'),
        ('rage_aura', draw_aura, AURA_W, AURA_H, AURA_FRAMES, 12, True, [AURA_W // 2, AURA_H // 2],
         '광폭화 오라', '실프 광폭화 · 발밑 고리'),
        ('blade_warn', draw_warn, WARN_W, WARN_H, WARN_FRAMES, 12, True, [0, WARN_H // 2],
         '즉사 칼날 예고선', '실프 즉사 패턴 · 칼날 방향으로 늘여 그림'),
    ]
    sheet_w = max(w * n for _, _, w, _, n, *_ in rows)
    sheet_h = sum(h for _, _, _, h, *_ in rows)
    sheet = Canvas(sheet_w, sheet_h)
    meta = {'image': f'{OUT}.png', 'sheet_w': sheet_w, 'sheet_h': sheet_h,
            'note': 'effects_monster 와 같은 형식. 한 줄 = 이펙트 하나. y는 이미지 맨 위 기준. '
                    'origin = 칸 왼쪽 위 기준 중심 위치(y 아래로). make_effects_boss.py 로 만든 그림.',
            'effects': {}}
    y = 0
    for name, fn, w, h, n, fps, loop, origin, label, use in rows:
        for f in range(n):
            sheet.paste(fn(f), f * w, y)
            print(name, f)
        meta['effects'][name] = {'x': 0, 'y': y, 'label': label, 'use': use, 'cell_w': w, 'cell_h': h,
                                 'frames': n, 'fps': fps, 'loop': loop, 'origin': origin}
        y += h
    sheet.save_png(f'{OUT}.png')
    with open(f'{OUT}.json', 'w', encoding='utf-8') as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    print('saved', f'{OUT}.png', sheet_w, 'x', sheet_h)


if __name__ == '__main__':
    main()
