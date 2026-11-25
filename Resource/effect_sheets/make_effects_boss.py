"""보스(실프) 전용 이펙트 시트 effects_boss.png + effects_boss.json 을 만든다.

기존 이펙트(effects_monster)와 어울리게 진한 보라 테두리 · 자홍 몸 · 분홍빛 하이라이트를 쓰되,
노이즈 질감 · 빛 번짐 · 안티앨리어싱으로 결을 살린다. 반복 애니메이션은 이음새 없이 돈다.
    python make_effects_boss.py      (이 폴더에서 실행, fxkit.py 사용)

이펙트 (이름 · 칸 크기 · origin 은 게임 코드와 맞춰 둠):
    storm        폭풍 회오리 (192×256, 8프레임 반복, origin = 발밑). 즉사 패턴 동안 실프 둘레를 돈다
    rage_aura    광폭화 오라 (256×256, 8프레임 반복). 실프 발밑에서 타오르는 붉은 불꽃 고리
    final_charge 마지막 힘 모으기 (256×256, 8프레임 반복). 바람이 빨려 들며 빛이 모임
    final_burst  맵 전체 폭발 (512×512, 8프레임 한 번, 크게 늘려 그림). 섬광 · 충격파 고리 · 바람 줄기
    blade_warn   즉사 칼날 예고선 (256×40, 4프레임 반복, origin = 왼쪽 가운데). 칼날 방향으로 길게 늘여 그림
"""
import math
import random

from fxkit import (Layer, Noise, Sheet, paint, dots, streak, clamp, smooth, mix, ramp, rgb, lerp, preview)

OUT = 'effects_boss'

OUTLINE = rgb('2a0626')
DEEP = rgb('3a0a3a')
MAGENTA = rgb('c2349a')
PINK = rgb('ff8fd2')
PALE = rgb('ffd6f0')
WHITE = (1.0, 0.97, 1.0)
WIND = [(0.0, DEEP), (0.35, rgb('7a1a6e')), (0.6, MAGENTA), (0.82, PINK), (1.0, PALE)]

N = Noise(7, period=256)
N2 = Noise(19, period=256)


def glow(layer, radius, color, strength):
    """알파 모양대로 바깥에 색 빛을 번지게 (빛 번짐)."""
    g = Layer(layer.w, layer.h)
    g.a = layer.a[:]
    g = g.blur(radius, passes=2)
    out = Layer(layer.w, layer.h)
    for i in range(layer.w * layer.h):
        a = clamp(g.a[i] * strength)
        out.r[i], out.g[i], out.b[i], out.a[i] = color[0] * a, color[1] * a, color[2] * a, a
    out.composite(layer)
    return out


# ── 폭풍 회오리 ──────────────────────────────────────
STORM_W, STORM_H, STORM_FRAMES = 192, 256, 8
BASE_Y, TOP_Y = 236, 16


