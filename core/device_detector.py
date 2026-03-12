"""
DeviceDetector 模块 - 设备自动检测与板块分配

核心功能：
1. 自动检测用户硬件（GPU、CPU、内存）
2. 根据硬件自动分配到合适板块
3. 硬件基准测试
4. 设备能力评估

⚠️ 安全警告 - 可信假设说明：
=================================
本模块依赖客户端自报硬件信息，存在以下已知局限性：

1. 【可被绕过】虚拟机/驱动层可伪造硬件信息
2. 【无法验证】无法远程验证客户端硬件真实性
3. 【信任模型】当前版本基于"客户端可信"假设运行

防护措施（已实现）：
- 异常检测：任务完成时间与声明算力不匹配时降低信誉
- 结果验证：多矿工冗余计算，作弊者会因结果不一致被惩罚
- 信誉系统：持续作弊的矿工会被暂停

未来改进方向：
- 可信执行环境（SGX/TDX）
- 硬件证明（TPM）
- 多源交叉验证

这是第一阶段实现，适用于测试网和信任环境。
生产环境需要额外的硬件验证机制。
=================================
"""

import platform
import subprocess
import re
import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum


# 信任假设标记
TRUST_ASSUMPTION = "CLIENT_TRUSTED"  # 客户端可信假设
HARDWARE_VERIFICATION_LEVEL = "SELF_REPORTED"  # 硬件验证级别：自报告


class DeviceType(Enum):
    """设备类型。"""
    GPU_HIGH = "GPU_HIGH"       # 高端 GPU (A100, H100, RTX4090)
    GPU_MID = "GPU_MID"         # 中端 GPU (RTX3080, RTX3090)
    GPU_LOW = "GPU_LOW"         # 低端 GPU (GTX1660, RTX2060)
    CPU_HIGH = "CPU_HIGH"       # 高端 CPU (服务器级)
    CPU_MID = "CPU_MID"         # 中端 CPU
    CPU_LOW = "CPU_LOW"         # 低端 CPU
    MEMORY_HIGH = "MEMORY_HIGH" # 高内存 (128GB+)
    STORAGE_HIGH = "STORAGE_HIGH"  # 高存储


