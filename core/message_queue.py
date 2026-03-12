"""
message_queue.py - 分布式消息队列系统

Phase 10 功能：
1. 异步消息传递（Kafka/RabbitMQ 风格）
2. 发布/订阅模式
3. 消息持久化
4. 消息重试与死信队列
5. 模块间解耦通信
6. 高可用与容错
"""

import time
import uuid
import hashlib
import threading
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from enum import Enum
from collections import defaultdict, deque
import json
import heapq


# ============== 枚举类型 ==============

class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    EXPIRED = "expired"


class DeliveryMode(Enum):
    """投递模式"""
    AT_MOST_ONCE = "at_most_once"      # 最多一次
    AT_LEAST_ONCE = "at_least_once"    # 至少一次
    EXACTLY_ONCE = "exactly_once"       # 精确一次


class ExchangeType(Enum):
    """交换机类型"""
    DIRECT = "direct"                  # 直接路由
    FANOUT = "fanout"                  # 广播
    TOPIC = "topic"                    # 主题匹配
    HEADERS = "headers"                # 头部匹配


# ============== 数据结构 ==============

@dataclass
class Message:
    """消息"""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    
    # 内容
    topic: str = ""
    payload: Any = None
    headers: Dict = field(default_factory=dict)
    
    # 路由
    routing_key: str = ""
    exchange: str = ""
    
    # 优先级与状态
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    
    # 投递配置
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE
    ttl_seconds: int = 3600            # 消息过期时间
    max_retries: int = 3               # 最大重试次数
    retry_count: int = 0
    retry_delay_seconds: int = 60      # 重试延迟
    
    # 时间
    created_at: float = field(default_factory=time.time)
    scheduled_at: float = 0            # 延迟消息
    processed_at: float = 0
    expires_at: float = 0
    
    # 确认
    ack_required: bool = True
    acked: bool = False
    acked_by: str = ""
    
    # 关联
    correlation_id: str = ""           # 关联请求
    reply_to: str = ""                 # 回复队列
    
    def __post_init__(self):
        if self.expires_at == 0 and self.ttl_seconds > 0:
            self.expires_at = self.created_at + self.ttl_seconds
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return self.expires_at > 0 and time.time() > self.expires_at
    
    def should_retry(self) -> bool:
        """检查是否应该重试"""
        return self.retry_count < self.max_retries and not self.is_expired()
    
    def __lt__(self, other):
        """优先级排序"""
        # 高优先级先处理
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        # 同优先级按时间
        return self.created_at < other.created_at
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "routing_key": self.routing_key,
            "priority": self.priority.name,
            "status": self.status.value,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "payload_type": type(self.payload).__name__,
        }


@dataclass
class Queue:
    """消息队列"""
    name: str
    
    # 配置
    durable: bool = True               # 持久化
    exclusive: bool = False            # 独占
    auto_delete: bool = False          # 自动删除
    max_length: int = 10000            # 最大长度
    max_bytes: int = 0                 # 最大字节数
    
    # 死信配置
    dead_letter_exchange: str = ""
    dead_letter_routing_key: str = ""
    
    # 状态
    messages: List[Message] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    
    # 统计
    message_count: int = 0
    consumer_count: int = 0
    publish_count: int = 0
    consume_count: int = 0
    
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "durable": self.durable,
            "message_count": len(self.messages),
            "consumer_count": len(self.consumers),
            "max_length": self.max_length,
            "publish_count": self.publish_count,
            "consume_count": self.consume_count,
        }


@dataclass
class Exchange:
    """交换机"""
    name: str
    exchange_type: ExchangeType = ExchangeType.DIRECT
    
    # 配置
    durable: bool = True
    auto_delete: bool = False
    
    # 绑定关系
    bindings: Dict[str, List[str]] = field(default_factory=dict)  # routing_key -> [queue_names]
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.exchange_type.value,
            "durable": self.durable,
            "bindings_count": sum(len(v) for v in self.bindings.values()),
        }


@dataclass
class Consumer:
    """消费者"""
    consumer_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    queue_name: str = ""
    
    # 回调
    callback: Optional[Callable] = None
    
    # 配置
    prefetch_count: int = 10           # 预取数量
    auto_ack: bool = False
    exclusive: bool = False
    
    # 状态
    active: bool = True
    processing_count: int = 0
    
    # 统计
    messages_consumed: int = 0
    messages_acked: int = 0
    messages_rejected: int = 0
    
    created_at: float = field(default_factory=time.time)


# ============== 消息代理 ==============

