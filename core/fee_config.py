"""
fee_config.py — 统一费率配置 (Single Source of Truth)

C-09 修复: 系统中所有费率常量统一在此定义。
其他模块（treasury.py, protocol_fee_pool.py, compute_market_v3.py, dao_treasury.py）
引用此模块，避免重复定义和不一致。

两类费率：
1. 协议级交易手续费（每笔链上交易扣取）:
   - 总费率 1.0%
   - 0.5% 销毁（通缩）
   - 0.3% 矿工激励
   - 0.2% 基金会/协议池（多签控制）

2. 算力市场结算费（算力订单完成时从结算金额扣取）:
   - 5% 平台费（基金会运维）
   - 90% 给算力提供者（矿工）
   - 5% 进国库（DAO 治理分配）
"""


class ProtocolFeeRates:
    """协议级交易手续费 — 不可由 DAO 修改（硬编码）。
    
    所有链上交易（转账、兑换等）均扣除此费率。
    """
    TOTAL = 0.01           # 1.0% 总费率
    BURN = 0.005           # 0.5% 永久销毁（通缩机制）
    MINER = 0.003          # 0.3% 矿工激励
    FOUNDATION = 0.002     # 0.2% 基金会/协议池（多签控制）
    
    # 基金会多签地址
    FOUNDATION_MULTISIG = "MAIN_FOUNDATION_MULTISIG_001"
    
    @classmethod
    def validate(cls) -> bool:
        """验证费率分配总和。"""
        return abs(cls.BURN + cls.MINER + cls.FOUNDATION - cls.TOTAL) < 1e-10


class ComputeMarketFeeRates:
    """算力市场结算费 — 可由 DAO 治理投票修改。
    
    算力订单完成结算时，从总金额按此比例分配。
    """
    PLATFORM = 0.05        # 5% 平台运维费
    MINER = 0.90           # 90% 给算力提供者
    TREASURY = 0.05        # 5% 进 DAO 国库
    
    # DAO 可调范围
    PLATFORM_RANGE = (0.0, 0.10)   # 0% - 10%
    MINER_RANGE = (0.80, 0.95)     # 80% - 95%
    TREASURY_RANGE = (0.0, 0.10)   # 0% - 10%
    
    @classmethod
    def validate(cls) -> bool:
        """验证分配总和。"""
        return abs(cls.PLATFORM + cls.MINER + cls.TREASURY - 1.0) < 1e-10


# 支付规则
PAYMENT_CURRENCY = "MAIN"  # 只能用 MAIN 支付
