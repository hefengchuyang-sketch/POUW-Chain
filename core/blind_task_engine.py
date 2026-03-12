# -*- coding: utf-8 -*-
"""
盲任务引擎 (Blind Task Engine) - 矿工无感知的算力租用系统

核心设计理念：
    矿工不知道自己在执行付费任务，以为是在参与 PoUW 挖矿。
    通过「陷阱题」抽查验证矿工诚实性，不再需要多数派冗余共识。

架构优势：
    1. 消除算力浪费 - 每个任务只需 1 个矿工执行（而非 N 个冗余）
    2. 防止结果串通 - 矿工不知道是付费任务，无法与他人串通
    3. 防止偷懒作弊 - 陷阱题的答案已知，失败即惩罚
    4. 隐私保护     - 任务买家的身份对矿工完全隐藏

验证机制：
    - 在真实任务中随机混入已知答案的「陷阱题」
    - 陷阱题通过率决定矿工信任度
    - 高信任度矿工 → 低陷阱率（减少开销）
    - 低信任度矿工 → 高陷阱率（加强审查）
    - 陷阱不通过 → 重罚 + 任务重新调度

流程：
    1. 买家提交任务 → BlindTaskEngine.wrap_as_mining()
    2. 任务被伪装成 PoUW mining_challenge 推送给矿工
    3. 矿工的 mining_loop 自然消费该挑战（以为是挖矿）
    4. 矿工提交 "挖矿结果" → BlindTaskEngine.verify_blind()
    5. 检查陷阱题 → 通过则接受真实结果 → 结算
"""

import hashlib
import hmac
import json
import math
import os
import random
import secrets
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


# ============== 常量 ==============

# 陷阱题混入比率（根据矿工信任度动态调整）
TRAP_RATIO_NEW_MINER = 0.30          # 新矿工：30% 陷阱
TRAP_RATIO_TRUSTED = 0.05            # 高信任矿工：5% 陷阱
TRAP_RATIO_SUSPICIOUS = 0.50         # 可疑矿工：50% 陷阱

# 信任度阈值
TRUST_HIGH = 0.90                    # 高信任
TRUST_LOW = 0.50                     # 低信任（可疑）

# 惩罚系数
PENALTY_TRAP_FAIL = 0.20             # 陷阱失败：扣 20% PoUW 分
PENALTY_REPEATED_FAIL = 0.50         # 连续失败：扣 50% PoUW 分
MAX_CONSECUTIVE_FAILS = 3            # 连续失败 3 次 → 禁用矿工

# 伪装密钥（用于生成不可区分的任务 ID）
CAMOUFLAGE_SECRET = os.urandom(32)


class BlindTaskType(Enum):
    """盲任务类型（矿工侧不可见）"""
    REAL_TASK = "mining_challenge"        # 真实付费任务（伪装名称）
    TRAP_TASK = "mining_challenge"        # 陷阱校验题（相同伪装名称）
    PURE_MINING = "mining_challenge"      # 纯挖矿（对照组）


class TrapDifficulty(Enum):
    """陷阱题难度"""
    EASY = "easy"        # 简单（矩阵乘、哈希前缀）
    MEDIUM = "medium"    # 中等（线性回归）
    HARD = "hard"        # 困难（梯度下降优化）


@dataclass
class BlindChallenge:
    """盲挑战 - 矿工收到的工作包（不可区分的统一结构）

    矿工看到的字段完全一样，无法分辨是真实任务、陷阱还是纯挖矿。
    """
    challenge_id: str                # 看起来像挖矿挑战 ID
    challenge_type: str = "mining_challenge"   # 对矿工永远是 "mining_challenge"
    challenge_data: str = ""         # 加密/编码后的任务数据
    difficulty: int = 1              # 计算难度
    reward_hint: float = 0.0        # 预估挖矿奖励（伪装）
    deadline: float = 0.0           # 截止时间
    nonce_range: Tuple[int, int] = (0, 1000000)  # nonce 范围（统一格式）

    def to_miner_view(self) -> Dict:
        """返回矿工可见的数据（隐藏内部信息）"""
        return {
            "challenge_id": self.challenge_id,
            "type": self.challenge_type,
            "data": self.challenge_data,
            "difficulty": self.difficulty,
            "reward_hint": self.reward_hint,
            "deadline": self.deadline,
            "nonce_range": list(self.nonce_range),
        }


