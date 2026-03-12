# -*- coding: utf-8 -*-
"""
留言机制模块 - 链上哈希 + 链外存储

协议层边界声明：
├── 模块：message_system
├── 层级：APPLICATION (应用层)
├── 类别：NON_CONSENSUS (非共识)
├── 共识影响：❌ 无 - 留言不参与区块共识
├── 出块影响：❌ 无 - 留言不影响出块
└── 存储方式：链外存储，链上只存哈希

链上/链外分离原则：
1. 链上只存储：消息哈希、发送者、时间戳、消息类型
2. 链外存储：完整消息内容、附件、元数据
3. 链上哈希用于验证链外内容的完整性
4. 这样设计减轻了链上存储压力，同时保证可验证性

功能：
1. 用户评论：任务完成后对矿工的服务评价
2. 矿工评论：矿工对任务需求的评论和反馈
3. 链上哈希：消息哈希写入区块链，不可篡改
4. 链外内容：完整内容存储在链外，可压缩
5. 通知系统：评论时自动通知相关方
6. 合约绑定：智能合约触发留言功能

设计原则：
- 链上只存哈希，减轻存储压力
- 链外内容可通过哈希验证
- 支持评分 + 文字评价
- 支持回复和追评
- 防垃圾留言机制
"""

import time
import json
import hashlib
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import contextmanager


class MessageType(Enum):
    """留言类型"""
    USER_REVIEW = "user_review"           # 用户对矿工的评价
    MINER_FEEDBACK = "miner_feedback"     # 矿工对任务的反馈
    TASK_COMMENT = "task_comment"         # 任务评论
    REPLY = "reply"                       # 回复
    FOLLOW_UP = "follow_up"               # 追评
    DISPUTE = "dispute"                   # 争议留言
    SYSTEM = "system"                     # 系统通知


class MessageStatus(Enum):
    """留言状态"""
    PENDING = "pending"           # 待确认（等待上链）
    CONFIRMED = "confirmed"       # 已确认（已上链）
    HIDDEN = "hidden"             # 已隐藏（违规）
    DELETED = "deleted"           # 已删除


class NotificationType(Enum):
    """通知类型"""
    NEW_REVIEW = "new_review"             # 新评价
    NEW_REPLY = "new_reply"               # 新回复
    TASK_COMPLETED = "task_completed"     # 任务完成
    RATING_RECEIVED = "rating_received"   # 收到评分
    DISPUTE_OPENED = "dispute_opened"     # 争议开启
    SYSTEM_ALERT = "system_alert"         # 系统提醒


