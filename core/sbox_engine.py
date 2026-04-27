"""
sbox_engine.py - S-Box 密码学评分引擎与挖矿核心

实现 AES 风格 8x8 S-Box 的生成、优化和密码学评估:
  - 非线性度 (Nonlinearity, Walsh-Hadamard Transform)
  - 差分均匀性 (Differential Uniformity)
  - 雪崩效应 (Avalanche Effect)
  - 综合评分系统 (加权可调)
  - 遗传算法优化
  - S-Box 序列化与反序列化

安全设计:
  - 使用 secrets 模块生成密码学安全随机数
  - 所有 S-Box 必须为双射 (bijective) 置换
  - 评分权重可由治理投票动态调整 → 抗 ASIC 硬编码
  - 评分计算为确定性纯函数，验证节点可毫秒级复现
"""

import hashlib
import os
import secrets
import time
import json
import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any
from copy import deepcopy


# ============== 常量 ==============

SBOX_SIZE = 256          # 8-bit S-Box: 256 个元素
SBOX_BITS = 8            # 8-bit 置换
SBOX_ROWS = 16           # 16x16 矩阵显示
SBOX_COLS = 16

# 默认评分权重 (可动态调整，w1+w2+w3=1)
DEFAULT_SCORE_WEIGHTS = {
    "nonlinearity": 0.40,       # w1: 非线性度权重
    "diff_uniformity": 0.35,    # w2: 差分均匀性权重
    "avalanche": 0.25,          # w3: 雪崩效应权重
}

# AES S-Box 参考值 (用于归一化)
AES_NONLINEARITY = 112        # AES S-Box 非线性度
AES_DIFF_UNIFORMITY = 4       # AES 差分均匀性
AES_AVALANCHE = 4.0           # AES 理想雪崩 (n/2 = 4.0)

# 评估上限/下限 (归一化)
MAX_NONLINEARITY = 120        # 理论最大 2^(n-1) - 2^(n/2-1) = 120
MIN_NONLINEARITY = 0
MAX_DIFF_UNIFORMITY = 256     # 最差情况
MIN_DIFF_UNIFORMITY = 2       # bent 函数理论极限
IDEAL_AVALANCHE = SBOX_BITS / 2.0  # 4.0


# ============== 可选加速器 (C 扩展等) ==============

_SBOX_ACCEL_MAX_WALSH = None
if os.getenv("POUW_SBOX_DISABLE_ACCEL", "false").strip().lower() != "true":
    try:
        from core import _sbox_accel  # type: ignore
        _SBOX_ACCEL_MAX_WALSH = getattr(_sbox_accel, "max_walsh_spectrum", None)
    except Exception:
        _SBOX_ACCEL_MAX_WALSH = None


# ============== Walsh-Hadamard 变换工具 ==============

def _dot_product_gf2(a: int, b: int) -> int:
    """计算 GF(2) 上 a 和 b 的内积 (模2点乘)。"""
    return bin(a & b).count('1') % 2


def _walsh_hadamard_spectrum(sbox: List[int]) -> List[List[int]]:
    """计算 S-Box 的 Walsh-Hadamard 频谱矩阵。

    W_f(a, b) = Σ_{x=0}^{2^n-1} (-1)^{b·S(x) ⊕ a·x}

    Returns:
        256x256 频谱矩阵 W[a][b]
    """
    n = SBOX_BITS
    size = 1 << n  # 256

    spectrum = [[0] * size for _ in range(size)]

    for a in range(size):
        for b in range(1, size):  # b=0 时无意义
            total = 0
            for x in range(size):
                exponent = _dot_product_gf2(b, sbox[x]) ^ _dot_product_gf2(a, x)
                total += 1 if exponent == 0 else -1
            spectrum[a][b] = total

    return spectrum