def storm_frame(f):
    ph = f / STORM_FRAMES
    span = BASE_Y - TOP_Y

    def axis(v):
        cx = STORM_W / 2 + math.sin(v * 3.6 + ph * math.tau) * 9 * v + math.sin(v * 8.5 - ph * math.tau) * 2.5
        hw = 8 + 72 * v ** 1.35
        return cx, hw

    def body(x, y):
        v = (BASE_Y - y) / span
        if v < -0.04 or v > 1.08:
            return None
        vc = clamp(v)
        cx, hw = axis(vc)
        hw *= 0.88 + 0.24 * N2.wrap_fbm(ph, vc * 5.0, freq=2, octaves=2)   # 일렁이는 실루엣
        u = (x - cx) / hw
        au = abs(u)
        if au > 1.3:
            return None
        th = math.asin(clamp(u, -1, 1))                       # 원통 둘레 각 (앞면)
        s = ((th / math.pi + 0.5) * 0.5 - ph) % 1.0           # 둘레 좌표 (돌아감)
        tex = N.wrap_fbm(s, vc * 5.0, freq=4, octaves=4)
        warp = N2.wrap_fbm(s, vc * 3.0, freq=4, octaves=2)
        # 가는 바람 줄 여러 개 (노이즈로 휘어짐)
        lines = 0.0
        for k, (fr, w) in enumerate(((3, 0.92), (5, 0.95), (7, 0.965))):
            b = math.sin((s * fr + vc * (2.2 + k) + warp * 0.6) * math.tau)
            lines = max(lines, smooth(w, 1.0, b))
        lines *= 1 - smooth(0.82, 1.0, au)                      # 가장자리 밖으로는 줄이 새지 않게
        light = 0.5 + 0.5 * math.cos(th)                      # 가운데가 밝음 (앞면)
        dens = 0.18 + 0.82 * smooth(0.3, 0.78, tex)           # 바람 덩어리 · 빈 틈
        dens *= 1 - smooth(0.72, 1.25, au)                     # 가장자리로 갈수록 옅게
        top = 0.8 + 0.2 * N2.wrap_fbm(s, 3.0, freq=4, octaves=3)
        dens *= 1 - smooth(top - 0.22, top, v)                 # 꼭대기는 구름처럼 흩어짐
        dens *= smooth(-0.04, 0.08, v)
        if dens <= 0.01 and lines < 0.05:
            return None
        depth = 0.35 + 0.65 * light                            # 뒤쪽(가장자리 안쪽)은 어둡게 → 부피감
        t = depth * (0.35 + 0.5 * tex) + 0.15
        col = ramp(WIND, t)
        a = dens * 0.85
        if lines > 0 and math.cos(th) > -0.2:
            col = mix(col, mix(PINK, WHITE, light), lines * 0.9)
            a = max(a, lines * 0.95 * (1 - smooth(top - 0.1, top + 0.02, v)) * smooth(-0.02, 0.05, v))
        return col, clamp(a)

    L = paint(STORM_W, STORM_H, body, ss=2)

    # 발밑 흙먼지 소용돌이 (납작한 타원)
    def dust(x, y):
        dx, dy = (x - STORM_W / 2) / 62, (y - BASE_Y) / 13
        d = math.hypot(dx, dy)
        if d > 1.3:
            return None
        ang = math.atan2(dy, dx) / math.tau
        tex = N2.wrap_fbm((ang - ph) % 1.0, d * 3, freq=6, octaves=3)
        a = (1 - smooth(0.6, 1.3, d)) * (0.25 + 0.55 * smooth(0.4, 0.75, tex))
        return mix(rgb('5a1f4c'), PINK, tex * 0.6), a * 0.8

    base = paint(STORM_W, STORM_H, dust, ss=1)
    base.composite(L)
    L = base

    # 감겨 도는 부스러기 (꽃잎 · 돌조각). 앞쪽에 있을 때만 진하게
    rnd = random.Random(3)
    pts_back, pts_front = [], []
    for k in range(22):
        v0 = rnd.random()
        speed = rnd.choice((1, 2))
        a0 = rnd.random()
        v = (v0 + ph * 0.35 * speed) % 1.0
        cx, hw = axis(v)
        ang = (a0 + ph * speed) * math.tau
        x = cx + math.sin(ang) * (hw * 1.08 + 6)
        y = BASE_Y - v * span
        front = math.cos(ang) > 0
        col = PALE if k % 3 else rgb('4a1e33')
        size = rnd.uniform(1.0, 2.0) * (1.15 if front else 0.8)
        (pts_front if front else pts_back).append((x, y, size, col, 0.95 if front else 0.4))
    dots(L, pts_front)
    L = glow(L, 5, MAGENTA, 0.35)
    L = L.outline(OUTLINE, width=1.5, strength=0.55)
    back = Layer(STORM_W, STORM_H)
    dots(back, pts_back)
    back.composite(L)
    return back


# ── 광폭화 오라 ──────────────────────────────────────
AURA = 256


