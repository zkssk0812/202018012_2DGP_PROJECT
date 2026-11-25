"""이펙트 그림을 그리는 작은 도구 모음 (외부 라이브러리 없이 순수 파이썬).

    Layer        RGBA 그림 한 장 (미리 곱한 알파, 0~1 실수). 덮어 그리기(over) · 더해 그리기(add, 빛) ·
                 흐리기(blur, 빛 번짐) · 줄이기(downsample, 안티앨리어싱)
    paint()      칸 하나를 픽셀 함수로 칠한다. ss 배로 크게 그려 줄여서 가장자리를 매끄럽게 한다
    Noise        이어지는 값 노이즈 + fBm (구름 · 연기 · 돌 질감)
    voronoi()    보로노이 (가장 가까운 점 · 두 번째 점 거리) → 갈라진 땅 · 돌 면
    Sheet        여러 이펙트를 한 장의 시트 + json 으로 저장
"""
import json
import math
import random
import struct
import zlib


# ── 수학 ────────────────────────────────────────────
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)


def mix(c1, c2, t):
    t = clamp(t)
    return (c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t)


def ramp(stops, t):
    """색 띠: stops = [(위치, (r,g,b)), ...] 0~1."""
    t = clamp(t)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            return mix(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0)
    return stops[-1][1]


def rgb(hexstr):
    h = hexstr.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ── 노이즈 ──────────────────────────────────────────
class Noise:
    def __init__(self, seed=0, period=256):
        rnd = random.Random(seed)
        self.p = period
        self.v = [rnd.random() for _ in range(period * period)]

    def value(self, x, y):
        """0~1, period 마다 이어짐."""
        p = self.p
        xi, yi = math.floor(x), math.floor(y)
        fx, fy = x - xi, y - yi
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x0, y0 = xi % p, yi % p
        x1, y1 = (x0 + 1) % p, (y0 + 1) % p
        v = self.v
        a = v[y0 * p + x0] + (v[y0 * p + x1] - v[y0 * p + x0]) * fx
        b = v[y1 * p + x0] + (v[y1 * p + x1] - v[y1 * p + x0]) * fx
        return a + (b - a) * fy

    def pvalue(self, x, y, px):
        """x 방향으로 px 마다 이어지는 값 노이즈 (빙글 도는 무늬 · 반복 애니메이션용)."""
        p = self.p
        xi, yi = math.floor(x), math.floor(y)
        fx, fy = x - xi, y - yi
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        x0, y0 = xi % px, yi % p
        x1, y1 = (x0 + 1) % px, (y0 + 1) % p
        v = self.v
        a = v[y0 * p + x0] + (v[y0 * p + x1] - v[y0 * p + x0]) * fx
        b = v[y1 * p + x0] + (v[y1 * p + x1] - v[y1 * p + x0]) * fx
        return a + (b - a) * fy

    def wrap_fbm(self, s, y, freq=4, octaves=4):
        """s(0~1)가 한 바퀴 돌면 이어지는 fBm."""
        total, amp, norm = 0.0, 1.0, 0.0
        for k in range(octaves):
            f = freq * (2 ** k)
            total += self.pvalue(s * f, y * (2 ** k) + k * 13.7, f) * amp
            norm += amp
            amp *= 0.5
        return total / norm

    def fbm(self, x, y, octaves=4, lac=2.0, gain=0.5):
        total, amp, norm = 0.0, 1.0, 0.0
        for _ in range(octaves):
            total += self.value(x, y) * amp
            norm += amp
            x, y, amp = x * lac + 17.3, y * lac + 9.1, amp * gain
        return total / norm


def voronoi(points, x, y):
    """(가장 가까운 거리, 두 번째 거리, 가장 가까운 점 번호)."""
    d1 = d2 = 1e9
    idx = -1
    for i, (px, py) in enumerate(points):
        d = (px - x) ** 2 + (py - y) ** 2
        if d < d1:
            d2, d1, idx = d1, d, i
        elif d < d2:
            d2 = d
    return math.sqrt(d1), math.sqrt(d2), idx