class SectorMapping:
    """板块映射配置。
    
    设计原则：
    1. 板块按算力等级划分，而非具体型号
    2. 矿工根据实际硬件型号匹配到合适的板块
    3. 板块名称：H100（数据中心）, RTX4090（高端消费级）, RTX3080（中端）, CPU
    
    链配置的板块：H100, RTX4090, RTX3080, CPU
    """
    
    # GPU 型号 -> 所属板块（精确匹配）
    # 根据 GPU 实际性能分配到对应板块
    GPU_TO_SECTOR = {
        # ===== H100 板块（数据中心级，100+ TFLOPs）=====
        "H100": "H100",
        "A100": "H100",
        "A6000": "H100",
        "A40": "H100",
        "A30": "H100",
        "L40": "H100",
        
        # ===== RTX4090 板块（高端消费级，150+ TFLOPs FP16）=====
        "RTX 4090": "RTX4090",
        "RTX 4080": "RTX4090",
        "RTX 3090 TI": "RTX4090",
        "RTX 3090": "RTX4090",
        "RTX 4070 TI SUPER": "RTX4090",
        
        # ===== RTX3080 板块（中端消费级）=====
        "RTX 4070 TI": "RTX3080",
        "RTX 4070 SUPER": "RTX3080",
        "RTX 4070": "RTX3080",
        "RTX 3080 TI": "RTX3080",
        "RTX 3080": "RTX3080",
        "RTX 4060 TI": "RTX3080",
        "RTX 4060": "RTX3080",      # RTX 4060 归入 RTX3080 板块
        "RTX 3070 TI": "RTX3080",
        "RTX 3070": "RTX3080",
        "RTX 3060 TI": "RTX3080",
        "RTX 3060": "RTX3080",
        "RTX 2080 TI": "RTX3080",
        "RTX 2080 SUPER": "RTX3080",
        "RTX 2080": "RTX3080",
        "RTX 2070 SUPER": "RTX3080",
        "RTX 2070": "RTX3080",
        "RTX 2060 SUPER": "RTX3080",
        "RTX 2060": "RTX3080",
        
        # ===== CPU 板块（入门级 GPU 和 CPU）=====
        "GTX 1660": "CPU",
        "GTX 1650": "CPU",
        "GTX 1080 TI": "CPU",
        "GTX 1080": "CPU",
        "GTX 1070": "CPU",
        "GTX 1060": "CPU",
        
        # AMD GPU
        "RX 7900 XTX": "RTX4090",
        "RX 7900 XT": "RTX4090",
        "RX 7800 XT": "RTX3080",
        "RX 7700 XT": "RTX3080",
        "RX 6900 XT": "RTX3080",
        "RX 6800 XT": "RTX3080",
        "RX 6800": "RTX3080",
        "RX 6700 XT": "RTX3080",
        "RX 6600": "CPU",
    }
    
    # 设备类型到默认板块（用于未知 GPU）
    DEVICE_TO_SECTOR = {
        DeviceType.GPU_HIGH: ["H100"],
        DeviceType.GPU_MID: ["RTX4090"],
        DeviceType.GPU_LOW: ["RTX3080"],
        DeviceType.CPU_HIGH: ["CPU"],
        DeviceType.CPU_MID: ["CPU"],
        DeviceType.CPU_LOW: ["CPU"],
        DeviceType.MEMORY_HIGH: ["CPU"],
        DeviceType.STORAGE_HIGH: ["CPU"],
    }
    
    @classmethod
    def get_sector_for_gpu(cls, gpu_name: str) -> str:
        """根据 GPU 型号获取对应板块"""
        gpu_upper = gpu_name.upper()
        
        # 精确匹配（按长度降序，优先匹配更具体的型号）
        sorted_models = sorted(cls.GPU_TO_SECTOR.keys(), key=len, reverse=True)
        for model in sorted_models:
            if model.upper() in gpu_upper:
                return cls.GPU_TO_SECTOR[model]
        
        # 默认返回 RTX3080（中端板块）
        return "RTX3080"
    
    # GPU 型号到类型的映射（用于设备类型判断）
    GPU_MODELS = {
        # NVIDIA 高端
        "H100": DeviceType.GPU_HIGH,
        "A100": DeviceType.GPU_HIGH,
        "A6000": DeviceType.GPU_HIGH,
        "A40": DeviceType.GPU_HIGH,
        
        # NVIDIA 消费级高端
        "RTX 4090": DeviceType.GPU_HIGH,
        "RTX 4080": DeviceType.GPU_MID,
        "RTX 3090": DeviceType.GPU_MID,
        "RTX 3080": DeviceType.GPU_MID,
        
        # NVIDIA 中端
        "RTX 4070": DeviceType.GPU_MID,
        "RTX 3070": DeviceType.GPU_LOW,
        "RTX 4060": DeviceType.GPU_LOW,
        "RTX 3060": DeviceType.GPU_LOW,
        "RTX 2080": DeviceType.GPU_MID,
        "RTX 2070": DeviceType.GPU_LOW,
        "RTX 2060": DeviceType.GPU_LOW,
        
        # NVIDIA 低端
        "GTX 1660": DeviceType.GPU_LOW,
        "GTX 1650": DeviceType.GPU_LOW,
        "GTX 1080": DeviceType.GPU_LOW,
        "GTX 1070": DeviceType.GPU_LOW,
        
        # AMD
        "RX 7900": DeviceType.GPU_MID,
        "RX 7800": DeviceType.GPU_MID,
        "RX 6900": DeviceType.GPU_MID,
        "RX 6800": DeviceType.GPU_MID,
        "RX 6700": DeviceType.GPU_LOW,
    }


@dataclass
class GPUInfo:
    """GPU 信息。"""
    name: str = ""
    memory_total: int = 0  # MB
    memory_free: int = 0
    compute_capability: str = ""
    driver_version: str = ""
    cuda_version: str = ""
    device_type: DeviceType = DeviceType.GPU_LOW
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "memory_total_gb": self.memory_total / 1024,
            "memory_free_gb": self.memory_free / 1024,
            "compute_capability": self.compute_capability,
            "driver": self.driver_version,
            "cuda": self.cuda_version,
            "type": self.device_type.value,
        }


@dataclass
class CPUInfo:
    """CPU 信息。"""
    name: str = ""
    cores: int = 0
    threads: int = 0
    frequency_mhz: float = 0.0
    architecture: str = ""
    device_type: DeviceType = DeviceType.CPU_MID
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "cores": self.cores,
            "threads": self.threads,
            "frequency_ghz": self.frequency_mhz / 1000,
            "architecture": self.architecture,
            "type": self.device_type.value,
        }