def aura_frame(f, part='back'):
    """바닥의 고리에서 위로 날름거리며 솟는 붉은 불꽃 벽. part: 'back' (실프 뒤: 뒤쪽 불꽃 + 바닥 빛) / 'front' (실프 앞)."""
    ph = f / 8
    c = AURA / 2
    cy = c + 34                                                  # 고리 중심 (칸 아래쪽, 불꽃이 위로 솟을 자리)
    rx, ry = 74, 30
    FLAME = [(0.0, rgb('4a0612')), (0.25, rgb('a3122e')), (0.5, rgb('ef3b3b')), (0.75, rgb('ff9a5c')),
             (1.0, rgb('fff1c9'))]

    def flame_at(x, y, front):
        dx = (x - c) / rx
        if abs(dx) > 1.0:
            return 0.0, 0.0
        ring_y = cy + (1 if front else -1) * ry * math.sqrt(1 - dx * dx)
        d = ring_y - y                                           # 고리 위로 얼마나 올라왔나
        if d < -6:
            return 0.0, 0.0
        s = ((math.atan2((ring_y - cy) / ry, dx) / math.tau) + (0.5 if front else 0)) % 1.0
        n = N.wrap_fbm((s + ph * 0.15) % 1.0, y * 0.05 + ph * 4.0, freq=10, octaves=4)
        h = (18 + 46 * n) * (0.55 + 0.45 * math.sqrt(1 - dx * dx))   # 양 끝은 낮게
        t = d / h
        if t > 1.1:
            return 0.0, 0.0
        a = (1 - smooth(0.6, 1.1, t)) * smooth(-6, 2, d)
        heat = clamp((1 - t) * (0.7 + 0.5 * n))
        return a, heat

    def fn(x, y):
        if part == 'front':
            a, heat = flame_at(x, y, True)
            return (ramp(FLAME, heat), a * 0.85) if a > 0.01 else None
        a, heat = flame_at(x, y, False)
        if a > 0.01:
            return ramp(FLAME, heat), a
        dx, dy = (x - c) / rx, (y - cy) / ry
        r = math.hypot(dx, dy)
        if r < 1.15:                                             # 바닥에 번진 붉은 빛
            return rgb('d1203c'), (1 - smooth(0.6, 1.15, r)) * 0.35
        return None

    L = paint(AURA, AURA, fn, ss=2)
    rnd = random.Random(8)
    embers = []
    for k in range(28):                                           # 위로 날아오르는 불씨
        a0 = rnd.random() * math.tau
        life = (rnd.random() + ph) % 1.0
        if (math.sin(a0) > 0) != (part == 'front'):            # 앞쪽 불씨는 앞 그림에만
            continue
        x = c + math.cos(a0) * rx * rnd.uniform(0.6, 1.0) + math.sin(life * 9 + k) * 4
        y = cy + math.sin(a0) * ry - life * 95
        s = (1 - life) * 2.2 + 0.5
        embers.append((x, y, s, rgb('ffcf8a'), 0.95 * (1 - life)))
    dots(L, embers, mode='add')
    L = glow(L, 7, rgb('ff3b4a'), 0.45)
    return L.outline(rgb('2a0610'), width=1.2, strength=0.45)


# ── 마지막 힘 모으기 ────────────────────────────────
CHARGE = 256