@dataclass
class Rating:
    """评分详情"""
    overall: float = 5.0          # 总体评分 (0-5, 0.5步进)
    quality: float = 5.0          # 质量评分
    speed: float = 5.0            # 速度评分
    communication: float = 5.0    # 沟通评分
    reliability: float = 5.0      # 可靠性评分
    
    def average(self) -> float:
        """计算平均分"""
        scores = [self.quality, self.speed, self.communication, self.reliability]
        return round(sum(scores) / len(scores), 1)
    
    def to_dict(self) -> Dict:
        return {
            "overall": self.overall,
            "quality": self.quality,
            "speed": self.speed,
            "communication": self.communication,
            "reliability": self.reliability,
            "average": self.average()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Rating':
        return cls(
            overall=data.get("overall", 5.0),
            quality=data.get("quality", 5.0),
            speed=data.get("speed", 5.0),
            communication=data.get("communication", 5.0),
            reliability=data.get("reliability", 5.0)
        )
    
    @staticmethod
    def validate_score(score: float) -> bool:
        """验证评分是否有效 (0-5, 0.5步进)"""
        if score < 0 or score > 5:
            return False
        return score * 2 == int(score * 2)


@dataclass
class Message:
    """链上留言"""
    message_id: str
    message_type: MessageType
    sender_address: str           # 发送者地址
    receiver_address: str         # 接收者地址
    task_id: str                  # 关联的任务ID
    content: str                  # 留言内容
    rating: Optional[Rating] = None  # 评分（可选）
    
    # 元数据
    reply_to: Optional[str] = None    # 回复的留言ID
    contract_id: Optional[str] = None # 关联的合约ID
    
    # 状态
    status: MessageStatus = MessageStatus.PENDING
    block_height: int = 0         # 上链区块高度
    block_hash: str = ""          # 上链区块哈希
    tx_hash: str = ""             # 交易哈希
    
    # 时间戳
    created_at: float = field(default_factory=time.time)
    confirmed_at: Optional[float] = None
    
    # 签名
    signature: str = ""
    
    def __post_init__(self):
        if not self.message_id:
            self.message_id = self._generate_id()
    
    def _generate_id(self) -> str:
        import uuid
        # 使用 UUID 确保唯一性，结合时间戳和内容哈希
        unique_data = f"{self.sender_address}{self.receiver_address}{self.task_id}{self.created_at}{uuid.uuid4().hex[:8]}"
        return f"MSG_{hashlib.sha256(unique_data.encode()).hexdigest()[:16]}"
    
    def compute_hash(self) -> str:
        """计算留言哈希（用于上链）"""
        data = {
            "message_id": self.message_id,
            "type": self.message_type.value,
            "sender": self.sender_address,
            "receiver": self.receiver_address,
            "task_id": self.task_id,
            "content": self.content,
            "rating": self.rating.to_dict() if self.rating else None,
            "reply_to": self.reply_to,
            "created_at": self.created_at
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_address": self.sender_address,
            "receiver_address": self.receiver_address,
            "task_id": self.task_id,
            "content": self.content,
            "rating": self.rating.to_dict() if self.rating else None,
            "reply_to": self.reply_to,
            "contract_id": self.contract_id,
            "status": self.status.value,
            "block_height": self.block_height,
            "block_hash": self.block_hash,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at,
            "confirmed_at": self.confirmed_at,
            "signature": self.signature,
            "hash": self.compute_hash()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        rating = None
        if data.get("rating"):
            rating = Rating.from_dict(data["rating"])
        
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            sender_address=data["sender_address"],
            receiver_address=data["receiver_address"],
            task_id=data["task_id"],
            content=data["content"],
            rating=rating,
            reply_to=data.get("reply_to"),
            contract_id=data.get("contract_id"),
            status=MessageStatus(data.get("status", "pending")),
            block_height=data.get("block_height", 0),
            block_hash=data.get("block_hash", ""),
            tx_hash=data.get("tx_hash", ""),
            created_at=data.get("created_at", time.time()),
            confirmed_at=data.get("confirmed_at"),
            signature=data.get("signature", "")
        )


@dataclass
class Notification:
    """通知"""
    notification_id: str
    notification_type: NotificationType
    recipient_address: str        # 接收者
    sender_address: str           # 发送者
    title: str
    content: str
    related_id: str               # 关联的留言/任务ID
    
    # 状态
    is_read: bool = False
    created_at: float = field(default_factory=time.time)
    read_at: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value,
            "recipient_address": self.recipient_address,
            "sender_address": self.sender_address,
            "title": self.title,
            "content": self.content,
            "related_id": self.related_id,
            "is_read": self.is_read,
            "created_at": self.created_at,
            "read_at": self.read_at
        }