class MessageBroker:
    """消息代理"""
    
    def __init__(self):
        self.queues: Dict[str, Queue] = {}
        self.exchanges: Dict[str, Exchange] = {}
        self.consumers: Dict[str, Consumer] = {}
        self.dead_letter_queue: Queue = Queue(name="__dead_letter__")
        
        self._lock = threading.RLock()
        self._processing = True
        self._worker_threads: List[threading.Thread] = []
        
        # 消息存储（模拟持久化）
        self.message_store: Dict[str, Message] = {}
        
        # 延迟消息堆
        self.delayed_messages: List[Tuple[float, str]] = []  # (scheduled_time, message_id)
        
        # 统计
        self.stats = {
            "total_published": 0,
            "total_consumed": 0,
            "total_acked": 0,
            "total_rejected": 0,
            "total_dead_lettered": 0,
        }
        
        # 创建默认交换机
        self._create_default_exchanges()
    
    def _create_default_exchanges(self):
        """创建默认交换机"""
        # 默认直接交换机
        self.exchanges[""] = Exchange(name="", exchange_type=ExchangeType.DIRECT)
        # 扇出交换机
        self.exchanges["amq.fanout"] = Exchange(name="amq.fanout", exchange_type=ExchangeType.FANOUT)
        # 主题交换机
        self.exchanges["amq.topic"] = Exchange(name="amq.topic", exchange_type=ExchangeType.TOPIC)
    
    def declare_queue(
        self,
        name: str,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
        max_length: int = 10000,
        dead_letter_exchange: str = "",
    ) -> Queue:
        """声明队列"""
        with self._lock:
            if name in self.queues:
                return self.queues[name]
            
            queue = Queue(
                name=name,
                durable=durable,
                exclusive=exclusive,
                auto_delete=auto_delete,
                max_length=max_length,
                dead_letter_exchange=dead_letter_exchange,
            )
            
            self.queues[name] = queue
            return queue
    
    def declare_exchange(
        self,
        name: str,
        exchange_type: ExchangeType = ExchangeType.DIRECT,
        durable: bool = True,
    ) -> Exchange:
        """声明交换机"""
        with self._lock:
            if name in self.exchanges:
                return self.exchanges[name]
            
            exchange = Exchange(
                name=name,
                exchange_type=exchange_type,
                durable=durable,
            )
            
            self.exchanges[name] = exchange
            return exchange
    
    def bind_queue(
        self,
        queue_name: str,
        exchange_name: str,
        routing_key: str = "",
    ) -> bool:
        """绑定队列到交换机"""
        with self._lock:
            if queue_name not in self.queues:
                return False
            if exchange_name not in self.exchanges:
                return False
            
            exchange = self.exchanges[exchange_name]
            if routing_key not in exchange.bindings:
                exchange.bindings[routing_key] = []
            
            if queue_name not in exchange.bindings[routing_key]:
                exchange.bindings[routing_key].append(queue_name)
            
            return True
    
    def publish(
        self,
        message: Message,
        exchange_name: str = "",
        routing_key: str = "",
    ) -> str:
        """发布消息"""
        with self._lock:
            message.exchange = exchange_name
            message.routing_key = routing_key
            
            # 存储消息
            self.message_store[message.message_id] = message
            
            # 检查延迟消息
            if message.scheduled_at > time.time():
                heapq.heappush(self.delayed_messages, (message.scheduled_at, message.message_id))
                return message.message_id
            
            # 路由消息
            self._route_message(message)
            
            self.stats["total_published"] += 1
            return message.message_id
    
    def _route_message(self, message: Message):
        """路由消息到队列"""
        exchange = self.exchanges.get(message.exchange, self.exchanges[""])
        
        target_queues = []
        
        if exchange.exchange_type == ExchangeType.DIRECT:
            # 直接匹配
            target_queues = exchange.bindings.get(message.routing_key, [])
            # 默认交换机直接路由到同名队列
            if exchange.name == "" and message.routing_key in self.queues:
                target_queues = [message.routing_key]
        
        elif exchange.exchange_type == ExchangeType.FANOUT:
            # 广播到所有绑定队列
            for queues in exchange.bindings.values():
                target_queues.extend(queues)
            target_queues = list(set(target_queues))
        
        elif exchange.exchange_type == ExchangeType.TOPIC:
            # 主题匹配
            for pattern, queues in exchange.bindings.items():
                if self._match_topic(message.routing_key, pattern):
                    target_queues.extend(queues)
            target_queues = list(set(target_queues))
        
        # 投递到目标队列
        for queue_name in target_queues:
            queue = self.queues.get(queue_name)
            if queue:
                if len(queue.messages) < queue.max_length:
                    queue.messages.append(message)
                    queue.publish_count += 1
                else:
                    # 队列满，发送到死信
                    self._send_to_dead_letter(message, "queue_full")
    
    def _match_topic(self, routing_key: str, pattern: str) -> bool:
        """匹配主题模式"""
        # 简化的主题匹配
        # * 匹配一个单词
        # # 匹配零个或多个单词
        rk_parts = routing_key.split(".")
        pattern_parts = pattern.split(".")
        
        return self._topic_match_recursive(rk_parts, pattern_parts)
    
    def _topic_match_recursive(self, rk_parts: List[str], pattern_parts: List[str]) -> bool:
        """递归主题匹配"""
        if not pattern_parts:
            return not rk_parts
        
        if pattern_parts[0] == "#":
            if len(pattern_parts) == 1:
                return True
            # # 可以匹配零个或多个
            for i in range(len(rk_parts) + 1):
                if self._topic_match_recursive(rk_parts[i:], pattern_parts[1:]):
                    return True
            return False
        
        if not rk_parts:
            return False
        
        if pattern_parts[0] == "*" or pattern_parts[0] == rk_parts[0]:
            return self._topic_match_recursive(rk_parts[1:], pattern_parts[1:])
        
        return False
    
    def consume(
        self,
        queue_name: str,
        callback: Callable,
        auto_ack: bool = False,
        prefetch_count: int = 10,
    ) -> str:
        """注册消费者"""
        with self._lock:
            if queue_name not in self.queues:
                raise ValueError(f"Queue {queue_name} not found")
            
            consumer = Consumer(
                queue_name=queue_name,
                callback=callback,
                auto_ack=auto_ack,
                prefetch_count=prefetch_count,
            )
            
            self.consumers[consumer.consumer_id] = consumer
            self.queues[queue_name].consumers.append(consumer.consumer_id)
            
            return consumer.consumer_id
    
    def get_message(self, queue_name: str, auto_ack: bool = False) -> Optional[Message]:
        """获取消息（拉取模式）"""
        with self._lock:
            queue = self.queues.get(queue_name)
            if not queue or not queue.messages:
                return None
            
            # 获取最高优先级消息
            queue.messages.sort()
            message = queue.messages.pop(0)
            
            message.status = MessageStatus.PROCESSING
            message.processed_at = time.time()
            
            if auto_ack:
                message.status = MessageStatus.COMPLETED
                message.acked = True
                self.stats["total_acked"] += 1
            
            queue.consume_count += 1
            self.stats["total_consumed"] += 1
            
            return message
    
    def ack(self, message_id: str, consumer_id: str = "") -> bool:
        """确认消息"""
        with self._lock:
            message = self.message_store.get(message_id)
            if not message:
                return False
            
            message.status = MessageStatus.COMPLETED
            message.acked = True
            message.acked_by = consumer_id
            
            self.stats["total_acked"] += 1
            
            return True
    
    def nack(self, message_id: str, requeue: bool = True) -> bool:
        """拒绝消息"""
        with self._lock:
            message = self.message_store.get(message_id)
            if not message:
                return False
            
            message.retry_count += 1
            
            if requeue and message.should_retry():
                # 重新入队
                message.status = MessageStatus.PENDING
                queue = self.queues.get(message.routing_key)
                if queue:
                    queue.messages.append(message)
            else:
                # 发送到死信队列
                message.status = MessageStatus.DEAD_LETTER
                self._send_to_dead_letter(message, "rejected")
            
            self.stats["total_rejected"] += 1
            
            return True
    
    def _send_to_dead_letter(self, message: Message, reason: str):
        """发送到死信队列"""
        message.status = MessageStatus.DEAD_LETTER
        message.headers["x-death-reason"] = reason
        message.headers["x-death-time"] = time.time()
        
        self.dead_letter_queue.messages.append(message)
        self.stats["total_dead_lettered"] += 1
    
    def get_queue_stats(self, queue_name: str) -> Optional[Dict]:
        """获取队列统计"""
        with self._lock:
            queue = self.queues.get(queue_name)
            if queue:
                return queue.to_dict()
            return None
    
    def get_broker_stats(self) -> Dict:
        """获取代理统计"""
        with self._lock:
            return {
                "queues": len(self.queues),
                "exchanges": len(self.exchanges),
                "consumers": len(self.consumers),
                "messages_stored": len(self.message_store),
                "dead_letter_count": len(self.dead_letter_queue.messages),
                **self.stats,
            }