# ── 그림 한 장 ──────────────────────────────────────
class Layer:
    def __init__(self, w, h):
        self.w, self.h = w, h
        n = w * h
        self.r, self.g, self.b, self.a = [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n

    def over(self, i, color, a):
        """미리 곱한 알파로 위에 덮어 그리기."""
        if a <= 0:
            return
        if a > 1:
            a = 1.0
        k = 1 - a
        self.r[i] = color[0] * a + self.r[i] * k
        self.g[i] = color[1] * a + self.g[i] * k
        self.b[i] = color[2] * a + self.b[i] * k
        self.a[i] = a + self.a[i] * k

    def add(self, i, color, a):
        """빛: 색을 더한다 (알파도 늘어남)."""
        if a <= 0:
            return
        self.r[i] = min(1.0, self.r[i] + color[0] * a)
        self.g[i] = min(1.0, self.g[i] + color[1] * a)
        self.b[i] = min(1.0, self.b[i] + color[2] * a)
        self.a[i] = min(1.0, self.a[i] + a * max(color))

    def blur(self, radius, passes=3):
        """상자 흐리기 여러 번 = 가우시안 비슷 (빛 번짐)."""
        if radius < 1:
            return self
        out = Layer(self.w, self.h)
        chans = [self.r[:], self.g[:], self.b[:], self.a[:]]
        for _ in range(passes):
            chans = [_box(c, self.w, self.h, radius) for c in chans]
        out.r, out.g, out.b, out.a = chans
        return out

    def composite(self, other, mode='over', strength=1.0, ox=0, oy=0):
        """다른 그림을 이 그림 위에 (ox, oy) 에 합친다."""
        for y in range(other.h):
            ty = y + oy
            if not 0 <= ty < self.h:
                continue
            for x in range(other.w):
                tx = x + ox
                if not 0 <= tx < self.w:
                    continue
                j = y * other.w + x
                a = other.a[j] * strength
                if a <= 0:
                    continue
                i = ty * self.w + tx
                if mode == 'add':
                    self.r[i] = min(1.0, self.r[i] + other.r[j] * strength)
                    self.g[i] = min(1.0, self.g[i] + other.g[j] * strength)
                    self.b[i] = min(1.0, self.b[i] + other.b[j] * strength)
                    self.a[i] = min(1.0, self.a[i] + a)
                else:
                    k = 1 - a
                    self.r[i] = other.r[j] * strength + self.r[i] * k
                    self.g[i] = other.g[j] * strength + self.g[i] * k
                    self.b[i] = other.b[j] * strength + self.b[i] * k
                    self.a[i] = a + self.a[i] * k

    def downsample(self, f):
        if f == 1:
            return self
        w, h = self.w // f, self.h // f
        out = Layer(w, h)
        inv = 1 / (f * f)
        for y in range(h):
            for x in range(w):
                r = g = b = a = 0.0
                for yy in range(y * f, y * f + f):
                    base = yy * self.w + x * f
                    for i in range(base, base + f):
                        r += self.r[i]
                        g += self.g[i]
                        b += self.b[i]
                        a += self.a[i]
                j = y * w + x
                out.r[j], out.g[j], out.b[j], out.a[j] = r * inv, g * inv, b * inv, a * inv
        return out

    def outline(self, color, width=2.0, strength=0.9):
        """알파 바깥쪽에 어두운 테두리 (기존 이펙트들의 진한 보라 테두리)."""
        halo = Layer(self.w, self.h)
        halo.a = self.a[:]
        halo = halo.blur(width, passes=2)
        out = Layer(self.w, self.h)
        for i in range(self.w * self.h):
            ha = clamp(halo.a[i] * 3.0) * strength
            out.r[i], out.g[i], out.b[i], out.a[i] = color[0] * ha, color[1] * ha, color[2] * ha, ha
        out.composite(self)
        return out


def _box(c, w, h, r):
    r = int(r)
    tmp = [0.0] * (w * h)
    for y in range(h):                                   # 가로
        row = y * w
        acc = sum(c[row + clamp_i(k, w)] for k in range(-r, r + 1))
        inv = 1 / (2 * r + 1)
        for x in range(w):
            tmp[row + x] = acc * inv
            acc += c[row + clamp_i(x + r + 1, w)] - c[row + clamp_i(x - r, w)]
    out = [0.0] * (w * h)
    for x in range(w):                                   # 세로
        acc = sum(tmp[clamp_i(k, h) * w + x] for k in range(-r, r + 1))
        inv = 1 / (2 * r + 1)
        for y in range(h):
            out[y * w + x] = acc * inv
            acc += tmp[clamp_i(y + r + 1, h) * w + x] - tmp[clamp_i(y - r, h) * w + x]
    return out


def clamp_i(i, n):
    return 0 if i < 0 else n - 1 if i >= n else i


def paint(w, h, fn, ss=2, layer=None):
    """fn(x, y) → (color, alpha) 또는 None. 좌표는 칸 픽셀 단위(실수). ss 배로 그려 줄인다."""
    big = Layer(w * ss, h * ss)
    inv = 1 / ss
    for y in range(h * ss):
        fy = (y + 0.5) * inv
        row = y * w * ss
        for x in range(w * ss):
            res = fn((x + 0.5) * inv, fy)
            if res:
                big.over(row + x, res[0], res[1])
    small = big.downsample(ss)
    if layer is not None:
        layer.composite(small)
        return layer
    return small


def dots(layer, pts, mode='over'):
    """작은 원들: pts = [(x, y, 반지름, color, alpha)]. 가장자리 부드럽게."""
    for x0, y0, r, color, a in pts:
        for y in range(int(y0 - r - 2), int(y0 + r + 3)):
            if not 0 <= y < layer.h:
                continue
            for x in range(int(x0 - r - 2), int(x0 + r + 3)):
                if not 0 <= x < layer.w:
                    continue
                d = math.hypot(x + 0.5 - x0, y + 0.5 - y0)
                k = a * (1 - smooth(r - 0.7, r + 0.7, d))
                if k > 0:
                    if mode == 'add':
                        layer.add(y * layer.w + x, color, k)
                    else:
                        layer.over(y * layer.w + x, color, k)


def streak(layer, x1, y1, x2, y2, width, color, a, mode='over', taper=True):
    """선 (끝으로 갈수록 가늘고 옅게)."""
    n = int(max(abs(x2 - x1), abs(y2 - y1)) * 1.5) + 1
    pts = []
    for k in range(n + 1):
        t = k / n
        f = (1 - t) if taper else 1.0
        pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, max(0.4, width / 2 * (0.4 + 0.6 * f)), color, a * (0.3 + 0.7 * f)))
    dots(layer, pts, mode)


