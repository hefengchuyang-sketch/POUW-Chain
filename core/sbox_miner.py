"""
sbox_miner.py - S-Box PoUW 挖矿引擎

实现:
  1. Hybrid PoUW 挖矿: S-Box 质量评分 + Hash 难度双重验证
  2. 多板块并行挖矿: 各板块独立挖矿，同一时刻出块
  3. 随机选取板块 S-Box 全网公布: VRF 确定性随机选择
  4. 难度自适应调整: Hash 难度 + Score 阈值双重调整
  5. 遗传优化加速: 可选遗传算法提升 S-Box 质量

安全设计:
  - VRF 随机选择板块，不可预测、不可操纵
  - 验证节点只需一次 score + 一次 hash，毫秒级验证
  - 动态权重调整 w1/w2/w3 → 抗 ASIC 硬编码
  - 每次出块权重微调 → 防止专用硬件提前优化
"""

import hashlib
import secrets
import time
import json
import threading
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from copy import deepcopy

from core.sbox_engine import (
    generate_random_sbox,
    genetic_optimize,
    compute_sbox_score,
    verify_sbox_submission,
    sbox_to_hex,
    hex_to_sbox,
    sbox_hash,
    is_bijective,
    SBoxMetrics,
    BlockSBox,
    get_sbox_library,
    DEFAULT_SCORE_WEIGHTS,
    SBOX_SIZE,
)

logger = logging.getLogger(__name__)


# ============== 挖矿参数 ==============

@dataclass
class SBoxMiningParams:
    """S-Box 挖矿参数。"""
    # Score 阈值 (S-Box 质量门槛)
    score_threshold: float = 0.55

    # Hash 难度 (前导零数量)
    hash_difficulty: int = 4

    # 目标出块时间 (秒)
    target_block_time: float = 30.0

    # 难度调整间隔 (区块数)
    adjustment_interval: int = 10

    # 评分权重 (可动态调整)
    score_weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCORE_WEIGHTS))

    # 权重漂移参数 (每次出块微调幅度)
    weight_drift_range: float = 0.03

    # 遗传优化参数
    genetic_iterations: int = 100
    genetic_population: int = 10
    use_genetic: bool = True
    # 确定性遗传优化（降低方差、方便复现实验）
    deterministic_genetic: bool = True
    deterministic_genetic_salt: str = ""

    # Score 阈值范围
    min_score_threshold: float = 0.30
    max_score_threshold: float = 0.95

    # Hash 难度范围
    min_hash_difficulty: int = 2
    max_hash_difficulty: int = 32


# ============== 难度调整器 ==============

