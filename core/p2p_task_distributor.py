"""
P2P 任务分发模块

提供分布式计算任务的创建、分发、执行和结果聚合功能。
通过 P2P 网络将计算任务分片并分配给可用矿工节点。
"""

import time
import hashlib
import json
import logging
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """节点角色。"""
    FULL = "full"
    MINER = "miner"
    LIGHT = "light"


class P2PTaskStatus(Enum):
    """P2P 任务状态。"""
    CREATED = "created"
    DISTRIBUTING = "distributing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ShardStatus(Enum):
    """分片状态。"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskShard:
    """任务分片。"""
    shard_id: str
    task_id: str
    shard_index: int
    data: bytes = b""
    status: ShardStatus = ShardStatus.PENDING
    assigned_miner: str = ""
    result: Any = None
    result_hash: str = ""
    assigned_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class P2PTask:
    """P2P 分布式任务。"""
    task_id: str
    task_name: str
    task_type: str
    task_data: bytes
    config: Dict[str, Any]
    creator_id: str
    gpu_count: int = 1
    redundancy: int = 1
    status: P2PTaskStatus = P2PTaskStatus.CREATED
    shards: List[TaskShard] = field(default_factory=list)
    aggregated_result: Any = None
    result_hash: str = ""
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "status": self.status.value,
            "shard_count": len(self.shards),
            "progress": self.progress,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class P2PTaskDistributor:
    """P2P 任务分发器。"""

    def __init__(
        self,
        node_id: str,
        p2p_node: Any = None,
        log_fn: Optional[Callable] = None,
    ):
        self.node_id = node_id
        self.p2p_node = p2p_node
        self.log_fn = log_fn or logger.info
        self.tasks: Dict[str, P2PTask] = {}
        self.available_miners: Dict[str, Dict[str, Any]] = {}
        self._task_counter = 0
        self._running = False

    def start(self):
        """启动分发器。"""
        self._running = True
        self.log_fn(f"P2P 任务分发器已启动: {self.node_id}")

    def stop(self):
        """停止分发器。"""
        self._running = False

    def create_task(
        self,
        task_name: str,
        task_type: str = "compute",
        task_data: bytes = b"",
        config: Dict = None,
        gpu_count: int = 1,
        redundancy: int = 1,
        shard_count: int = 1,
        creator_id: str = "",
    ) -> P2PTask:
        """创建新的分布式任务。"""
        self._task_counter += 1
        task_id = f"p2p_task_{self._task_counter:06d}_{int(time.time())}"

        shards = []
        for i in range(shard_count):
            shard = TaskShard(
                shard_id=f"{task_id}_shard_{i}",
                task_id=task_id,
                shard_index=i,
            )
            shards.append(shard)

        task = P2PTask(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            task_data=task_data,
            config=config or {},
            creator_id=creator_id or self.node_id,
            gpu_count=gpu_count,
            redundancy=redundancy,
            shards=shards,
        )

        self.tasks[task_id] = task
        self.log_fn(f"P2P 任务已创建: {task_id} ({task_name})")
        return task

    async def distribute_task(self, task_id: str) -> bool:
        """分发任务的分片到可用矿工。"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        task.status = P2PTaskStatus.DISTRIBUTING

        miners = list(self.available_miners.keys())
        if not miners:
            logger.warning(f"无可用矿工，任务 {task_id} 分发失败")
            task.status = P2PTaskStatus.FAILED
            return False

        for i, shard in enumerate(task.shards):
            miner_id = miners[i % len(miners)]
            shard.assigned_miner = miner_id
            shard.status = ShardStatus.ASSIGNED
            shard.assigned_at = time.time()

            if self.p2p_node:
                try:
                    await self._send_shard_to_miner(miner_id, shard, task)
                except Exception as e:
                    logger.error(f"分片 {shard.shard_id} 发送失败: {e}")
                    shard.status = ShardStatus.FAILED

        task.status = P2PTaskStatus.RUNNING
        self.log_fn(f"任务 {task_id} 已分发到 {len(miners)} 个矿工")
        return True

    async def _send_shard_to_miner(
        self, miner_id: str, shard: TaskShard, task: P2PTask
    ):
        """通过 P2P 网络发送分片到矿工。"""
        if not self.p2p_node:
            return

        message = {
            "type": "task_shard",
            "task_id": task.task_id,
            "shard_id": shard.shard_id,
            "shard_index": shard.shard_index,
            "task_type": task.task_type,
            "config": task.config,
        }

        if hasattr(self.p2p_node, 'send_to_peer'):
            await self.p2p_node.send_to_peer(miner_id, json.dumps(message))

    def submit_shard_result(
        self,
        task_id: str,
        shard_id: str,
        miner_id: str,
        result: Any,
        result_hash: str = "",
    ) -> bool:
        """提交分片计算结果。"""
        task = self.tasks.get(task_id)
        if not task:
            return False

        for shard in task.shards:
            if shard.shard_id == shard_id:
                shard.result = result
                shard.result_hash = result_hash
                shard.status = ShardStatus.COMPLETED
                shard.completed_at = time.time()
                break
        else:
            return False

        # 更新进度
        completed = sum(1 for s in task.shards if s.status == ShardStatus.COMPLETED)
        task.progress = completed / len(task.shards) if task.shards else 0

        # 如果所有分片完成，聚合结果
        if completed == len(task.shards):
            self._aggregate_results(task)

        return True

    def _aggregate_results(self, task: P2PTask):
        """聚合所有分片的结果。"""
        results = [s.result for s in task.shards if s.result is not None]
        task.aggregated_result = results
        result_str = json.dumps(results, sort_keys=True, default=str)
        task.result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:32]
        task.status = P2PTaskStatus.COMPLETED
        task.completed_at = time.time()
        self.log_fn(f"任务 {task.task_id} 已完成，结果哈希: {task.result_hash}")

    def register_miner(self, miner_id: str, info: Dict[str, Any]):
        """注册可用矿工。"""
        info["node_id"] = miner_id
        self.available_miners[miner_id] = info
        self.log_fn(f"矿工已注册: {miner_id}")

    def unregister_miner(self, miner_id: str):
        """注销矿工。"""
        self.available_miners.pop(miner_id, None)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态。"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        return task.to_dict()

    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务。"""
        return [t.to_dict() for t in self.tasks.values()]

    def get_stats(self) -> Dict[str, Any]:
        """获取分发器统计信息。"""
        status_counts = {}
        for task in self.tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "node_id": self.node_id,
            "total_tasks": len(self.tasks),
            "available_miners": len(self.available_miners),
            "status_counts": status_counts,
            "running": self._running,
        }


class P2PComputeNode:
    """P2P 计算节点 — 接收并执行分片任务。"""

    def __init__(
        self,
        node_id: str,
        p2p_node: Any = None,
        log_fn: Optional[Callable] = None,
    ):
        self.node_id = node_id
        self.p2p_node = p2p_node
        self.log_fn = log_fn or logger.info
        self.active_shards: Dict[str, TaskShard] = {}
        self._running = False

    def start(self):
        self._running = True

    def stop(self):
        self._running = False

    async def execute_shard(self, shard: TaskShard, task_config: Dict) -> Any:
        """执行一个分片任务。"""
        shard.status = ShardStatus.RUNNING
        self.active_shards[shard.shard_id] = shard

        try:
            # 实际计算逻辑由上层注入
            result = {"status": "completed", "shard_index": shard.shard_index}
            shard.result = result
            shard.status = ShardStatus.COMPLETED
            shard.completed_at = time.time()
            return result
        except Exception as e:
            shard.status = ShardStatus.FAILED
            logger.error(f"分片执行失败 {shard.shard_id}: {e}")
            return None
        finally:
            self.active_shards.pop(shard.shard_id, None)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "active_shards": len(self.active_shards),
            "running": self._running,
        }


class P2PTaskMessageHandler:
    """P2P 任务消息处理器 — 处理任务相关的 P2P 消息。"""

    def __init__(
        self,
        distributor: P2PTaskDistributor,
        compute_node: P2PComputeNode,
        log_fn: Optional[Callable] = None,
    ):
        self.distributor = distributor
        self.compute_node = compute_node
        self.log_fn = log_fn or logger.info

    async def handle_message(self, peer_id: str, message: Dict[str, Any]):
        """处理收到的 P2P 任务消息。"""
        msg_type = message.get("type", "")

        if msg_type == "task_shard":
            await self._handle_shard_assignment(peer_id, message)
        elif msg_type == "shard_result":
            self._handle_shard_result(peer_id, message)
        elif msg_type == "task_status_query":
            self._handle_status_query(peer_id, message)

    async def _handle_shard_assignment(self, peer_id: str, message: Dict):
        """处理分片分配消息。"""
        shard = TaskShard(
            shard_id=message["shard_id"],
            task_id=message["task_id"],
            shard_index=message["shard_index"],
            assigned_miner=self.compute_node.node_id,
            status=ShardStatus.ASSIGNED,
            assigned_at=time.time(),
        )

        result = await self.compute_node.execute_shard(shard, message.get("config", {}))

        # 返回结果给分发者
        if result is not None and self.compute_node.p2p_node:
            result_msg = {
                "type": "shard_result",
                "task_id": shard.task_id,
                "shard_id": shard.shard_id,
                "miner_id": self.compute_node.node_id,
                "result": result,
                "result_hash": hashlib.sha256(
                    json.dumps(result, default=str).encode()
                ).hexdigest()[:16],
            }
            if hasattr(self.compute_node.p2p_node, 'send_to_peer'):
                await self.compute_node.p2p_node.send_to_peer(
                    peer_id, json.dumps(result_msg)
                )

    def _handle_shard_result(self, peer_id: str, message: Dict):
        """处理分片结果消息。"""
        self.distributor.submit_shard_result(
            task_id=message["task_id"],
            shard_id=message["shard_id"],
            miner_id=message.get("miner_id", peer_id),
            result=message.get("result"),
            result_hash=message.get("result_hash", ""),
        )

    def _handle_status_query(self, peer_id: str, message: Dict):
        """处理任务状态查询。"""
        task_id = message.get("task_id", "")
        status = self.distributor.get_task_status(task_id)
        self.log_fn(f"状态查询 from {peer_id}: {task_id} -> {status}")


def create_p2p_task_system(
    node_id: str,
    p2p_node: Any = None,
    role: NodeRole = NodeRole.FULL,
    log_fn: Optional[Callable] = None,
) -> Tuple[P2PTaskDistributor, P2PComputeNode, P2PTaskMessageHandler]:
    """创建完整的 P2P 任务系统。

    Returns:
        (distributor, compute_node, message_handler)
    """
    distributor = P2PTaskDistributor(
        node_id=node_id,
        p2p_node=p2p_node,
        log_fn=log_fn,
    )

    compute_node = P2PComputeNode(
        node_id=node_id,
        p2p_node=p2p_node,
        log_fn=log_fn,
    )

    message_handler = P2PTaskMessageHandler(
        distributor=distributor,
        compute_node=compute_node,
        log_fn=log_fn,
    )

    if role in (NodeRole.FULL, NodeRole.MINER):
        compute_node.start()

    return distributor, compute_node, message_handler
