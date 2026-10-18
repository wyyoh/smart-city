import math


def binder_content_pct(oil_stone_pct: float) -> float:
    if not math.isfinite(oil_stone_pct) or oil_stone_pct < 0:
        raise ValueError('油石比必须为非负有限数')
    return 100 * oil_stone_pct / (100 + oil_stone_pct)


def mineral_blend(fractions: list[float], curves: list[list[float]], *, mass_basis: str):
    if mass_basis != 'mineral_mass':
        raise ValueError('仅对已确认的矿料质量基准计算合成级配')
    if not fractions or len(fractions) != len(curves) or any(not math.isfinite(v) or v < 0 for v in fractions):
        raise ValueError('各档比例及曲线必须完整且非负')
    if abs(sum(fractions) - 1) > 1e-6:
        raise ValueError('各档矿料质量比例之和必须为1')
    width = len(curves[0])
    if width == 0 or any(len(c) != width or any(not math.isfinite(v) or not 0 <= v <= 100 for v in c) for c in curves):
        raise ValueError('筛分曲线维度或通过率无效')
    if any(any(c[i] < c[i+1] for i in range(width-1)) for c in curves):
        raise ValueError('筛孔按由大到小排列时，通过率应单调不增')
    return [sum(f*c[k] for f,c in zip(fractions,curves)) for k in range(width)]