def _walsh_hadamard_spectrum_fast(sbox: List[int]) -> List[int]:
    """快速计算 Walsh-Hadamard 最大绝对值谱。

    对每个分量函数 f_b(x) = b·S(x) 计算 WHT，
    取所有 a≠0 的最大 |W(a)| 值。

    使用 Fast Walsh-Hadamard Transform (FWHT) 加速，
    时间复杂度 O(n * 2^n) 而非 O(2^(2n))。

    Returns:
        长度 256 的列表，max_walsh[b] = max_{a≠0} |W_b(a)|
    """
    n = SBOX_BITS
    size = 1 << n  # 256

    # 优先走可选加速器，失败则自动回退到纯 Python 实现。
    if callable(_SBOX_ACCEL_MAX_WALSH):
        try:
            accel_values = _SBOX_ACCEL_MAX_WALSH(sbox)
            if isinstance(accel_values, (list, tuple)) and len(accel_values) == size:
                return [int(v) for v in accel_values]
        except Exception:
            pass

    max_walsh_values = [0] * size

    for b in range(1, size):
        # 构造布尔函数 f(x) = b·S(x)
        # truth table: f[x] = (-1)^{b·S(x)}
        f = [0] * size
        for x in range(size):
            f[x] = 1 if _dot_product_gf2(b, sbox[x]) == 0 else -1

        # FWHT (in-place butterfly)
        h = 1
        while h < size:
            for i in range(0, size, h * 2):
                for j in range(i, i + h):
                    u = f[j]
                    v = f[j + h]
                    f[j] = u + v
                    f[j + h] = u - v
            h *= 2

        # 取 a≠0 的最大绝对值
        max_val = 0
        for a in range(1, size):
            if abs(f[a]) > max_val:
                max_val = abs(f[a])

        max_walsh_values[b] = max_val

    return max_walsh_values


# ============== S-Box 密码学指标计算 ==============

def compute_nonlinearity(sbox: List[int]) -> int:
    """计算 S-Box 非线性度 (Nonlinearity)。

    NL(S) = 2^{n-1} - (1/2) * max_{a≠0, b≠0} |W_S(a, b)|

    使用 FWHT 加速。

    Args:
        sbox: 长度 256 的置换列表

    Returns:
        非线性度值 (0 ~ 120, AES=112)
    """
    max_walsh = _walsh_hadamard_spectrum_fast(sbox)

    # 取所有分量函数中的全局最大值
    global_max = 0
    for b in range(1, SBOX_SIZE):
        if max_walsh[b] > global_max:
            global_max = max_walsh[b]

    nl = (1 << (SBOX_BITS - 1)) - global_max // 2
    return nl


def compute_differential_uniformity(sbox: List[int]) -> int:
    """计算 S-Box 差分均匀性 (Differential Uniformity)。

    DU(S) = max_{a≠0, b} #{x | S(x) ⊕ S(x⊕a) = b}

    值越小越安全 (AES=4, 理论最低=2)。

    Args:
        sbox: 长度 256 的置换列表

    Returns:
        差分均匀性值
    """
    size = SBOX_SIZE
    max_count = 0

    for a in range(1, size):
        # 统计差分分布
        diff_dist = [0] * size
        for x in range(size):
            b = sbox[x] ^ sbox[x ^ a]
            diff_dist[b] += 1

        # 取本轮最大值
        local_max = max(diff_dist)
        if local_max > max_count:
            max_count = local_max

    return max_count


def compute_avalanche(sbox: List[int]) -> float:
    """计算 S-Box 平均雪崩效应 (Avalanche Effect)。

    AE(S) = (1/n) * Σ_{i=1}^{n} mean_x(HammingDistance(S(x), S(x ⊕ e_i)))

    理想值 = n/2 = 4.0。

    Args:
        sbox: 长度 256 的置换列表

    Returns:
        平均雪崩效应值 (0 ~ 8, 理想=4.0)
    """
    n = SBOX_BITS
    size = SBOX_SIZE
    total_distance = 0.0
    total_tests = 0

    for i in range(n):
        ei = 1 << i  # 单位向量 e_i
        bit_sum = 0
        for x in range(size):
            diff = sbox[x] ^ sbox[x ^ ei]
            bit_sum += bin(diff).count('1')
        total_distance += bit_sum / size
        total_tests += 1

    return total_distance / total_tests if total_tests > 0 else 0.0