class MessageSystem:
    """
    链上留言系统
    
    核心功能：
    1. 创建留言并写入区块链
    2. 评分系统
    3. 通知系统
    4. 防垃圾机制
    """
    
    # 留言限制
    MAX_CONTENT_LENGTH = 2000     # 最大留言长度
    MIN_CONTENT_LENGTH = 10       # 最小留言长度
    COOLDOWN_SECONDS = 60         # 同一任务留言冷却时间
    MAX_MESSAGES_PER_TASK = 20    # 每个任务最大留言数
    
    # 评分要求
    REQUIRE_TIP_FOR_RATING = True # 评分是否需要小费
    MIN_TIP_AMOUNT = 0.1          # 最小小费金额
    
    def __init__(self, db_path: str = "data/messages.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # 回调函数
        self._on_message_created: List = []
        self._on_notification: List = []
    
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
            # 留言表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    message_type TEXT NOT NULL,
                    sender_address TEXT NOT NULL,
                    receiver_address TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    rating_data TEXT,
                    reply_to TEXT,
                    contract_id TEXT,
                    status TEXT DEFAULT 'pending',
                    block_height INTEGER DEFAULT 0,
                    block_hash TEXT,
                    tx_hash TEXT,
                    signature TEXT,
                    message_hash TEXT,
                    created_at REAL NOT NULL,
                    confirmed_at REAL
                )
            """)
            
            # 通知表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    notification_type TEXT NOT NULL,
                    recipient_address TEXT NOT NULL,
                    sender_address TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    related_id TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    read_at REAL
                )
            """)
            
            # 用户评分汇总表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_ratings (
                    address TEXT PRIMARY KEY,
                    total_ratings INTEGER DEFAULT 0,
                    avg_overall REAL DEFAULT 5.0,
                    avg_quality REAL DEFAULT 5.0,
                    avg_speed REAL DEFAULT 5.0,
                    avg_communication REAL DEFAULT 5.0,
                    avg_reliability REAL DEFAULT 5.0,
                    total_tips_received REAL DEFAULT 0,
                    updated_at REAL
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_task ON messages(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_receiver ON messages(receiver_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_status ON messages(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_address)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_unread ON notifications(recipient_address, is_read)")
    
    # ============== 留言操作 ==============
    
    def create_user_review(self, 
                           user_address: str,
                           miner_address: str,
                           task_id: str,
                           content: str,
                           rating: Rating,
                           tip_amount: float = 0,
                           signature: str = "") -> Tuple[bool, str, Optional[Message]]:
        """
        用户对矿工发表评价
        
        Args:
            user_address: 用户地址
            miner_address: 矿工地址
            task_id: 任务ID
            content: 评价内容
            rating: 评分
            tip_amount: 小费金额
            signature: 签名
            
        Returns:
            (成功, 消息, Message对象)
        """
        # 验证评分
        if not all([
            Rating.validate_score(rating.overall),
            Rating.validate_score(rating.quality),
            Rating.validate_score(rating.speed),
            Rating.validate_score(rating.communication),
            Rating.validate_score(rating.reliability)
        ]):
            return False, "评分无效，必须是 0-5 之间的 0.5 倍数", None
        
        # 验证小费
        if self.REQUIRE_TIP_FOR_RATING and tip_amount < self.MIN_TIP_AMOUNT:
            return False, f"评价需要至少 {self.MIN_TIP_AMOUNT} 小费", None
        
        # 验证内容长度
        if len(content) < self.MIN_CONTENT_LENGTH:
            return False, f"评价内容至少 {self.MIN_CONTENT_LENGTH} 字符", None
        if len(content) > self.MAX_CONTENT_LENGTH:
            return False, f"评价内容最多 {self.MAX_CONTENT_LENGTH} 字符", None
        
        # 检查冷却时间
        if not self._check_cooldown(user_address, task_id):
            return False, f"请等待 {self.COOLDOWN_SECONDS} 秒后再评价", None
        
        # 检查任务留言数量
        if not self._check_message_limit(task_id):
            return False, f"该任务留言已达上限 ({self.MAX_MESSAGES_PER_TASK})", None
        
        # 创建留言
        message = Message(
            message_id="",
            message_type=MessageType.USER_REVIEW,
            sender_address=user_address,
            receiver_address=miner_address,
            task_id=task_id,
            content=content,
            rating=rating,
            signature=signature
        )
        
        # 保存到数据库
        self._save_message(message)
        
        # 更新矿工评分汇总
        self._update_user_ratings(miner_address, rating, tip_amount)
        
        # 发送通知
        self._send_notification(
            notification_type=NotificationType.NEW_REVIEW,
            recipient=miner_address,
            sender=user_address,
            title="收到新评价",
            content=f"用户对您的任务 {task_id[:8]}... 发表了评价",
            related_id=message.message_id
        )
        
        # 触发回调
        for callback in self._on_message_created:
            callback(message)
        
        return True, "评价发布成功", message
    
    def create_miner_feedback(self,
                              miner_address: str,
                              user_address: str,
                              task_id: str,
                              content: str,
                              signature: str = "") -> Tuple[bool, str, Optional[Message]]:
        """
        矿工对任务发表反馈
        """
        # 验证内容长度
        if len(content) < self.MIN_CONTENT_LENGTH:
            return False, f"反馈内容至少 {self.MIN_CONTENT_LENGTH} 字符", None
        if len(content) > self.MAX_CONTENT_LENGTH:
            return False, f"反馈内容最多 {self.MAX_CONTENT_LENGTH} 字符", None
        
        # 创建留言
        message = Message(
            message_id="",
            message_type=MessageType.MINER_FEEDBACK,
            sender_address=miner_address,
            receiver_address=user_address,
            task_id=task_id,
            content=content,
            signature=signature
        )
        
        self._save_message(message)
        
        # 发送通知
        self._send_notification(
            notification_type=NotificationType.NEW_REVIEW,
            recipient=user_address,
            sender=miner_address,
            title="矿工反馈",
            content=f"矿工对任务 {task_id[:8]}... 发表了反馈",
            related_id=message.message_id
        )
        
        return True, "反馈发布成功", message
    
    def reply_to_message(self,
                         sender_address: str,
                         original_message_id: str,
                         content: str,
                         signature: str = "") -> Tuple[bool, str, Optional[Message]]:
        """
        回复留言
        """
        # 获取原始留言
        original = self.get_message(original_message_id)
        if not original:
            return False, "原留言不存在", None
        
        # 确定接收者
        if sender_address == original.sender_address:
            receiver = original.receiver_address
        else:
            receiver = original.sender_address
        
        # 验证内容
        if len(content) < 5:
            return False, "回复内容太短", None
        if len(content) > self.MAX_CONTENT_LENGTH:
            return False, "回复内容太长", None
        
        # 创建回复
        message = Message(
            message_id="",
            message_type=MessageType.REPLY,
            sender_address=sender_address,
            receiver_address=receiver,
            task_id=original.task_id,
            content=content,
            reply_to=original_message_id,
            signature=signature
        )
        
        self._save_message(message)
        
        # 发送通知
        self._send_notification(
            notification_type=NotificationType.NEW_REPLY,
            recipient=receiver,
            sender=sender_address,
            title="收到回复",
            content=f"您的留言收到了新回复",
            related_id=message.message_id
        )
        
        return True, "回复成功", message
    
    def create_dispute(self,
                       sender_address: str,
                       receiver_address: str,
                       task_id: str,
                       content: str,
                       signature: str = "") -> Tuple[bool, str, Optional[Message]]:
        """
        创建争议留言
        """
        message = Message(
            message_id="",
            message_type=MessageType.DISPUTE,
            sender_address=sender_address,
            receiver_address=receiver_address,
            task_id=task_id,
            content=content,
            signature=signature
        )
        
        self._save_message(message)
        
        # 发送通知给双方
        self._send_notification(
            notification_type=NotificationType.DISPUTE_OPENED,
            recipient=receiver_address,
            sender=sender_address,
            title="争议已开启",
            content=f"任务 {task_id[:8]}... 的争议已开启",
            related_id=message.message_id
        )
        
        return True, "争议已提交", message
    
    # ============== 查询操作 ==============
    
    def get_message(self, message_id: str) -> Optional[Message]:
        """获取留言"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row:
                return self._row_to_message(row)
        return None
    
    def get_task_messages(self, task_id: str, limit: int = 50) -> List[Message]:
        """获取任务的所有留言"""
        messages = []
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM messages 
                WHERE task_id = ? AND status != 'deleted'
                ORDER BY created_at ASC
                LIMIT ?
            """, (task_id, limit)).fetchall()
            for row in rows:
                messages.append(self._row_to_message(row))
        return messages
    
    def get_user_reviews(self, address: str, as_sender: bool = True, 
                         limit: int = 50) -> List[Message]:
        """获取用户的评价"""
        messages = []
        if as_sender:
            query = "SELECT * FROM messages WHERE sender_address = ? AND message_type = 'user_review' ORDER BY created_at DESC LIMIT ?"
        else:
            query = "SELECT * FROM messages WHERE receiver_address = ? AND message_type = 'user_review' ORDER BY created_at DESC LIMIT ?"
        with self._conn() as conn:
            rows = conn.execute(query, (address, limit)).fetchall()
            for row in rows:
                messages.append(self._row_to_message(row))
        return messages
    
    def get_user_rating_summary(self, address: str) -> Dict:
        """获取用户评分汇总"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_ratings WHERE address = ?", (address,)
            ).fetchone()
            if row:
                return {
                    "address": row["address"],
                    "total_ratings": row["total_ratings"],
                    "avg_overall": row["avg_overall"],
                    "avg_quality": row["avg_quality"],
                    "avg_speed": row["avg_speed"],
                    "avg_communication": row["avg_communication"],
                    "avg_reliability": row["avg_reliability"],
                    "total_tips_received": row["total_tips_received"]
                }
        return {
            "address": address,
            "total_ratings": 0,
            "avg_overall": 5.0,
            "avg_quality": 5.0,
            "avg_speed": 5.0,
            "avg_communication": 5.0,
            "avg_reliability": 5.0,
            "total_tips_received": 0
        }
    
    # ============== 通知操作 ==============
    
    def get_notifications(self, address: str, unread_only: bool = False,
                          limit: int = 50) -> List[Dict]:
        """获取通知"""
        notifications = []
        with self._conn() as conn:
            if unread_only:
                rows = conn.execute("""
                    SELECT * FROM notifications 
                    WHERE recipient_address = ? AND is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (address, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM notifications 
                    WHERE recipient_address = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (address, limit)).fetchall()
            
            for row in rows:
                notifications.append({
                    "notification_id": row["notification_id"],
                    "notification_type": row["notification_type"],
                    "sender_address": row["sender_address"],
                    "title": row["title"],
                    "content": row["content"],
                    "related_id": row["related_id"],
                    "is_read": bool(row["is_read"]),
                    "created_at": row["created_at"]
                })
        return notifications
    
    def get_unread_count(self, address: str) -> int:
        """获取未读通知数"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM notifications 
                WHERE recipient_address = ? AND is_read = 0
            """, (address,)).fetchone()
            return row["cnt"] if row else 0
    
    def mark_notification_read(self, notification_id: str, address: str) -> bool:
        """标记通知已读"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE notifications 
                SET is_read = 1, read_at = ?
                WHERE notification_id = ? AND recipient_address = ?
            """, (time.time(), notification_id, address))
        return True
    
    def mark_all_read(self, address: str) -> int:
        """标记所有通知已读"""
        with self._conn() as conn:
            cursor = conn.execute("""
                UPDATE notifications 
                SET is_read = 1, read_at = ?
                WHERE recipient_address = ? AND is_read = 0
            """, (time.time(), address))
            return cursor.rowcount
    
    # ============== 区块链集成 ==============
    
    def confirm_message(self, message_id: str, block_height: int, 
                        block_hash: str, tx_hash: str) -> bool:
        """确认留言已上链"""
        with self._conn() as conn:
            conn.execute("""
                UPDATE messages 
                SET status = 'confirmed', block_height = ?, block_hash = ?, 
                    tx_hash = ?, confirmed_at = ?
                WHERE message_id = ?
            """, (block_height, block_hash, tx_hash, time.time(), message_id))
        return True
    
    def get_pending_messages(self, limit: int = 100) -> List[Message]:
        """获取待上链的留言"""
        messages = []
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM messages 
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,)).fetchall()
            for row in rows:
                messages.append(self._row_to_message(row))
        return messages
    
    # ============== 回调注册 ==============
    
    def on_message_created(self, callback):
        """注册留言创建回调"""
        self._on_message_created.append(callback)
    
    def on_notification(self, callback):
        """注册通知回调"""
        self._on_notification.append(callback)
    
    # ============== 内部方法 ==============
    
    def _save_message(self, message: Message):
        """保存留言到数据库"""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO messages (
                    message_id, message_type, sender_address, receiver_address,
                    task_id, content, rating_data, reply_to, contract_id,
                    status, signature, message_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id,
                message.message_type.value,
                message.sender_address,
                message.receiver_address,
                message.task_id,
                message.content,
                json.dumps(message.rating.to_dict()) if message.rating else None,
                message.reply_to,
                message.contract_id,
                message.status.value,
                message.signature,
                message.compute_hash(),
                message.created_at
            ))
    
    def _row_to_message(self, row) -> Message:
        """数据库行转换为 Message 对象"""
        rating = None
        if row["rating_data"]:
            rating = Rating.from_dict(json.loads(row["rating_data"]))
        
        return Message(
            message_id=row["message_id"],
            message_type=MessageType(row["message_type"]),
            sender_address=row["sender_address"],
            receiver_address=row["receiver_address"],
            task_id=row["task_id"],
            content=row["content"],
            rating=rating,
            reply_to=row["reply_to"],
            contract_id=row["contract_id"],
            status=MessageStatus(row["status"]),
            block_height=row["block_height"],
            block_hash=row["block_hash"] or "",
            tx_hash=row["tx_hash"] or "",
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
            signature=row["signature"] or ""
        )
    
    def _send_notification(self, notification_type: NotificationType,
                           recipient: str, sender: str, title: str,
                           content: str, related_id: str):
        """发送通知"""
        notification_id = f"NOTIF_{hashlib.sha256(f'{recipient}{time.time()}'.encode()).hexdigest()[:12]}"
        
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO notifications (
                    notification_id, notification_type, recipient_address,
                    sender_address, title, content, related_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notification_id, notification_type.value, recipient,
                sender, title, content, related_id, time.time()
            ))
        
        # 触发回调
        notification = Notification(
            notification_id=notification_id,
            notification_type=notification_type,
            recipient_address=recipient,
            sender_address=sender,
            title=title,
            content=content,
            related_id=related_id
        )
        for callback in self._on_notification:
            callback(notification)
    
    def _update_user_ratings(self, address: str, rating: Rating, tip_amount: float):
        """更新用户评分汇总"""
        with self._conn() as conn:
            # 获取当前汇总
            row = conn.execute(
                "SELECT * FROM user_ratings WHERE address = ?", (address,)
            ).fetchone()
            
            if row:
                # 更新现有记录
                n = row["total_ratings"]
                new_n = n + 1
                
                # 计算新的平均分
                new_avg_overall = (row["avg_overall"] * n + rating.overall) / new_n
                new_avg_quality = (row["avg_quality"] * n + rating.quality) / new_n
                new_avg_speed = (row["avg_speed"] * n + rating.speed) / new_n
                new_avg_communication = (row["avg_communication"] * n + rating.communication) / new_n
                new_avg_reliability = (row["avg_reliability"] * n + rating.reliability) / new_n
                new_tips = row["total_tips_received"] + tip_amount
                
                conn.execute("""
                    UPDATE user_ratings SET
                        total_ratings = ?,
                        avg_overall = ?,
                        avg_quality = ?,
                        avg_speed = ?,
                        avg_communication = ?,
                        avg_reliability = ?,
                        total_tips_received = ?,
                        updated_at = ?
                    WHERE address = ?
                """, (
                    new_n, new_avg_overall, new_avg_quality, new_avg_speed,
                    new_avg_communication, new_avg_reliability, new_tips,
                    time.time(), address
                ))
            else:
                # 创建新记录
                conn.execute("""
                    INSERT INTO user_ratings (
                        address, total_ratings, avg_overall, avg_quality,
                        avg_speed, avg_communication, avg_reliability,
                        total_tips_received, updated_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    address, rating.overall, rating.quality, rating.speed,
                    rating.communication, rating.reliability, tip_amount, time.time()
                ))
    
    def _check_cooldown(self, sender: str, task_id: str) -> bool:
        """检查冷却时间"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT created_at FROM messages 
                WHERE sender_address = ? AND task_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (sender, task_id)).fetchone()
            
            if row:
                elapsed = time.time() - row["created_at"]
                return elapsed >= self.COOLDOWN_SECONDS
        return True
    
    def _check_message_limit(self, task_id: str) -> bool:
        """检查任务留言数量限制"""
        with self._conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM messages 
                WHERE task_id = ? AND status != 'deleted'
            """, (task_id,)).fetchone()
            return row["cnt"] < self.MAX_MESSAGES_PER_TASK


# 全局实例
_message_system: Optional[MessageSystem] = None

def get_message_system(db_path: str = "data/messages.db") -> MessageSystem:
    """获取留言系统实例"""
    global _message_system
    if _message_system is None:
        _message_system = MessageSystem(db_path)
    return _message_system