@dataclass
class MemoryInfo:
    """内存信息。"""
    total: int = 0  # MB
    available: int = 0
    used: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "total_gb": self.total / 1024,
            "available_gb": self.available / 1024,
            "used_gb": self.used / 1024,
            "usage_percent": (self.used / self.total * 100) if self.total > 0 else 0,
        }


@dataclass
class DeviceProfile:
    """设备档案。"""
    device_id: str = ""
    hostname: str = ""
    platform: str = ""
    
    gpu_list: List[GPUInfo] = field(default_factory=list)
    cpu_info: CPUInfo = field(default_factory=CPUInfo)
    memory_info: MemoryInfo = field(default_factory=MemoryInfo)
    
    # 自动分配的板块
    assigned_sectors: List[str] = field(default_factory=list)
    primary_sector: str = "GENERAL"
    
    # 能力评分
    compute_score: float = 0.0
    memory_score: float = 0.0
    storage_score: float = 0.0
    overall_score: float = 0.0
    
    # 时间戳
    detected_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "device_id": self.device_id,
            "hostname": self.hostname,
            "platform": self.platform,
            "gpu_count": len(self.gpu_list),
            "gpus": [g.to_dict() for g in self.gpu_list],
            "cpu": self.cpu_info.to_dict(),
            "memory": self.memory_info.to_dict(),
            "assigned_sectors": self.assigned_sectors,
            "primary_sector": self.primary_sector,
            "scores": {
                "compute": self.compute_score,
                "memory": self.memory_score,
                "storage": self.storage_score,
                "overall": self.overall_score,
            }
        }