class SBoxDifficultyAdjuster:
    """S-Box 挖矿双重难度调整器。

    1. Hash 难度调整 (控制出块速度):
       target_new = target_old * (actual_time / expected_time)

    2. Score 阈值调整 (控制 S-Box 质量):
       threshold_new = threshold_old * (expected_blocks / actual_blocks)
    """

    def __init__(self, params: SBoxMiningParams):
        self.params = params
        self.block_times: List[float] = []
        self.block_scores: List[float] = []
        self._last_adjustment_height: int = 0

    def record_block(self, block_time: float, sbox_score: float):
        """记录区块信息。"""
        self.block_times.append(block_time)
        self.block_scores.append(sbox_score)

        # 保持有限历史
        max_history = self.params.adjustment_interval * 3
        if len(self.block_times) > max_history:
            self.block_times = self.block_times[-max_history:]
        if len(self.block_scores) > max_history:
            self.block_scores = self.block_scores[-max_history:]

    def should_adjust(self, block_height: int) -> bool:
        """是否需要调整难度。"""
        return (
            block_height > 0
            and block_height % self.params.adjustment_interval == 0
            and block_height != self._last_adjustment_height
        )

    def adjust(self, block_height: int) -> Tuple[int, float, Dict[str, float]]:
        """执行难度调整。

        Returns:
            (new_hash_difficulty, new_score_threshold, new_weights)
        """
        self._last_adjustment_height = block_height
        interval = self.params.adjustment_interval

        if len(self.block_times) < interval:
            return (
                self.params.hash_difficulty,
                self.params.score_threshold,
                dict(self.params.score_weights),
            )

        recent_times = self.block_times[-interval:]
        recent_scores = self.block_scores[-interval:]

        # --- 1. Hash 难度调整 ---
        avg_time = sum(recent_times) / len(recent_times)
        ratio = self.params.target_block_time / avg_time if avg_time > 0 else 1.0

        new_hash_diff = self.params.hash_difficulty
        # 限制每次调整幅度 ±1
        if ratio > 1.15:
            new_hash_diff = min(
                self.params.max_hash_difficulty,
                self.params.hash_difficulty + 1
            )
        elif ratio < 0.85:
            new_hash_diff = max(
                self.params.min_hash_difficulty,
                self.params.hash_difficulty - 1
            )

        # --- 2. Score 阈值调整 ---
        # 如果出块太快 → 提高阈值; 太慢 → 降低阈值
        expected_total_time = self.params.target_block_time * interval
        actual_total_time = sum(recent_times)
        time_ratio = expected_total_time / actual_total_time if actual_total_time > 0 else 1.0

        # 平滑调整: 乘以比率但限制变化幅度
        adjustment_factor = max(0.9, min(1.1, time_ratio))
        new_threshold = self.params.score_threshold * adjustment_factor
        new_threshold = max(
            self.params.min_score_threshold,
            min(self.params.max_score_threshold, new_threshold)
        )

        # --- 3. 权重微调 (抗 ASIC) ---
        new_weights = self._drift_weights()

        # 更新参数
        self.params.hash_difficulty = new_hash_diff
        self.params.score_threshold = new_threshold
        self.params.score_weights = new_weights

        return new_hash_diff, new_threshold, new_weights

    def _drift_weights(self) -> Dict[str, float]:
        """权重微调 (每次出块随机漂移，防 ASIC 硬编码)。

        确保 w1+w2+w3=1，每个权重变化不超过 drift_range。
        """
        drift = self.params.weight_drift_range
        w = dict(self.params.score_weights)

        # 随机漂移
        keys = list(w.keys())
        for k in keys:
            delta = (secrets.randbelow(2001) - 1000) / 1000.0 * drift
            w[k] = max(0.05, w[k] + delta)  # 最小权重 5%

        # 归一化
        total = sum(w.values())
        for k in w:
            w[k] = w[k] / total

        return w

    def get_stats(self) -> Dict:
        """获取统计信息。"""
        if not self.block_times:
            return {
                "avg_block_time": 0,
                "avg_score": 0,
                "hash_difficulty": self.params.hash_difficulty,
                "score_threshold": self.params.score_threshold,
            }
        return {
            "avg_block_time": sum(self.block_times[-10:]) / min(10, len(self.block_times)),
            "avg_score": sum(self.block_scores[-10:]) / min(10, len(self.block_scores)),
            "hash_difficulty": self.params.hash_difficulty,
            "score_threshold": self.params.score_threshold,
            "weights": self.params.score_weights,
        }


# ============== S-Box PoUW 区块 ==============