def charge_frame(f):
    ph = f / 8
    c = CHARGE / 2

    def fn(x, y):
        dx, dy = x - c, y - c
        r = math.hypot(dx, dy)
        if r > 126:
            return None
        ang = math.atan2(dy, dx) / math.tau
        # 로그 나선 팔 5개가 안으로 감겨 듦 (ph 가 갈수록 안쪽으로 흐름)
        spiral = (ang * 5 + math.log(max(r, 2)) * 1.6 + ph * 2) % 1.0
        arm = max(0.0, 1 - abs(spiral - 0.5) * 2) ** 3
        tex = N.wrap_fbm((ang + ph * 0.5) % 1.0, r * 0.03 + ph * 2, freq=6, octaves=3)
        fade = smooth(126, 60, r) * smooth(10, 30, r)
        a = arm * fade * (0.5 + 0.6 * tex)
        if a < 0.01:
            return None
        return ramp(WIND, 0.45 + 0.55 * arm), clamp(a)

    L = paint(CHARGE, CHARGE, fn, ss=2)
    rnd = random.Random(5)
    for k in range(34):                                         # 빨려 드는 빛 알갱이 (꼬리)
        a0 = rnd.random() * math.tau
        life = (rnd.random() + ph) % 1.0
        r = 120 * (1 - life) ** 1.3 + 8
        x, y = c + math.cos(a0) * r, c + math.sin(a0) * r
        tail = 10 + 18 * (1 - life)
        streak(L, c + math.cos(a0) * (r + tail), c + math.sin(a0) * (r + tail), x, y, 2.2, PINK, 0.8, mode='add')
    pulse = 0.5 + 0.5 * math.sin(ph * math.tau)
    core = Layer(CHARGE, CHARGE)                               # 가운데 빛 덩어리 + 4갈래 빛
    for y in range(CHARGE):
        for x in range(CHARGE):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            r = math.hypot(dx, dy)
            k = math.exp(-(r / (16 + 6 * pulse)) ** 2)
            cross = math.exp(-abs(dx) / 2.2) * math.exp(-abs(dy) / (40 + 20 * pulse)) + \
                math.exp(-abs(dy) / 2.2) * math.exp(-abs(dx) / (40 + 20 * pulse))
            halo = math.exp(-(r / 48) ** 2) * 0.35
            if k + cross + halo > 0.01:
                core.add(y * CHARGE + x, mix(PINK, WHITE, k), clamp(k + cross * 0.6 + halo))
    L.composite(core, mode='add')
    return glow(L, 6, MAGENTA, 0.35)


# ── 맵 전체 폭발 ────────────────────────────────────
BURST = 512


def burst_frame(f):
    t = f / 7
    ease = 1 - (1 - t) ** 3
    c = BURST / 2
    ring = 20 + 226 * ease
    thick = 46 * (1 - t) ** 0.8 + 8
    fade = 1 - smooth(0.5, 1.0, t)

    def fn(x, y):
        dx, dy = x - c, y - c
        r = math.hypot(dx, dy)
        if r > 255:
            return None
        ang = (math.atan2(dy, dx) / math.tau) % 1.0
        tex = N.wrap_fbm(ang, r * 0.02 + t * 2, freq=12, octaves=3)
        out_col, out_a = None, 0.0
        if r < ring:                                          # 안: 하얀 섬광이 차 있다가 빠짐 + 가는 바람 줄기
            k = r / max(ring, 1)
            inner = (1 - t) ** 2.2 * (0.25 + 0.75 * (1 - k) ** 1.5)
            pick = N.wrap_fbm(ang, 5.0, freq=24, octaves=2)                 # 줄기마다 세기 · 길이가 다름
            start = 0.25 + 0.55 * N2.wrap_fbm(ang, 9.0, freq=24, octaves=2)
            ray = max(0.0, math.cos(ang * 48 * math.tau)) ** 6 * smooth(0.45, 0.7, pick)
            ray *= smooth(start, start + 0.25, k) * (1 - t) ** 1.2
            out_col, out_a = mix(PALE, WHITE, 1 - k), clamp(inner * 0.9 + ray * 0.8)
        d = (r - ring) / thick
        if -1.2 < d < 1.0:                                    # 충격파 고리: 바깥이 날카롭고 안쪽은 끌림
            edge = (1 - smooth(0.0, 1.0, d)) if d > 0 else math.exp(-(d / 0.6) ** 2)
            edge *= 0.5 + 0.7 * smooth(0.25, 0.75, tex)          # 고리의 난류 (뭉침 · 찢어짐)
            col = mix(WHITE, MAGENTA, clamp(abs(d) * 0.9 + (1 - tex) * 0.3))
            if out_col is None or edge > out_a:
                out_col, out_a = col, max(out_a, edge)
        if out_col is None or out_a < 0.01:
            return None
        return out_col, out_a * fade

    L = paint(BURST, BURST, fn, ss=1)
    rnd = random.Random(f + 40)
    pts = []
    for k in range(60):                                       # 고리에 실려 날아가는 꽃잎 · 빛 조각
        a = rnd.random() * math.tau
        r = ring + rnd.uniform(-thick, thick * 0.3)
        pts.append((c + math.cos(a) * r, c + math.sin(a) * r, rnd.uniform(1.5, 4) * (1 - t * 0.5),
                    PALE if k % 2 else PINK, 0.9 * fade))
    dots(L, pts)
    return glow(L, 10, MAGENTA, 0.5 * fade)