# ============== 事件总线 ==============

class EventBus:
    """事件总线（发布/订阅模式）"""
    
    def __init__(self, broker: MessageBroker = None):
        self.broker = broker or MessageBroker()
        self._lock = threading.RLock()
        
        # 事件处理器
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # 事件历史
        self.event_history: deque = deque(maxlen=1000)
    
    def subscribe(self, event_type: str, handler: Callable) -> str:
        """订阅事件"""
        with self._lock:
            self.handlers[event_type].append(handler)
            
            # 在消息代理中创建相应队列
            queue_name = f"event.{event_type}"
            self.broker.declare_queue(queue_name)
            
            return f"sub_{uuid.uuid4().hex[:8]}"
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """取消订阅"""
        with self._lock:
            if event_type in self.handlers:
                try:
                    self.handlers[event_type].remove(handler)
                    return True
                except ValueError:
                    return False
            return False
    
    def publish(
        self,
        event_type: str,
        data: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """发布事件"""
        with self._lock:
            event_id = uuid.uuid4().hex[:16]
            
            event = {
                "event_id": event_id,
                "event_type": event_type,
                "data": data,
                "timestamp": time.time(),
            }
            
            # 记录历史
            self.event_history.append(event)
            
            # 同步通知本地处理器
            for handler in self.handlers.get(event_type, []):
                try:
                    handler(event)
                except Exception as e:
                    print(f"Event handler error: {e}")
            
            # 通配符订阅者
            for handler in self.handlers.get("*", []):
                try:
                    handler(event)
                except Exception:
                    pass
            
            # 发布到消息队列
            message = Message(
                topic=event_type,
                payload=event,
                routing_key=f"event.{event_type}",
                priority=priority,
            )
            self.broker.publish(message)
            
            return event_id
    
    def get_event_history(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """获取事件历史"""
        with self._lock:
            events = list(self.event_history)
            if event_type:
                events = [e for e in events if e["event_type"] == event_type]
            return events[-limit:]


# ============== 任务队列 ==============

class TaskQueue:
    """任务队列（类似 Celery）"""
    
    def __init__(self, broker: MessageBroker = None):
        self.broker = broker or MessageBroker()
        self._lock = threading.RLock()
        
        # 注册的任务
        self.registered_tasks: Dict[str, Callable] = {}
        
        # 任务结果
        self.results: Dict[str, Any] = {}
        
        # 任务状态
        self.task_states: Dict[str, str] = {}
        
        # 创建任务队列
        self.broker.declare_queue("celery")
        self.broker.declare_queue("celery.results")
    
    def register_task(self, name: str, func: Callable):
        """注册任务"""
        self.registered_tasks[name] = func
    
    def task(self, name: str = None):
        """任务装饰器"""
        def decorator(func):
            task_name = name or f"{func.__module__}.{func.__name__}"
            self.register_task(task_name, func)
            
            # 添加 delay 方法
            def delay(*args, **kwargs):
                return self.send_task(task_name, args, kwargs)
            
            func.delay = delay
            return func
        
        return decorator
    
    def send_task(
        self,
        task_name: str,
        args: tuple = (),
        kwargs: dict = None,
        countdown: int = 0,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """发送任务"""
        with self._lock:
            task_id = uuid.uuid4().hex[:16]
            
            task_message = {
                "task_id": task_id,
                "task": task_name,
                "args": args,
                "kwargs": kwargs or {},
                "retries": 0,
            }
            
            message = Message(
                message_id=task_id,
                topic="task",
                payload=task_message,
                routing_key="celery",
                priority=priority,
                scheduled_at=time.time() + countdown if countdown > 0 else 0,
            )
            
            self.broker.publish(message, routing_key="celery")
            self.task_states[task_id] = "PENDING"
            
            return task_id
    
    def execute_task(self, task_id: str, task_name: str, args: tuple, kwargs: dict) -> Any:
        """执行任务"""
        with self._lock:
            if task_name not in self.registered_tasks:
                self.task_states[task_id] = "FAILURE"
                raise ValueError(f"Task {task_name} not registered")
            
            self.task_states[task_id] = "STARTED"
            
            try:
                func = self.registered_tasks[task_name]
                result = func(*args, **kwargs)
                
                self.results[task_id] = result
                self.task_states[task_id] = "SUCCESS"
                
                return result
            except Exception as e:
                self.task_states[task_id] = "FAILURE"
                self.results[task_id] = {"error": "task_execution_failed"}
                raise
    
    def get_result(self, task_id: str, timeout: float = None) -> Any:
        """获取任务结果"""
        start = time.time()
        while task_id not in self.results:
            if timeout and time.time() - start > timeout:
                raise TimeoutError("Task result timeout")
            time.sleep(0.1)
        
        return self.results.get(task_id)
    
    def get_task_state(self, task_id: str) -> str:
        """获取任务状态"""
        return self.task_states.get(task_id, "UNKNOWN")


# ============== 全局实例 ==============

_message_broker: Optional[MessageBroker] = None
_event_bus: Optional[EventBus] = None
_task_queue: Optional[TaskQueue] = None


def get_message_broker() -> MessageBroker:
    """获取消息代理单例"""
    global _message_broker
    if _message_broker is None:
        _message_broker = MessageBroker()
    return _message_broker


def get_event_bus() -> EventBus:
    """获取事件总线单例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus(get_message_broker())
    return _event_bus


def get_task_queue() -> TaskQueue:
    """获取任务队列单例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(get_message_broker())
    return _task_queue
