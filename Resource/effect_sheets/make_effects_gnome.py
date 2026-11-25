"""노움(바위의 상위 정령) 전용 이펙트 시트 effects_gnome.png + effects_gnome.json 을 만든다.

타락한 노움처럼 갈색 바위에 자홍 수정 · 마그마 빛을 섞는다. 바위는 높이맵 → 법선 → 빛 방향으로 입체 음영,
땅의 균열은 보로노이로 자연스럽게 갈라진다. (fxkit.py 사용)
    python make_effects_gnome.py                 시트 저장
    python make_effects_gnome.py 이름 out.png 2   확인용 미리보기 (2배)

이펙트 (이름 · 칸 크기 · origin 은 게임 코드와 맞춰 둠):
    crack_tile      대지 균열 예고 (240×240, 4프레임): 바닥 칸이 점점 깊게 갈라지며 마그마 빛
    rock_pillar     바위 기둥 (160×240, 6프레임 한 번, origin = 발밑): 솟아오름 → 흙먼지 → 가라앉음
    boulder         큰 바위 (192×192, origin = 발밑): 대지의 분노 · 충격파를 가림
    quake_wave      흙빛 충격파 (512×512, 8프레임 한 번, 크게 늘려 그림)
    life_stone_N    생명석 (96×128, 4프레임 = 맞은 수 0 · 1 · 2 · 부서지기 직전). N = 0 빨강 · 1 파랑 · 2 초록 · 3 노랑
    life_orb_N      생명석과 같은 색 기운 (64×64, 6프레임 반복)
"""
import math
import random
import sys

from fxkit import (Layer, Noise, Sheet, paint, dots, streak, clamp, smooth, mix, ramp, rgb, voronoi, preview)

OUT = 'effects_gnome'

OUTLINE = rgb('241410')
ROCK = [(0.0, rgb('2b1c17')), (0.3, rgb('4e382d')), (0.55, rgb('7a5a45')), (0.8, rgb('a8846a')),
        (1.0, rgb('d8bf9f'))]
CRYSTAL = [(0.0, rgb('4a0d3c')), (0.45, rgb('b02a8a')), (0.8, rgb('ff6fc8')), (1.0, rgb('ffe0f4'))]
MAGMA = [(0.0, rgb('3a0a10')), (0.35, rgb('a3241c')), (0.65, rgb('ff6a2a')), (0.85, rgb('ffb35c')),
         (1.0, rgb('fff0c8'))]
LIFE = [rgb('eb4646'), rgb('508cff'), rgb('5ad26e'), rgb('facd3c')]
LIGHT = (-0.5, -0.62, 0.6)                    # 왼쪽 위에서 오는 빛 (이미지 좌표: y 아래로)

N = Noise(11)
N2 = Noise(23)


def norm3(x, y, z):
    n = math.sqrt(x * x + y * y + z * z) or 1
    return x / n, y / n, z / n


LX, LY, LZ = norm3(*LIGHT)


def glow(layer, radius, color, strength):
    g = Layer(layer.w, layer.h)
    g.a = layer.a[:]
    g = g.blur(radius, passes=2)
    out = Layer(layer.w, layer.h)
    for i in range(layer.w * layer.h):
        a = clamp(g.a[i] * strength)
        out.r[i], out.g[i], out.b[i], out.a[i] = color[0] * a, color[1] * a, color[2] * a, a
    out.composite(layer)
    return out


def shade(height, x, y, eps=0.6):
    """높이 함수의 법선으로 빛을 계산 (0~1). height(x, y) 는 실수."""
    hx = (height(x + eps, y) - height(x - eps, y)) / (2 * eps)
    hy = (height(x, y + eps) - height(x, y - eps)) / (2 * eps)
    nx, ny, nz = norm3(-hx, -hy, 1.0)
    diffuse = max(0.0, nx * LX + ny * LY + nz * LZ)
    return diffuse, nz


