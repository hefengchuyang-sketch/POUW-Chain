"""
Core 模块 - POUW 多板块区块链核心组件

核心层：
- Block, ConsensusEngine: 统一共识（consensus.py）
- Transaction, TxType: 链上交易
- Account: 账户模型
- UTXOStore: UTXO 存储
- SectorCoinLedger: 板块币账本

算力市场：
- ComputeMarketV3, ComputeScheduler: 算力交易市场与调度
- PoUWExecutor, POUWScoringEngine, SandboxExecutor: 任务执行与评分
- MinerRegistry: 矿工注册
- GranularBillingEngine: 细粒度计费
- DynamicPricingEngine: 动态定价

安全与治理：
- UnifiedConsensus: 统一共识引擎
- DAOGovernance, TreasuryManager: DAO 国库治理
- SecureComputeMarket: 隐私算力市场
- TEEManager: 可信执行环境
- ArbitrationSystem: 仲裁系统
- ReputationEngine: 信誉引擎

网络与基础设施：
- TCPNetwork: P2P 网络
- MessageBroker, EventBus: 消息队列
- DataRedundancyManager: 数据冗余
- MainnetMonitor: 主网监控
"""

from .consensus import Block
from .account import Account

# Phase 5: 分布式网络模块
from .transaction import (
    Transaction,
    TxType,
    create_order_tx,
    create_pouw_tx,
    create_settlement_tx,
    create_refund_tx,
)
from .pouw_executor import PoUWExecutor, RealTaskType, RealPoUWTask, RealPoUWResult
from .blind_task_engine import BlindTaskEngine, BlindBatch, BlindChallenge, TrapGenerator

# Phase 6: 算力租用机制
from .miner_registry import (
    MinerRegistry,
    MinerCapability,
    HardwareSpec,
    NetworkSpec,
    HardwareType,
    TaskCapability,
    MinerStatus,
)
from .pouw_scoring import (
    POUWScoringEngine,
    ObjectiveMetrics,
    ObjectiveMetricsCollector,
    UserFeedback,
    UserFeedbackSystem,
    ScoringParameters,
)
from .sandbox_executor import (
    SandboxExecutor,
    SandboxResult,
    SandboxConfig,
    ExecutionEnvironment,
    ExecutionContext,
    DockerManager,
    SandboxStatus,
)
from .exchange_rate import (
    DynamicExchangeRate,
    ExchangeRateRecord,
    SectorMetrics,
    RateUpdateTrigger,
)
from .compute_witness import (
    ComputeWitnessSystem,
    WitnessRequest,
    WitnessRecord,
    WitnessType,
    WitnessStatus,
)

# Phase 7: 加密任务分发系统
from .encrypted_task import (
    EncryptedTaskManager,
    EncryptedTask,
    TaskSettlementContract,
    HybridEncryption,
    KeyPair,
    EncryptedPayload,
    ChainNode,
    TaskChainStatus,
    TimeBillingEngine,
    TimeBillingConfig,
    SettlementTransaction,
)

# Phase 8: 动态定价系统
from .dynamic_pricing import (
    DynamicPricingEngine,
    BasePriceManager,
    MarketMultiplierCalculator,
    TimeSlotCalculator,
    StrategyCalculator,
    BudgetLockManager,
    SettlementEngine as DynamicSettlementEngine,
    MarketMonitor,
    ElasticTaskQueue,
    GPUBasePrice,
    MarketState,
    TimeSlice,
    PricingResult,
    BudgetLock,
    SettlementRecord,
    PricingStrategy,
    TimeSlot,
    TaskPriority,
    get_pricing_system,
    create_pricing_system,
)

# Phase 9: 高级去中心化算力网络
from .tee_computing import (
    TEEType,
    VerificationLevel,
    VerificationStatus,
    TEENode,
    AttestationReport,
    TEEManager,
    VerifiableComputeEngine,
    TEEPricingIntegration,
    get_tee_system,
)

from .compute_market_orderbook import (
    AskOrder,
    BidOrder,
    OrderBook,
    MatchingEngine,
    Trade,
    AutoMarketMaker,
    OrderStatus,
    get_matching_engine,
    get_amm,
)

