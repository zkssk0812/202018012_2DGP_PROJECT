"""검은 기운 (psd 4.1).

적이 기절하면 그 자리에 생긴다. 바닥에 흡수 범위(원)를 그리고, 모아의 몸이 범위에 닿으면 F 로 흡수할 수 있다.
흡수가 시작되면 모아에게 날아가 사라진다.
"""
import math

from pico2d import draw_circle

import resources
from config import ABSORB_RADIUS, ESSENCE_FLOAT_Y, SPRITE_SCALE
from collision import Circle


class Essence:
    def __init__(self, source):
        self.source = source                       # 기절한 적
        self.x, self.y = source.x, source.y
        self.radius = ABSORB_RADIUS
        meta = resources.json_data('sprite_sheets', 'dark_essence.json')
        self.image = resources.image('sprite_sheets', meta['image'])
        self.cw, self.ch, self.frames, self.fps = meta['cell_w'], meta['cell_h'], meta['frames'], meta['fps']
        self.time = 0.0
        self.state = 'waiting'                     # waiting → flying → done
        self.fly_from = self.fly_to = None
        self.fly_time = self.fly_total = 0.0

    def in_range(self, body):
        """모아의 몸 원이 흡수 범위 원에 닿으면 True (psd 4.5 원 판정)."""
        return self.state == 'waiting' and Circle(self.x, self.y, self.radius).hits(body.x, body.y, body.radius)

    def fly_to_target(self, target, duration):
        self.state = 'flying'
        self.fly_from = (self.x, self.y + ESSENCE_FLOAT_Y)
        self.fly_to = target
        self.fly_time, self.fly_total = 0.0, duration

    @property
    def done(self):
        return self.state == 'done'

    def position(self):
        """그림이 그려지는 자리 (기다릴 때는 적 위에 둥실, 날 때는 모아 쪽으로)."""
        if self.state == 'flying':
            t = min(1.0, self.fly_time / self.fly_total)
            t = t * t * (3 - 2 * t)                # 처음과 끝을 부드럽게
            fx, fy = self.fly_from
            return fx + (self.fly_to.x - fx) * t, fy + (self.fly_to.y - fy) * t
        bob = math.sin(self.time * 3) * 6
        return self.x, self.y + ESSENCE_FLOAT_Y + bob

    def update(self, dt):
        self.time += dt
        if self.state == 'flying':
            self.fly_time += dt
            if self.fly_time >= self.fly_total:
                self.state = 'done'

    def draw_ground(self, camera):
        """바닥의 흡수 범위 원 (캐릭터보다 먼저 그린다)."""
        if self.state != 'waiting':
            return
        sx, sy = camera.to_screen(self.x, self.y)
        pulse = int(math.sin(self.time * 4) * 3)
        draw_circle(int(sx), int(sy), self.radius + pulse, 120, 60, 160)
        draw_circle(int(sx), int(sy), self.radius - 1 + pulse, 120, 60, 160)

    def draw(self, camera):
        if self.state == 'done':
            return
        x, y = self.position()
        sx, sy = camera.to_screen(x, y)
        k = int(self.time * self.fps) % self.frames
        scale = SPRITE_SCALE * 0.7
        if self.state == 'flying':                 # 모아에게 다가갈수록 작아짐
            scale *= 1 - 0.6 * min(1.0, self.fly_time / self.fly_total)
        self.image.clip_draw(k * self.cw, 0, self.cw, self.ch, sx, sy, self.cw * scale * 2, self.ch * scale * 2)