def rock_shape(cx, cy, rx, ry, seed):
    """울퉁불퉁한 바위 덩어리: (안에 있나, 높이 함수)."""
    rnd = random.Random(seed)
    bumps = [(rnd.uniform(0.015, 0.045) / (1 + k * 0.4), rnd.uniform(0, math.tau), k + 2) for k in range(6)]
    noise = Noise(seed)

    def edge(th):
        return 1 + sum(a * math.sin(th * k + p) for a, p, k in bumps)

    def height(x, y):
        dx, dy = (x - cx) / rx, (y - cy) / ry
        d = math.hypot(dx, dy) / edge(math.atan2(dy, dx))
        if d >= 1:
            return 0.0
        base = math.sqrt(1 - d * d)
        return base * 18 + noise.fbm(x * 0.09, y * 0.09, 4) * 6 * base + \
            (1 - abs(noise.value(x * 0.05, y * 0.05) * 2 - 1)) * 4 * base      # 깨진 면 느낌

    def inside(x, y):
        dx, dy = (x - cx) / rx, (y - cy) / ry
        return math.hypot(dx, dy) / edge(math.atan2(dy, dx))

    return inside, height


def paint_rock(L, cx, cy, rx, ry, seed, crystals=3, crystal_scale=1.0):
    inside, height = rock_shape(cx, cy, rx, ry, seed)

    def fn(x, y):
        d = inside(x, y)
        if d > 1.0:
            return None
        diffuse, nz = shade(height, x, y)
        ao = 0.65 + 0.35 * smooth(1.0, 0.55, d)                 # 가장자리는 어둡게 (둥근 덩어리감)
        grain = N.fbm(x * 0.35, y * 0.35, 2)
        t = clamp(diffuse * 0.85 * ao + grain * 0.12)
        a = 1 - smooth(0.96, 1.0, d)
        return ramp(ROCK, t), a

    paint(L.w, L.h, fn, ss=2, layer=L)
    rnd = random.Random(seed * 7 + 1)
    for k in range(crystals):                                   # 박힌 자홍 수정 (면 2개 + 빛)
        a = rnd.uniform(-2.6, -0.6)
        rr = rnd.uniform(0.15, 0.55)
        x0, y0 = cx + math.cos(a) * rx * rr, cy + math.sin(a) * ry * rr
        s = rnd.uniform(5, 9) * crystal_scale
        tilt = rnd.uniform(-0.5, 0.5)
        crystal(L, x0, y0, s, tilt)


def crystal(L, x0, y0, s, tilt, colors=CRYSTAL):
    """작은 수정 기둥 (왼쪽 면은 밝게, 오른쪽 면은 어둡게)."""
    tip = (x0 + math.sin(tilt) * s * 2.2, y0 - math.cos(tilt) * s * 2.2)
    left = (x0 - s * 0.7, y0)
    right = (x0 + s * 0.7, y0)
    mid = (x0 + math.sin(tilt) * s * 0.4, y0 + s * 0.25)

    def tri(p, a, b, c):
        (px, py) = p
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if d == 0:
            return False
        l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
        l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
        return l1 >= 0 and l2 >= 0 and 1 - l1 - l2 >= 0

    def fn(x, y):
        if tri((x, y), tip, left, mid):
            t = (y - tip[1]) / max(1, mid[1] - tip[1])
            return ramp(colors, 0.95 - t * 0.35), 1.0
        if tri((x, y), tip, mid, right):
            t = (y - tip[1]) / max(1, mid[1] - tip[1])
            return ramp(colors, 0.55 - t * 0.3), 1.0
        return None

    sub = paint(L.w, L.h, fn, ss=2)
    sub = glow(sub, 3, colors[2][1], 0.35)
    L.composite(sub)


# ── 대지 균열 ────────────────────────────────────────
CRACK = 240


def crack_points(seed):
    rnd = random.Random(seed)
    pts = []
    n = 5
    for j in range(n):
        for i in range(n):
            pts.append(((i + 0.2 + rnd.random() * 0.6) * CRACK / n, (j + 0.2 + rnd.random() * 0.6) * CRACK / n))
    return pts


PTS = crack_points(5)


