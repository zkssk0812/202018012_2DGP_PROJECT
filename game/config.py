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
MOA_MAX_LEVEL = 15

# ── 경험치 (임시값, psd 에 수치가 없어 정함) ──
# 다음 레벨까지 필요한 경험치 = EXP_BASE + EXP_PER_LEVEL × 지금 레벨
# 정령을 쓰러뜨리면 얻는 경험치 = EXP_REWARD_BASE + EXP_REWARD_PER_LEVEL × 정령 레벨
EXP_BASE = 20
EXP_PER_LEVEL = 10
EXP_REWARD_BASE = 10
EXP_REWARD_PER_LEVEL = 5

# ── 기술 칸 ── psd 4.2: Q·W 시작, E Lv10, R Lv15
SLOT_KEYS = ('Q', 'W', 'E', 'R')
SLOT_UNLOCK_LEVELS = (1, 1, 10, 15)
MOA_START_SKILLS = ('scratch', None, None, None)   # 임시: 오프닝이 생기기 전까지 Q 에 할퀴기
MOA_SKILL_WINDUP = 0.1        # 모아 기술: 누르고 판정이 켜지기까지 (적은 더 길게 예고)

# ── 전투 맵과 상대 ──
BATTLE_MAP = 'battle_tutorial'           # 오프닝 빈터 전투 맵
DUMMY_SHEET = 'tori_corrupt_sheet'       # 타락한 토리 (가시몽 색 변경 개체, psd 6.2)

# ── 훈련용 상대 (임시 적, 배틀 AI 로 교체 예정) ── 토리는 가시몽 능력치·그림 크기 그대로
DUMMY_BASE_STATS = (40, 10, 8)
DUMMY_LEVEL = 2               # 토리 Lv2 (psd 6.1)
DUMMY_BODY_RADIUS = 30        # 몸통 + 팔 대부분 + 잎 아래쪽
DUMMY_SPEED = 160
DUMMY_SPRITE_OFFSET_Y = 5     # 원 중심이 그림 중심보다 5px 아래
DUMMY_ATTACK_RANGE = 140      # 몸 중심 사이 거리가 이보다 가까우면 할퀴기 (할퀴기 닿는 거리 120 + 모아 몸 28 안쪽)
DUMMY_ATTACK_GAP = 0.6        # 기술 사이 짧은 틈

# 적이 맞았을 때: 짧게 밀려나고 하던 공격(예고 중)은 취소. 연속 주먹이 다 맞도록 적은 무적 없음
ENEMY_HURT_TIME = 0.15
ENEMY_KNOCKBACK_SPEED = 300
DUMMY_SKILL_WINDUP = 0.3      # 적 기술: 동작 시작 → 판정 (보고 피할 수 있게)
DUMMY_REVIVE_TIME = 3.0       # 임시: F 흡수가 생기기 전까지 기절하면 이 시간 뒤 다시 일어남

# ── 기술 이펙트 ──
FX_SKIP = 0.06                # 판정이 켜질 때 이펙트의 흐린 첫 프레임을 건너뜀