from .compute_futures import (
    ContractStatus,
    FuturesContract,
    FuturesContractManager,
    FuturesMarket,
    DeliveryRecord,
    get_futures_system,
)

from .granular_billing import (
    ResourceUsage,
    GranularBill,
    GranularBillingEngine,
    CostEstimator,
)

from .data_lifecycle import (
    RetentionPolicy,
    DataAsset,
    DestructionCertificate,
    DataLifecycleManager,
    EphemeralKeyManager,
    SessionKeyProtocol,
    EphemeralKey,
    get_data_lifecycle_system,
)

from .p2p_direct import (
    TransportProtocol,
    NATType,
    ConnectionState,
    P2PSession,
    P2PConnectionManager,
    NATTraversalService,
    KeyExchangeService,
    get_p2p_service,
)

from .did_identity import (
    ReputationTier,
    DIDDocument,
    VerifiableCredential,
    DIDManager,
    ReputationSystem,
    SybilDetector,
    IdentityService,
    get_identity_service,
)

from .dao_treasury import (
    ProposalStatus,
    ProposalType,
    Proposal,
    Vote,
    TreasuryManager,
    DAOGovernance,
    FeeDistributor,
    get_dao_system,
)

# Phase 11: 贡献权重治理投票
from .contribution_governance import (
    GovernanceConfig,
    ProposalRisk,
    ProposalType as ContribProposalType,
    ProposalStatus as ContribProposalStatus,
    VoteChoice,
    ContributorRole,
    ContributionRecord,
    GovernanceWeight,
    ProposalBond,
    Vote as ContribVote,
    Proposal as ContribProposal,
    ContributionWeightCalculator,
    ContributionGovernance,
)

# Phase 10: 主网上线准备
from .message_queue import (
    MessageBroker,
    EventBus,
    TaskQueue,
    get_message_broker,
    get_event_bus,
    get_task_queue,
)

from .data_redundancy import (
    DataRedundancyManager,
    get_data_redundancy_manager,
)

from .load_testing import (
    LoadTestEngine,
    get_load_test_engine,
)

from .zk_verification import (
    ZKVerificationManager,
    get_zk_verification_manager,
)

from .attack_prevention import (
    AttackPreventionManager,
    get_attack_prevention_manager,
)

from .smart_contract_audit import (
    SmartContractAuditManager,
    get_smart_contract_audit_manager,
)

from .revenue_tracking import (
    RevenueTrackingManager,
    get_revenue_tracking_manager,
)

from .mainnet_monitor import (
    MainnetMonitor,
    get_mainnet_monitor,
)

from .sdk_api import (
    SDKAPIManager,
    get_sdk_api_manager,
)

# 算力市场隐私与安全模块
from .secure_compute_market import (
    SecureComputeMarket,
    TaskShardingEngine,
    KeyDerivationEngine,
    AuditEngine,
    DistributedExecutionEngine,
    ContainerSecurityEnforcer,
    SecureResultAggregator,
    SecurityConfig,
    ShardType,
    EncryptionState,
    ExecutionMode,
    ContainerSecurityLevel,
    TaskShard,
    DerivedKey,
    ContainerSecurityPolicy,
    AuditRecord,
    DistributedExecutionPlan,
    create_secure_market,
)

# Phase 12: 统一共识引擎
from .unified_consensus import (
    UnifiedConsensus,
    UnifiedMinerMode,
    UnifiedMinerConfig,
    TaskDistributionMode,
    WitnessScope,
    SecurityThreatLevel,
    SecureTaskEnvelope,
    SecurityAuditEvent,
)

# Phase 13: 查漏补缺 — 将断开模块接入统一共识
from .protocol_fee_pool import (
    ProtocolHardRules,
    ProtocolFeePool,
    ProtocolFeePoolManager,
    FeeDistribution,
    SpendingCategory,
    SpendingProposal,
)

from .arbitration import (
    ArbitrationSystem,
    TaskArbitration,
    Dispute,
    DisputeStatus,
    DisputeReason,
)