def crack_frame(f):
    k = (f + 1) / 4                                            # 0.25 → 1
    cell_rnd = [random.Random(i * 31 + 7).random() for i in range(len(PTS))]

    def fn(x, y):
        e = min(x, y, CRACK - x, CRACK - y)
        border = math.exp(-e / (5 + 6 * k))                    # 칸 테두리 빛 (위험 범위 표시)
        jx = (N.fbm(x * 0.06, y * 0.06, 3) - 0.5) * 14        # 금이 구불구불하게
        jy = (N2.fbm(x * 0.06, y * 0.06, 3) - 0.5) * 14
        d1, d2, idx = voronoi(PTS, x + jx, y + jy)
        gap = d2 - d1                                          # 경계에서 0
        show = smooth(0.9 - k, 1.05 - k * 0.8, cell_rnd[idx])  # 처음엔 일부 금만, 점점 전부
        width = (1.2 + 4.0 * k) * (0.6 + 0.8 * N.fbm(x * 0.03 + 9, y * 0.03, 2))
        crack = (1 - smooth(width * 0.5, width, gap)) * max(show, 0.35 if k > 0.5 else 0.0)
        plate = 0.10 + 0.14 * k                                # 갈라진 판: 어둡게 + 가장자리 살짝 밝게 (들뜬 판)
        lip = math.exp(-((gap - width * 1.2) / 2.0) ** 2) * 0.35 * k
        col, a = rgb('2a110c'), plate
        if lip > 0.02:
            col, a = mix(col, rgb('9c6a4c'), lip * 2), max(a, lip)
        if border > 0.02:
            col, a = mix(col, ramp(MAGMA, 0.55 + 0.4 * k), border), max(a, border * (0.55 + 0.4 * k))
        if crack > 0.02:
            heat = clamp(crack * (0.4 + 0.35 * k) + (1 - gap / max(width, 0.1)) * 0.15, 0, 0.82)
            col, a = ramp(MAGMA, heat), max(a, crack)
        return col, clamp(a)

    L = paint(CRACK, CRACK, fn, ss=2)
    return glow(L, 4, rgb('ff5a2a'), 0.25 * k)


# ── 바위 기둥 ───────────────────────────────────────
PW, PH = 160, 240
P_BASE = PH - 14


def pillar_frame(f):
    grow = [0.32, 0.72, 1.0, 1.04, 0.98, 0.85][f]
    fade = [1, 1, 1, 1, 0.85, 0.55][f]
    h = 196 * grow
    cx = PW / 2
    apex_x, apex_y = cx - 4, P_BASE - h
    left_b, right_b = cx - 54, cx + 56                         # 밑면 양 끝
    edge1_b, edge2_b = cx - 18, cx + 22                        # 면 사이 모서리 (밑에서)

    def fn(x, y):
        if y > P_BASE + 1 or y < apex_y - 1:
            return None
        t = (P_BASE - y) / max(h, 1)                           # 0 바닥 → 1 꼭대기
        jag = (N.fbm(y * 0.09, 3.1 + f * 0.2, 3) - 0.5) * 9 * (1 - t * 0.5)
        xl = left_b + (apex_x - left_b) * t + jag
        xr = right_b + (apex_x - right_b) * t - jag * 0.7
        if not xl <= x <= xr:
            return None
        e1 = edge1_b + (apex_x - edge1_b) * t
        e2 = edge2_b + (apex_x - edge2_b) * t
        face = 0.82 if x < e1 else (0.58 if x < e2 else 0.3)  # 밝은 면 · 정면 · 그늘 면
        tex = N.fbm(x * 0.11, y * 0.05, 4)
        strata = 0.5 + 0.5 * math.sin(y * 0.21 + tex * 5)       # 지층 무늬
        tt = clamp(face + (tex - 0.5) * 0.3 + strata * 0.07 - (1 - t) * 0.06)
        col = ramp(ROCK, tt)
        if abs(x - e1) < 1.2 or abs(x - e2) < 1.2:             # 모서리 빛
            col = mix(col, ramp(ROCK, 1.0), 0.35)
        vein = abs(N2.fbm(x * 0.045, y * 0.028, 3) - 0.5)       # 자홍 수정 맥
        if vein < 0.016:
            col = mix(col, ramp(CRYSTAL, 0.9 - vein * 20), 0.85)
        return col, fade

    L = paint(PW, PH, fn, ss=2)
    L = glow(L, 2, rgb('ff6fc8'), 0.08)
    L = L.outline(OUTLINE, width=1.5, strength=0.9 * fade)
    rnd = random.Random(f + 3)
    pts = []
    for k in range(18 if f < 3 else 8):                        # 튀는 흙 · 돌조각 (기둥 바깥으로)
        x = cx + rnd.choice((-1, 1)) * rnd.uniform(40, 74)
        y = P_BASE - rnd.uniform(0, 30 + 40 * f)
        r = rnd.uniform(1.5, 4.0)
        pts.append((x, y, r + 1, OUTLINE, 0.9 * fade))
        pts.append((x - 0.5, y - 0.5, r, ramp(ROCK, rnd.uniform(0.5, 0.9)), 0.95 * fade))
    dots(L, pts)
    if f in (1, 2, 3):                                           # 발밑 흙먼지
        dust = paint(PW, PH, lambda x, y: (
            (rgb('8a6a52'), (1 - smooth(0.4, 1.0, math.hypot((x - cx) / (64 + f * 8), (y - P_BASE + 6) / 16))) *
             (0.35 + 0.4 * N.fbm(x * 0.08, y * 0.1 + f, 3)) * (0.9 if f < 3 else 0.5))
            if math.hypot((x - cx) / (64 + f * 8), (y - P_BASE + 6) / 16) < 1 else None), ss=1)
        dust.composite(L)
        L = dust
    return L


