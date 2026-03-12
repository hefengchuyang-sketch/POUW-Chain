# -*- coding: utf-8 -*-
"""
信誉系统优化模块 - 多维度评分与动态调整

协议层边界声明：
├── 模块：reputation_engine
├── 层级：SERVICE (服务层)
├── 类别：NON_CONSENSUS (非共识)
├── 共识影响：❌ 无
├── 出块影响：❌ 无 - 不影响出块权
├── 挖矿奖励：❌ 无 - 不影响挖矿奖励分配
└── 用途：任务调度优先级参考（仅建议性质）

重要限制（IMPORTANT CONSTRAINTS）：
1. 信誉分数不影响区块有效性
2. 信誉分数不影响出块权或出块概率
3. 信誉分数不影响挖矿奖励金额
4. 信誉系统仅用于任务调度的优先级参考
5. 低信誉矿工仍然可以正常挖矿和获得奖励

功能：
1. 多维度评分：任务完成质量、速度、成功率、用户评价
2. 任务类型权重：不同任务类型权重不同
3. 动态信誉调整：根据最近表现动态调整
4. 信誉加权调度：高信誉矿工优先分配任务（仅调度优化）

评分维度：
- quality_score: 任务完成质量 (0-100)
- speed_score: 完成速度评分 (0-100)
- success_rate: 成功率 (0-100)
- user_rating: 用户评价 (0-100)
- reliability_score: 可靠性评分 (0-100)
"""

import time
import json
import math
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import contextmanager


class TaskCategory(Enum):
    """任务类别"""
    AI_TRAINING = "ai_training"           # AI 训练
    AI_INFERENCE = "ai_inference"         # AI 推理
    RENDERING = "rendering"               # 渲染
    SCIENTIFIC = "scientific"             # 科学计算
    VIDEO_PROCESSING = "video_processing" # 视频处理
    DATA_PROCESSING = "data_processing"   # 数据处理
    GENERAL = "general"                   # 通用计算


class ReputationTier(Enum):
    """信誉等级"""
    LEGENDARY = "legendary"     # 传奇 (95+)
    DIAMOND = "diamond"         # 钻石 (90-95)
    PLATINUM = "platinum"       # 白金 (80-90)
    GOLD = "gold"               # 黄金 (70-80)
    SILVER = "silver"           # 白银 (60-70)
    BRONZE = "bronze"           # 青铜 (50-60)
    IRON = "iron"               # 铁 (40-50)
    UNRANKED = "unranked"       # 未定级 (<40 或新用户)


# 等级阈值
TIER_THRESHOLDS = {
    ReputationTier.LEGENDARY: 95,
    ReputationTier.DIAMOND: 90,
    ReputationTier.PLATINUM: 80,
    ReputationTier.GOLD: 70,
    ReputationTier.SILVER: 60,
    ReputationTier.BRONZE: 50,
    ReputationTier.IRON: 40,
    ReputationTier.UNRANKED: 0
}

# 任务类型权重
TASK_WEIGHTS = {
    TaskCategory.AI_TRAINING: 1.5,      # AI 训练权重最高
    TaskCategory.AI_INFERENCE: 1.3,
    TaskCategory.RENDERING: 1.2,
    TaskCategory.SCIENTIFIC: 1.4,
    TaskCategory.VIDEO_PROCESSING: 1.1,
    TaskCategory.DATA_PROCESSING: 1.0,
    TaskCategory.GENERAL: 1.0
}

# ========== 信誉影响力限制 ==========
# 这些限制确保信誉系统不会过度影响系统公平性