@dataclass
class BlindBatch:
    """盲批次 - 一组混合了陷阱题的工作包"""
    batch_id: str
    miner_id: str
    challenges: List[BlindChallenge] = field(default_factory=list)

    # ── 内部跟踪（不暴露给矿工） ──
    _real_task_ids: List[str] = field(default_factory=list)    # 哪些是真实任务
    _trap_ids: List[str] = field(default_factory=list)         # 哪些是陷阱题
    _trap_answers: Dict[str, str] = field(default_factory=dict)  # 陷阱答案
    _original_task_map: Dict[str, str] = field(default_factory=dict)  # challenge_id → original_task_id

    created_at: float = field(default_factory=time.time)
    status: str = "pending"   # pending / submitted / verified / failed

    def to_miner_view(self) -> Dict:
        """矿工只能看到挑战列表，看不到哪个是陷阱"""
        return {
            "batch_id": self.batch_id,
            "challenges": [c.to_miner_view() for c in self.challenges],
            "total_challenges": len(self.challenges),
        }


@dataclass
class MinerTrustProfile:
    """矿工信任档案"""
    miner_id: str
    trust_score: float = 0.70          # 信任度 (0-1)
    trap_total: int = 0                # 总陷阱题数
    trap_passed: int = 0               # 通过数
    trap_failed: int = 0               # 失败数
    consecutive_fails: int = 0         # 连续失败计数
    tasks_executed: int = 0            # 总任务数
    is_banned: bool = False            # 是否被禁用
    last_trap_at: float = 0.0          # 上次陷阱时间

    @property
    def trap_pass_rate(self) -> float:
        if self.trap_total == 0:
            return 0.70  # 默认通过率
        return self.trap_passed / self.trap_total

    @property
    def current_trap_ratio(self) -> float:
        """根据信任度计算当前陷阱比率"""
        if self.trust_score >= TRUST_HIGH:
            return TRAP_RATIO_TRUSTED
        elif self.trust_score <= TRUST_LOW:
            return TRAP_RATIO_SUSPICIOUS
        else:
            # 线性插值
            t = (self.trust_score - TRUST_LOW) / (TRUST_HIGH - TRUST_LOW)
            return TRAP_RATIO_SUSPICIOUS + t * (TRAP_RATIO_TRUSTED - TRAP_RATIO_SUSPICIOUS)

    def to_dict(self) -> Dict:
        """返回公开可见的信任信息（隐藏当前陷阱比率）"""
        return {
            "miner_id": self.miner_id,
            "trust_score": self.trust_score,
            "trap_total": self.trap_total,
            "trap_passed": self.trap_passed,
            "trap_failed": self.trap_failed,
            "consecutive_fails": self.consecutive_fails,
            "tasks_executed": self.tasks_executed,
            "is_banned": self.is_banned,
            "trap_pass_rate": self.trap_pass_rate,
            # 不暴露 current_trap_ratio —— 防止矿工推算陷阱数量
        }


# ============== 陷阱题生成器 ==============