# ── 큰 바위 ─────────────────────────────────────────
BW, BH = 192, 192


def boulder_frame(f):
    L = Layer(BW, BH)
    shadow = paint(BW, BH, lambda x, y: ((0, 0, 0), 0.45 * (1 - smooth(0.3, 1.0, math.hypot(
        (x - BW / 2) / 84, (y - BH + 32) / 20)))) if math.hypot((x - BW / 2) / 84, (y - BH + 32) / 20) < 1 else None,
        ss=1)
    L.composite(shadow)
    paint_rock(L, BW / 2, BH / 2 + 8, 78, 70, seed=5, crystals=5, crystal_scale=1.3)
    return L.outline(OUTLINE, width=1.5, strength=0.85)


# ── 흙빛 충격파 ──────────────────────────────────────
WAVE = 512


def wave_frame(f):
    t = f / 7
    ease = 1 - (1 - t) ** 3
    c = WAVE / 2
    ring = 22 + 222 * ease
    thick = 50 * (1 - t) ** 0.7 + 10
    fade = 1 - smooth(0.45, 1.0, t)
    DUST = [(0.0, rgb('3b2a20')), (0.4, rgb('7a5a42')), (0.75, rgb('c6a27c')), (1.0, rgb('f4e2c4'))]

    def fn(x, y):
        dx, dy = x - c, y - c
        r = math.hypot(dx, dy)
        if r > 255:
            return None
        ang = (math.atan2(dy, dx) / math.tau) % 1.0
        billow = N.wrap_fbm(ang, r * 0.025 - t * 3, freq=14, octaves=4)
        d = (r - ring) / thick
        col, a = None, 0.0
        if -1.6 < d < 1.0:                                    # 흙먼지 고리 (뭉게뭉게)
            body = (1 - smooth(0.0, 1.0, d)) if d > 0 else math.exp(-(d / 0.9) ** 2)
            body *= 0.35 + 0.85 * smooth(0.3, 0.75, billow)
            col, a = ramp(DUST, 0.3 + 0.7 * billow * (1 - abs(d) * 0.4)), body
        if r < ring * 0.97:                                    # 안쪽: 땅에 새겨진 방사형 금 (점점 옅어짐)
            k = r / max(ring, 1)
            crack = max(0.0, math.cos((ang * 22 + N2.wrap_fbm(ang, r * 0.02, freq=8, octaves=2) * 0.8) * math.tau))
            crack = smooth(0.975, 1.0, crack) * smooth(0.25, 0.6, k) * (1 - t) * 0.5
            if crack > a:
                col, a = mix(rgb('2a1810'), rgb('ff8a4a'), 0.3), crack
        if col is None or a < 0.01:
            return None
        return col, a * fade

    L = paint(WAVE, WAVE, fn, ss=1)
    rnd = random.Random(f + 70)
    pts = []
    for k in range(70):                                         # 고리에 실려 날아가는 돌조각
        a = rnd.random() * math.tau
        r = ring + rnd.uniform(-thick * 0.6, thick * 0.4)
        s = rnd.uniform(1.5, 4.5) * (1 - t * 0.4)
        x, y = c + math.cos(a) * r, c + math.sin(a) * r
        pts.append((x, y, s + 1, OUTLINE, 0.9 * fade))
        pts.append((x, y, s, ramp(ROCK, rnd.uniform(0.4, 0.9)), 0.95 * fade))
    dots(L, pts)
    return L


