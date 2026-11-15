"""대상을 화면 가운데에 두고 따라가는 카메라. 맵 밖은 보여 주지 않는다."""
from config import SCREEN_W, SCREEN_H


class Camera:
    def __init__(self, map_w, map_h):
        self.map_w, self.map_h = map_w, map_h
        self.x = self.y = 0.0          # 화면 왼쪽 아래가 가리키는 맵 좌표

    def follow(self, tx, ty):
        self.x = min(max(tx - SCREEN_W / 2, 0), self.map_w - SCREEN_W)
        self.y = min(max(ty - SCREEN_H / 2, 0), self.map_h - SCREEN_H)

    def follow_smooth(self, tx, ty, dt, speed=6.0):
        """목표 쪽으로 부드럽게 다가간다 (연출이 끝나고 모아에게 돌아올 때)."""
        ox, oy = self.x, self.y
        self.follow(tx, ty)
        k = min(1.0, dt * speed)
        self.x, self.y = ox + (self.x - ox) * k, oy + (self.y - oy) * k

    def to_screen(self, x, y):
        return x - self.x, y - self.y