@dataclass
class SBoxBlock:
    """S-Box PoUW 区块。

    字段说明:
        block_height      区块高度
        prev_hash         上一块区块哈希
        miner_id          矿工节点 ID
        timestamp         UNIX 时间戳
        sbox              挖矿产出的 S-Box (256 元素)
        sbox_hex          S-Box 的 hex 表示
        score             S-Box 综合安全评分
        score_weights     评分权重 (验证用)
        nonlinearity      非线性度
        diff_uniformity   差分均匀性
        avalanche         雪崩效应
        nonce             用于哈希难度控制
        hash              本区块哈希
        sector            所属板块
        score_threshold   本区块的评分阈值
        hash_difficulty   本区块的哈希难度
    """
    block_height: int = 0
    prev_hash: str = ""
    miner_id: str = ""
    timestamp: float = field(default_factory=time.time)
    sbox: List[int] = field(default_factory=list)
    sbox_hex: str = ""
    score: float = 0.0
    score_weights: Dict[str, float] = field(default_factory=dict)
    nonlinearity: int = 0
    diff_uniformity: int = 0
    avalanche: float = 0.0
    nonce: int = 0
    hash: str = ""
    sector: str = ""
    score_threshold: float = 0.55
    hash_difficulty: int = 4

    def compute_hash(self) -> str:
        """计算区块哈希 (包含 S-Box + nonce)。

        hash = SHA256(prev_hash || miner_id || sbox_hex || nonce || timestamp || sector)
        """
        header = (
            f"{self.prev_hash}"
            f"{self.miner_id}"
            f"{self.sbox_hex}"
            f"{self.nonce}"
            f"{self.timestamp}"
            f"{self.sector}"
            f"{self.score:.6f}"
            f"{self.block_height}"
        )
        return hashlib.sha256(header.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "block_height": self.block_height,
            "prev_hash": self.prev_hash,
            "miner_id": self.miner_id,
            "timestamp": self.timestamp,
            "sbox_hex": self.sbox_hex,
            "sbox_hash": sbox_hash(self.sbox) if self.sbox else "",
            "score": round(self.score, 6),
            "score_weights": self.score_weights,
            "nonlinearity": self.nonlinearity,
            "diff_uniformity": self.diff_uniformity,
            "avalanche": round(self.avalanche, 4),
            "nonce": self.nonce,
            "hash": self.hash,
            "sector": self.sector,
            "score_threshold": self.score_threshold,
            "hash_difficulty": self.hash_difficulty,
        }

    @staticmethod
    def from_dict(data: Dict) -> 'SBoxBlock':
        sbox = hex_to_sbox(data["sbox_hex"]) if data.get("sbox_hex") else []
        return SBoxBlock(
            block_height=data.get("block_height", 0),
            prev_hash=data.get("prev_hash", ""),
            miner_id=data.get("miner_id", ""),
            timestamp=data.get("timestamp", 0.0),
            sbox=sbox,
            sbox_hex=data.get("sbox_hex", ""),
            score=data.get("score", 0.0),
            score_weights=data.get("score_weights", {}),
            nonlinearity=data.get("nonlinearity", 0),
            diff_uniformity=data.get("diff_uniformity", 0),
            avalanche=data.get("avalanche", 0.0),
            nonce=data.get("nonce", 0),
            hash=data.get("hash", ""),
            sector=data.get("sector", ""),
            score_threshold=data.get("score_threshold", 0.55),
            hash_difficulty=data.get("hash_difficulty", 4),
        )


# ============== 单板块 S-Box 矿工 ==============

class SBoxSectorMiner:
    """单个板块的 S-Box 矿工。

    挖矿流程 (Hybrid PoUW):
      while True:
        1. 生成随机 S-Box
        2. 遗传优化 (可选)
        3. 计算安全得分
        4. 验证 score >= threshold
        5. 随机 nonce
        6. 计算区块 hash = SHA256(prev_hash + miner_id + SBOX + nonce)
        7. hash 难度验证
        8. 满足条件 → 提交区块
    """

    def __init__(
        self,
        sector: str,
        miner_id: str,
        params: SBoxMiningParams = None,
        log_fn: Callable = None,
    ):
        self.sector = sector
        self.miner_id = miner_id
        self.params = params or SBoxMiningParams()
        self.log = log_fn or logger.info
        self.difficulty_adjuster = SBoxDifficultyAdjuster(self.params)

        # 挖矿状态
        self._stop = False
        self._mining = False
        self._last_block: Optional[SBoxBlock] = None
        self._blocks_mined: int = 0

    def mine_one_block(
        self,
        prev_hash: str,
        block_height: int,
        max_attempts: int = 100000,
    ) -> Optional[SBoxBlock]:
        """尝试挖一个区块。

        Args:
            prev_hash: 上一个区块哈希
            block_height: 目标区块高度
            max_attempts: 最大尝试次数

        Returns:
            成功则返回 SBoxBlock, 否则 None
        """
        threshold = self.params.score_threshold
        difficulty = self.params.hash_difficulty
        weights = dict(self.params.score_weights)
        hash_target = "0" * difficulty

        for attempt in range(max_attempts):
            if self._stop:
                return None

            # 1. 生成随机 S-Box
            sbox = generate_random_sbox()

            # 2. 遗传优化 (可选)
            if self.params.use_genetic:
                deterministic_seed = None
                if self.params.deterministic_genetic:
                    seed_material = (
                        f"{self.miner_id}|{self.sector}|{block_height}|"
                        f"{attempt}|{prev_hash}|{self.params.deterministic_genetic_salt}"
                    )
                    deterministic_seed = int.from_bytes(
                        hashlib.sha256(seed_material.encode("utf-8")).digest()[:8],
                        "big",
                    )

                sbox, metrics = genetic_optimize(
                    initial_sbox=sbox,
                    iterations=self.params.genetic_iterations,
                    population_size=self.params.genetic_population,
                    weights=weights,
                    target_score=threshold,
                    deterministic_seed=deterministic_seed,
                )
            else:
                metrics = compute_sbox_score(sbox, weights)

            # 3. 验证 score >= threshold
            if metrics.score < threshold:
                continue

            # 4-7. 尝试 nonce 直到 hash 满足难度
            block = SBoxBlock(
                block_height=block_height,
                prev_hash=prev_hash,
                miner_id=self.miner_id,
                timestamp=time.time(),
                sbox=sbox,
                sbox_hex=sbox_to_hex(sbox),
                score=metrics.score,
                score_weights=weights,
                nonlinearity=metrics.nonlinearity,
                diff_uniformity=metrics.diff_uniformity,
                avalanche=metrics.avalanche,
                nonce=0,
                sector=self.sector,
                score_threshold=threshold,
                hash_difficulty=difficulty,
            )

            # Hash 搜索: 尝试多个 nonce
            for nonce in range(50000):
                if self._stop:
                    return None
                block.nonce = nonce
                block.hash = block.compute_hash()
                if block.hash.startswith(hash_target):
                    self._blocks_mined += 1
                    self._last_block = block
                    return block

        return None

    def stop(self):
        """停止挖矿。"""
        self._stop = True

    def reset(self):
        """重置状态。"""
        self._stop = False
        self._mining = False