# ── 생명석 ──────────────────────────────────────────
SW, SH = 96, 128


def stone_frame(ci, f):
    color = LIFE[ci]
    GEM = [(0.0, mix(color, (0, 0, 0), 0.75)), (0.35, mix(color, (0, 0, 0), 0.35)), (0.65, color),
           (0.85, mix(color, (1, 1, 1), 0.45)), (1.0, mix(color, (1, 1, 1), 0.85))]
    cx = SW / 2
    L = Layer(SW, SH)
    L.composite(paint(SW, SH, lambda x, y: ((0, 0, 0), 0.4 * (1 - smooth(0.3, 1.0, math.hypot(
        (x - cx) / 38, (y - SH + 16) / 9)))) if math.hypot((x - cx) / 38, (y - SH + 16) / 9) < 1 else None, ss=1))
    paint_rock(L, cx, SH - 30, 36, 20, seed=3, crystals=0)    # 받침돌

    # 육각 기둥 보석: 왼쪽 면 · 가운데 면 · 오른쪽 면 + 뾰족한 머리
    top_y, shoulder, bottom = 10, 36, 96
    hw = 24

    def fn(x, y):
        if y < top_y or y > bottom + 2:
            return None
        if y < shoulder:                                         # 머리 (뾰족)
            w = hw * (y - top_y) / (shoulder - top_y)
        else:
            w = hw - (y - shoulder) / (bottom - shoulder) * 4
        dx = x - cx
        if abs(dx) > w:
            return None
        u = dx / max(w, 0.1)                                     # -1 ~ 1
        if u < -0.38:
            t = 0.88
        elif u < 0.32:
            t = 0.62
        else:
            t = 0.32
        t += (0.08 if y < shoulder else 0) - (y - top_y) / (bottom - top_y) * 0.18
        inner = math.exp(-((y - 58) / 22) ** 2) * math.exp(-(dx / 10) ** 2) * 0.35     # 안쪽 빛
        col = ramp(GEM, clamp(t + inner))
        if abs(u + 0.38) < 0.05 or abs(u - 0.32) < 0.05:          # 면 사이 모서리 빛
            col = mix(col, (1, 1, 1), 0.35)
        if -0.75 < u < -0.55 and shoulder < y < 82:              # 세로 하이라이트
            col = mix(col, (1, 1, 1), 0.55)
        return col, 1.0

    gem = paint(SW, SH, fn, ss=3)
    # 맞은 만큼 금 (빛이 새어 나옴)
    cracks = [[(cx - 5, 26), (cx + 4, 42), (cx - 3, 56), (cx + 7, 72)],
              [(cx + 12, 40), (cx + 2, 54), (cx + 11, 68), (cx + 4, 84)],
              [(cx - 15, 50), (cx - 6, 64), (cx - 13, 80), (cx - 2, 92)]]
    for k in range(min(f, 3)):
        pts = cracks[k]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            streak(gem, x1, y1, x2, y2, 3.2, mix(color, (1, 1, 1), 0.85), 0.8, taper=False)
            streak(gem, x1, y1, x2, y2, 1.3, mix(color, (0, 0, 0), 0.8), 1.0, taper=False)
    gem = gem.outline(mix(color, (0, 0, 0), 0.8), width=1.2, strength=0.9)
    gem = glow(gem, 6, color, 0.5 + 0.15 * f)
    if f == 3:                                                   # 부서지기 직전: 빛줄기
        rnd = random.Random(ci)
        for k in range(7):
            a = rnd.uniform(0, math.tau)
            streak(gem, cx, 60, cx + math.cos(a) * 44, 60 + math.sin(a) * 44, 2.4, mix(color, (1, 1, 1), 0.7),
                   0.7, mode='add')
    L.composite(gem)
    return L