# ── 시트 저장 ───────────────────────────────────────
class Sheet:
    def __init__(self, name, note):
        self.name, self.note = name, note
        self.rows = []          # (이름, [Layer...], fps, loop, origin, label, use)

    def add(self, name, frames, fps, loop, origin, label, use):
        self.rows.append((name, frames, fps, loop, origin, label, use))
        print(' ', name, len(frames), 'x', frames[0].w, frames[0].h)

    def save(self):
        sheet_w = max(f[0].w * len(f) for _, f, *_ in self.rows)
        sheet_h = sum(f[0].h for _, f, *_ in self.rows)
        big = Layer(sheet_w, sheet_h)
        meta = {'image': f'{self.name}.png', 'sheet_w': sheet_w, 'sheet_h': sheet_h, 'note': self.note, 'effects': {}}
        y = 0
        for name, frames, fps, loop, origin, label, use in self.rows:
            w, h = frames[0].w, frames[0].h
            for k, f in enumerate(frames):
                big.composite(f, ox=k * w, oy=y)
            meta['effects'][name] = {'x': 0, 'y': y, 'label': label, 'use': use, 'cell_w': w, 'cell_h': h,
                                     'frames': len(frames), 'fps': fps, 'loop': loop, 'origin': origin}
            y += h
        save_png(big, f'{self.name}.png')
        with open(f'{self.name}.json', 'w', encoding='utf-8') as fp:
            json.dump(meta, fp, ensure_ascii=False, indent=2)
        print('saved', f'{self.name}.png', sheet_w, 'x', sheet_h)


def save_png(layer, path):
    """미리 곱한 알파 → 일반 RGBA PNG."""
    raw = bytearray()
    for y in range(layer.h):
        raw.append(0)
        for x in range(layer.w):
            i = y * layer.w + x
            a = layer.a[i]
            if a <= 1e-4:
                raw += b'\x00\x00\x00\x00'
                continue
            inv = 1 / a
            raw += bytes((int(clamp(layer.r[i] * inv) * 255 + 0.5), int(clamp(layer.g[i] * inv) * 255 + 0.5),
                          int(clamp(layer.b[i] * inv) * 255 + 0.5), int(clamp(a) * 255 + 0.5)))

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', layer.w, layer.h, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def preview(layers, path, bg=(0.10, 0.14, 0.14), scale=1, cols=None):
    """확인용: 여러 칸을 어두운 바탕 위에 나란히 (scale 배로 크게)."""
    cols = cols or len(layers)
    w, h = layers[0].w, layers[0].h
    rows = (len(layers) + cols - 1) // cols
    out = Layer(w * cols * scale, h * rows * scale)
    for i in range(out.w * out.h):
        out.r[i], out.g[i], out.b[i], out.a[i] = bg[0], bg[1], bg[2], 1.0
    for k, L in enumerate(layers):
        ox, oy = (k % cols) * w * scale, (k // cols) * h * scale
        for y in range(h * scale):
            for x in range(w * scale):
                j = (y // scale) * w + x // scale
                a = L.a[j]
                if a <= 0:
                    continue
                i = (oy + y) * out.w + ox + x
                kk = 1 - a
                out.r[i] = L.r[j] + out.r[i] * kk
                out.g[i] = L.g[j] + out.g[i] * kk
                out.b[i] = L.b[j] + out.b[i] * kk
    save_png(out, path)
