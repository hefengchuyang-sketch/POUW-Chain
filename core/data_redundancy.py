"""
data_redundancy.py - 数据冗余与备份系统

Phase 10 功能：
1. IPFS 集成（分布式存储）
2. 热备份（实时同步）
3. 增量备份（成本优化）
4. 数据分片与纠删码
5. 灾难恢复
6. 数据完整性验证
"""

import time
import uuid
import hashlib
import threading
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
from collections import defaultdict
import base64
import zlib


# ============== 枚举类型 ==============

class StorageBackend(Enum):
    """存储后端"""
    LOCAL = "local"
    IPFS = "ipfs"
    S3 = "s3"
    DISTRIBUTED = "distributed"


class ReplicationMode(Enum):
    """复制模式"""
    SYNC = "sync"                      # 同步复制
    ASYNC = "async"                    # 异步复制
    SEMI_SYNC = "semi_sync"            # 半同步


class BackupType(Enum):
    """备份类型"""
    FULL = "full"                      # 全量备份
    INCREMENTAL = "incremental"        # 增量备份
    DIFFERENTIAL = "differential"      # 差异备份


class DataState(Enum):
    """数据状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    CORRUPTED = "corrupted"


class RecoveryPriority(Enum):
    """恢复优先级"""
    CRITICAL = "critical"              # 关键数据
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# ============== 数据结构 ==============

@dataclass
class DataShard:
    """数据分片"""
    shard_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 数据
    data: bytes = b""
    checksum: str = ""
    size: int = 0
    
    # 位置
    shard_index: int = 0
    total_shards: int = 1
    is_parity: bool = False            # 是否是奇偶校验分片
    
    # 存储位置
    storage_nodes: List[str] = field(default_factory=list)
    replicas: int = 0
    
    # 状态
    state: DataState = DataState.ACTIVE
    verified: bool = False
    last_verified: float = 0
    
    created_at: float = field(default_factory=time.time)
    
    def compute_checksum(self) -> str:
        """计算校验和"""
        self.checksum = hashlib.sha256(self.data).hexdigest()
        return self.checksum
    
    def verify(self) -> bool:
        """验证完整性"""
        expected = self.checksum
        actual = hashlib.sha256(self.data).hexdigest()
        self.verified = expected == actual
        self.last_verified = time.time()
        return self.verified


@dataclass
class DataObject:
    """数据对象"""
    object_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    
    # 元数据
    name: str = ""
    content_type: str = "application/octet-stream"
    size: int = 0
    checksum: str = ""
    
    # 分片信息
    shards: List[str] = field(default_factory=list)     # shard_ids
    shard_size: int = 4 * 1024 * 1024                   # 4MB
    total_shards: int = 0
    parity_shards: int = 0                              # 纠删码分片数
    
    # 存储
    storage_backend: StorageBackend = StorageBackend.DISTRIBUTED
    replication_factor: int = 3
    
    # IPFS
    ipfs_hash: str = ""
    
    # 状态
    state: DataState = DataState.ACTIVE
    recovery_priority: RecoveryPriority = RecoveryPriority.NORMAL
    
    # 时间
    created_at: float = field(default_factory=time.time)
    modified_at: float = 0
    last_accessed: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "object_id": self.object_id,
            "name": self.name,
            "size": self.size,
            "checksum": self.checksum,
            "storage_backend": self.storage_backend.value,
            "replication_factor": self.replication_factor,
            "ipfs_hash": self.ipfs_hash,
            "state": self.state.value,
            "total_shards": self.total_shards,
        }


@dataclass
class BackupJob:
    """备份任务"""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 配置
    backup_type: BackupType = BackupType.INCREMENTAL
    source_path: str = ""
    destination: str = ""
    
    # 状态
    status: str = "pending"            # pending, running, completed, failed
    progress: float = 0.0
    
    # 统计
    total_objects: int = 0
    processed_objects: int = 0
    total_bytes: int = 0
    processed_bytes: int = 0
    
    # 时间
    started_at: float = 0
    completed_at: float = 0
    scheduled_at: float = field(default_factory=time.time)
    
    # 错误
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "backup_type": self.backup_type.value,
            "status": self.status,
            "progress": self.progress,
            "total_objects": self.total_objects,
            "processed_objects": self.processed_objects,
            "started_at": self.started_at,
        }


@dataclass
class StorageNode:
    """存储节点"""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 信息
    endpoint: str = ""
    region: str = ""
    zone: str = ""
    
    # 容量
    total_capacity: int = 0            # bytes
    used_capacity: int = 0
    reserved_capacity: int = 0
    
    # 状态
    online: bool = True
    healthy: bool = True
    read_only: bool = False
    
    # 性能
    read_latency_ms: float = 0
    write_latency_ms: float = 0
    iops: int = 0
    
    # 统计
    objects_stored: int = 0
    read_count: int = 0
    write_count: int = 0
    
    last_heartbeat: float = field(default_factory=time.time)
    
    @property
    def available_capacity(self) -> int:
        return self.total_capacity - self.used_capacity - self.reserved_capacity
    
    @property
    def usage_percent(self) -> float:
        if self.total_capacity == 0:
            return 0
        return (self.used_capacity / self.total_capacity) * 100
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "endpoint": self.endpoint,
            "online": self.online,
            "healthy": self.healthy,
            "usage_percent": round(self.usage_percent, 2),
            "available_capacity": self.available_capacity,
        }


# ============== IPFS 模拟层 ==============

class IPFSSimulator:
    """IPFS 模拟器（用于测试）"""
    
    def __init__(self):
        self.objects: Dict[str, bytes] = {}
        self.pins: Set[str] = set()
        self._lock = threading.RLock()
    
    def add(self, data: bytes) -> str:
        """添加数据到 IPFS"""
        with self._lock:
            # 模拟 IPFS CID（Content Identifier）
            content_hash = hashlib.sha256(data).hexdigest()
            cid = f"Qm{content_hash[:44]}"
            
            self.objects[cid] = data
            return cid
    
    def get(self, cid: str) -> Optional[bytes]:
        """从 IPFS 获取数据"""
        with self._lock:
            return self.objects.get(cid)
    
    def pin(self, cid: str) -> bool:
        """固定数据（防止被垃圾回收）"""
        with self._lock:
            if cid in self.objects:
                self.pins.add(cid)
                return True
            return False
    
    def unpin(self, cid: str) -> bool:
        """取消固定"""
        with self._lock:
            if cid in self.pins:
                self.pins.remove(cid)
                return True
            return False
    
    def stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            total_size = sum(len(d) for d in self.objects.values())
            return {
                "objects": len(self.objects),
                "pins": len(self.pins),
                "total_size": total_size,
            }


# ============== 纠删码 ==============

class ErasureCoding:
    """简化的纠删码实现"""
    
    def __init__(self, data_shards: int = 4, parity_shards: int = 2):
        self.data_shards = data_shards
        self.parity_shards = parity_shards
        self.total_shards = data_shards + parity_shards
    
    def encode(self, data: bytes) -> List[bytes]:
        """编码数据为分片"""
        # 填充到可以均分的大小
        shard_size = (len(data) + self.data_shards - 1) // self.data_shards
        padded_data = data.ljust(shard_size * self.data_shards, b'\x00')
        
        # 分割数据分片
        shards = []
        for i in range(self.data_shards):
            start = i * shard_size
            end = start + shard_size
            shards.append(padded_data[start:end])
        
        # 生成奇偶校验分片
        for p in range(self.parity_shards):
            parity = bytes(shard_size)
            for i, shard in enumerate(shards):
                # 简化的 XOR 奇偶校验
                parity = bytes(a ^ b for a, b in zip(parity, shard))
            # 添加一些变化以区分不同的奇偶分片
            parity = bytes((b + p) % 256 for b in parity)
            shards.append(parity)
        
        return shards
    
    def decode(self, shards: List[Optional[bytes]], original_size: int) -> bytes:
        """从分片恢复数据"""
        # 检查是否有足够的分片
        available = [i for i, s in enumerate(shards) if s is not None]
        
        if len(available) < self.data_shards:
            raise ValueError("Not enough shards to recover data")
        
        # 如果所有数据分片都可用，直接拼接
        if all(shards[i] is not None for i in range(self.data_shards)):
            data = b"".join(shards[:self.data_shards])
            return data[:original_size]
        
        # 利用 XOR 校验恢复单个丢失的数据分片
        missing_data = [i for i in range(self.data_shards) if shards[i] is None]
        if len(missing_data) == 1 and shards[self.data_shards] is not None:
            # 单分片恢复: missing = parity XOR 所有其他数据分片
            idx = missing_data[0]
            recovered = bytearray(shards[self.data_shards])
            for i in range(self.data_shards):
                if i != idx and shards[i] is not None:
                    recovered = bytearray(a ^ b for a, b in zip(recovered, shards[i]))
            shards[idx] = bytes(recovered)
            data = b"".join(shards[:self.data_shards])
            return data[:original_size]
        
        # 多分片丢失需要 Reed-Solomon，当前仅支持单分片恢复
        raise ValueError(f"Cannot recover {len(missing_data)} missing data shards (max 1)")
    
    def verify(self, shards: List[bytes]) -> bool:
        """验证分片完整性"""
        if len(shards) != self.total_shards:
            return False
        
        # 检查所有分片长度一致
        shard_size = len(shards[0])
        if any(len(s) != shard_size for s in shards):
            return False
        
        # 验证第一个奇偶校验分片
        expected_parity = bytes(shard_size)
        for shard in shards[:self.data_shards]:
            expected_parity = bytes(a ^ b for a, b in zip(expected_parity, shard))
        
        # 与第一个 parity 分片对比（p=0 时偏移量为 0）
        actual_parity = shards[self.data_shards]
        return expected_parity == actual_parity


# ============== 数据冗余管理器 ==============

class DataRedundancyManager:
    """数据冗余管理器"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # 存储
        self.objects: Dict[str, DataObject] = {}
        self.shards: Dict[str, DataShard] = {}
        self.storage_nodes: Dict[str, StorageNode] = {}
        
        # IPFS
        self.ipfs = IPFSSimulator()
        
        # 纠删码
        self.erasure_coding = ErasureCoding(data_shards=4, parity_shards=2)
        
        # 备份
        self.backup_jobs: Dict[str, BackupJob] = {}
        self.backup_checkpoints: Dict[str, float] = {}  # object_id -> last_backup_time
        
        # 热备份配置
        self.hot_backup_enabled = True
        self.replication_mode = ReplicationMode.ASYNC
        
        # 统计
        self.stats = {
            "total_objects": 0,
            "total_shards": 0,
            "total_bytes": 0,
            "replicated_bytes": 0,
            "backup_count": 0,
            "recovery_count": 0,
        }
        
        # 初始化默认存储节点
        self._init_default_nodes()
    
    def _init_default_nodes(self):
        """初始化默认存储节点"""
        regions = ["us-east", "us-west", "eu-west", "ap-east"]
        for i, region in enumerate(regions):
            node = StorageNode(
                node_id=f"node_{i+1}",
                endpoint=f"storage-{region}.pouwchain.io",
                region=region,
                zone=f"{region}-a",
                total_capacity=1024 * 1024 * 1024 * 100,  # 100GB
            )
            self.storage_nodes[node.node_id] = node
    
    def store_object(
        self,
        data: bytes,
        name: str = "",
        replication_factor: int = 3,
        use_erasure_coding: bool = False,
        use_ipfs: bool = False,
    ) -> DataObject:
        """存储数据对象"""
        with self._lock:
            obj = DataObject(
                name=name or f"object_{uuid.uuid4().hex[:8]}",
                size=len(data),
                checksum=hashlib.sha256(data).hexdigest(),
                replication_factor=replication_factor,
            )
            
            # IPFS 存储
            if use_ipfs:
                obj.ipfs_hash = self.ipfs.add(data)
                self.ipfs.pin(obj.ipfs_hash)
                obj.storage_backend = StorageBackend.IPFS
            
            # 分片存储
            if use_erasure_coding:
                shard_data_list = self.erasure_coding.encode(data)
                obj.total_shards = len(shard_data_list)
                obj.parity_shards = self.erasure_coding.parity_shards
                
                for i, shard_data in enumerate(shard_data_list):
                    shard = DataShard(
                        data=shard_data,
                        size=len(shard_data),
                        shard_index=i,
                        total_shards=len(shard_data_list),
                        is_parity=i >= self.erasure_coding.data_shards,
                    )
                    shard.compute_checksum()
                    
                    # 分配存储节点
                    nodes = self._select_storage_nodes(replication_factor)
                    shard.storage_nodes = [n.node_id for n in nodes]
                    shard.replicas = len(nodes)
                    
                    self.shards[shard.shard_id] = shard
                    obj.shards.append(shard.shard_id)
                    
                    self.stats["total_shards"] += 1
            else:
                # 单一分片
                shard = DataShard(
                    data=data,
                    size=len(data),
                )
                shard.compute_checksum()
                
                nodes = self._select_storage_nodes(replication_factor)
                shard.storage_nodes = [n.node_id for n in nodes]
                shard.replicas = len(nodes)
                
                self.shards[shard.shard_id] = shard
                obj.shards.append(shard.shard_id)
                obj.total_shards = 1
                
                self.stats["total_shards"] += 1
            
            self.objects[obj.object_id] = obj
            self.stats["total_objects"] += 1
            self.stats["total_bytes"] += obj.size
            self.stats["replicated_bytes"] += obj.size * replication_factor
            
            # 热备份
            if self.hot_backup_enabled:
                self._trigger_hot_backup(obj)
            
            return obj
    
    def _select_storage_nodes(self, count: int) -> List[StorageNode]:
        """选择存储节点（跨区域分布）"""
        available = [
            n for n in self.storage_nodes.values()
            if n.online and n.healthy and not n.read_only
        ]
        
        # 按区域分组
        by_region: Dict[str, List[StorageNode]] = defaultdict(list)
        for node in available:
            by_region[node.region].append(node)
        
        # 优先选择不同区域的节点
        selected = []
        regions = list(by_region.keys())
        
        for i in range(min(count, len(available))):
            region = regions[i % len(regions)]
            if by_region[region]:
                # 选择使用率最低的节点
                node = min(by_region[region], key=lambda n: n.usage_percent)
                selected.append(node)
                by_region[region].remove(node)
        
        return selected
    
    def retrieve_object(self, object_id: str) -> Optional[bytes]:
        """获取数据对象"""
        with self._lock:
            obj = self.objects.get(object_id)
            if not obj:
                return None
            
            obj.last_accessed = time.time()
            
            # 从 IPFS 获取
            if obj.ipfs_hash:
                data = self.ipfs.get(obj.ipfs_hash)
                if data:
                    return data
            
            # 从分片获取
            if obj.shards:
                if obj.parity_shards > 0:
                    # 纠删码恢复
                    shard_data = []
                    for shard_id in obj.shards:
                        shard = self.shards.get(shard_id)
                        if shard and shard.verify():
                            shard_data.append(shard.data)
                        else:
                            shard_data.append(None)
                    
                    return self.erasure_coding.decode(shard_data, obj.size)
                else:
                    # 单一分片
                    shard = self.shards.get(obj.shards[0])
                    if shard and shard.verify():
                        return shard.data
            
            return None
    
    def _trigger_hot_backup(self, obj: DataObject):
        """触发热备份"""
        # 模拟实时同步到备份节点
        self.backup_checkpoints[obj.object_id] = time.time()
    
    def create_backup(
        self,
        backup_type: BackupType = BackupType.INCREMENTAL,
        source_objects: List[str] = None,
    ) -> BackupJob:
        """创建备份任务"""
        with self._lock:
            job = BackupJob(
                backup_type=backup_type,
            )
            
            # 确定需要备份的对象
            if source_objects:
                objects_to_backup = [
                    self.objects[oid] for oid in source_objects
                    if oid in self.objects
                ]
            else:
                objects_to_backup = list(self.objects.values())
            
            # 增量备份：只备份自上次备份后修改的对象
            if backup_type == BackupType.INCREMENTAL:
                objects_to_backup = [
                    obj for obj in objects_to_backup
                    if obj.modified_at > self.backup_checkpoints.get(obj.object_id, 0)
                    or obj.object_id not in self.backup_checkpoints
                ]
            
            job.total_objects = len(objects_to_backup)
            job.total_bytes = sum(obj.size for obj in objects_to_backup)
            job.status = "running"
            job.started_at = time.time()
            
            # 模拟备份过程
            for obj in objects_to_backup:
                job.processed_objects += 1
                job.processed_bytes += obj.size
                job.progress = job.processed_objects / max(job.total_objects, 1)
                self.backup_checkpoints[obj.object_id] = time.time()
            
            job.status = "completed"
            job.completed_at = time.time()
            
            self.backup_jobs[job.job_id] = job
            self.stats["backup_count"] += 1
            
            return job
    
    def verify_integrity(self, object_id: str = None) -> Dict:
        """验证数据完整性"""
        with self._lock:
            results = {
                "verified": 0,
                "corrupted": 0,
                "missing": 0,
                "details": [],
            }
            
            objects_to_check = [self.objects[object_id]] if object_id else list(self.objects.values())
            
            for obj in objects_to_check:
                obj_result = {
                    "object_id": obj.object_id,
                    "name": obj.name,
                    "status": "ok",
                    "shards_verified": 0,
                    "shards_corrupted": 0,
                }
                
                for shard_id in obj.shards:
                    shard = self.shards.get(shard_id)
                    if not shard:
                        obj_result["status"] = "missing"
                        results["missing"] += 1
                    elif not shard.verify():
                        obj_result["shards_corrupted"] += 1
                        obj_result["status"] = "corrupted"
                        results["corrupted"] += 1
                    else:
                        obj_result["shards_verified"] += 1
                        results["verified"] += 1
                
                results["details"].append(obj_result)
            
            return results
    
    def recover_object(self, object_id: str, from_backup: bool = False) -> bool:
        """恢复数据对象"""
        with self._lock:
            obj = self.objects.get(object_id)
            if not obj:
                return False
            
            self.stats["recovery_count"] += 1
            
            # 从 IPFS 恢复
            if obj.ipfs_hash:
                data = self.ipfs.get(obj.ipfs_hash)
                if data:
                    # 重新创建分片
                    return True
            
            # 纠删码恢复
            if obj.parity_shards > 0:
                available_shards = []
                for shard_id in obj.shards:
                    shard = self.shards.get(shard_id)
                    if shard and shard.verify():
                        available_shards.append(shard.data)
                    else:
                        available_shards.append(None)
                
                try:
                    data = self.erasure_coding.decode(available_shards, obj.size)
                    # 重新创建丢失的分片
                    return True
                except Exception:
                    pass
            
            return False
    
    def get_storage_stats(self) -> Dict:
        """获取存储统计"""
        with self._lock:
            node_stats = [n.to_dict() for n in self.storage_nodes.values()]
            
            return {
                **self.stats,
                "nodes": node_stats,
                "ipfs": self.ipfs.stats(),
                "hot_backup_enabled": self.hot_backup_enabled,
                "replication_mode": self.replication_mode.value,
            }
    
    def register_storage_node(
        self,
        endpoint: str,
        region: str,
        capacity: int,
    ) -> StorageNode:
        """注册存储节点"""
        with self._lock:
            node = StorageNode(
                endpoint=endpoint,
                region=region,
                total_capacity=capacity,
            )
            self.storage_nodes[node.node_id] = node
            return node


# ============== 全局实例 ==============

_data_redundancy_manager: Optional[DataRedundancyManager] = None


def get_data_redundancy_manager() -> DataRedundancyManager:
    """获取数据冗余管理器单例"""
    global _data_redundancy_manager
    if _data_redundancy_manager is None:
        _data_redundancy_manager = DataRedundancyManager()
    return _data_redundancy_manager