class TrapGenerator:
    """陷阱题生成器 - 生成已知答案的计算挑战"""

    @staticmethod
    def generate(difficulty: TrapDifficulty = TrapDifficulty.EASY,
                 seed: Optional[int] = None) -> Tuple[Dict, str]:
        """生成陷阱题及其正确答案

        Returns:
            (task_data_dict, correct_answer_hash)
        """
        if seed is None:
            # S-3 fix: 使用密码学安全的随机数生成陷阱题种子，防止矿工预测
            seed = int.from_bytes(os.urandom(4), 'big')

        rng = random.Random(seed)

        if difficulty == TrapDifficulty.EASY:
            return TrapGenerator._trap_hash_prefix(rng, seed)
        elif difficulty == TrapDifficulty.MEDIUM:
            return TrapGenerator._trap_matrix_checksum(rng, seed)
        elif difficulty == TrapDifficulty.HARD:
            return TrapGenerator._trap_gradient_target(rng, seed)
        else:
            return TrapGenerator._trap_hash_prefix(rng, seed)

    @staticmethod
    def _trap_hash_prefix(rng: random.Random, seed: int) -> Tuple[Dict, str]:
        """陷阱：找到 hash 前缀匹配的 nonce（确定性答案）"""
        data_str = f"trap_block_{seed}"
        prefix_len = 2  # 前缀长度 2（难度低，快速验证）
        prefix = "0" * prefix_len
        # 随机化 max_nonce 范围，避免固定 500000 成为指纹特征
        max_nonce = rng.randint(300000, 800000)

        # 预计算正确答案
        correct_nonce = None
        for nonce in range(max_nonce):
            h = hashlib.sha256(f"{data_str}{nonce}".encode()).hexdigest()
            if h.startswith(prefix):
                correct_nonce = nonce
                break

        if correct_nonce is None:
            correct_nonce = 0

        correct_hash = hashlib.sha256(
            f"{data_str}{correct_nonce}".encode()
        ).hexdigest()
        answer_hash = hashlib.sha256(
            f"nonce={correct_nonce}|hash={correct_hash}".encode()
        ).hexdigest()

        task_data = {
            "computation": "hash_search",
            "block_data": data_str,
            "target_prefix": prefix,
            "max_nonce": max_nonce,
        }
        return task_data, answer_hash

    @staticmethod
    def _trap_matrix_checksum(rng: random.Random, seed: int) -> Tuple[Dict, str]:
        """陷阱：矩阵乘法的结果校验和（确定性答案）"""
        # 随机化矩阵大小，避免固定 size=4 成为指纹
        size = rng.randint(3, 6)
        # 确定性随机矩阵
        r = random.Random(seed)
        A = [[r.randint(-10, 10) for _ in range(size)] for _ in range(size)]
        B = [[r.randint(-10, 10) for _ in range(size)] for _ in range(size)]

        # 预计算正确结果
        C = [[0] * size for _ in range(size)]
        for i in range(size):
            for j in range(size):
                for k in range(size):
                    C[i][j] += A[i][k] * B[k][j]

        # 结果 hash
        result_str = json.dumps(C, sort_keys=True)
        answer_hash = hashlib.sha256(result_str.encode()).hexdigest()

        task_data = {
            "computation": "matrix_multiply",
            "matrix_a": A,
            "matrix_b": B,
            "size": size,
        }
        return task_data, answer_hash

    @staticmethod
    def _trap_gradient_target(rng: random.Random, seed: int) -> Tuple[Dict, str]:
        """陷阱：梯度下降到指定目标点（确定性答案）"""
        r = random.Random(seed)
        # 随机化参数维度和范围，避免固定 3 维成为指纹
        dim = rng.randint(2, 5)
        target = [round(r.uniform(-5, 5), 2) for _ in range(dim)]
        initial = [0.0] * dim
        lr = round(rng.uniform(0.05, 0.2), 3)
        max_iter = rng.randint(100, 400)

        # 预计算最终参数
        params = list(initial)
        for _ in range(max_iter):
            for i in range(len(params)):
                grad = 2 * (params[i] - target[i])
                params[i] -= lr * grad

        # 四舍五入到 4 位精度
        final_params = [round(p, 4) for p in params]
        result_str = json.dumps(final_params, sort_keys=True)
        answer_hash = hashlib.sha256(result_str.encode()).hexdigest()

        task_data = {
            "computation": "gradient_descent",
            "target": target,
            "initial": initial,
            "learning_rate": lr,
            "max_iterations": max_iter,
        }
        return task_data, answer_hash


# ============== 盲任务引擎 ==============

