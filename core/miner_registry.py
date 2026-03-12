"""
miner_registry.py - 矿工链上能力声明注册系统

Phase 6 实现：
- 矿工入网时声明硬件/网络/任务能力
- 能力信息上链存证
- 可被任何人验证
- 不直接决定收益，仅决定"可接哪些任务"

设计原则：
- 用户不能指定矿工，只能指定需求（防止"算力关系户"）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import uuid
import time
import hashlib


class HardwareType(Enum):
    """硬件类型枚举。"""
    GPU_CONSUMER = "gpu_consumer"      # 消费级 GPU (RTX 3090/4090)
    GPU_DATACENTER = "gpu_datacenter"  # 数据中心 GPU (A100/H100)
    CPU_STANDARD = "cpu_standard"      # 标准 CPU
    CPU_HIGH_CORE = "cpu_high_core"    # 高核心 CPU
    TPU = "tpu"                        # TPU 加速器
    FPGA = "fpga"                      # FPGA


class TaskCapability(Enum):
    """支持的任务类型。"""
    INFERENCE = "inference"             # 推理任务
    TRAINING = "training"               # 训练任务
    BATCH_COMPUTE = "batch_compute"     # 批处理计算
    REAL_TIME = "real_time"             # 实时计算
    RENDERING = "rendering"             # 渲染
    SCIENTIFIC = "scientific"           # 科学计算


class MinerStatus(Enum):
    """矿工状态。"""
    ONLINE = "online"
    OFFLINE = "offline"
    OVERLOADED = "overloaded"
    PENALIZED = "penalized"
    MAINTENANCE = "maintenance"


@dataclass
class HardwareSpec:
    """硬件规格声明。"""
    hardware_type: HardwareType
    model: str                          # 型号 (e.g., "RTX 4090", "A100 80G")
    compute_power: float                # 算力评级 (TFLOPS)
    memory_gb: float                    # 显存/内存 GB
    memory_bandwidth: float = 0.0       # 带宽 GB/s


@dataclass
class NetworkSpec:
    """网络能力声明。"""
    bandwidth_mbps: float               # 带宽 Mbps
    latency_ms_range: tuple             # 延迟区间 (min, max) ms
    uptime_guarantee: float = 0.95      # 在线时间保证


@dataclass
class MinerCapability:
    """矿工能力声明（链上存证）。"""
    miner_id: str
    registration_id: str                # 注册 ID（唯一）
    hardware: HardwareSpec
    network: NetworkSpec
    supported_tasks: List[TaskCapability]
    sector_type: str                    # 所属板块
    registered_at: float
    last_updated: float
    status: MinerStatus = MinerStatus.ONLINE
    
    # 动态指标（自动采集，不可人为干预）
    current_load: float = 0.0           # 当前负载 0-1
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    avg_response_time_ms: float = 0.0
    uptime_hours: float = 0.0

    def capability_hash(self) -> str:
        """生成能力声明的哈希（用于链上存证）。"""
        data = f"{self.miner_id}:{self.hardware.model}:{self.hardware.compute_power}"
        data += f":{self.network.bandwidth_mbps}:{','.join(t.value for t in self.supported_tasks)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def completion_rate(self) -> float:
        """任务完成率。"""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 1.0
        return self.total_tasks_completed / total

    def to_dict(self) -> dict:
        return {
            "miner_id": self.miner_id,
            "registration_id": self.registration_id,
            "hardware_type": self.hardware.hardware_type.value,
            "hardware_model": self.hardware.model,
            "compute_power": self.hardware.compute_power,
            "memory_gb": self.hardware.memory_gb,
            "bandwidth_mbps": self.network.bandwidth_mbps,
            "latency_range": self.network.latency_ms_range,
            "supported_tasks": [t.value for t in self.supported_tasks],
            "sector_type": self.sector_type,
            "status": self.status.value,
            "current_load": self.current_load,
            "completion_rate": self.completion_rate(),
            "capability_hash": self.capability_hash(),
        }


class MinerRegistry:
    """矿工注册中心（链上能力声明）。

    功能：
    - 矿工入网注册
    - 能力声明存证
    - 状态管理
    - 查询与验证
    """

    def __init__(
        self,
        main_chain: Any = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.main_chain = main_chain
        self.miners: Dict[str, MinerCapability] = {}
        self.registrations: List[dict] = []  # 注册历史（链上存证）
        self._log_fn = log_fn or (lambda x: None)

    def _log(self, msg: str):
        self._log_fn(f"[REGISTRY] {msg}")

    def register_miner(
        self,
        miner_id: str,
        hardware: HardwareSpec,
        network: NetworkSpec,
        supported_tasks: List[TaskCapability],
        sector_type: str,
    ) -> MinerCapability:
        """矿工入网注册。

        Args:
            miner_id: 矿工 ID
            hardware: 硬件规格
            network: 网络能力
            supported_tasks: 支持的任务类型
            sector_type: 所属板块

        Returns:
            注册的矿工能力声明
        """
        now = time.time()
        registration_id = uuid.uuid4().hex[:8]

        capability = MinerCapability(
            miner_id=miner_id,
            registration_id=registration_id,
            hardware=hardware,
            network=network,
            supported_tasks=supported_tasks,
            sector_type=sector_type,
            registered_at=now,
            last_updated=now,
        )

        self.miners[miner_id] = capability

        # 创建注册记录（链上存证）
        registration_record = {
            "type": "MINER_REGISTRATION",
            "registration_id": registration_id,
            "miner_id": miner_id,
            "capability_hash": capability.capability_hash(),
            "timestamp": now,
            "hardware_type": hardware.hardware_type.value,
            "sector_type": sector_type,
        }
        self.registrations.append(registration_record)
        # 内存中只保留最近 10000 条注册记录（已上链的记录不会丢失）
        if len(self.registrations) > 10000:
            self.registrations = self.registrations[-10000:]

        # 上链
        if self.main_chain:
            self.main_chain.record_transaction(registration_record)

        self._log(f"Registered: {miner_id} ({hardware.model}, {sector_type})")

        return capability

    def update_status(self, miner_id: str, status: MinerStatus):
        """更新矿工状态。"""
        if miner_id in self.miners:
            self.miners[miner_id].status = status
            self.miners[miner_id].last_updated = time.time()
            self._log(f"{miner_id} status -> {status.value}")

    def update_load(self, miner_id: str, load: float):
        """更新矿工负载。"""
        if miner_id in self.miners:
            self.miners[miner_id].current_load = min(1.0, max(0.0, load))
            if load > 0.9:
                self.miners[miner_id].status = MinerStatus.OVERLOADED

    def record_task_completion(
        self,
        miner_id: str,
        success: bool,
        response_time_ms: float,
    ):
        """记录任务完成（自动采集指标）。"""
        if miner_id not in self.miners:
            return

        cap = self.miners[miner_id]
        if success:
            cap.total_tasks_completed += 1
        else:
            cap.total_tasks_failed += 1

        # 更新平均响应时间（滑动平均）
        total = cap.total_tasks_completed + cap.total_tasks_failed
        cap.avg_response_time_ms = (
            (cap.avg_response_time_ms * (total - 1) + response_time_ms) / total
        )

    def penalize(self, miner_id: str, reason: str):
        """惩罚矿工。"""
        if miner_id in self.miners:
            self.miners[miner_id].status = MinerStatus.PENALIZED
            self._log(f"PENALIZED {miner_id}: {reason}")

    def get_online_miners(self) -> List[MinerCapability]:
        """获取所有在线矿工。"""
        return [
            m for m in self.miners.values()
            if m.status == MinerStatus.ONLINE
        ]

    def get_miners_by_sector(self, sector_type: str) -> List[MinerCapability]:
        """按板块获取矿工。"""
        return [
            m for m in self.miners.values()
            if m.sector_type == sector_type and m.status == MinerStatus.ONLINE
        ]

    def get_miners_by_capability(
        self,
        task_type: TaskCapability,
        min_compute_power: float = 0,
        min_memory_gb: float = 0,
    ) -> List[MinerCapability]:
        """按能力筛选矿工。"""
        result = []
        for m in self.miners.values():
            if m.status != MinerStatus.ONLINE:
                continue
            if task_type not in m.supported_tasks:
                continue
            if m.hardware.compute_power < min_compute_power:
                continue
            if m.hardware.memory_gb < min_memory_gb:
                continue
            result.append(m)
        return result

    def verify_registration(self, miner_id: str) -> Optional[str]:
        """验证矿工注册（返回能力哈希）。"""
        if miner_id in self.miners:
            return self.miners[miner_id].capability_hash()
        return None

    def print_registry(self):
        """打印注册表。"""
        print("\n" + "=" * 70)
        print("MINER REGISTRY")
        print("=" * 70)
        for m in self.miners.values():
            print(f"\n[{m.miner_id}] {m.hardware.model}")
            print(f"    Sector: {m.sector_type}, Status: {m.status.value}")
            print(f"    Compute: {m.hardware.compute_power} TFLOPS, Mem: {m.hardware.memory_gb} GB")
            print(f"    Tasks: {[t.value for t in m.supported_tasks]}")
            print(f"    Load: {m.current_load*100:.1f}%, Completion: {m.completion_rate()*100:.1f}%")
            print(f"    Hash: {m.capability_hash()}")

    def __repr__(self) -> str:
        online = len(self.get_online_miners())
        return f"MinerRegistry(total={len(self.miners)}, online={online})"
