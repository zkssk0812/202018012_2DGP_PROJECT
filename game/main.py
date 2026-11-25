"""텅 빈 정령 — 실행 진입점.

실행: 프로젝트 폴더에서  python game/main.py
릴리즈 실행 파일은 tools/build_release.py 로 만든다. 릴리즈에서 오류가 나면 실행 파일 옆 error_log.txt 에 남긴다.
"""
import os
import traceback

import pico2d
from pico2d import open_canvas, close_canvas

import game_framework
import battle_mode
import field_mode
from config import SCREEN_W, SCREEN_H, TUTORIAL, FROZEN, ROOT_DIR, GAME_TITLE


def main():
    open_canvas(SCREEN_W, SCREEN_H)
    pico2d.pico2d.SDL_SetWindowTitle(pico2d.pico2d.window, GAME_TITLE.encode('utf-8'))
    game_framework.run(field_mode if TUTORIAL else battle_mode)   # 튜토리얼이면 숲에서 시작
    close_canvas()


if __name__ == '__main__':
    if FROZEN:
        try:
            main()
        except Exception:                                         # 콘솔이 없으니 파일로 남김 (테스트 보고용)
            with open(os.path.join(ROOT_DIR, 'error_log.txt'), 'w', encoding='utf-8') as f:
                f.write(traceback.format_exc())
            raise
    else:
        main()