class BlindTaskEngine:
    """盲任务引擎 - 将付费任务伪装为挖矿挑战

    矿工完全无法区分自己在执行付费任务还是纯挖矿。

    工作流程：
        1. wrap_as_mining(task) → 伪装任务为 mining_challenge
        2. create_blind_batch(miner_id, real_tasks) → 混入陷阱题
        3. 矿工执行 batch 中所有 challenge（以为都是挖矿）
        4. verify_batch(batch_id, results) → 检查陷阱 → 接受/拒绝真实结果

    Properties:
        trust_profiles: 矿工信任档案（决定陷阱比率）
        pending_batches: 等待验证的批次
        trap_generator: 陷阱题生成器
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.trust_profiles: Dict[str, MinerTrustProfile] = {}
        self.pending_batches: Dict[str, BlindBatch] = {}
        self.completed_batches: Dict[str, BlindBatch] = {}
        self.trap_generator = TrapGenerator()
        self._batch_counter = 0

    # ── 任务伪装 ──

    def _generate_camouflaged_id(self, real_task_id: str) -> str:
        """生成不可逆的伪装 ID（矿工无法反推出原始任务 ID）"""
        salt = os.urandom(8).hex()
        raw = f"{real_task_id}:{salt}:{time.time()}"
        h = hmac.new(CAMOUFLAGE_SECRET, raw.encode(), hashlib.sha256).hexdigest()
        # 看起来像挖矿挑战 ID
        return f"mc_{h[:16]}"

    def wrap_as_mining(self, task_id: str, task_data: Dict,
                       difficulty: int = 1,
                       total_payment: float = 0.0) -> BlindChallenge:
        """将付费任务伪装为挖矿挑战

        Args:
            task_id: 原始任务 ID（内部跟踪，矿工不可见）
            task_data: 任务数据
            difficulty: 难度
            total_payment: 总支付（用于计算伪装奖励提示）

        Returns:
            BlindChallenge - 矿工看到的是标准挖矿挑战
        """
        camouflaged_id = self._generate_camouflaged_id(task_id)

        # 任务数据编码（与普通挖矿数据格式一致）
        challenge_data = json.dumps({
            "computation": task_data.get("computation", "hash_search"),
            **{k: v for k, v in task_data.items() if k != "computation"},
        }, sort_keys=True)

        # 伪装的挖矿奖励提示（与真实任务的奖励范围一致，避免固定范围成为指纹）
        fake_reward = round(secrets.randbelow(4951) / 100000 + 0.0005, 4)

        return BlindChallenge(
            challenge_id=camouflaged_id,
            challenge_type="mining_challenge",
            challenge_data=challenge_data,
            difficulty=difficulty,
            reward_hint=fake_reward,
            deadline=time.time() + secrets.randbelow(5401) + 1800,  # 随机化截止时间，避免固定 3600 秒成为指纹
            nonce_range=(0, 1000000),
        )

    # ── 陷阱注入 ──

    def _get_or_create_trust(self, miner_id: str) -> MinerTrustProfile:
        """获取或创建矿工信任档案"""
        if miner_id not in self.trust_profiles:
            self.trust_profiles[miner_id] = MinerTrustProfile(miner_id=miner_id)
        return self.trust_profiles[miner_id]

    def create_blind_batch(self, miner_id: str,
                           real_tasks: List[Tuple[str, Dict]],
                           force_trap_count: Optional[int] = None
                           ) -> BlindBatch:
        """创建盲批次 - 混合真实任务和陷阱题

        Args:
            miner_id: 矿工 ID
            real_tasks: [(task_id, task_data), ...] 真实任务列表
            force_trap_count: 强制陷阱数量（测试用）

        Returns:
            BlindBatch - 矿工看到的是一组挖矿挑战
        """
        with self._lock:
            trust = self._get_or_create_trust(miner_id)

            if trust.is_banned:
                # 被禁矿工不分配任务
                return BlindBatch(
                    batch_id=f"batch_banned_{miner_id}",
                    miner_id=miner_id,
                    status="rejected",
                )

            self._batch_counter += 1
            batch_id = f"batch_{self._batch_counter:06d}"

            batch = BlindBatch(
                batch_id=batch_id,
                miner_id=miner_id,
            )

            # 1. 包装真实任务
            for task_id, task_data in real_tasks:
                challenge = self.wrap_as_mining(
                    task_id=task_id,
                    task_data=task_data,
                    difficulty=task_data.get("difficulty", 1),
                )
                batch.challenges.append(challenge)
                batch._real_task_ids.append(challenge.challenge_id)
                batch._original_task_map[challenge.challenge_id] = task_id

            # 2. 计算陷阱数量
            real_count = len(real_tasks)
            if force_trap_count is not None:
                trap_count = force_trap_count
            else:
                trap_ratio = trust.current_trap_ratio
                trap_count = max(1, round(real_count * trap_ratio / (1 - trap_ratio)))
                # 至少 1 个陷阱
                trap_count = max(1, trap_count)

            # 3. 生成并混入陷阱题
            difficulties = [TrapDifficulty.EASY, TrapDifficulty.MEDIUM, TrapDifficulty.HARD]
            for i in range(trap_count):
                diff = difficulties[i % len(difficulties)]
                # S-3 fix: 密码学安全的陷阱题种子
                seed = int.from_bytes(os.urandom(4), 'big')
                trap_data, trap_answer = self.trap_generator.generate(diff, seed)

                trap_challenge = self.wrap_as_mining(
                    task_id=f"_trap_{batch_id}_{i}",
                    task_data=trap_data,
                    difficulty=1,
                )
                batch.challenges.append(trap_challenge)
                batch._trap_ids.append(trap_challenge.challenge_id)
                batch._trap_answers[trap_challenge.challenge_id] = trap_answer

            # 4. 打乱顺序（关键：让矿工无法根据位置判断哪个是陷阱）
            # 必须使用密码学安全 PRNG，防止矿工通过推断 MT19937 状态预测打乱结果
            _secure_rng = secrets.SystemRandom()
            _secure_rng.shuffle(batch.challenges)

            self.pending_batches[batch_id] = batch
            return batch

    # ── 结果验证 ──

    def verify_batch(self, batch_id: str,
                     results: Dict[str, str]
                     ) -> Tuple[bool, Dict]:
        """验证盲批次结果

        Args:
            batch_id: 批次 ID
            results: {challenge_id: result_hash, ...} 矿工提交的结果

        Returns:
            (is_trusted, verification_report)
                is_trusted=True 时接受真实任务结果
                is_trusted=False 时拒绝，需要重新调度
        """
        with self._lock:
            batch = self.pending_batches.get(batch_id)
            if not batch:
                return False, {"error": "批次不存在"}

            trust = self._get_or_create_trust(batch.miner_id)

            # 检查陷阱题结果
            trap_total = len(batch._trap_ids)
            trap_passed = 0
            trap_details = []

            for trap_id in batch._trap_ids:
                expected = batch._trap_answers.get(trap_id)
                actual = results.get(trap_id)

                if actual and expected and actual == expected:
                    trap_passed += 1
                    trap_details.append({
                        "trap_id": trap_id, "status": "passed"
                    })
                else:
                    trap_details.append({
                        "trap_id": trap_id, "status": "failed",
                        "expected": expected[:8] + "..." if expected else None,
                        "got": actual[:8] + "..." if actual else None,
                    })

            # 计算陷阱通过率
            trap_pass_rate = trap_passed / trap_total if trap_total > 0 else 0.0

            # 更新矿工信任档案
            trust.trap_total += trap_total
            trust.trap_passed += trap_passed
            trust.trap_failed += (trap_total - trap_passed)
            trust.tasks_executed += len(batch._real_task_ids)
            trust.last_trap_at = time.time()

            # 判定信任度
            is_trusted = trap_pass_rate >= 0.8  # 80% 陷阱通过率以上才信任

            if is_trusted:
                trust.consecutive_fails = 0
                # 提升信任度（缓慢上升）
                trust.trust_score = min(
                    1.0,
                    trust.trust_score + 0.02 * trap_pass_rate
                )
                batch.status = "verified"
            else:
                trust.consecutive_fails += 1
                # 降低信任度（快速下降）
                penalty = PENALTY_TRAP_FAIL
                if trust.consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    penalty = PENALTY_REPEATED_FAIL
                    trust.is_banned = True

                trust.trust_score = max(0.0, trust.trust_score - penalty)
                batch.status = "failed"

            # 提取真实任务结果（仅在信任时使用）
            real_results = {}
            if is_trusted:
                for challenge_id in batch._real_task_ids:
                    original_id = batch._original_task_map.get(challenge_id)
                    result = results.get(challenge_id)
                    if original_id and result:
                        real_results[original_id] = result

            # 始终提供原始任务 ID 列表（用于失败时重置任务）
            original_task_ids = [
                batch._original_task_map[cid]
                for cid in batch._real_task_ids
                if cid in batch._original_task_map
            ]

            # 移到已完成
            self.completed_batches[batch_id] = batch
            del self.pending_batches[batch_id]

            report = {
                "batch_id": batch_id,
                "miner_id": batch.miner_id,
                "is_trusted": is_trusted,
                "trap_total": trap_total,
                "trap_passed": trap_passed,
                "trap_pass_rate": trap_pass_rate,
                "trust_score_after": trust.trust_score,
                "consecutive_fails": trust.consecutive_fails,
                "is_banned": trust.is_banned,
                "real_results": real_results,
                "original_task_ids": original_task_ids,
                "trap_details": trap_details,
            }

            return is_trusted, report

    # ── 信任度查询 ──

    def get_trust_profile(self, miner_id: str) -> Dict:
        """获取矿工信任档案"""
        trust = self._get_or_create_trust(miner_id)
        return trust.to_dict()

    def get_trap_ratio(self, miner_id: str) -> float:
        """获取矿工当前陷阱比率"""
        trust = self._get_or_create_trust(miner_id)
        return trust.current_trap_ratio

    def unban_miner(self, miner_id: str) -> bool:
        """解禁矿工（治理行为）"""
        trust = self.trust_profiles.get(miner_id)
        if not trust:
            return False
        trust.is_banned = False
        trust.consecutive_fails = 0
        trust.trust_score = TRUST_LOW  # 重置到低信任
        return True

    def get_stats(self) -> Dict:
        """引擎统计"""
        total_miners = len(self.trust_profiles)
        banned = sum(1 for t in self.trust_profiles.values() if t.is_banned)
        high_trust = sum(1 for t in self.trust_profiles.values()
                         if t.trust_score >= TRUST_HIGH)
        avg_trust = (
            sum(t.trust_score for t in self.trust_profiles.values()) / total_miners
            if total_miners > 0 else 0.0
        )

        return {
            "total_miners": total_miners,
            "banned_miners": banned,
            "high_trust_miners": high_trust,
            "avg_trust_score": round(avg_trust, 4),
            "pending_batches": len(self.pending_batches),
            "completed_batches": len(self.completed_batches),
            "total_trap_ratio_savings": self._calc_savings(),
        }

    def _calc_savings(self) -> str:
        """计算相比旧多数派方案节省的算力百分比"""
        # 旧方案：每任务 redundancy=2 → 50% 浪费
        # 新方案：每任务 1 矿工 + ~10% 陷阱开销 → 90% 效率
        if not self.trust_profiles:
            return "尚无数据"
        avg_trap = sum(t.current_trap_ratio for t in self.trust_profiles.values()) / len(self.trust_profiles)
        old_waste = 0.50  # 旧方案 2 倍冗余 = 50% 浪费
        new_waste = avg_trap / (1 + avg_trap)
        saving = (old_waste - new_waste) / old_waste * 100
        return f"节省 {saving:.1f}% 算力（旧：{old_waste*100:.0f}% 浪费 → 新：{new_waste*100:.1f}% 陷阱开销）"