from .reputation_engine import (
    ReputationEngine,
    ReputationScore,
    ReputationInfluenceLimits,
    TaskCategory as ReputationTaskCategory,
    get_reputation_engine,
)

from .monitor import (
    TransactionMonitor,
    MonitorConfig,
    Alert,
    AlertLevel,
    AlertType,
)

from .task_acceptance import (
    TaskAcceptanceService,
    SLADefinition,
    ProtocolVerdict,
    ServiceVerdict,
    ApplicationVerdict,
    AcceptanceLevel,
)

from .message_system import (
    MessageSystem,
    MessageType as MsgType,
    MessageStatus,
    Rating,
)

from .miner_behavior import (
    MinerBehaviorAnalyzer,
    MinerBehaviorScore,
    OrderPriceLevel,
    BehaviorConfig,
    FulfillmentStatus,
)

__all__ = [
    # 核心层
    "Block",
    "Account",
    # 交易
    "Transaction",
    "TxType",
    "create_order_tx",
    "create_pouw_tx",
    "create_settlement_tx",
    "create_refund_tx",
    # PoUW 执行器
    "PoUWExecutor",
    "RealTaskType",
    "RealPoUWTask",
    "RealPoUWResult",
    # 矿工注册
    "MinerRegistry",
    "MinerCapability",
    "HardwareSpec",
    "NetworkSpec",
    "HardwareType",
    "TaskCapability",
    "MinerStatus",
    # POUW 评分
    "POUWScoringEngine",
    "ObjectiveMetrics",
    "ObjectiveMetricsCollector",
    "UserFeedback",
    "UserFeedbackSystem",
    "ScoringParameters",
    "SandboxExecutor",
    "SandboxResult",
    "SandboxConfig",
    "ExecutionEnvironment",
    "ExecutionContext",
    "DockerManager",
    "SandboxStatus",
    # 动态汇率
    "DynamicExchangeRate",
    "ExchangeRateRecord",
    "SectorMetrics",
    "RateUpdateTrigger",
    # Phase 6 - 算力交易双见证
    "ComputeWitnessSystem",
    "WitnessRequest",
    "WitnessRecord",
    "WitnessType",
    "WitnessStatus",
    # Phase 7 - 加密任务分发
    "EncryptedTaskManager",
    "EncryptedTask",
    "TaskSettlementContract",
    "HybridEncryption",
    "KeyPair",
    "EncryptedPayload",
    "ChainNode",
    "TaskChainStatus",
    "TimeBillingEngine",
    "TimeBillingConfig",
    "SettlementTransaction",
    # Phase 8 - 动态定价系统
    "DynamicPricingEngine",
    "BasePriceManager",
    "MarketMultiplierCalculator",
    "TimeSlotCalculator",
    "StrategyCalculator",
    "BudgetLockManager",
    "DynamicSettlementEngine",
    "MarketMonitor",
    "ElasticTaskQueue",
    "GPUBasePrice",
    "MarketState",
    "TimeSlice",
    "PricingResult",
    "BudgetLock",
    "SettlementRecord",
    "PricingStrategy",
    "TimeSlot",
    "TaskPriority",
    "get_pricing_system",
    "create_pricing_system",
    # Phase 9 - TEE 可信执行环境
    "TEEType",
    "VerificationLevel",
    "VerificationStatus",
    "TEENode",
    "AttestationReport",
    "TEEManager",
    "VerifiableComputeEngine",
    "TEEPricingIntegration",
    "get_tee_system",
    # Phase 9 - 算力市场订单簿
    "AskOrder",
    "BidOrder",
    "OrderBook",
    "MatchingEngine",
    "Trade",
    "AutoMarketMaker",
    "OrderStatus",
    "get_matching_engine",
    "get_amm",
    # Phase 9 - 算力期货
    "ContractStatus",
    "FuturesContract",
    "FuturesContractManager",
    "FuturesMarket",
    "DeliveryRecord",
    "get_futures_system",
    # Phase 9 - 细粒度计费
    "ResourceUsage",
    "GranularBill",
    "GranularBillingEngine",
    "CostEstimator",
    # Phase 9 - 数据生命周期
    "RetentionPolicy",
    "DataAsset",
    "DestructionCertificate",
    "DataLifecycleManager",
    "EphemeralKeyManager",
    "SessionKeyProtocol",
    "EphemeralKey",
    "get_data_lifecycle_system",
    # Phase 9 - P2P 直连
    "TransportProtocol",
    "NATType",
    "ConnectionState",
    "P2PSession",
    "P2PConnectionManager",
    "NATTraversalService",
    "KeyExchangeService",
    "get_p2p_service",
    # Phase 9 - DID 身份
    "ReputationTier",
    "DIDDocument",
    "VerifiableCredential",
    "DIDManager",
    "ReputationSystem",
    "SybilDetector",
    "IdentityService",
    "get_identity_service",
    # Phase 9 - DAO 国库治理
    "ProposalStatus",
    "ProposalType",
    "Proposal",
    "Vote",
    "TreasuryManager",
    "DAOGovernance",
    "FeeDistributor",
    "get_dao_system",
    # Phase 11 - 贡献权重治理投票
    "GovernanceConfig",
    "ProposalRisk",
    "VoteChoice",
    "ContributorRole",
    "ContributionRecord",
    "GovernanceWeight",
    "ProposalBond",
    "ContributionWeightCalculator",
    "ContributionGovernance",
    # Phase 10 - 主网上线准备
    "MessageBroker",
    "EventBus",
    "TaskQueue",
    "get_message_broker",
    "get_event_bus",
    "get_task_queue",
    "DataRedundancyManager",
    "get_data_redundancy_manager",
    "LoadTestEngine",
    "get_load_test_engine",
    "ZKVerificationManager",
    "get_zk_verification_manager",
    "AttackPreventionManager",
    "get_attack_prevention_manager",
    "SmartContractAuditManager",
    "get_smart_contract_audit_manager",
    "RevenueTrackingManager",
    "get_revenue_tracking_manager",
    "MainnetMonitor",
    "get_mainnet_monitor",
    "SDKAPIManager",
    "get_sdk_api_manager",
    # 算力市场隐私与安全
    "SecureComputeMarket",
    "TaskShardingEngine",
    "KeyDerivationEngine",
    "AuditEngine",
    "DistributedExecutionEngine",
    "ContainerSecurityEnforcer",
    "SecureResultAggregator",
    "SecurityConfig",
    "ShardType",
    "EncryptionState",
    "ExecutionMode",
    "ContainerSecurityLevel",
    "TaskShard",
    "DerivedKey",
    "ContainerSecurityPolicy",
    "AuditRecord",
    "DistributedExecutionPlan",
    "create_secure_market",
    # Phase 12 - 统一共识引擎
    "UnifiedConsensus",
    "UnifiedMinerMode",
    "UnifiedMinerConfig",
    "TaskDistributionMode",
    "WitnessScope",
    "SecurityThreatLevel",
    "SecureTaskEnvelope",
    "SecurityAuditEvent",
    # Phase 13 - 查漏补缺
    # 协议费用池
    "ProtocolHardRules",
    "ProtocolFeePool",
    "ProtocolFeePoolManager",
    "FeeDistribution",
    "SpendingCategory",
    "SpendingProposal",
    # 仲裁系统
    "ArbitrationSystem",
    "TaskArbitration",
    "Dispute",
    "DisputeStatus",
    "DisputeReason",
    # 信誉引擎
    "ReputationEngine",
    "ReputationScore",
    "ReputationInfluenceLimits",
    "ReputationTaskCategory",
    "get_reputation_engine",
    # 交易监控
    "TransactionMonitor",
    "MonitorConfig",
    "Alert",
    "AlertLevel",
    "AlertType",
    # 任务验收/SLA
    "TaskAcceptanceService",
    "SLADefinition",
    "ProtocolVerdict",
    "ServiceVerdict",
    "ApplicationVerdict",
    "AcceptanceLevel",
    # 留言评价系统
    "MessageSystem",
    "MsgType",
    "MessageStatus",
    "Rating",
    # 矿工行为分析
    "MinerBehaviorAnalyzer",
    "MinerBehaviorScore",
    "OrderPriceLevel",
    "BehaviorConfig",
    "FulfillmentStatus",
]
