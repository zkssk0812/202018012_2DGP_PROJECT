"""전투 맵: 배경·전경 그림과 움직일 수 있는 범위(arena).

맵 정보는 Resource/battle_maps/<이름>.json 에 있다.
그리는 순서: 배경(draw_background) → 캐릭터 → 전경(draw_foreground, 나무 윗부분).
"""
import resources
from config import SCREEN_W, SCREEN_H


class BattleMap:
    def __init__(self, name):
        info = resources.json_data('battle_maps', f'{name}.json')
        self.name = name
        self.w, self.h = info['size']
        self.arena = info['arena']                  # [left, bottom, right, top]
        self.player_start = tuple(info['player_start'])
        self.enemy_start = tuple(info['enemy_start'])
        self.bg = resources.image('battle_maps', info['background'])
        self.fg = resources.image('battle_maps', info['foreground'])

    def move(self, x, y, dx, dy, radius):
        """(x, y) 에서 (dx, dy) 만큼 움직인 자리. 전투 맵은 arena 안으로만 자른다."""
        return self.clamp(x + dx, y + dy, radius)

    def clamp(self, x, y, radius):
        """몸(원)이 arena 밖으로 나가지 않도록 중심 좌표를 잘라 준다."""
        l, b, r, t = self.arena
        return min(max(x, l + radius), r - radius), min(max(y, b + radius), t - radius)

    def _draw_layer(self, image, camera):
        image.clip_draw(int(camera.x), int(camera.y), SCREEN_W, SCREEN_H, SCREEN_W / 2, SCREEN_H / 2)

    def draw_background(self, camera):
        self._draw_layer(self.bg, camera)

    def draw_foreground(self, camera):
        self._draw_layer(self.fg, camera)
