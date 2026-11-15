"""전투 모드: 전투 맵 위에서 1대1 전투를 한다."""
from pico2d import get_events
from sdl2 import SDL_QUIT, SDL_KEYDOWN, SDLK_ESCAPE

import game_framework
from battle_map import BattleMap
from camera import Camera
from moa import Moa

MAP_NAME = 'battle_forest1'

battle_map = None
camera = None
moa = None


def init():
    global battle_map, camera, moa
    battle_map = BattleMap(MAP_NAME)
    camera = Camera(battle_map.w, battle_map.h)
    moa = Moa(*battle_map.player_start, battle_map)
    camera.follow(moa.x, moa.y)


def finish():
    pass


def handle_events():
    for e in get_events():
        if e.type == SDL_QUIT:
            game_framework.quit()
        elif e.type == SDL_KEYDOWN and e.key == SDLK_ESCAPE:   # 임시: 일시정지 화면이 생기기 전까지는 종료
            game_framework.quit()
        else:
            moa.handle_event(e)


def update(dt):
    moa.update(dt)
    camera.follow(moa.x, moa.y)


def draw():
    battle_map.draw_background(camera)
    moa.draw(camera)
    battle_map.draw_foreground(camera)


def debug_state():
    """테스트용: 현재 상태를 짧게 돌려준다."""
    return f'moa {moa.state} ({moa.x:.0f},{moa.y:.0f}) face={moa.face}'
