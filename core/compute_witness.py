"""
compute_witness.py - 算力交易双见证机制

为算力租用交易提供双见证验证：
1. 任务发布见证（防止虚假任务）
2. 执行完成见证（防止虚假结果）
3. 结算见证（防止虚假支付）

见证者选择规则：
- 不能是交易双方（用户/矿工）
- 不能是同一个实体
- 至少 2 个独立见证者
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable
from enum import Enum
import time
import hashlib
import uuid


class WitnessType(Enum):
    """见证类型。"""
    JOB_SUBMISSION = "job_submission"       # 任务提交见证
    EXECUTION_START = "execution_start"     # 执行开始见证
    EXECUTION_COMPLETE = "execution_complete"  # 执行完成见证
    RESULT_VERIFICATION = "result_verification"  # 结果验证见证
    SETTLEMENT = "settlement"               # 结算见证


class WitnessStatus(Enum):
    """见证状态。"""
    PENDING = "pending"         # 待见证
    WITNESSED = "witnessed"     # 已见证
    REJECTED = "rejected"       # 被拒绝
    EXPIRED = "expired"         # 已过期


@dataclass
class WitnessRequest:
    """见证请求。"""
    request_id: str
    witness_type: WitnessType
    
    # 交易信息
    job_id: str
    user_id: str
    miner_id: str
    sector_type: str
    
    # 见证数据
    data_hash: str              # 交易数据哈希
    amount: float = 0.0         # 涉及金额
    currency: str = "MAIN"      # 币种
    
    # 见证状态
    status: WitnessStatus = WitnessStatus.PENDING
    required_witnesses: int = 2
    witnesses: List[str] = field(default_factory=list)
    witness_signatures: Dict[str, str] = field(default_factory=dict)
    rejections: List[str] = field(default_factory=list)
    
    # 时间
    created_at: float = field(default_factory=time.time)
    witnessed_at: Optional[float] = None
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1小时过期

    def add_witness(self, witness_id: str, signature: str) -> bool:
        """添加见证。"""
        if witness_id in self.witnesses:
            return False
        if witness_id == self.user_id or witness_id == self.miner_id:
            return False  # 交易双方不能见证
        
        self.witnesses.append(witness_id)
        self.witness_signatures[witness_id] = signature
        
        if len(self.witnesses) >= self.required_witnesses:
            self.status = WitnessStatus.WITNESSED
            self.witnessed_at = time.time()
        
        return True

    def add_rejection(self, witness_id: str, reason: str = ""):
        """添加拒绝。"""
        if witness_id not in self.rejections:
            self.rejections.append(witness_id)

    def is_witnessed(self) -> bool:
        """是否已完成见证。"""
        return len(self.witnesses) >= self.required_witnesses

    def is_expired(self) -> bool:
        """是否已过期。"""
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "type": self.witness_type.value,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "miner_id": self.miner_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value,
            "witnesses": self.witnesses.copy(),
            "required": self.required_witnesses,
        }


@dataclass
class WitnessRecord:
    """见证记录（链上存储）。"""
    record_id: str
    request_id: str
    witness_type: WitnessType
    job_id: str
    witnesses: List[str]
    signatures: Dict[str, str]
    data_hash: str
    amount: float
    currency: str
    timestamp: float = field(default_factory=time.time)
    block_height: int = 0


class ComputeWitnessSystem:
    """算力交易双见证系统。
    
    职责：
    1. 管理见证者池
    2. 分配见证任务
    3. 验证见证签名
    4. 记录见证历史
    """

    def __init__(
        self,
        required_witnesses: int = 2,
        witness_timeout_seconds: float = 3600,
        witness_reward: float = 0.001,  # 见证奖励
        witness_pubkey_getter: Optional[Callable[[str], Optional[str]]] = None,
        require_signature_verification: bool = True,
        log_fn=None,
    ):
        self.required_witnesses = required_witnesses
        self.witness_timeout = witness_timeout_seconds
        self.witness_reward = witness_reward
        self._witness_pubkey_getter = witness_pubkey_getter
        self._require_signature_verification = require_signature_verification
        
        # 见证者池 {sector: [witness_ids]}
        self.witness_pool: Dict[str, List[str]] = {}
        # 见证者公钥注册表 {witness_id: public_key_hex}
        self.witness_pubkeys: Dict[str, str] = {}
        # 待处理请求
        self.pending_requests: Dict[str, WitnessRequest] = {}
        # 完成的记录
        self.witness_records: List[WitnessRecord] = []
        # 见证者统计 {witness_id: {completed, rejected, rewards}}
        self.witness_stats: Dict[str, Dict[str, Any]] = {}
        
        self._log_fn = log_fn or (lambda x: None)

    def _log(self, msg: str):
        self._log_fn(f"[WITNESS] {msg}")

    def _generate_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def _hash_data(self, data: dict) -> str:
        """计算数据哈希。"""
        content = str(sorted(data.items()))
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _build_witness_message(self, request: WitnessRequest) -> bytes:
        """构造见证签名消息（稳定序列化，防重放）。"""
        payload = {
            "request_id": request.request_id,
            "witness_type": request.witness_type.value,
            "job_id": request.job_id,
            "user_id": request.user_id,
            "miner_id": request.miner_id,
            "data_hash": request.data_hash,
            "amount": request.amount,
            "currency": request.currency,
        }
        ordered = str(sorted(payload.items()))
        return ordered.encode()

    def _verify_witness_signature(
        self,
        request: WitnessRequest,
        witness_id: str,
        signature: str,
    ) -> bool:
        """验证见证签名。"""
        if not signature or not isinstance(signature, str):
            return False

        if not self._require_signature_verification:
            return True

        if not self._witness_pubkey_getter:
            pubkey_hex = self.witness_pubkeys.get(witness_id, "")
        else:
            pubkey_hex = self._witness_pubkey_getter(witness_id)
        if not pubkey_hex or not isinstance(pubkey_hex, str):
            self._log(f"Signature verify failed: no public key for witness {witness_id}")
            return False

        try:
            from core.crypto import ECDSASigner

            pubkey_bytes = bytes.fromhex(pubkey_hex)
            sig_bytes = bytes.fromhex(signature)
            msg_bytes = self._build_witness_message(request)
            return ECDSASigner.verify(pubkey_bytes, msg_bytes, sig_bytes)
        except Exception as e:
            self._log(f"Signature verify error for witness {witness_id}: {e}")
            return False

    def register_witness(
        self,
        witness_id: str,
        sector_type: str,
        public_key: str = "",
    ):
        """注册见证者。"""
        if sector_type not in self.witness_pool:
            self.witness_pool[sector_type] = []

        if public_key:
            self.witness_pubkeys[witness_id] = public_key
        
        if witness_id not in self.witness_pool[sector_type]:
            self.witness_pool[sector_type].append(witness_id)
            self.witness_stats[witness_id] = {
                "completed": 0,
                "rejected": 0,
                "rewards": 0.0,
            }
            self._log(f"Registered witness {witness_id} for {sector_type}")

    def select_witnesses(
        self,
        sector_type: str,
        exclude_ids: Set[str],
        count: int = 2,
    ) -> List[str]:
        """选择见证者。
        
        规则：
        1. 排除交易双方
        2. 优先选择完成率高的见证者
        3. 跨板块见证者优先（增加独立性）
        """
        candidates = []
        
        # 首先从其他板块选择（增加独立性）
        for other_sector, witnesses in self.witness_pool.items():
            if other_sector != sector_type:
                for wid in witnesses:
                    if wid not in exclude_ids:
                        candidates.append((wid, "cross_sector"))
        
        # 然后从同板块选择
        for wid in self.witness_pool.get(sector_type, []):
            if wid not in exclude_ids:
                candidates.append((wid, "same_sector"))
        
        # 按完成率排序
        def witness_score(item):
            wid, source = item
            stats = self.witness_stats.get(wid, {})
            completed = stats.get("completed", 0)
            rejected = stats.get("rejected", 0)
            total = completed + rejected
            rate = completed / total if total > 0 else 0.5
            # 跨板块加分
            cross_bonus = 0.1 if source == "cross_sector" else 0
            return rate + cross_bonus
        
        candidates.sort(key=witness_score, reverse=True)
        
        selected = [wid for wid, _ in candidates[:count]]
        return selected

    def create_witness_request(
        self,
        witness_type: WitnessType,
        job_id: str,
        user_id: str,
        miner_id: str,
        sector_type: str,
        transaction_data: dict,
        amount: float = 0.0,
        currency: str = "MAIN",
    ) -> Optional[WitnessRequest]:
        """创建见证请求。"""
        data_hash = self._hash_data(transaction_data)
        
        request = WitnessRequest(
            request_id=self._generate_id(),
            witness_type=witness_type,
            job_id=job_id,
            user_id=user_id,
            miner_id=miner_id,
            sector_type=sector_type,
            data_hash=data_hash,
            amount=amount,
            currency=currency,
            required_witnesses=self.required_witnesses,
            expires_at=time.time() + self.witness_timeout,
        )
        
        self.pending_requests[request.request_id] = request
        self._log(f"Created {witness_type.value} witness request: {request.request_id}")
        
        return request

    def request_witness(
        self,
        request_id: str,
        auto_select: bool = True,
    ) -> List[str]:
        """请求见证（分配见证者）。"""
        request = self.pending_requests.get(request_id)
        if not request:
            self._log(f"Request {request_id} not found")
            return []
        
        if auto_select:
            exclude = {request.user_id, request.miner_id}
            witnesses = self.select_witnesses(
                request.sector_type,
                exclude,
                self.required_witnesses,
            )
            self._log(f"Selected witnesses for {request_id}: {witnesses}")
            return witnesses
        
        return []

    def submit_witness(
        self,
        request_id: str,
        witness_id: str,
        approve: bool,
        signature: str = "",
        reason: str = "",
    ) -> bool:
        """提交见证（通过或拒绝）。"""
        request = self.pending_requests.get(request_id)
        if not request:
            self._log(f"Request {request_id} not found")
            return False
        
        if request.is_expired():
            request.status = WitnessStatus.EXPIRED
            self._log(f"Request {request_id} expired")
            return False
        
        if approve:
            if not self._verify_witness_signature(request, witness_id, signature):
                self._log(
                    f"Witness {witness_id} signature verification failed for {request_id}"
                )
                return False
            
            success = request.add_witness(witness_id, signature)
            if success:
                self._log(f"Witness {witness_id} approved {request_id}")
                
                # 更新统计
                if witness_id in self.witness_stats:
                    self.witness_stats[witness_id]["completed"] += 1
                
                # 检查是否完成
                if request.is_witnessed():
                    self._finalize_witness(request)
                
                return True
        else:
            request.add_rejection(witness_id, reason)
            self._log(f"Witness {witness_id} rejected {request_id}: {reason}")
            
            if witness_id in self.witness_stats:
                self.witness_stats[witness_id]["rejected"] += 1
            
            return False
        
        return False

    def _finalize_witness(self, request: WitnessRequest):
        """完成见证，生成记录。"""
        record = WitnessRecord(
            record_id=self._generate_id(),
            request_id=request.request_id,
            witness_type=request.witness_type,
            job_id=request.job_id,
            witnesses=request.witnesses.copy(),
            signatures=request.witness_signatures.copy(),
            data_hash=request.data_hash,
            amount=request.amount,
            currency=request.currency,
        )
        
        self.witness_records.append(record)
        
        # 从待处理移除
        if request.request_id in self.pending_requests:
            del self.pending_requests[request.request_id]
        
        self._log(f"Witness complete: {request.request_id} ({request.witness_type.value})")
        self._log(f"  Witnesses: {request.witnesses}")

    def verify_transaction(
        self,
        job_id: str,
        witness_type: WitnessType,
    ) -> Optional[WitnessRecord]:
        """验证交易是否已完成见证。"""
        for record in reversed(self.witness_records):
            if record.job_id == job_id and record.witness_type == witness_type:
                return record
        return None

    def is_transaction_witnessed(
        self,
        job_id: str,
        witness_type: WitnessType,
    ) -> bool:
        """检查交易是否已见证。"""
        return self.verify_transaction(job_id, witness_type) is not None

    def get_witness_rewards(self, witness_id: str) -> float:
        """获取见证者累计奖励。"""
        return self.witness_stats.get(witness_id, {}).get("rewards", 0.0)

    def pay_witness_rewards(
        self,
        request_id: str,
        treasury: Any = None,
    ) -> Dict[str, float]:
        """支付见证奖励。"""
        # 查找对应的记录
        record = None
        for r in self.witness_records:
            if r.request_id == request_id:
                record = r
                break
        
        if not record:
            return {}
        
        payments = {}
        for witness_id in record.witnesses:
            if witness_id in self.witness_stats:
                self.witness_stats[witness_id]["rewards"] += self.witness_reward
                payments[witness_id] = self.witness_reward
        
        self._log(f"Paid witness rewards for {request_id}: {payments}")
        return payments

    def get_pending_requests(
        self,
        witness_id: str = None,
        sector_type: str = None,
    ) -> List[WitnessRequest]:
        """获取待处理的见证请求。"""
        requests = []
        for req in self.pending_requests.values():
            if req.is_expired():
                continue
            if witness_id and witness_id in [req.user_id, req.miner_id]:
                continue  # 不能见证自己的交易
            if sector_type and req.sector_type != sector_type:
                continue
            requests.append(req)
        return requests

    def cleanup_expired(self):
        """清理过期请求。"""
        expired = []
        for rid, req in self.pending_requests.items():
            if req.is_expired():
                expired.append(rid)
        
        for rid in expired:
            self.pending_requests[rid].status = WitnessStatus.EXPIRED
            del self.pending_requests[rid]
        
        if expired:
            self._log(f"Cleaned up {len(expired)} expired requests")

    def print_stats(self):
        """打印见证统计。"""
        print("\n" + "=" * 50)
        print("WITNESS SYSTEM STATISTICS")
        print("=" * 50)
        print(f"Witness Pools: {len(self.witness_pool)}")
        for sector, witnesses in self.witness_pool.items():
            print(f"  {sector}: {len(witnesses)} witnesses")
        print(f"Pending Requests: {len(self.pending_requests)}")
        print(f"Completed Records: {len(self.witness_records)}")
        print()

    def __repr__(self) -> str:
        return f"ComputeWitnessSystem(required={self.required_witnesses}, pending={len(self.pending_requests)})"