# ============== 多板块并行挖矿与随机选取 ==============

class MultiSectorSBoxMiner:
    """多板块并行 S-Box 矿工。

    核心机制:
    1. 所有板块同时挖矿，各自独立产出 S-Box 区块
    2. 各板块同一时间出块
    3. 随机选取一个板块的 S-Box 向全网公布 (VRF 确定性选择)
    4. 被选中的 S-Box 成为全网当前活跃加密 S-Box
    5. 未被选中的 S-Box 也记录在区块中 (用于 S-Box 库)
    """

    def __init__(
        self,
        miner_id: str,
        sectors: List[str] = None,
        params: SBoxMiningParams = None,
        log_fn: Callable = None,
    ):
        self.miner_id = miner_id
        self.sectors = sectors or ["H100", "RTX4090", "RTX3080", "CPU", "GENERAL"]
        self.params = params or SBoxMiningParams()
        self.log = log_fn or logger.info

        # 每个板块一个矿工
        self.sector_miners: Dict[str, SBoxSectorMiner] = {}
        for sector in self.sectors:
            self.sector_miners[sector] = SBoxSectorMiner(
                sector=sector,
                miner_id=miner_id,
                params=SBoxMiningParams(
                    score_threshold=self.params.score_threshold,
                    hash_difficulty=self.params.hash_difficulty,
                    target_block_time=self.params.target_block_time,
                    adjustment_interval=self.params.adjustment_interval,
                    score_weights=dict(self.params.score_weights),
                    genetic_iterations=self.params.genetic_iterations,
                    genetic_population=self.params.genetic_population,
                    use_genetic=self.params.use_genetic,
                ),
                log_fn=log_fn,
            )

        # 状态
        self._stop = False
        self._lock = threading.Lock()

        # 全局难度调整器
        self.global_adjuster = SBoxDifficultyAdjuster(self.params)

    def mine_parallel(
        self,
        prev_hash: str,
        block_height: int,
        timeout: float = None,
    ) -> Tuple[Optional[SBoxBlock], List[SBoxBlock], str]:
        """所有板块并行挖矿，然后 VRF 随机选一个公布。

        Args:
            prev_hash: 上一个区块哈希
            block_height: 目标区块高度
            timeout: 超时时间 (秒)

        Returns:
            (selected_block, all_blocks, selected_sector)
            - selected_block: 被选中向全网公布的 S-Box 区块
            - all_blocks: 所有板块产出的区块 (含 selected)
            - selected_sector: 被选中的板块名称
        """
        results: Dict[str, Optional[SBoxBlock]] = {}
        threads: List[threading.Thread] = []
        start_time = time.monotonic()

        # 并行启动所有板块挖矿
        def mine_sector(sector: str):
            miner = self.sector_miners[sector]
            miner.reset()
            block = miner.mine_one_block(prev_hash, block_height)
            with self._lock:
                results[sector] = block

        for sector in self.sectors:
            t = threading.Thread(target=mine_sector, args=(sector,), daemon=True)
            threads.append(t)
            t.start()

        # 等待所有线程完成 (或超时)
        effective_timeout = timeout or (self.params.target_block_time * 3)
        for t in threads:
            remaining = effective_timeout - (time.monotonic() - start_time)
            if remaining > 0:
                t.join(timeout=remaining)
            else:
                # 超时，停止所有矿工
                for m in self.sector_miners.values():
                    m.stop()
                break

        # 收集所有成功的区块
        all_blocks: List[SBoxBlock] = []
        for sector in self.sectors:
            block = results.get(sector)
            if block is not None:
                all_blocks.append(block)

        if not all_blocks:
            return None, [], ""

        # VRF 确定性随机选择一个板块
        selected_block, selected_sector = self._vrf_select(
            all_blocks, prev_hash, block_height
        )

        # 将选中的 S-Box 注册到全网 S-Box 库
        sbox_lib = get_sbox_library()
        for block in all_blocks:
            block_sbox = BlockSBox(
                sbox=block.sbox,
                sbox_hash=sbox_hash(block.sbox),
                score=block.score,
                nonlinearity=block.nonlinearity,
                diff_uniformity=block.diff_uniformity,
                avalanche=block.avalanche,
                weights=block.score_weights,
                miner_id=block.miner_id,
                sector=block.sector,
            )
            sbox_lib.add(block_sbox)

        # 设置选中的为当前活跃 S-Box
        if selected_block:
            selected_sbox = BlockSBox(
                sbox=selected_block.sbox,
                sbox_hash=sbox_hash(selected_block.sbox),
                score=selected_block.score,
                nonlinearity=selected_block.nonlinearity,
                diff_uniformity=selected_block.diff_uniformity,
                avalanche=selected_block.avalanche,
                weights=selected_block.score_weights,
                miner_id=selected_block.miner_id,
                sector=selected_block.sector,
            )
            sbox_lib.set_current(selected_sbox)

        return selected_block, all_blocks, selected_sector

    def _vrf_select(
        self,
        blocks: List[SBoxBlock],
        prev_hash: str,
        block_height: int,
    ) -> Tuple[SBoxBlock, str]:
        """VRF 确定性随机选择板块。

        使用 SHA-256(prev_hash || block_height || all_sbox_hashes) 的值
        模板块数量来确定选择哪个板块。

        这确保:
        - 选择是确定性的 (任何节点可独立验证)
        - 选择是不可预测的 (依赖前一块哈希)
        - 选择是不可操纵的 (依赖所有板块的 S-Box 哈希)
        """
        if len(blocks) == 1:
            return blocks[0], blocks[0].sector

        # 按板块名称排序以确保一致性
        sorted_blocks = sorted(blocks, key=lambda b: b.sector)

        # 构建 VRF 种子
        sbox_hashes = "".join(sbox_hash(b.sbox) for b in sorted_blocks)
        vrf_input = f"{prev_hash}{block_height}{sbox_hashes}"
        vrf_hash = hashlib.sha256(vrf_input.encode()).hexdigest()

        # 取模选择
        index = int(vrf_hash[:8], 16) % len(sorted_blocks)
        selected = sorted_blocks[index]

        return selected, selected.sector

    def stop_all(self):
        """停止所有板块挖矿。"""
        self._stop = True
        for miner in self.sector_miners.values():
            miner.stop()

    def update_params(self, block_height: int, block_time: float, score: float):
        """更新全局挖矿参数 (难度调整)。"""
        self.global_adjuster.record_block(block_time, score)

        if self.global_adjuster.should_adjust(block_height):
            new_diff, new_threshold, new_weights = self.global_adjuster.adjust(block_height)

            self.log(
                f"[难度调整] height={block_height}: "
                f"hash_diff={new_diff}, "
                f"score_threshold={new_threshold:.4f}, "
                f"weights={new_weights}"
            )

            # 同步到所有板块矿工
            for miner in self.sector_miners.values():
                miner.params.hash_difficulty = new_diff
                miner.params.score_threshold = new_threshold
                miner.params.score_weights = dict(new_weights)


