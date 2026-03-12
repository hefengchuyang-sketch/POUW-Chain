# -*- coding: utf-8 -*-
"""
PoUW 出块类型定义 - 明确无任务情况下的出块规则

协议层边界声明：
├── 模块：pouw_block_types
├── 层级：PROTOCOL (协议层)
├── 类别：CONSENSUS_CRITICAL (共识关键)
├── 共识影响：✓ 影响区块有效性
└── 确定性要求：✓ 必须

设计原则：
1. PoUW 以有用工作为主，但网络安全与连续性也被承认是工作
2. 无任务时链不停摆，但奖励衰减
3. 三种出块类型有明确的触发条件和奖励规则

出块类型：
- TASK_BLOCK: 有有效算力任务，全额奖励
- IDLE_BLOCK: 无任务但节点在线，基础奖励的 20%
- VALIDATION_BLOCK: 只参与验证/见证，极低奖励
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


class BlockType(Enum):
    """PoUW 出块类型"""
    TASK_BLOCK = "task_block"             # 任务区块：有有效算力任务
    IDLE_BLOCK = "idle_block"             # 空闲区块：无任务但节点在线
    VALIDATION_BLOCK = "validation_block" # 验证区块：只参与验证/见证


class BlockRewardTier(Enum):
    """奖励等级"""
    FULL = "full"           # 全额奖励
    REDUCED = "reduced"     # 缩减奖励
    MINIMAL = "minimal"     # 最小奖励


@dataclass
class BlockTypeDefinition:
    """出块类型定义"""
    block_type: BlockType
    description: str
    
    # 触发条件
    requires_task: bool                    # 是否需要有任务
    requires_online: bool                  # 是否需要在线
    requires_witness: bool                 # 是否需要见证
    
    # 奖励规则
    reward_tier: BlockRewardTier
    reward_multiplier: float               # 奖励乘数（相对于全额）
    
    # 约束
    max_consecutive: int                   # 最大连续出块数（防止滥用）
    min_interval_seconds: int              # 最小出块间隔
    
    # 验证要求
    min_witnesses: int                     # 最少见证数
    difficulty_adjustment: float           # 难度调整因子


# ========== 出块类型配置 ==========

BLOCK_TYPE_DEFINITIONS: Dict[BlockType, BlockTypeDefinition] = {
    
    BlockType.TASK_BLOCK: BlockTypeDefinition(
        block_type=BlockType.TASK_BLOCK,
        description="任务区块：包含已完成的有效算力任务，获得全额板块币奖励",
        requires_task=True,
        requires_online=True,
        requires_witness=True,
        reward_tier=BlockRewardTier.FULL,
        reward_multiplier=1.0,              # 100% 奖励
        max_consecutive=0,                  # 无限制
        min_interval_seconds=10,            # 最小 10 秒
        min_witnesses=2,                    # 需要 2 个见证
        difficulty_adjustment=1.0           # 标准难度
    ),
    
    BlockType.IDLE_BLOCK: BlockTypeDefinition(
        block_type=BlockType.IDLE_BLOCK,
        description="空闲区块：无算力任务但节点保持在线，获得基础奖励的 20%",
        requires_task=False,
        requires_online=True,
        requires_witness=True,
        reward_tier=BlockRewardTier.REDUCED,
        reward_multiplier=0.20,             # 20% 奖励
        max_consecutive=10,                 # 最多连续 10 个空闲块
        min_interval_seconds=60,            # 最小 60 秒（比任务块慢）
        min_witnesses=1,                    # 只需 1 个见证
        difficulty_adjustment=0.5           # 降低难度
    ),
    
    BlockType.VALIDATION_BLOCK: BlockTypeDefinition(
        block_type=BlockType.VALIDATION_BLOCK,
        description="验证区块：只参与验证和见证他人任务，获得极低奖励",
        requires_task=False,
        requires_online=True,
        requires_witness=False,             # 自己就是见证者
        reward_tier=BlockRewardTier.MINIMAL,
        reward_multiplier=0.05,             # 5% 奖励
        max_consecutive=5,                  # 最多连续 5 个验证块
        min_interval_seconds=120,           # 最小 120 秒
        min_witnesses=0,
        difficulty_adjustment=0.3           # 大幅降低难度
    ),
}


# ========== 奖励衰减规则 ==========

class RewardDecayRules:
    """
    奖励衰减规则
    
    无任务情况下的奖励衰减机制，确保：
    1. 链不停摆
    2. 有任务时优先激励
    3. 防止空闲挖矿滥用
    """
    
    # 连续空闲块衰减
    IDLE_DECAY_PER_BLOCK = 0.10           # 每个连续空闲块衰减 10%
    IDLE_MIN_REWARD = 0.05                # 最低保留 5%
    
    # 验证块衰减
    VALIDATION_DECAY_PER_BLOCK = 0.20     # 每个连续验证块衰减 20%
    VALIDATION_MIN_REWARD = 0.01          # 最低保留 1%
    
    # 恢复规则
    TASK_RESETS_DECAY = True              # 任务块重置衰减
    
    @classmethod
    def calculate_reward(
        cls,
        block_type: BlockType,
        base_reward: float,
        consecutive_count: int
    ) -> float:
        """
        计算实际奖励
        
        Args:
            block_type: 出块类型
            base_reward: 基础奖励
            consecutive_count: 连续同类型块数量
            
        Returns:
            float: 实际奖励
        """
        definition = BLOCK_TYPE_DEFINITIONS[block_type]
        
        # 基础乘数
        reward = base_reward * definition.reward_multiplier
        
        # 衰减计算
        if block_type == BlockType.IDLE_BLOCK:
            decay = (1 - cls.IDLE_DECAY_PER_BLOCK) ** consecutive_count
            reward *= max(decay, cls.IDLE_MIN_REWARD / definition.reward_multiplier)
            
        elif block_type == BlockType.VALIDATION_BLOCK:
            decay = (1 - cls.VALIDATION_DECAY_PER_BLOCK) ** consecutive_count
            reward *= max(decay, cls.VALIDATION_MIN_REWARD / definition.reward_multiplier)
        
        return round(reward, 8)


# ========== 链活性约束 ==========

class LivenessConstraints:
    """
    最小活性约束
    
    确保链在无任务情况下不会停摆
    """
    
    # 最大空块间隔（秒）
    MAX_EMPTY_INTERVAL = 600              # 10 分钟必须有块
    
    # 强制出块阈值
    FORCE_BLOCK_AFTER_SECONDS = 300       # 5 分钟无块则强制出空闲块
    
    # 网络健康指标
    MIN_ONLINE_MINERS_RATIO = 0.10        # 至少 10% 矿工在线
    
    # 紧急模式
    EMERGENCY_MODE_THRESHOLD = 0.05       # 低于 5% 在线进入紧急模式
    EMERGENCY_REWARD_BOOST = 2.0          # 紧急模式奖励翻倍
    
    @classmethod
    def should_force_block(
        cls,
        seconds_since_last_block: float,
        pending_tasks: int
    ) -> tuple[bool, BlockType]:
        """
        判断是否应该强制出块
        
        Returns:
            (should_force, block_type)
        """
        if pending_tasks > 0:
            return False, BlockType.TASK_BLOCK
        
        if seconds_since_last_block >= cls.FORCE_BLOCK_AFTER_SECONDS:
            return True, BlockType.IDLE_BLOCK
        
        return False, BlockType.TASK_BLOCK
    
    @classmethod
    def is_network_healthy(
        cls,
        online_miners: int,
        total_miners: int
    ) -> tuple[bool, str]:
        """
        检查网络健康状态
        
        Returns:
            (is_healthy, status_message)
        """
        if total_miners == 0:
            return False, "无注册矿工"
        
        ratio = online_miners / total_miners
        
        if ratio < cls.EMERGENCY_MODE_THRESHOLD:
            return False, f"紧急模式：仅 {ratio:.1%} 矿工在线"
        
        if ratio < cls.MIN_ONLINE_MINERS_RATIO:
            return False, f"警告：仅 {ratio:.1%} 矿工在线"
        
        return True, f"正常：{ratio:.1%} 矿工在线"


# ========== 出块类型选择器 ==========

class BlockTypeSelector:
    """
    出块类型选择器
    
    根据网络状态自动选择合适的出块类型
    """
    
    @staticmethod
    def select(
        has_pending_tasks: bool,
        miner_is_online: bool,
        miner_is_witness: bool,
        consecutive_idle_blocks: int,
        consecutive_validation_blocks: int
    ) -> tuple[BlockType, str]:
        """
        选择出块类型
        
        Returns:
            (block_type, reason)
        """
        # 优先级 1: 有任务就出任务块
        if has_pending_tasks and miner_is_online:
            return BlockType.TASK_BLOCK, "有待处理任务"
        
        # 优先级 2: 没任务但可以见证
        if miner_is_witness and miner_is_online:
            definition = BLOCK_TYPE_DEFINITIONS[BlockType.VALIDATION_BLOCK]
            if consecutive_validation_blocks < definition.max_consecutive:
                return BlockType.VALIDATION_BLOCK, "无任务，参与见证"
        
        # 优先级 3: 空闲但在线
        if miner_is_online:
            definition = BLOCK_TYPE_DEFINITIONS[BlockType.IDLE_BLOCK]
            if consecutive_idle_blocks < definition.max_consecutive:
                return BlockType.IDLE_BLOCK, "无任务，保持在线"
        
        # 默认：不出块
        return None, "条件不满足，不出块"


# ========== 导出 ==========

def get_block_type_definition(block_type: BlockType) -> BlockTypeDefinition:
    """获取出块类型定义"""
    return BLOCK_TYPE_DEFINITIONS.get(block_type)


def list_block_types() -> List[Dict[str, Any]]:
    """列出所有出块类型"""
    return [
        {
            "type": bt.value,
            "description": definition.description,
            "reward_multiplier": definition.reward_multiplier,
            "requires_task": definition.requires_task
        }
        for bt, definition in BLOCK_TYPE_DEFINITIONS.items()
    ]
