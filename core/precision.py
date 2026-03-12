"""
[H-07] 精度安全工具模块 — 解决浮点漂移问题

所有金额列在 SQLite 中使用 REAL (float64) 存储，浮点运算会导致精度漂移。
本模块提供 Decimal 包装函数，用于关键金额计算（余额、费率、兑换等），
确保中间结果不丢失精度，最终结果按照 8 位小数（satoshi 级）四舍五入。

使用方式:
    from core.precision import safe_add, safe_sub, safe_mul, safe_div, to_display

    fee = safe_mul(amount, rate)           # Decimal 精确乘法
    balance = safe_sub(old_balance, fee)   # Decimal 精确减法
    display = to_display(balance)          # 转回 float (8位小数)
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union

# 精度常量
PRECISION_DIGITS = 8                        # 与 1 satoshi = 0.00000001 BTC 对齐
QUANTIZE_EXP = Decimal(f"1E-{PRECISION_DIGITS}")   # 0.00000001

Number = Union[int, float, str, Decimal]


def _to_decimal(v: Number) -> Decimal:
    """安全转换为 Decimal，float 先转 str 避免二进制噪声"""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, float):
        return Decimal(str(v))
    return Decimal(v)


def _quantize(d: Decimal) -> Decimal:
    """四舍五入到 PRECISION_DIGITS 位"""
    return d.quantize(QUANTIZE_EXP, rounding=ROUND_HALF_UP)


# ==================== 基础运算 ====================

def safe_add(a: Number, b: Number) -> Decimal:
    """精确加法"""
    return _quantize(_to_decimal(a) + _to_decimal(b))


def safe_sub(a: Number, b: Number) -> Decimal:
    """精确减法"""
    return _quantize(_to_decimal(a) - _to_decimal(b))


def safe_mul(a: Number, b: Number) -> Decimal:
    """精确乘法（常用于 amount × rate）"""
    return _quantize(_to_decimal(a) * _to_decimal(b))


def safe_div(a: Number, b: Number) -> Decimal:
    """精确除法（除数不可为 0）"""
    bd = _to_decimal(b)
    if bd == 0:
        raise ZeroDivisionError("safe_div: divisor is zero")
    return _quantize(_to_decimal(a) / bd)


def safe_sum(values) -> Decimal:
    """精确求和（接受可迭代对象）"""
    total = Decimal("0")
    for v in values:
        total += _to_decimal(v)
    return _quantize(total)


# ==================== 转换 ====================

def to_display(v: Number) -> float:
    """
    Decimal → float，用于 JSON 序列化 / SQLite 写入。
    先量化再转 float，确保结果在 8 位精度范围内。
    """
    return float(_quantize(_to_decimal(v)))


def to_satoshi(v: Number) -> int:
    """
    金额 → satoshi 整数（× 10^8）。
    可用于精确整数比较，避免浮点 == 判断。
    """
    d = _to_decimal(v)
    return int((d * Decimal(10 ** PRECISION_DIGITS)).to_integral_value())


def from_satoshi(sat: int) -> Decimal:
    """satoshi 整数 → Decimal 金额"""
    return _quantize(Decimal(sat) / Decimal(10 ** PRECISION_DIGITS))


# ==================== 校验 ====================

def amounts_equal(a: Number, b: Number) -> bool:
    """判断两个金额是否在精度范围内相等"""
    return _quantize(_to_decimal(a)) == _quantize(_to_decimal(b))


def is_valid_amount(v) -> bool:
    """检查是否为有效正数金额"""
    try:
        d = _to_decimal(v)
        return d > 0 and d.is_finite()
    except (InvalidOperation, TypeError, ValueError):
        return False


# ==================== 费率计算便捷函数 ====================

def apply_fee(amount: Number, fee_rate: Number) -> tuple:
    """
    扣除手续费，返回 (net_amount, fee_amount)。
    fee_rate 通常是 0.01 (1%) 这类小数。
    """
    amt = _to_decimal(amount)
    rate = _to_decimal(fee_rate)
    fee = _quantize(amt * rate)
    net = _quantize(amt - fee)
    return net, fee