class DeviceDetector:
    """设备检测器。"""
    
    def __init__(self, log_fn: Callable = print):
        self.log = log_fn
        self.profile: Optional[DeviceProfile] = None
    
    def detect_all(self) -> DeviceProfile:
        """检测所有设备。"""
        profile = DeviceProfile(
            hostname=platform.node(),
            platform=platform.system(),
        )
        
        # 生成设备 ID
        profile.device_id = self._generate_device_id()
        
        # 检测各组件
        profile.gpu_list = self._detect_gpus()
        profile.cpu_info = self._detect_cpu()
        profile.memory_info = self._detect_memory()
        
        # 计算分数
        self._calculate_scores(profile)
        
        # 自动分配板块
        self._assign_sectors(profile)
        
        self.profile = profile
        self.log(f"🔍 设备检测完成: {profile.primary_sector}")
        
        return profile
    
    def _generate_device_id(self) -> str:
        """生成唯一设备 ID。"""
        data = f"{platform.node()}{platform.machine()}{platform.processor()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _detect_gpus(self) -> List[GPUInfo]:
        """检测 GPU。"""
        gpus = []
        
        # 尝试使用 nvidia-smi
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 4:
                            gpu = GPUInfo(
                                name=parts[0],
                                memory_total=int(float(parts[1])),
                                memory_free=int(float(parts[2])),
                                driver_version=parts[3],
                            )
                            
                            # 判断设备类型
                            gpu.device_type = self._classify_gpu(gpu.name)
                            gpus.append(gpu)
                            
                            self.log(f"[GPU] 检测到 GPU: {gpu.name} ({gpu.memory_total}MB)")
        
        except FileNotFoundError:
            self.log("⚠️ nvidia-smi 未找到，无 NVIDIA GPU 或驱动未安装")
        except subprocess.TimeoutExpired:
            self.log("⚠️ nvidia-smi 超时")
        except Exception as e:
            self.log(f"GPU 检测错误: {e}")
        
        # 如果没有检测到 GPU，创建虚拟条目
        if not gpus:
            gpus.append(GPUInfo(
                name="No GPU Detected",
                device_type=DeviceType.CPU_MID,
            ))
        
        return gpus
    
    def _classify_gpu(self, gpu_name: str) -> DeviceType:
        """分类 GPU。"""
        name_upper = gpu_name.upper()
        
        for model, device_type in SectorMapping.GPU_MODELS.items():
            if model.upper() in name_upper:
                return device_type
        
        # 默认
        if "NVIDIA" in name_upper or "GEFORCE" in name_upper:
            return DeviceType.GPU_LOW
        
        return DeviceType.CPU_MID
    
    def _detect_cpu(self) -> CPUInfo:
        """检测 CPU。"""
        import os
        
        cpu = CPUInfo(
            name=platform.processor() or "Unknown",
            architecture=platform.machine(),
        )
        
        # 获取核心数
        try:
            cpu.cores = os.cpu_count() or 1
            cpu.threads = cpu.cores  # 简化
        except (OSError, ValueError, TypeError):
            cpu.cores = 1
            cpu.threads = 1
        
        # 判断类型
        if cpu.cores >= 32:
            cpu.device_type = DeviceType.CPU_HIGH
        elif cpu.cores >= 8:
            cpu.device_type = DeviceType.CPU_MID
        else:
            cpu.device_type = DeviceType.CPU_LOW
        
        self.log(f"🖥️ 检测到 CPU: {cpu.cores} 核心")
        
        return cpu
    
    def _detect_memory(self) -> MemoryInfo:
        """检测内存。"""
        memory = MemoryInfo()
        
        try:
            # Windows
            if platform.system() == "Windows":
                import ctypes
                
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                
                memory.total = stat.ullTotalPhys // (1024 * 1024)
                memory.available = stat.ullAvailPhys // (1024 * 1024)
                memory.used = memory.total - memory.available
            
            else:
                # Linux/Mac
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if "MemTotal" in line:
                            memory.total = int(line.split()[1]) // 1024
                        elif "MemAvailable" in line:
                            memory.available = int(line.split()[1]) // 1024
                    memory.used = memory.total - memory.available
        
        except Exception as e:
            self.log(f"⚠️ 内存检测错误: {e}")
            memory.total = 8192  # 默认 8GB
            memory.available = 4096
            memory.used = 4096
        
        self.log(f"💾 检测到内存: {memory.total // 1024} GB")
        
        return memory
    
    def _calculate_scores(self, profile: DeviceProfile):
        """计算能力分数。"""
        # 计算分数（0-100）
        compute_score = 0
        
        # GPU 分数
        for gpu in profile.gpu_list:
            if gpu.device_type == DeviceType.GPU_HIGH:
                compute_score += 40
            elif gpu.device_type == DeviceType.GPU_MID:
                compute_score += 25
            elif gpu.device_type == DeviceType.GPU_LOW:
                compute_score += 15
            
            # 显存加分
            compute_score += min(20, gpu.memory_total / 1024)  # 每 GB 1 分，最多 20 分
        
        # CPU 分数
        cpu = profile.cpu_info
        if cpu.device_type == DeviceType.CPU_HIGH:
            compute_score += 20
        elif cpu.device_type == DeviceType.CPU_MID:
            compute_score += 10
        else:
            compute_score += 5
        
        profile.compute_score = min(100, compute_score)
        
        # 内存分数
        mem_gb = profile.memory_info.total / 1024
        profile.memory_score = min(100, mem_gb * 2)  # 每 GB 2 分
        
        # 存储分数（简化）
        profile.storage_score = 50  # 默认中等
        
        # 总分
        profile.overall_score = (
            profile.compute_score * 0.5 +
            profile.memory_score * 0.3 +
            profile.storage_score * 0.2
        )
    
    def _assign_sectors(self, profile: DeviceProfile):
        """根据设备自动分配板块。
        
        设计原则：
        1. 根据 GPU 具体型号精确匹配板块
        2. 同时保留 CPU 作为备选板块
        3. 主板块取性能最高的
        """
        sectors = set()
        gpu_sector = None
        
        # 根据 GPU 型号精确匹配板块
        for gpu in profile.gpu_list:
            if "No GPU" not in gpu.name:
                # 使用新的精确匹配方法
                sector = SectorMapping.get_sector_for_gpu(gpu.name)
                sectors.add(sector)
                # 记录第一个 GPU 的板块作为主板块候选
                if gpu_sector is None:
                    gpu_sector = sector
        
        # 同时加入 CPU 板块（作为备选）
        sectors.add("CPU")
        
        profile.assigned_sectors = list(sectors)
        
        # 确定主板块
        # 按优先级从高到低选取：H100 > RTX4090 > RTX3080 > CPU > GENERAL
        priority_order = ["H100", "RTX4090", "RTX3080", "CPU", "GENERAL"]
        
        profile.primary_sector = "CPU"  # 默认回退
        for ps in priority_order:
            if ps in sectors and ps != "CPU":
                profile.primary_sector = ps
                break
        
        self.log(f"📍 自动分配板块: {profile.assigned_sectors}")
        self.log(f"📍 主板块: {profile.primary_sector}")


