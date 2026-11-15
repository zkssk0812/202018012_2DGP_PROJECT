"""주인공 모아.

상태는 transitions 의 Machine 으로 관리한다.
    idle ──walk──▶ move
    move ──stop──▶ idle
x, y 는 몸 원의 중심(맵 좌표)이다.
"""
import math

from sdl2 import SDL_KEYDOWN, SDL_KEYUP, SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN
from transitions import Machine

from config import MOA_SPEED, MOA_BODY_RADIUS, MOA_SPRITE_OFFSET_Y
from sprite import SheetSprite

# 방향키 → (dx, dy, 그림 방향)
DIR_KEYS = {
    SDLK_LEFT: (-1, 0, 'left'),
    SDLK_RIGHT: (1, 0, 'right'),
    SDLK_UP: (0, 1, 'up'),
    SDLK_DOWN: (0, -1, 'down'),
}


class Moa:
    states = ['idle', 'move']

    def __init__(self, x, y, battle_map):
        self.x, self.y = x, y
        self.radius = MOA_BODY_RADIUS
        self.battle_map = battle_map
        self.sprite = SheetSprite('sprite_sheets', 'moa_sheet')

        self.held = []                 # 누르고 있는 방향키 (누른 순서)
        self.face = 'down'             # 그림 방향 (4방향)
        self.dir_x, self.dir_y = 0.0, -1.0   # 바라보는 방향 (8방향, 단위 벡터) — 기술이 나가는 방향

        self.machine = Machine(model=self, states=Moa.states, initial='idle',
                               ignore_invalid_triggers=True)
        self.machine.add_transition('walk', 'idle', 'move')
        self.machine.add_transition('stop', 'move', 'idle')
        self.on_enter_idle()

    # ── 입력 ────────────────────────────────────────
    def handle_event(self, e):
        if e.type == SDL_KEYDOWN and e.key in DIR_KEYS:
            if e.key not in self.held:
                self.held.append(e.key)
        elif e.type == SDL_KEYUP and e.key in DIR_KEYS:
            if e.key in self.held:
                self.held.remove(e.key)

    def input_vector(self):
        """누른 방향키를 합친 이동 방향 (단위 벡터). 안 누르면 (0, 0)."""
        dx = sum(DIR_KEYS[k][0] for k in self.held)
        dy = sum(DIR_KEYS[k][1] for k in self.held)
        n = math.hypot(dx, dy)
        return (dx / n, dy / n) if n else (0.0, 0.0)

    def update_facing(self, vx, vy):
        if vx or vy:
            self.dir_x, self.dir_y = vx, vy
        if self.held:                      # 그림은 마지막에 누른 방향을 본다
            self.face = DIR_KEYS[self.held[-1]][2]

    # ── 상태 진입 ────────────────────────────────────
    def on_enter_idle(self):
        self.sprite.play('idle', self.face)

    def on_enter_move(self):
        self.sprite.play('move', self.face)

    # ── 매 프레임 ────────────────────────────────────
    def update(self, dt):
        getattr(self, f'update_{self.state}')(dt)
        self.sprite.update(dt)

    def update_idle(self, dt):
        vx, vy = self.input_vector()
        if vx or vy:
            self.walk()

    def update_move(self, dt):
        vx, vy = self.input_vector()
        if not (vx or vy):
            self.stop()
            return
        self.update_facing(vx, vy)
        self.sprite.play('move', self.face)
        self.move_by(vx * MOA_SPEED * dt, vy * MOA_SPEED * dt)

    def move_by(self, dx, dy):
        self.x, self.y = self.battle_map.clamp(self.x + dx, self.y + dy, self.radius)

    # ── 그리기 ──────────────────────────────────────
    def draw(self, camera):
        sx, sy = camera.to_screen(self.x, self.y)
        self.sprite.draw(sx, sy + MOA_SPRITE_OFFSET_Y)
