"""도형 충돌 판정 (psd 4.5).

정령의 몸은 원 하나다. 공격 범위는 원 · 부채꼴 · 캡슐 세 가지만 쓴다.
pico2d 를 쓰지 않는 순수 계산 모듈이라 단위 테스트로 바로 확인할 수 있다.
각도는 라디안, 오른쪽 0 / 위 π/2 (반시계 방향).
"""
import math


class Circle:
    """원: 투사체, 폭발, 주변 범위 기술. 몸 판정에도 쓴다."""
    def __init__(self, x, y, r):
        self.x, self.y, self.r = x, y, r

    def hits(self, bx, by, br):
        return math.hypot(bx - self.x, by - self.y) <= self.r + br


class Rect:
    """사각형 [left, bottom, right, top]: 노움 대지 균열의 바닥 칸."""
    def __init__(self, left, bottom, right, top):
        self.left, self.bottom, self.right, self.top = left, bottom, right, top

    def hits(self, bx, by, br):
        cx = min(max(bx, self.left), self.right)
        cy = min(max(by, self.bottom), self.top)
        return math.hypot(bx - cx, by - cy) <= br


class Sector:
    """부채꼴: 근접 기술. (x, y)에서 angle 방향으로 반지름 r, 전체 각도 width."""
    def __init__(self, x, y, r, angle, width):
        self.x, self.y, self.r = x, y, r
        self.angle, self.width = angle, width

    def hits(self, bx, by, br):
        d = math.hypot(bx - self.x, by - self.y)
        if d > self.r + br:
            return False
        if d <= br:                    # 몸이 부채꼴 꼭짓점을 덮고 있으면 방향과 상관없이 맞음
            return True
        return angle_diff(math.atan2(by - self.y, bx - self.x), self.angle) <= self.width / 2


class Capsule:
    """캡슐(굵은 직선): 빔, 돌진. 선분 (x1, y1)-(x2, y2), 굵기(반지름) r."""
    def __init__(self, x1, y1, x2, y2, r):
        self.x1, self.y1, self.x2, self.y2, self.r = x1, y1, x2, y2, r

    @classmethod
    def from_origin(cls, x, y, angle, length, r):
        """시전자 위치에서 angle 방향으로 length 만큼 뻗는 캡슐."""
        return cls(x, y, x + math.cos(angle) * length, y + math.sin(angle) * length, r)

    def hits(self, bx, by, br):
        return point_segment_distance(bx, by, self.x1, self.y1, self.x2, self.y2) <= self.r + br


def angle_diff(a, b):
    """두 각도 차이의 절댓값 (0 ~ π)."""
    d = (a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def point_segment_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def separate(a, b, b_fixed=False):
    """두 몸(원)이 겹치면 반씩 밀어낸다. b_fixed 면 b 는 그대로 두고 a 만 밀어낸다.
    a, b 는 x, y, radius 속성을 가진 객체."""
    dx, dy = b.x - a.x, b.y - a.y
    d = math.hypot(dx, dy)
    overlap = a.radius + b.radius - d
    if overlap <= 0:
        return
    if d == 0:
        dx, dy, d = 1.0, 0.0, 1.0
    share = 1.0 if b_fixed else 0.5
    push_x, push_y = dx / d * overlap * share, dy / d * overlap * share
    a.x, a.y = a.x - push_x, a.y - push_y
    if not b_fixed:
        b.x, b.y = b.x + push_x, b.y + push_y