class ReputationInfluenceLimits:
    """
    信誉影响力限制
    
    重要：信誉系统只用于任务调度优化，不影响：
    - 出块权/出块概率
    - 挖矿奖励金额
    - 区块验证
    """
    
    # 调度权重上限：信誉最多影响调度优先级的 30%
    MAX_SCHEDULING_WEIGHT = 0.30
    
    # 最低保障：即使信誉为 0，也至少有 70% 的调度机会
    MIN_SCHEDULING_CHANCE = 0.70
    
    # 信誉惩罚上限：单次失败最多降低 5 分
    MAX_PENALTY_PER_FAILURE = 5.0
    
    # 信誉恢复速度：每完成一个任务最多恢复 2 分
    MAX_RECOVERY_PER_SUCCESS = 2.0
    
    # 新用户保护期：前 10 个任务不受信誉影响
    NEW_USER_PROTECTION_TASKS = 10
    
    # 信誉分数范围
    MIN_SCORE = 0.0
    MAX_SCORE = 100.0
    
    @classmethod
    def calculate_scheduling_factor(cls, reputation_score: float) -> float:
        """
        计算调度因子
        
        返回值范围: [MIN_SCHEDULING_CHANCE, 1.0]
        信誉分数对调度的影响被限制在 MAX_SCHEDULING_WEIGHT 范围内
        """
        # 归一化信誉分数到 0-1
        normalized = max(0, min(100, reputation_score)) / 100
        
        # 信誉带来的额外权重（最多 30%）
        bonus = normalized * cls.MAX_SCHEDULING_WEIGHT
        
        # 基础机会 + 信誉加成
        return cls.MIN_SCHEDULING_CHANCE + bonus
    
    @classmethod
    def is_protected(cls, total_tasks: int) -> bool:
        """检查是否在新用户保护期"""
        return total_tasks < cls.NEW_USER_PROTECTION_TASKS


@dataclass
class ReputationScore:
    """信誉评分"""
    # 五维度评分 (0-100)
    quality_score: float = 50.0      # 质量评分
    speed_score: float = 50.0        # 速度评分
    success_rate: float = 100.0      # 成功率
    user_rating: float = 50.0        # 用户评价
    reliability_score: float = 50.0  # 可靠性
    
    # 综合分数
    overall_score: float = 50.0
    
    # 等级
    tier: ReputationTier = ReputationTier.UNRANKED
    
    # 统计数据
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_reviews: int = 0
    
    # 时间加权因子
    recent_weight: float = 1.0       # 最近表现权重
    
    def to_dict(self) -> Dict:
        return {
            "quality_score": round(self.quality_score, 2),
            "speed_score": round(self.speed_score, 2),
            "success_rate": round(self.success_rate, 2),
            "user_rating": round(self.user_rating, 2),
            "reliability_score": round(self.reliability_score, 2),
            "overall_score": round(self.overall_score, 2),
            "tier": self.tier.value,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_reviews": self.total_reviews,
            "recent_weight": round(self.recent_weight, 3)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ReputationScore':
        return cls(
            quality_score=data.get("quality_score", 50.0),
            speed_score=data.get("speed_score", 50.0),
            success_rate=data.get("success_rate", 100.0),
            user_rating=data.get("user_rating", 50.0),
            reliability_score=data.get("reliability_score", 50.0),
            overall_score=data.get("overall_score", 50.0),
            tier=ReputationTier(data.get("tier", "unranked")),
            total_tasks=data.get("total_tasks", 0),
            successful_tasks=data.get("successful_tasks", 0),
            failed_tasks=data.get("failed_tasks", 0),
            total_reviews=data.get("total_reviews", 0),
            recent_weight=data.get("recent_weight", 1.0)
        )


@dataclass
class TaskRecord:
    """任务记录"""
    record_id: str
    miner_address: str
    task_id: str
    task_category: TaskCategory
    
    # 表现数据
    success: bool = True
    quality: float = 0                   # 质量评分 (0-100)
    expected_duration: float = 0         # 预期耗时（秒）
    actual_duration: float = 0           # 实际耗时（秒）
    
    # 验证
    verified: bool = False
    verified_by: str = ""
    
    # 时间戳
    started_at: float = 0
    completed_at: float = 0
    recorded_at: float = field(default_factory=time.time)
    
    def speed_ratio(self) -> float:
        """速度比率（预期/实际，>1 表示更快）"""
        if self.actual_duration <= 0:
            return 1.0
        return self.expected_duration / self.actual_duration
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "miner_address": self.miner_address,
            "task_id": self.task_id,
            "task_category": self.task_category.value,
            "success": self.success,
            "quality": self.quality,
            "expected_duration": self.expected_duration,
            "actual_duration": self.actual_duration,
            "verified": self.verified,
            "verified_by": self.verified_by,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "recorded_at": self.recorded_at
        }