# ── 즉사 칼날 예고선 ────────────────────────────────
WARN_W, WARN_H = 256, 40


def warn_frame(f):
    ph = f / 4
    mid = WARN_H / 2
    pulse = 0.5 + 0.5 * math.sin(ph * math.tau)

    def fn(x, y):
        d = abs(y - mid)
        flow = 0.5 + 0.5 * math.sin((x / WARN_W * 3 - ph) * math.tau)    # 바깥으로 흐르는 빛
        start = smooth(0, 14, x)                                         # 실프 쪽에서 시작
        core = math.exp(-(d / (1.3 + 0.7 * pulse)) ** 2)
        inner = math.exp(-(d / 4.5) ** 2) * (0.55 + 0.45 * flow)
        outer = math.exp(-(d / 11) ** 2) * 0.35
        a = clamp(core + inner * 0.8 + outer) * start
        if a < 0.01:
            return None
        col = mix(MAGENTA, WHITE, clamp(core * 1.2 + inner * 0.3))
        return col, a

    L = paint(WARN_W, WARN_H, fn, ss=2)
    return L.outline(OUTLINE, width=1.2, strength=0.35)


def main():
    sheet = Sheet(OUT, 'effects_monster 와 같은 형식. 한 줄 = 이펙트 하나. y는 이미지 맨 위 기준. '
                       'origin = 칸 왼쪽 위 기준 중심 위치(y 아래로). make_effects_boss.py (fxkit) 로 만든 그림.')
    sheet.add('storm', [storm_frame(f) for f in range(STORM_FRAMES)], 12, True, [STORM_W // 2, BASE_Y],
              '폭풍', '실프 즉사 패턴 · 닿으면 2초간 띄워 올림 (무적)')
    sheet.add('rage_aura', [aura_frame(f, 'back') for f in range(8)], 12, True, [AURA // 2, AURA // 2 + 34],
              '광폭화 오라 (뒤)', '실프 광폭화 · 실프 뒤에 그림 (뒤쪽 불꽃 + 바닥 빛). origin = 고리 가운데')
    sheet.add('rage_aura_front', [aura_frame(f, 'front') for f in range(8)], 12, True, [AURA // 2, AURA // 2 + 34],
              '광폭화 오라 (앞)', '실프 광폭화 · 실프 앞에 그림 (앞쪽 불꽃)')
    sheet.add('final_charge', [charge_frame(f) for f in range(8)], 14, True, [CHARGE // 2, CHARGE // 2],
              '마지막 힘 모으기', '실프 즉사 패턴 · "끝이다" 동안 실프 몸에')
    sheet.add('final_burst', [burst_frame(f) for f in range(8)], 12, False, [BURST // 2, BURST // 2],
              '맵 전체 폭발', '실프 즉사 패턴 · 마지막 맵 전체 즉사 (크게 늘려 그림)')
    sheet.add('blade_warn', [warn_frame(f) for f in range(4)], 12, True, [0, WARN_H // 2],
              '즉사 칼날 예고선', '실프 즉사 패턴 · 칼날 방향으로 늘여 그림')
    sheet.save()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:                                       # 확인용: python make_effects_boss.py storm out.png
        fn = {'storm': (storm_frame, 8), 'rage_aura': (lambda f: aura_frame(f, 'back'), 8),
              'rage_aura_front': (lambda f: aura_frame(f, 'front'), 8), 'final_charge': (charge_frame, 8),
              'final_burst': (burst_frame, 8), 'blade_warn': (warn_frame, 4)}[sys.argv[1]]
        frames = [fn[0](f) for f in range(fn[1])]
        preview(frames, sys.argv[2], scale=int(sys.argv[3]) if len(sys.argv) > 3 else 1, cols=4)
    else:
        main()