def normalize_nonlinearity(nl: int) -> float:
    """归一化非线性度到 [0, 1]。"""
    return max(0.0, min(1.0, nl / MAX_NONLINEARITY))


def normalize_diff_uniformity(du: int) -> float:
    """归一化差分均匀性到 [0, 1] (越小越好，所以归一化后越小=越好)。"""
    if du <= MIN_DIFF_UNIFORMITY:
        return 0.0
    return max(0.0, min(1.0, (du - MIN_DIFF_UNIFORMITY) / (MAX_DIFF_UNIFORMITY - MIN_DIFF_UNIFORMITY)))


def normalize_avalanche(ae: float) -> float:
    """归一化雪崩效应到 [0, 1] (越接近理想值 n/2 越好)。"""
    deviation = abs(ae - IDEAL_AVALANCHE) / IDEAL_AVALANCHE
    return max(0.0, 1.0 - deviation)


# ============== 综合评分 ==============

@dataclass
class SBoxMetrics:
    """S-Box 密码学指标结果。"""
    nonlinearity: int = 0
    diff_uniformity: int = 0
    avalanche: float = 0.0

    # 归一化值
    nl_norm: float = 0.0
    du_norm: float = 0.0
    ae_norm: float = 0.0

    # 综合得分
    score: float = 0.0

    # 权重 (记录用于验证)
    weights: Dict[str, float] = field(default_factory=dict)

    # 计算耗时
    compute_time_ms: float = 0.0


def compute_sbox_score(
    sbox: List[int],
    weights: Dict[str, float] = None,
) -> SBoxMetrics:
    """计算 S-Box 综合安全评分。

    score(S) = w1 * NL_norm + w2 * (1 - DU_norm) + w3 * AE_norm

    Args:
        sbox: 长度 256 的双射置换
        weights: 评分权重 {nonlinearity, diff_uniformity, avalanche}

    Returns:
        SBoxMetrics 包含所有指标和综合评分
    """
    if weights is None:
        weights = dict(DEFAULT_SCORE_WEIGHTS)

    # 验证权重合法性
    w1 = weights.get("nonlinearity", 0.4)
    w2 = weights.get("diff_uniformity", 0.35)
    w3 = weights.get("avalanche", 0.25)
    w_sum = w1 + w2 + w3
    if abs(w_sum - 1.0) > 0.001:
        # 自动归一化
        w1, w2, w3 = w1 / w_sum, w2 / w_sum, w3 / w_sum

    start = time.monotonic()

    # 计算三项核心指标
    nl = compute_nonlinearity(sbox)
    du = compute_differential_uniformity(sbox)
    ae = compute_avalanche(sbox)

    # 归一化
    nl_norm = normalize_nonlinearity(nl)
    du_norm = normalize_diff_uniformity(du)
    ae_norm = normalize_avalanche(ae)

    # 综合评分 (DU 越小越好，所以用 1-DU_norm)
    score = w1 * nl_norm + w2 * (1.0 - du_norm) + w3 * ae_norm

    elapsed_ms = (time.monotonic() - start) * 1000

    return SBoxMetrics(
        nonlinearity=nl,
        diff_uniformity=du,
        avalanche=ae,
        nl_norm=nl_norm,
        du_norm=du_norm,
        ae_norm=ae_norm,
        score=score,
        weights={"w1": w1, "w2": w2, "w3": w3},
        compute_time_ms=elapsed_ms,
    )


# ============== S-Box 生成 ==============

def generate_random_sbox() -> List[int]:
    """生成密码学安全的随机 S-Box (双射置换)。

    使用 Fisher-Yates 洗牌算法，基于 secrets 模块的 CSPRNG。

    Returns:
        长度 256 的双射置换列表
    """
    return generate_random_sbox_with_rng(secrets.SystemRandom())