class Benchmark:
    """硬件基准测试。"""
    
    def __init__(self, log_fn: Callable = print):
        self.log = log_fn
        self.results: Dict[str, float] = {}
    
    def run_cpu_benchmark(self, duration: float = 2.0) -> float:
        """CPU 基准测试（计算密集）。"""
        import math
        
        start = time.time()
        operations = 0
        
        while time.time() - start < duration:
            # 计算密集型操作
            for i in range(1000):
                _ = math.sqrt(i) * math.log(i + 1)
            operations += 1000
        
        elapsed = time.time() - start
        ops_per_sec = operations / elapsed
        
        self.results["cpu"] = ops_per_sec
        self.log(f"🔢 CPU: {ops_per_sec:.0f} ops/sec")
        
        return ops_per_sec
    
    def run_memory_benchmark(self, size_mb: int = 100) -> float:
        """内存基准测试。"""
        import array
        
        # 分配
        start = time.time()
        data = array.array('d', [0.0] * (size_mb * 1024 * 128))  # 8 bytes per double
        alloc_time = time.time() - start
        
        # 写入
        start = time.time()
        for i in range(len(data)):
            data[i] = float(i)
        write_time = time.time() - start
        
        # 读取
        start = time.time()
        total = sum(data)
        read_time = time.time() - start
        
        bandwidth = size_mb / (write_time + read_time)
        
        self.results["memory"] = bandwidth
        self.log(f"💾 内存: {bandwidth:.0f} MB/s")
        
        return bandwidth
    
    def run_hash_benchmark(self, iterations: int = 100000) -> float:
        """哈希计算基准测试（模拟挖矿）。"""
        import hashlib
        
        start = time.time()
        
        for i in range(iterations):
            hashlib.sha256(str(i).encode()).hexdigest()
        
        elapsed = time.time() - start
        hash_rate = iterations / elapsed
        
        self.results["hash"] = hash_rate
        self.log(f"⛏️ 哈希: {hash_rate:.0f} H/s")
        
        return hash_rate
    
    def run_all(self) -> Dict[str, float]:
        """运行所有基准测试。"""
        self.log("🏃 开始基准测试...")
        
        self.run_cpu_benchmark()
        self.run_memory_benchmark()
        self.run_hash_benchmark()
        
        # 综合分数
        overall = (
            self.results.get("cpu", 0) / 10000 * 30 +
            self.results.get("memory", 0) / 100 * 30 +
            self.results.get("hash", 0) / 100000 * 40
        )
        
        self.results["overall"] = min(100, overall)
        self.log(f"📊 综合分数: {self.results['overall']:.1f}")
        
        return self.results


# 全局检测器实例
_detector: Optional[DeviceDetector] = None


def get_device_profile() -> DeviceProfile:
    """获取设备档案（单例）。"""
    global _detector

    # ====== 集群硬件劫持 ======
    try:
        from core.cluster_manager import is_master, get_cluster_hardware_summary
        if is_master():
            cluster_hw = get_cluster_hardware_summary()
            if cluster_hw and cluster_hw.get("worker_count", 0) > 0:
                profile = DeviceProfile(
                    device_id="CLUSTER-MASTER",
                    hostname="Cluster-Master",
                    platform="Cluster",
                )
                profile.gpu_list = [GPUInfo(name=cluster_hw.get("name", "Cluster Multi-GPU"), memory_total=cluster_hw.get("memory_gb", 0)*1024, memory_free=cluster_hw.get("memory_gb", 0)*1024, compute_capability="8.0")]
                profile.compute_score = float(cluster_hw.get("compute_power", 100))
                profile.primary_sector = "AI_TRAINING"  # 因为是集群，硬编码为主力AI即可
                profile.assigned_sectors = ["AI_TRAINING", "AI_INFERENCE", "RENDERING", "GENERAL"]
                return profile
    except ImportError:
        pass
    # ==========================

    if _detector is None or _detector.profile is None:
        _detector = DeviceDetector()
        _detector.detect_all()
    
    return _detector.profile


def auto_assign_sector() -> str:
    """自动分配板块。"""
    profile = get_device_profile()
    return profile.primary_sector


def get_assigned_sectors() -> List[str]:
    """获取所有可用板块。"""
    profile = get_device_profile()
    return profile.assigned_sectors
