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
MOA_BODY_RADIUS = 28          # 몸 원 반지름 (psd 5.3)
MOA_SPRITE_OFFSET_Y = 20      # 몸 중심에서 그림 중심까지 (그림이 몸보다 위로 올라가 보이게)

# ── 회피 (Space) ── psd 4.4: 대시, 0.3초 무적, 쿨다운 1.5초
DODGE_TIME = 0.3              # 대시 시간 = 무적 시간
DODGE_SPEED = 800             # 대시 속도 → 거리 약 240
DODGE_COOLDOWN = 1.5          # 회피를 시작한 순간부터 센다

# ── 피격 ── psd 4.4: 넉백 + 0.5초 무적
HURT_TIME = 0.2               # 넉백되는 동안 조작 불가
KNOCKBACK_SPEED = 450         # → 거리 약 90
HIT_INVINCIBLE = 0.5
FAINT_RESTART_TIME = 2.0      # 쓰러진 뒤 다시 시작하기까지

# ── 능력치 ── psd 4.7: HP / 공격 / 방어
MOA_BASE_STATS = (45, 12, 10)
MOA_LEVEL = 1

# ── 훈련용 가시몽 (1주차 임시 적, 2주차에 배틀 AI 로 교체) ──
DUMMY_BASE_STATS = (40, 10, 8)
DUMMY_LEVEL = 3
DUMMY_BODY_RADIUS = 24        # 둥근 몸통에 맞춤 (잎·팔은 판정에서 뺌)
DUMMY_SPEED = 160
DUMMY_SPRITE_OFFSET_Y = 10    # 몸통 중심이 그림 중심보다 10px 아래
DUMMY_ATTACK_RANGE = 140      # 몸 중심 사이 거리가 이보다 가까우면 할퀴기 (할퀴기 닿는 거리 120 + 모아 몸 28 안쪽)
DUMMY_ATTACK_GAP = 0.6        # 기술 사이 짧은 틈

# ── 기술: 할퀴기 (psd 5.2, 5.3) ──
SCRATCH_POWER = 40
SCRATCH_RADIUS = 120
SCRATCH_ANGLE = 90            # 도
SCRATCH_COOLDOWN = 1.0
SCRATCH_WINDUP = 0.3          # 공격 동작 시작 → 판정이 생기기까지
SCRATCH_ACTIVE = 0.1          # 판정이 남아 있는 시간
SCRATCH_FX_LEAD = 0.1         # 이펙트를 판정보다 이만큼 먼저 시작