def generate_random_sbox_with_rng(rng: random.Random) -> List[int]:
    """使用指定 RNG 生成随机 S-Box (双射置换)。

    该接口用于测试/复现实验：
    - 生产默认仍建议使用 secrets.SystemRandom()
    - 在需要可复现结果时可注入 deterministic Random(seed)
    """
    sbox = list(range(SBOX_SIZE))
    # Fisher-Yates shuffle
    for i in range(SBOX_SIZE - 1, 0, -1):
        j = rng.randrange(i + 1)
        sbox[i], sbox[j] = sbox[j], sbox[i]
    return sbox


def is_bijective(sbox: List[int]) -> bool:
    """验证 S-Box 是否为双射置换。"""
    if len(sbox) != SBOX_SIZE:
        return False
    return set(sbox) == set(range(SBOX_SIZE))


def sbox_to_bytes(sbox: List[int]) -> bytes:
    """S-Box 序列化为 256 字节。"""
    return bytes(sbox)


def bytes_to_sbox(data: bytes) -> List[int]:
    """从 256 字节反序列化 S-Box。"""
    if len(data) != SBOX_SIZE:
        raise ValueError(f"Invalid S-Box data length: {len(data)}, expected {SBOX_SIZE}")
    sbox = list(data)
    if not is_bijective(sbox):
        raise ValueError("Deserialized S-Box is not bijective")
    return sbox


def sbox_hash(sbox: List[int]) -> str:
    """计算 S-Box 的 SHA-256 哈希。"""
    return hashlib.sha256(sbox_to_bytes(sbox)).hexdigest()


def sbox_to_hex(sbox: List[int]) -> str:
    """S-Box 转为紧凑 hex 字符串 (512 字符)。"""
    return sbox_to_bytes(sbox).hex()


def hex_to_sbox(hex_str: str) -> List[int]:
    """从 hex 字符串恢复 S-Box。"""
    return bytes_to_sbox(bytes.fromhex(hex_str))


# ============== 遗传算法优化 ==============

def _crossover(parent1: List[int], parent2: List[int], rng: random.Random) -> List[int]:
    """有序交叉 (OX) 保持双射性。"""
    size = len(parent1)
    start = rng.randrange(size)
    end = start + rng.randrange(size - start)

    child = [-1] * size
    # 复制 parent1 的片段
    child[start:end] = parent1[start:end]
    included = set(child[start:end])

    # 从 parent2 填充剩余位置
    p2_idx = 0
    for i in range(size):
        if child[i] == -1:
            while parent2[p2_idx] in included:
                p2_idx += 1
            child[i] = parent2[p2_idx]
            included.add(parent2[p2_idx])
            p2_idx += 1

    return child


def _mutate(sbox: List[int], mutation_rate: float = 0.02, rng: Optional[random.Random] = None) -> List[int]:
    """变异：随机交换两个位置 (保持双射性)。"""
    rng = rng or secrets.SystemRandom()
    result = list(sbox)
    n_swaps = max(1, int(SBOX_SIZE * mutation_rate))
    for _ in range(n_swaps):
        i = rng.randrange(SBOX_SIZE)
        j = rng.randrange(SBOX_SIZE)
        result[i], result[j] = result[j], result[i]
    return result