@dataclass
class UserReview:
    """用户评价"""
    review_id: str
    miner_address: str
    reviewer_address: str
    task_id: str
    
    # 评分 (1-5)
    rating: float = 5.0
    
    # 细分评分 (可选, 1-5)
    quality_rating: Optional[float] = None
    speed_rating: Optional[float] = None
    communication_rating: Optional[float] = None
    
    # 评论
    comment: str = ""
    
    # 权重（评价者的信誉影响权重）
    weight: float = 1.0
    
    timestamp: float = field(default_factory=time.time)
    
    def normalized_rating(self) -> float:
        """将 1-5 转为 0-100"""
        return (self.rating - 1) * 25
    
    def to_dict(self) -> Dict:
        return {
            "review_id": self.review_id,
            "miner_address": self.miner_address,
            "reviewer_address": self.reviewer_address,
            "task_id": self.task_id,
            "rating": self.rating,
            "quality_rating": self.quality_rating,
            "speed_rating": self.speed_rating,
            "communication_rating": self.communication_rating,
            "comment": self.comment,
            "weight": self.weight,
            "timestamp": self.timestamp
        }


class ReputationEngine:
    """
    信誉引擎
    
    核心功能：
    1. 多维度评分计算
    2. 动态信誉调整
    3. 等级评定
    4. 加权调度支持
    """
    
    # 评分维度权重
    DIMENSION_WEIGHTS = {
        "quality": 0.30,      # 质量权重
        "speed": 0.20,        # 速度权重
        "success_rate": 0.25, # 成功率权重
        "user_rating": 0.15,  # 用户评价权重
        "reliability": 0.10   # 可靠性权重
    }
    
    # 时间衰减参数
    TIME_DECAY_HALF_LIFE = 30 * 24 * 3600  # 30 天半衰期
    
    # 最小任务数（达到才有可靠评分）
    MIN_TASKS_FOR_RATING = 5
    
    # 信誉变化限制
    MAX_DAILY_CHANGE = 10        # 每日最大变化
    MAX_SINGLE_CHANGE = 5        # 单次最大变化
    
    def __init__(self, db_path: str = "data/reputation.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """初始化数据库"""
        with self._conn() as conn:
            # 矿工信誉表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS miner_reputations (
                    miner_address TEXT PRIMARY KEY,
                    reputation_data TEXT NOT NULL,
                    quality_score REAL DEFAULT 50,
                    speed_score REAL DEFAULT 50,
                    success_rate REAL DEFAULT 100,
                    user_rating REAL DEFAULT 50,
                    reliability_score REAL DEFAULT 50,
                    overall_score REAL DEFAULT 50,
                    tier TEXT DEFAULT 'unranked',
                    total_tasks INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL
                )
            """)
            
            # 任务记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_records (
                    record_id TEXT PRIMARY KEY,
                    miner_address TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_category TEXT NOT NULL,
                    success INTEGER DEFAULT 1,
                    quality REAL DEFAULT 0,
                    expected_duration REAL,
                    actual_duration REAL,
                    verified INTEGER DEFAULT 0,
                    recorded_at REAL NOT NULL
                )
            """)
            
            # 用户评价表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_reviews (
                    review_id TEXT PRIMARY KEY,
                    miner_address TEXT NOT NULL,
                    reviewer_address TEXT NOT NULL,
                    task_id TEXT,
                    rating REAL NOT NULL,
                    quality_rating REAL,
                    speed_rating REAL,
                    weight REAL DEFAULT 1,
                    comment TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            
            # 每日变化记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_address TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_change REAL DEFAULT 0,
                    UNIQUE(miner_address, date)
                )
            """)
            
            # 类别专精表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS category_specialization (
                    miner_address TEXT NOT NULL,
                    category TEXT NOT NULL,
                    score REAL DEFAULT 50,
                    task_count INTEGER DEFAULT 0,
                    last_updated REAL,
                    PRIMARY KEY (miner_address, category)
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reputation_score ON miner_reputations(overall_score)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_miner ON task_records(miner_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_miner ON user_reviews(miner_address)")
    
    # ============== 信誉初始化与获取 ==============
    
    def get_reputation(self, miner_address: str) -> ReputationScore:
        """获取矿工信誉"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT reputation_data FROM miner_reputations WHERE miner_address = ?",
                (miner_address,)
            ).fetchone()
            
            if row:
                return ReputationScore.from_dict(json.loads(row["reputation_data"]))
        
        # 返回默认信誉
        return ReputationScore()
    
    def initialize_reputation(self, miner_address: str,
                              initial_score: float = 50.0) -> ReputationScore:
        """初始化矿工信誉"""
        reputation = ReputationScore(
            quality_score=initial_score,
            speed_score=initial_score,
            success_rate=100.0,
            user_rating=initial_score,
            reliability_score=initial_score,
            overall_score=initial_score,
            tier=self._calculate_tier(initial_score)
        )
        
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO miner_reputations (
                    miner_address, reputation_data, quality_score, speed_score,
                    success_rate, user_rating, reliability_score, overall_score,
                    tier, total_tasks, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                miner_address, json.dumps(reputation.to_dict()),
                reputation.quality_score, reputation.speed_score,
                reputation.success_rate, reputation.user_rating,
                reputation.reliability_score, reputation.overall_score,
                reputation.tier.value, 0, time.time(), time.time()
            ))
        
        return reputation
    
    # ============== 任务记录 ==============
    
    def record_task_completion(self,
                               miner_address: str,
                               task_id: str,
                               category: TaskCategory,
                               success: bool,
                               quality: float,
                               expected_duration: float,
                               actual_duration: float,
                               verified: bool = False,
                               verified_by: str = "") -> Tuple[bool, str]:
        """
        记录任务完成情况
        """
        import hashlib
        record_id = f"REC_{hashlib.sha256(f'{miner_address}{task_id}{time.time()}'.encode()).hexdigest()[:12]}"
        
        record = TaskRecord(
            record_id=record_id,
            miner_address=miner_address,
            task_id=task_id,
            task_category=category,
            success=success,
            quality=quality,
            expected_duration=expected_duration,
            actual_duration=actual_duration,
            verified=verified,
            verified_by=verified_by,
            completed_at=time.time()
        )
        
        # 保存记录
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO task_records (
                    record_id, miner_address, task_id, task_category,
                    success, quality, expected_duration, actual_duration,
                    verified, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id, record.miner_address, record.task_id,
                record.task_category.value, 1 if record.success else 0,
                record.quality, record.expected_duration, record.actual_duration,
                1 if record.verified else 0, record.recorded_at
            ))
        
        # 更新信誉
        self._update_reputation_from_task(miner_address, record)
        
        # 更新类别专精
        self._update_category_specialization(miner_address, category, quality)
        
        return True, f"任务记录已添加: {record_id}"
    
    def add_user_review(self,
                        miner_address: str,
                        reviewer_address: str,
                        rating: float,
                        task_id: str = "",
                        quality_rating: float = None,
                        speed_rating: float = None,
                        comment: str = "") -> Tuple[bool, str]:
        """
        添加用户评价
        """
        if not 1 <= rating <= 5:
            return False, "评分必须在 1-5 之间"
        
        import hashlib
        review_id = f"REV_{hashlib.sha256(f'{miner_address}{reviewer_address}{time.time()}'.encode()).hexdigest()[:12]}"
        
        # 获取评价者权重（基于其信誉）
        reviewer_rep = self.get_reputation(reviewer_address)
        weight = 0.5 + (reviewer_rep.overall_score / 200)  # 0.5-1.0 权重
        
        review = UserReview(
            review_id=review_id,
            miner_address=miner_address,
            reviewer_address=reviewer_address,
            task_id=task_id,
            rating=rating,
            quality_rating=quality_rating,
            speed_rating=speed_rating,
            comment=comment,
            weight=weight
        )
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO user_reviews (
                    review_id, miner_address, reviewer_address, task_id,
                    rating, quality_rating, speed_rating, weight, comment, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                review.review_id, review.miner_address, review.reviewer_address,
                review.task_id, review.rating, review.quality_rating,
                review.speed_rating, review.weight, review.comment, review.timestamp
            ))
        
        # 更新信誉
        self._update_reputation_from_review(miner_address, review)
        
        return True, f"评价已添加: {review_id}"
    
    # ============== 信誉计算 ==============
    
    def recalculate_reputation(self, miner_address: str) -> ReputationScore:
        """
        重新计算矿工信誉
        """
        with self._conn() as conn:
            # 获取任务记录
            task_rows = conn.execute("""
                SELECT * FROM task_records 
                WHERE miner_address = ? 
                ORDER BY recorded_at DESC LIMIT 100
            """, (miner_address,)).fetchall()
            
            # 获取用户评价
            review_rows = conn.execute("""
                SELECT * FROM user_reviews 
                WHERE miner_address = ? 
                ORDER BY timestamp DESC LIMIT 50
            """, (miner_address,)).fetchall()
        
        now = time.time()
        
        # ========== 计算质量评分 ==========
        quality_sum = 0
        quality_weight_sum = 0
        for row in task_rows:
            age = now - row["recorded_at"]
            time_weight = self._time_decay(age)
            task_weight = TASK_WEIGHTS.get(TaskCategory(row["task_category"]), 1.0)
            
            weight = time_weight * task_weight
            quality_sum += row["quality"] * weight
            quality_weight_sum += weight
        
        quality_score = quality_sum / quality_weight_sum if quality_weight_sum > 0 else 50
        
        # ========== 计算速度评分 ==========
        speed_scores = []
        for row in task_rows:
            if row["expected_duration"] and row["actual_duration"]:
                ratio = row["expected_duration"] / max(row["actual_duration"], 1)
                # 转换为 0-100 分数
                speed_score = min(100, max(0, 50 + (ratio - 1) * 50))
                age = now - row["recorded_at"]
                time_weight = self._time_decay(age)
                speed_scores.append((speed_score, time_weight))
        
        if speed_scores:
            speed_score = sum(s * w for s, w in speed_scores) / sum(w for _, w in speed_scores)
        else:
            speed_score = 50
        
        # ========== 计算成功率 ==========
        total_tasks = len(task_rows)
        successful_tasks = sum(1 for row in task_rows if row["success"])
        success_rate = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 100
        
        # ========== 计算用户评价 ==========
        if review_rows:
            rating_sum = 0
            rating_weight_sum = 0
            for row in review_rows:
                age = now - row["timestamp"]
                time_weight = self._time_decay(age)
                reviewer_weight = row["weight"]
                
                weight = time_weight * reviewer_weight
                normalized_rating = (row["rating"] - 1) * 25  # 1-5 -> 0-100
                rating_sum += normalized_rating * weight
                rating_weight_sum += weight
            
            user_rating = rating_sum / rating_weight_sum if rating_weight_sum > 0 else 50
        else:
            user_rating = 50
        
        # ========== 计算可靠性 ==========
        # 基于上线时间、任务完成规律性等
        reliability_score = self._calculate_reliability(miner_address, task_rows)
        
        # ========== 计算综合分数 ==========
        overall_score = (
            quality_score * self.DIMENSION_WEIGHTS["quality"] +
            speed_score * self.DIMENSION_WEIGHTS["speed"] +
            success_rate * self.DIMENSION_WEIGHTS["success_rate"] +
            user_rating * self.DIMENSION_WEIGHTS["user_rating"] +
            reliability_score * self.DIMENSION_WEIGHTS["reliability"]
        )
        
        # 计算最近表现权重
        recent_weight = self._calculate_recent_weight(task_rows)
        
        # 确定等级
        tier = self._calculate_tier(overall_score)
        
        # 创建信誉对象
        reputation = ReputationScore(
            quality_score=quality_score,
            speed_score=speed_score,
            success_rate=success_rate,
            user_rating=user_rating,
            reliability_score=reliability_score,
            overall_score=overall_score,
            tier=tier,
            total_tasks=total_tasks,
            successful_tasks=successful_tasks,
            failed_tasks=total_tasks - successful_tasks,
            total_reviews=len(review_rows),
            recent_weight=recent_weight
        )
        
        # 保存
        self._save_reputation(miner_address, reputation)
        
        return reputation
    
    def _update_reputation_from_task(self, miner_address: str, record: TaskRecord):
        """根据任务记录更新信誉"""
        current = self.get_reputation(miner_address)
        
        # 计算质量变化
        quality_delta = (record.quality - current.quality_score) * 0.1
        
        # 计算速度变化
        speed_ratio = record.speed_ratio()
        speed_score = min(100, max(0, 50 + (speed_ratio - 1) * 50))
        speed_delta = (speed_score - current.speed_score) * 0.1
        
        # 计算成功率变化
        if record.success:
            new_success_rate = ((current.success_rate * current.total_tasks) + 100) / (current.total_tasks + 1)
        else:
            new_success_rate = (current.success_rate * current.total_tasks) / (current.total_tasks + 1)
        
        # 任务类型权重
        task_weight = TASK_WEIGHTS.get(record.task_category, 1.0)
        
        # 应用变化限制
        quality_delta = self._limit_change(quality_delta * task_weight)
        speed_delta = self._limit_change(speed_delta * task_weight)
        
        # 检查每日限制
        if not self._check_daily_limit(miner_address, abs(quality_delta) + abs(speed_delta)):
            quality_delta *= 0.5
            speed_delta *= 0.5
        
        # 更新分数
        new_reputation = ReputationScore(
            quality_score=min(100, max(0, current.quality_score + quality_delta)),
            speed_score=min(100, max(0, current.speed_score + speed_delta)),
            success_rate=new_success_rate,
            user_rating=current.user_rating,
            reliability_score=current.reliability_score,
            total_tasks=current.total_tasks + 1,
            successful_tasks=current.successful_tasks + (1 if record.success else 0),
            failed_tasks=current.failed_tasks + (0 if record.success else 1),
            total_reviews=current.total_reviews
        )
        
        # 重算综合分数和等级
        new_reputation.overall_score = self._calculate_overall(new_reputation)
        new_reputation.tier = self._calculate_tier(new_reputation.overall_score)
        
        # 保存
        self._save_reputation(miner_address, new_reputation)
        self._record_daily_change(miner_address, abs(quality_delta) + abs(speed_delta))
    
    def _update_reputation_from_review(self, miner_address: str, review: UserReview):
        """根据用户评价更新信誉"""
        current = self.get_reputation(miner_address)
        
        # 计算新的用户评价分数
        normalized_rating = review.normalized_rating()
        
        # 加权平均
        if current.total_reviews > 0:
            new_user_rating = (
                current.user_rating * current.total_reviews + normalized_rating * review.weight
            ) / (current.total_reviews + review.weight)
        else:
            new_user_rating = normalized_rating
        
        # 应用变化
        rating_delta = self._limit_change(new_user_rating - current.user_rating)
        
        new_reputation = ReputationScore(
            quality_score=current.quality_score,
            speed_score=current.speed_score,
            success_rate=current.success_rate,
            user_rating=min(100, max(0, current.user_rating + rating_delta)),
            reliability_score=current.reliability_score,
            total_tasks=current.total_tasks,
            successful_tasks=current.successful_tasks,
            failed_tasks=current.failed_tasks,
            total_reviews=current.total_reviews + 1
        )
        
        new_reputation.overall_score = self._calculate_overall(new_reputation)
        new_reputation.tier = self._calculate_tier(new_reputation.overall_score)
        
        self._save_reputation(miner_address, new_reputation)
    
    # ============== 辅助计算方法 ==============
    
    def _time_decay(self, age_seconds: float) -> float:
        """时间衰减函数（半衰期）"""
        return math.pow(0.5, age_seconds / self.TIME_DECAY_HALF_LIFE)
    
    def _calculate_tier(self, score: float) -> ReputationTier:
        """根据分数计算等级"""
        for tier, threshold in TIER_THRESHOLDS.items():
            if score >= threshold:
                return tier
        return ReputationTier.UNRANKED
    
    def _calculate_overall(self, rep: ReputationScore) -> float:
        """计算综合分数"""
        return (
            rep.quality_score * self.DIMENSION_WEIGHTS["quality"] +
            rep.speed_score * self.DIMENSION_WEIGHTS["speed"] +
            rep.success_rate * self.DIMENSION_WEIGHTS["success_rate"] +
            rep.user_rating * self.DIMENSION_WEIGHTS["user_rating"] +
            rep.reliability_score * self.DIMENSION_WEIGHTS["reliability"]
        )
    
    def _calculate_reliability(self, miner_address: str, task_rows: list) -> float:
        """计算可靠性评分"""
        if len(task_rows) < self.MIN_TASKS_FOR_RATING:
            return 50  # 数据不足
        
        # 基于任务完成的规律性
        intervals = []
        for i in range(len(task_rows) - 1):
            interval = task_rows[i]["recorded_at"] - task_rows[i+1]["recorded_at"]
            intervals.append(interval)
        
        if not intervals:
            return 50
        
        avg_interval = sum(intervals) / len(intervals)
        variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
        std_dev = math.sqrt(variance)
        
        # 标准差越小，可靠性越高
        cv = std_dev / avg_interval if avg_interval > 0 else 1
        reliability = max(0, min(100, 100 - cv * 50))
        
        return reliability
    
    def _calculate_recent_weight(self, task_rows: list) -> float:
        """计算最近表现权重"""
        now = time.time()
        recent_tasks = [r for r in task_rows if now - r["recorded_at"] < 7 * 24 * 3600]
        
        if not recent_tasks:
            return 0.8  # 最近不活跃，降低权重
        
        # 最近任务的平均质量
        recent_quality = sum(r["quality"] for r in recent_tasks) / len(recent_tasks)
        
        # 相对于基准的表现
        weight = 0.8 + (recent_quality - 50) / 250  # 0.6-1.0
        return max(0.6, min(1.2, weight))
    
    def _limit_change(self, change: float) -> float:
        """限制单次变化幅度"""
        return max(-self.MAX_SINGLE_CHANGE, min(self.MAX_SINGLE_CHANGE, change))
    
    def _check_daily_limit(self, miner_address: str, change: float) -> bool:
        """检查每日变化限制"""
        today = time.strftime("%Y-%m-%d")
        
        with self._conn() as conn:
            row = conn.execute("""
                SELECT total_change FROM daily_changes 
                WHERE miner_address = ? AND date = ?
            """, (miner_address, today)).fetchone()
            
            current = row["total_change"] if row else 0
            return (current + change) <= self.MAX_DAILY_CHANGE
    
    def _record_daily_change(self, miner_address: str, change: float):
        """记录每日变化"""
        today = time.strftime("%Y-%m-%d")
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO daily_changes (miner_address, date, total_change)
                VALUES (?, ?, ?)
                ON CONFLICT(miner_address, date) DO UPDATE SET
                total_change = total_change + ?
            """, (miner_address, today, change, change))
    
    def _update_category_specialization(self, miner_address: str,
                                         category: TaskCategory, quality: float):
        """更新类别专精"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT score, task_count FROM category_specialization 
                WHERE miner_address = ? AND category = ?
            """, (miner_address, category.value)).fetchone()
            
            if row:
                new_count = row["task_count"] + 1
                new_score = (row["score"] * row["task_count"] + quality) / new_count
                conn.execute("""
                    UPDATE category_specialization 
                    SET score = ?, task_count = ?, last_updated = ?
                    WHERE miner_address = ? AND category = ?
                """, (new_score, new_count, time.time(), miner_address, category.value))
            else:
                conn.execute("""
                    INSERT INTO category_specialization (
                        miner_address, category, score, task_count, last_updated
                    ) VALUES (?, ?, ?, ?, ?)
                """, (miner_address, category.value, quality, 1, time.time()))
    
    def _save_reputation(self, miner_address: str, reputation: ReputationScore):
        """保存信誉"""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO miner_reputations (
                    miner_address, reputation_data, quality_score, speed_score,
                    success_rate, user_rating, reliability_score, overall_score,
                    tier, total_tasks, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT created_at FROM miner_reputations WHERE miner_address = ?),
                    ?
                ), ?)
            """, (
                miner_address, json.dumps(reputation.to_dict()),
                reputation.quality_score, reputation.speed_score,
                reputation.success_rate, reputation.user_rating,
                reputation.reliability_score, reputation.overall_score,
                reputation.tier.value, reputation.total_tasks,
                miner_address, time.time(), time.time()
            ))
    
    # ============== 查询接口 ==============
    
    def get_top_miners(self, limit: int = 20, 
                       category: TaskCategory = None) -> List[Dict]:
        """获取顶级矿工"""
        with self._conn() as conn:
            if category:
                rows = conn.execute("""
                    SELECT m.miner_address, m.reputation_data, c.score as category_score
                    FROM miner_reputations m
                    LEFT JOIN category_specialization c 
                    ON m.miner_address = c.miner_address AND c.category = ?
                    ORDER BY COALESCE(c.score, m.overall_score) DESC
                    LIMIT ?
                """, (category.value, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT miner_address, reputation_data FROM miner_reputations
                    ORDER BY overall_score DESC LIMIT ?
                """, (limit,)).fetchall()
        
        return [
            {
                "address": row["miner_address"],
                "reputation": json.loads(row["reputation_data"])
            }
            for row in rows
        ]
    
    def get_category_specialists(self, category: TaskCategory,
                                  min_tasks: int = 10,
                                  limit: int = 20) -> List[Dict]:
        """获取特定类别的专家矿工"""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT c.miner_address, c.score, c.task_count, m.reputation_data
                FROM category_specialization c
                JOIN miner_reputations m ON c.miner_address = m.miner_address
                WHERE c.category = ? AND c.task_count >= ?
                ORDER BY c.score DESC LIMIT ?
            """, (category.value, min_tasks, limit)).fetchall()
        
        return [
            {
                "address": row["miner_address"],
                "category_score": row["score"],
                "task_count": row["task_count"],
                "overall_reputation": json.loads(row["reputation_data"])
            }
            for row in rows
        ]
    
    def get_weighted_candidates(self, category: TaskCategory = None,
                                 min_score: float = 40,
                                 limit: int = 50) -> List[Tuple[str, float]]:
        """
        获取加权任务调度候选人
        返回 [(address, weight), ...]，权重用于随机选择
        """
        with self._conn() as conn:
            if category:
                rows = conn.execute("""
                    SELECT m.miner_address, m.overall_score, 
                           COALESCE(c.score, m.overall_score) as effective_score
                    FROM miner_reputations m
                    LEFT JOIN category_specialization c 
                    ON m.miner_address = c.miner_address AND c.category = ?
                    WHERE m.overall_score >= ?
                    ORDER BY effective_score DESC LIMIT ?
                """, (category.value, min_score, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT miner_address, overall_score, overall_score as effective_score
                    FROM miner_reputations
                    WHERE overall_score >= ?
                    ORDER BY overall_score DESC LIMIT ?
                """, (min_score, limit)).fetchall()
        
        # 计算权重（分数的平方，放大差异）
        candidates = []
        for row in rows:
            score = row["effective_score"]
            weight = (score / 100) ** 2  # 归一化并平方
            candidates.append((row["miner_address"], weight))
        
        return candidates
    
    def get_miner_history(self, miner_address: str,
                           days: int = 30) -> Dict:
        """获取矿工历史数据"""
        cutoff = time.time() - days * 24 * 3600
        
        with self._conn() as conn:
            # 任务记录
            tasks = conn.execute("""
                SELECT * FROM task_records 
                WHERE miner_address = ? AND recorded_at > ?
                ORDER BY recorded_at DESC
            """, (miner_address, cutoff)).fetchall()
            
            # 用户评价
            reviews = conn.execute("""
                SELECT * FROM user_reviews 
                WHERE miner_address = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (miner_address, cutoff)).fetchall()
            
            # 类别专精
            specializations = conn.execute("""
                SELECT category, score, task_count FROM category_specialization
                WHERE miner_address = ?
            """, (miner_address,)).fetchall()
        
        return {
            "tasks": [dict(t) for t in tasks],
            "reviews": [dict(r) for r in reviews],
            "specializations": {s["category"]: {"score": s["score"], "count": s["task_count"]} 
                               for s in specializations}
        }


# 全局实例
_reputation_engine: Optional[ReputationEngine] = None

def get_reputation_engine(db_path: str = "data/reputation.db") -> ReputationEngine:
    """获取信誉引擎实例"""
    global _reputation_engine
    if _reputation_engine is None:
        _reputation_engine = ReputationEngine(db_path)
    return _reputation_engine