# ── 생명석과 같은 색 기운 ────────────────────────────
OW = 64


def orb_frame(ci, f):
    color = LIFE[ci]
    ph = f / 6
    c = OW / 2

    def fn(x, y):
        dx, dy = x - c, y - c
        r = math.hypot(dx, dy)
        if r > 31:
            return None
        ang = (math.atan2(dy, dx) / math.tau) % 1.0
        swirl = N.wrap_fbm((ang + ph + r * 0.02) % 1.0, r * 0.08, freq=4, octaves=3)
        rad = 12.5 + 3 * swirl
        if r < rad:
            k = r / rad
            col = mix(mix(color, (1, 1, 1), 0.9), color, k ** 1.5)
            arm = max(0.0, math.sin((ang * 3 - r * 0.12 + ph) * math.tau)) ** 3 * k   # 안에서 도는 소용돌이
            col = mix(col, mix(color, (0, 0, 0), 0.35), arm * 0.5)
            return col, 1.0 - smooth(0.85, 1.0, k) * 0.2
        halo = math.exp(-((r - rad) / 7) ** 2) * (0.55 + 0.45 * swirl)
        return color, halo * 0.8

    L = paint(OW, OW, fn, ss=2)
    pts = []
    for k in range(4):                                           # 도는 작은 빛
        a = (ph + k / 4) * math.tau
        rr = 20 + 3 * math.sin(a * 2)
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr * 0.75, 1.8, mix(color, (1, 1, 1), 0.8), 0.95))
    dots(L, pts, mode='add')
    return L


BUILDERS = {
    'crack_tile': (crack_frame, 4), 'rock_pillar': (pillar_frame, 6), 'boulder': (boulder_frame, 1),
    'quake_wave': (wave_frame, 8),
    **{f'life_stone_{i}': ((lambda f, i=i: stone_frame(i, f)), 4) for i in range(4)},
    **{f'life_orb_{i}': ((lambda f, i=i: orb_frame(i, f)), 6) for i in range(4)},
}


def main():
    sheet = Sheet(OUT, 'effects_monster 와 같은 형식. 한 줄 = 이펙트 하나. y는 이미지 맨 위 기준. '
                       'origin = 칸 왼쪽 위 기준 중심 위치(y 아래로). make_effects_gnome.py (fxkit) 로 만든 그림.')
    sheet.add('crack_tile', [crack_frame(f) for f in range(4)], 4, False, [CRACK // 2, CRACK // 2],
              '대지 균열 예고', '노움 · 갈라지는 바닥 칸')
    sheet.add('rock_pillar', [pillar_frame(f) for f in range(6)], 12, False, [PW // 2, P_BASE],
              '바위 기둥', '노움 대지 균열 · 칸에서 솟음')
    sheet.add('boulder', [boulder_frame(0)], 1, True, [BW // 2, BH - 30], '큰 바위', '노움 대지의 분노 · 충격파를 가림')
    sheet.add('quake_wave', [wave_frame(f) for f in range(8)], 12, False, [WAVE // 2, WAVE // 2],
              '흙빛 충격파', '노움 대지의 분노 · 맵 전체 (크게 늘려 그림)')
    for i in range(4):
        sheet.add(f'life_stone_{i}', [stone_frame(i, f) for f in range(4)], 1, True, [SW // 2, SH - 24],
                  f'생명석 {i}', '노움 생명석 · 프레임 = 맞은 수')
    for i in range(4):
        sheet.add(f'life_orb_{i}', [orb_frame(i, f) for f in range(6)], 10, True, [OW // 2, OW // 2],
                  f'생명 기운 {i}', '노움 생명석과 같은 색 기운')
    sheet.save()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        fn, n = BUILDERS[sys.argv[1]]
        preview([fn(f) for f in range(n)], sys.argv[2], scale=int(sys.argv[3]) if len(sys.argv) > 3 else 1, cols=4)
    else:
        main()