def genetic_optimize(
    initial_sbox: List[int] = None,
    iterations: int = 200,
    population_size: int = 20,
    weights: Dict[str, float] = None,
    target_score: float = 0.85,
    deterministic_seed: Optional[int] = None,
) -> Tuple[List[int], SBoxMetrics]:
    """遗传算法优化 S-Box。

    Args:
        initial_sbox: 初始 S-Box (None 则随机生成)
        iterations: 进化迭代次数
        population_size: 种群大小
        weights: 评分权重
        target_score: 达到此分数提前终止
        deterministic_seed: 可选固定随机种子，用于可复现实验/调试

    Returns:
        (best_sbox, best_metrics) 最优 S-Box 及其评分
    """
    if weights is None:
        weights = dict(DEFAULT_SCORE_WEIGHTS)

    rng: random.Random
    if deterministic_seed is None:
        rng = secrets.SystemRandom()
    else:
        rng = random.Random(deterministic_seed)

    # 初始化种群
    population = []
    if initial_sbox:
        population.append(list(initial_sbox))
    while len(population) < population_size:
        population.append(generate_random_sbox_with_rng(rng))

    best_sbox = None
    best_metrics = None
    best_score = -1.0

    for gen in range(iterations):
        # 评估适应度
        scored = []
        for sbox in population:
            metrics = compute_sbox_score(sbox, weights)
            scored.append((sbox, metrics))
            if metrics.score > best_score:
                best_score = metrics.score
                best_sbox = list(sbox)
                best_metrics = metrics

        # 提前终止
        if best_score >= target_score:
            break

        # 选择 (锦标赛选择)
        scored.sort(key=lambda x: x[1].score, reverse=True)
        survivors = [s[0] for s in scored[:population_size // 2]]

        # 繁殖
        new_population = list(survivors)
        while len(new_population) < population_size:
            p1 = survivors[rng.randrange(len(survivors))]
            p2 = survivors[rng.randrange(len(survivors))]
            child = _crossover(p1, p2, rng)
            child = _mutate(child, rng=rng)
            new_population.append(child)

        population = new_population

    if best_sbox is None:
        best_sbox = generate_random_sbox()
        best_metrics = compute_sbox_score(best_sbox, weights)

    return best_sbox, best_metrics


# ============== S-Box 验证 (轻量级，验证节点使用) ==============

def verify_sbox_submission(
    sbox: List[int],
    claimed_score: float,
    weights: Dict[str, float],
    score_threshold: float,
    tolerance: float = 0.001,
) -> Tuple[bool, str, SBoxMetrics]:
    """验证矿工提交的 S-Box。

    验证节点调用此函数，耗时仅数十毫秒:
    1. 验证 S-Box 是双射置换
    2. 重新计算 score
    3. 验证 score 与声称值一致
    4. 验证 score >= threshold

    Args:
        sbox: 矿工提交的 S-Box
        claimed_score: 矿工声称的评分
        weights: 当前网络评分权重
        score_threshold: 当前网络阈值
        tolerance: 浮点误差容忍度

    Returns:
        (valid, message, metrics)
    """
    # 1. 双射验证
    if not is_bijective(sbox):
        return False, "S-Box is not bijective", SBoxMetrics()

    # 2. 重新计算评分
    metrics = compute_sbox_score(sbox, weights)

    # 3. 验证声称分数的一致性
    if abs(metrics.score - claimed_score) > tolerance:
        return False, (
            f"Score mismatch: claimed {claimed_score:.6f}, "
            f"computed {metrics.score:.6f}"
        ), metrics

    # 4. 阈值验证
    if metrics.score < score_threshold:
        return False, (
            f"Score {metrics.score:.6f} below threshold {score_threshold:.6f}"
        ), metrics

    return True, "OK", metrics


# ============== S-Box 加密适配 (用于数据传输加密) ==============

def sbox_substitute(data: bytes, sbox: List[int]) -> bytes:
    """使用 S-Box 对数据进行字节级替换 (SubBytes)。

    类似 AES 的 SubBytes 步骤，逐字节通过 S-Box 置换。
    用于增强数据传输的加密层。

    Args:
        data: 输入数据
        sbox: 256 元素的双射置换

    Returns:
        置换后的数据 (等长)
    """
    return bytes(sbox[b] for b in data)


def sbox_inverse(sbox: List[int]) -> List[int]:
    """计算 S-Box 的逆置换 (用于解密)。"""
    inv = [0] * SBOX_SIZE
    for i in range(SBOX_SIZE):
        inv[sbox[i]] = i
    return inv


def sbox_substitute_inverse(data: bytes, sbox: List[int]) -> bytes:
    """使用 S-Box 逆置换解密。"""
    inv = sbox_inverse(sbox)
    return bytes(inv[b] for b in data)


# ============== 区块 S-Box 数据结构 ==============

@dataclass
class BlockSBox:
    """区块中的 S-Box 数据。"""
    sbox: List[int]                  # 256 元素置换
    sbox_hash: str = ""              # SHA-256(sbox_bytes)
    score: float = 0.0               # 综合评分
    nonlinearity: int = 0            # 非线性度
    diff_uniformity: int = 0         # 差分均匀性
    avalanche: float = 0.0           # 雪崩效应
    weights: Dict[str, float] = field(default_factory=dict)
    miner_id: str = ""               # 产出矿工
    sector: str = ""                 # 来源板块
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.sbox_hash and self.sbox:
            self.sbox_hash = hashlib.sha256(bytes(self.sbox)).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "sbox_hex": sbox_to_hex(self.sbox),
            "sbox_hash": self.sbox_hash,
            "score": round(self.score, 6),
            "nonlinearity": self.nonlinearity,
            "diff_uniformity": self.diff_uniformity,
            "avalanche": round(self.avalanche, 4),
            "weights": self.weights,
            "miner_id": self.miner_id,
            "sector": self.sector,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: Dict) -> 'BlockSBox':
        sbox = hex_to_sbox(data["sbox_hex"])
        return BlockSBox(
            sbox=sbox,
            sbox_hash=data.get("sbox_hash", ""),
            score=data.get("score", 0.0),
            nonlinearity=data.get("nonlinearity", 0),
            diff_uniformity=data.get("diff_uniformity", 0),
            avalanche=data.get("avalanche", 0.0),
            weights=data.get("weights", {}),
            miner_id=data.get("miner_id", ""),
            sector=data.get("sector", ""),
            timestamp=data.get("timestamp", 0.0),
        )


# ============== 全局 S-Box 库管理 ==============

class SBoxLibrary:
    """全网 S-Box 库 — 存储由区块产出的高质量 S-Box。

    每个区块会产出一个 S-Box，全网可调用用于:
    - 通信加密层替换
    - 隐私数据保护
    - 密码学研究
    """

    def __init__(self, max_size: int = 10000):
        self._library: Dict[str, BlockSBox] = {}  # sbox_hash -> BlockSBox
        self._max_size = max_size
        self._current_sbox: Optional[BlockSBox] = None  # 当前全网活跃 S-Box
        self._history: List[str] = []  # 按时间排序的 sbox_hash 列表

    @property
    def current(self) -> Optional[BlockSBox]:
        """获取当前全网活跃的 S-Box (最新区块选出的)。"""
        return self._current_sbox

    def add(self, block_sbox: BlockSBox) -> bool:
        """添加 S-Box 到库。"""
        if block_sbox.sbox_hash in self._library:
            return False
        if not is_bijective(block_sbox.sbox):
            return False

        self._library[block_sbox.sbox_hash] = block_sbox
        self._history.append(block_sbox.sbox_hash)

        # 超出容量时移除最旧的
        while len(self._library) > self._max_size:
            oldest = self._history.pop(0)
            self._library.pop(oldest, None)

        return True

    def set_current(self, block_sbox: BlockSBox):
        """设置当前全网活跃 S-Box (由区块选出)。"""
        self._current_sbox = block_sbox
        self.add(block_sbox)

    def get(self, sbox_hash: str) -> Optional[BlockSBox]:
        """按哈希获取 S-Box。"""
        return self._library.get(sbox_hash)

    def get_latest(self, n: int = 10) -> List[BlockSBox]:
        """获取最新 n 个 S-Box。"""
        hashes = self._history[-n:]
        return [self._library[h] for h in hashes if h in self._library]

    def size(self) -> int:
        return len(self._library)


# 全局单例
_sbox_library: Optional[SBoxLibrary] = None


def get_sbox_library() -> SBoxLibrary:
    """获取全局 S-Box 库。"""
    global _sbox_library
    if _sbox_library is None:
        _sbox_library = SBoxLibrary()
    return _sbox_library