# ============== S-Box 区块验证 (验证节点) ==============

def validate_sbox_block(
    block: SBoxBlock,
    expected_prev_hash: str = None,
    expected_height: int = None,
) -> Tuple[bool, str]:
    """验证 S-Box 区块 (轻量级，验证节点调用)。

    验证步骤:
    1. S-Box 双射性验证
    2. 独立计算 score 并与声称值比较
    3. score >= threshold 验证
    4. 独立计算 hash 并与声称值比较
    5. hash 前导零满足 difficulty
    6. 字段完整性检查

    耗时: ~50-200ms (主要是 score 计算中的 Walsh-Hadamard)

    Returns:
        (valid, message)
    """
    # 1. 基本字段完整性
    if not block.sbox or not block.sbox_hex:
        return False, "Missing S-Box data"
    if not block.hash:
        return False, "Missing block hash"
    if not block.miner_id:
        return False, "Missing miner_id"
    if not block.sector:
        return False, "Missing sector"

    # 2. 高度和前哈希检查 (如果提供)
    if expected_height is not None and block.block_height != expected_height:
        return False, f"Height mismatch: expected {expected_height}, got {block.block_height}"
    if expected_prev_hash is not None and block.prev_hash != expected_prev_hash:
        return False, "prev_hash mismatch"

    # 3. S-Box 双射性验证
    if not is_bijective(block.sbox):
        return False, "S-Box is not bijective"

    # 4. sbox_hex 一致性
    if block.sbox_hex != sbox_to_hex(block.sbox):
        return False, "sbox_hex does not match sbox data"

    # 5. 重新计算评分并验证
    valid, msg, metrics = verify_sbox_submission(
        sbox=block.sbox,
        claimed_score=block.score,
        weights=block.score_weights,
        score_threshold=block.score_threshold,
    )
    if not valid:
        return False, f"S-Box score verification failed: {msg}"

    # 6. 重新计算 hash 并验证
    recomputed_hash = block.compute_hash()
    if block.hash != recomputed_hash:
        return False, f"Hash mismatch: claimed {block.hash[:16]}..., computed {recomputed_hash[:16]}..."

    # 7. Hash 难度验证
    hash_target = "0" * block.hash_difficulty
    if not block.hash.startswith(hash_target):
        return False, f"Hash does not meet difficulty {block.hash_difficulty}"

    # 8. 时间戳合理性
    if block.timestamp > time.time() + 7200:
        return False, "Timestamp too far in future"

    return True, "OK"


def validate_vrf_selection(
    selected_block: SBoxBlock,
    all_blocks: List[SBoxBlock],
    prev_hash: str,
    block_height: int,
) -> Tuple[bool, str]:
    """验证 VRF 板块选择的正确性。

    验证节点可独立确认选择的板块是通过 VRF 确定性随机决定的。
    """
    if not all_blocks:
        return False, "No blocks provided"

    if len(all_blocks) == 1:
        if all_blocks[0].sector == selected_block.sector:
            return True, "OK (single block)"
        return False, "Single block sector mismatch"

    # 按板块名称排序
    sorted_blocks = sorted(all_blocks, key=lambda b: b.sector)

    # 重新计算 VRF
    sbox_hashes = "".join(sbox_hash(b.sbox) for b in sorted_blocks)
    vrf_input = f"{prev_hash}{block_height}{sbox_hashes}"
    vrf_hash = hashlib.sha256(vrf_input.encode()).hexdigest()
    index = int(vrf_hash[:8], 16) % len(sorted_blocks)

    expected_sector = sorted_blocks[index].sector
    if selected_block.sector != expected_sector:
        return False, f"VRF selection mismatch: expected {expected_sector}, got {selected_block.sector}"

    return True, "OK"
