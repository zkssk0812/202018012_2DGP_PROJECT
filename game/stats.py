"""능력치와 피해 계산 (psd 4.7)."""
import math


def round_half_up(v):
    return int(math.floor(v + 0.5))


def stat_at(base, level):
    """레벨 1마다 기본값의 10%씩 증가, 반올림."""
    return round_half_up(base * (1 + 0.1 * (level - 1)))


def stats_at(bases, level):
    return tuple(stat_at(b, level) for b in bases)


def exp_to_next(level):
    """지금 레벨에서 다음 레벨까지 필요한 경험치 (임시 공식, config 참고)."""
    from config import EXP_BASE, EXP_PER_LEVEL
    return EXP_BASE + EXP_PER_LEVEL * level


def exp_reward(level):
    """그 레벨의 정령을 쓰러뜨리면 얻는 경험치 (임시 공식, config 참고)."""
    from config import EXP_REWARD_BASE, EXP_REWARD_PER_LEVEL
    return EXP_REWARD_BASE + EXP_REWARD_PER_LEVEL * level


def damage(power, attack, defense):
    """피해 = 위력 × (공격 ÷ 방어) × 0.25. 최소 1."""
    return max(1, round_half_up(power * attack / defense * 0.25))
