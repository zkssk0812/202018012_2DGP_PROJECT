"""전투 모드: 전투 맵 위에서 1대1 전투를 한다.

지금은 맵과 카메라만 있다.
"""
from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE

import game_framework
from battle_map import BattleMap
from camera import Camera

MAP_NAME = 'battle_forest1'

battle_map = None
camera = None


def init():
    global battle_map, camera
    battle_map = BattleMap(MAP_NAME)
    camera = Camera(battle_map.w, battle_map.h)
    camera.follow(*battle_map.player_start)


def finish():
    pass


def handle_events():
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE:   # 임시: 일시정지 화면이 생기기 전까지는 종료
            game_framework.quit()


def update(dt):
    pass


def draw():
    battle_map.draw_background(camera)
    battle_map.draw_foreground(camera)
