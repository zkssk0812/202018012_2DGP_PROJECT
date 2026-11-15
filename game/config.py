"""게임 전체에서 쓰는 상수.

수치는 docs/psd.md 의 초안 값이다. 플레이테스트하면서 여기 한 곳만 고친다.
단위: 거리 = 맵 픽셀, 시간 = 초, 속도 = 픽셀/초.
"""
import os

# ── 경로 ─────────────────────────────────────────────
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(GAME_DIR)
RESOURCE_DIR = os.path.join(ROOT_DIR, 'Resource')

# ── 화면 ─────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1280, 720
SPRITE_SCALE = 0.5            # 스프라이트 시트는 0.5배로 그린다 (psd 5.3)
MAX_FRAME_TIME = 0.05         # 프레임이 길게 끊겨도 한 번에 이만큼만 진행

# ── 모아 ─────────────────────────────────────────────
MOA_SPEED = 300               # 이동 속도
MOA_BODY_RADIUS = 40          # 몸 원 반지름 (psd 5.3)
MOA_SPRITE_OFFSET_Y = 20      # 몸 중심에서 그림 중심까지 (그림이 몸보다 위로 올라가 보이게)

# ── 회피 (Space) ── psd 4.4: 대시, 0.3초 무적, 쿨다운 1.5초
DODGE_TIME = 0.3              # 대시 시간 = 무적 시간
DODGE_SPEED = 800             # 대시 속도 → 거리 약 240
DODGE_COOLDOWN = 1.5          # 회피를 시작한 순간부터 센다
