"""
compute_market_orderbook.py - 算力市场撮合系统

Phase 9 功能：
1. 算力挂单簿（Ask）- 矿工卖单
2. 用户竞价单（Bid）- 用户买单
3. 撮合引擎 - Bid/Ask 价格匹配
4. 闲置算力自动降价
5. 供需紧张时价格拉升
6. 从「平台定价」进化为「算力市场」
"""

import time
import uuid
import threading
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict
import json


# ============== 枚举类型 ==============

class OrderType(Enum):
    """订单类型"""
    ASK = "ask"          # 卖单（矿工挂单）
    BID = "bid"          # 买单（用户竞价）


class OrderStatus(Enum):
    """订单状态"""
    OPEN = "open"                # 开放中
    PARTIAL = "partial"          # 部分成交
    FILLED = "filled"            # 完全成交
    CANCELLED = "cancelled"      # 已取消
    EXPIRED = "expired"          # 已过期


class MatchingStrategy(Enum):
    """撮合策略"""
    PRICE_TIME = "price_time"              # 价格优先，时间优先
    PRO_RATA = "pro_rata"                  # 按比例分配
    BEST_PRICE = "best_price"              # 最优价格
    WEIGHTED = "weighted"                   # 加权撮合


class GPUResourceType(Enum):
    """GPU 资源类型"""
    RTX_3060 = "rtx_3060"
    RTX_3080 = "rtx_3080"
    RTX_3090 = "rtx_3090"
    RTX_4060 = "rtx_4060"
    RTX_4080 = "rtx_4080"
    RTX_4090 = "rtx_4090"
    A100 = "a100"
    H100 = "h100"
    H200 = "h200"


# ============== 数据结构 ==============

@dataclass
class ResourceSpec:
    """资源规格"""
    gpu_type: GPUResourceType
    gpu_count: int = 1
    gpu_memory_gb: int = 0                 # 显存要求
    min_utilization: float = 0             # 最小利用率保证
    duration_hours: float = 1.0            # 时长


@dataclass
class AskOrder:
    """卖单（矿工挂单）"""
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    miner_id: str = ""
    
    # 资源
    resource: ResourceSpec = None
    
    # 价格
    ask_price: float = 0                   # 挂单价格 (每GPU小时)
    min_price: float = 0                   # 最低接受价格
    auto_discount_rate: float = 0.01       # 每小时自动降价率
    
    # 时间
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expiry: float = 0                      # 过期时间
    valid_from: float = 0                  # 生效时间
    
    # 状态
    status: OrderStatus = OrderStatus.OPEN
    filled_quantity: float = 0             # 已成交数量（小时）
    total_quantity: float = 0              # 总数量（小时）
    remaining_quantity: float = 0          # 剩余数量
    
    # 节点信息
    node_reputation: float = 100.0
    has_tee: bool = False
    
    def __post_init__(self):
        if self.resource and self.total_quantity == 0:
            self.total_quantity = self.resource.duration_hours * self.resource.gpu_count
        self.remaining_quantity = self.total_quantity - self.filled_quantity
    
    def current_price(self) -> float:
        """获取当前有效价格（考虑自动降价）"""
        if self.auto_discount_rate <= 0:
            return self.ask_price
        
        hours_elapsed = (time.time() - self.created_at) / 3600
        discount = 1 - (self.auto_discount_rate * hours_elapsed)
        discounted_price = self.ask_price * max(discount, self.min_price / self.ask_price)
        
        return max(discounted_price, self.min_price)
    
    def __lt__(self, other):
        """排序：价格低优先，时间早优先"""
        if self.current_price() != other.current_price():
            return self.current_price() < other.current_price()
        return self.created_at < other.created_at
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "miner_id": self.miner_id,
            "type": "ask",
            "gpu_type": self.resource.gpu_type.value if self.resource else None,
            "gpu_count": self.resource.gpu_count if self.resource else 0,
            "ask_price": self.ask_price,
            "current_price": self.current_price(),
            "min_price": self.min_price,
            "status": self.status.value,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "created_at": self.created_at,
            "has_tee": self.has_tee,
        }


@dataclass
class BidOrder:
    """买单（用户竞价）"""
    order_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = ""
    
    # 资源需求
    resource: ResourceSpec = None
    
    # 价格
    bid_price: float = 0                   # 出价 (每GPU小时)
    max_price: float = 0                   # 最高可接受价格
    auto_increase_rate: float = 0          # 自动加价率
    
    # 时间
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expiry: float = 0                      # 过期时间
    urgency: str = "normal"                # immediate / normal / flexible
    
    # 状态
    status: OrderStatus = OrderStatus.OPEN
    filled_quantity: float = 0
    total_quantity: float = 0
    remaining_quantity: float = 0
    
    # 要求
    require_tee: bool = False
    min_reputation: float = 0
    
    def __post_init__(self):
        if self.resource and self.total_quantity == 0:
            self.total_quantity = self.resource.duration_hours * self.resource.gpu_count
        self.remaining_quantity = self.total_quantity - self.filled_quantity
    
    def current_price(self) -> float:
        """获取当前有效价格（考虑自动加价）"""
        if self.auto_increase_rate <= 0:
            return self.bid_price
        
        hours_elapsed = (time.time() - self.created_at) / 3600
        increase = 1 + (self.auto_increase_rate * hours_elapsed)
        increased_price = self.bid_price * min(increase, self.max_price / self.bid_price if self.bid_price > 0 else 1)
        
        return min(increased_price, self.max_price) if self.max_price > 0 else increased_price
    
    def __lt__(self, other):
        """排序：价格高优先，时间早优先"""
        if self.current_price() != other.current_price():
            return self.current_price() > other.current_price()
        return self.created_at < other.created_at
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "type": "bid",
            "gpu_type": self.resource.gpu_type.value if self.resource else None,
            "gpu_count": self.resource.gpu_count if self.resource else 0,
            "bid_price": self.bid_price,
            "current_price": self.current_price(),
            "max_price": self.max_price,
            "status": self.status.value,
            "total_quantity": self.total_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "created_at": self.created_at,
            "urgency": self.urgency,
            "require_tee": self.require_tee,
        }


@dataclass
class Trade:
    """成交记录"""
    trade_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    
    # 订单
    ask_order_id: str = ""
    bid_order_id: str = ""
    miner_id: str = ""
    user_id: str = ""
    
    # 成交详情
    gpu_type: str = ""
    quantity: float = 0                    # 成交数量（GPU小时）
    price: float = 0                       # 成交价格
    total_value: float = 0                 # 总价值
    
    # 时间
    executed_at: float = field(default_factory=time.time)
    
    # 链上
    tx_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "ask_order_id": self.ask_order_id,
            "bid_order_id": self.bid_order_id,
            "miner_id": self.miner_id,
            "user_id": self.user_id,
            "gpu_type": self.gpu_type,
            "quantity": self.quantity,
            "price": self.price,
            "total_value": self.total_value,
            "executed_at": self.executed_at,
            "tx_hash": self.tx_hash,
        }


@dataclass
class OrderBookSnapshot:
    """订单簿快照"""
    gpu_type: str
    timestamp: float = field(default_factory=time.time)
    
    # 最优价格
    best_ask: float = 0
    best_bid: float = 0
    spread: float = 0
    spread_percent: float = 0
    
    # 深度
    ask_depth: List[Tuple[float, float]] = field(default_factory=list)  # [(price, quantity), ...]
    bid_depth: List[Tuple[float, float]] = field(default_factory=list)
    
    # 统计
    total_ask_quantity: float = 0
    total_bid_quantity: float = 0
    ask_count: int = 0
    bid_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "gpu_type": self.gpu_type,
            "timestamp": self.timestamp,
            "best_ask": self.best_ask,
            "best_bid": self.best_bid,
            "spread": self.spread,
            "spread_percent": self.spread_percent,
            "ask_depth": self.ask_depth[:10],  # 前10档
            "bid_depth": self.bid_depth[:10],
            "total_ask_quantity": self.total_ask_quantity,
            "total_bid_quantity": self.total_bid_quantity,
        }


# ============== 订单簿 ==============

class OrderBook:
    """单个 GPU 类型的订单簿"""
    
    def __init__(self, gpu_type: GPUResourceType):
        self.gpu_type = gpu_type
        self.asks: Dict[str, AskOrder] = {}       # order_id -> AskOrder
        self.bids: Dict[str, BidOrder] = {}       # order_id -> BidOrder
        self._lock = threading.RLock()
        
        # 历史
        self.trades: List[Trade] = []
        self.last_trade_price: float = 0
    
    def add_ask(self, order: AskOrder) -> str:
        """添加卖单"""
        with self._lock:
            self.asks[order.order_id] = order
            return order.order_id
    
    def add_bid(self, order: BidOrder) -> str:
        """添加买单"""
        with self._lock:
            self.bids[order.order_id] = order
            return order.order_id
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        with self._lock:
            if order_id in self.asks:
                self.asks[order_id].status = OrderStatus.CANCELLED
                return True
            if order_id in self.bids:
                self.bids[order_id].status = OrderStatus.CANCELLED
                return True
            return False
    
    def get_sorted_asks(self) -> List[AskOrder]:
        """获取排序后的卖单（价低优先）"""
        with self._lock:
            active = [o for o in self.asks.values() 
                     if o.status == OrderStatus.OPEN and o.remaining_quantity > 0]
            return sorted(active)
    
    def get_sorted_bids(self) -> List[BidOrder]:
        """获取排序后的买单（价高优先）"""
        with self._lock:
            active = [o for o in self.bids.values() 
                     if o.status == OrderStatus.OPEN and o.remaining_quantity > 0]
            return sorted(active)
    
    def get_best_ask(self) -> Optional[float]:
        """获取最优卖价"""
        asks = self.get_sorted_asks()
        return asks[0].current_price() if asks else None
    
    def get_best_bid(self) -> Optional[float]:
        """获取最优买价"""
        bids = self.get_sorted_bids()
        return bids[0].current_price() if bids else None
    
    def get_snapshot(self) -> OrderBookSnapshot:
        """获取订单簿快照"""
        with self._lock:
            sorted_asks = self.get_sorted_asks()
            sorted_bids = self.get_sorted_bids()
            
            snapshot = OrderBookSnapshot(gpu_type=self.gpu_type.value)
            
            # 最优价格
            snapshot.best_ask = sorted_asks[0].current_price() if sorted_asks else 0
            snapshot.best_bid = sorted_bids[0].current_price() if sorted_bids else 0
            
            if snapshot.best_ask > 0 and snapshot.best_bid > 0:
                snapshot.spread = snapshot.best_ask - snapshot.best_bid
                snapshot.spread_percent = (snapshot.spread / snapshot.best_ask) * 100
            
            # 深度
            ask_depth = defaultdict(float)
            for o in sorted_asks:
                ask_depth[o.current_price()] += o.remaining_quantity
            snapshot.ask_depth = sorted(ask_depth.items())
            
            bid_depth = defaultdict(float)
            for o in sorted_bids:
                bid_depth[o.current_price()] += o.remaining_quantity
            snapshot.bid_depth = sorted(bid_depth.items(), reverse=True)
            
            # 统计
            snapshot.total_ask_quantity = sum(o.remaining_quantity for o in sorted_asks)
            snapshot.total_bid_quantity = sum(o.remaining_quantity for o in sorted_bids)
            snapshot.ask_count = len(sorted_asks)
            snapshot.bid_count = len(sorted_bids)
            
            return snapshot


# ============== 撮合引擎 ==============

class MatchingEngine:
    """撮合引擎"""
    
    def __init__(self):
        self.order_books: Dict[GPUResourceType, OrderBook] = {}
        self.trades: List[Trade] = []
        self._lock = threading.RLock()
        
        # 初始化所有 GPU 类型的订单簿
        for gpu_type in GPUResourceType:
            self.order_books[gpu_type] = OrderBook(gpu_type)
        
        # 撮合策略
        self.strategy = MatchingStrategy.PRICE_TIME
        
        # 价格限制
        self.max_price_deviation = 0.5     # 最大价格偏离 50%
        self.circuit_breaker_threshold = 0.2  # 熔断阈值
    
    def submit_ask(
        self,
        miner_id: str,
        gpu_type: GPUResourceType,
        ask_price: float,
        duration_hours: float = 1.0,
        gpu_count: int = 1,
        min_price: float = 0,
        auto_discount_rate: float = 0.01,
        has_tee: bool = False,
    ) -> Tuple[AskOrder, List[Trade]]:
        """提交卖单"""
        with self._lock:
            resource = ResourceSpec(
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                duration_hours=duration_hours,
            )
            
            order = AskOrder(
                miner_id=miner_id,
                resource=resource,
                ask_price=ask_price,
                min_price=min_price if min_price > 0 else ask_price * 0.5,
                auto_discount_rate=auto_discount_rate,
                total_quantity=duration_hours * gpu_count,
                has_tee=has_tee,
            )
            
            book = self.order_books[gpu_type]
            book.add_ask(order)
            
            # 尝试撮合
            trades = self._match(gpu_type)
            
            return order, trades
    
    def submit_bid(
        self,
        user_id: str,
        gpu_type: GPUResourceType,
        bid_price: float,
        duration_hours: float = 1.0,
        gpu_count: int = 1,
        max_price: float = 0,
        auto_increase_rate: float = 0,
        require_tee: bool = False,
        urgency: str = "normal",
    ) -> Tuple[BidOrder, List[Trade]]:
        """提交买单"""
        with self._lock:
            resource = ResourceSpec(
                gpu_type=gpu_type,
                gpu_count=gpu_count,
                duration_hours=duration_hours,
            )
            
            order = BidOrder(
                user_id=user_id,
                resource=resource,
                bid_price=bid_price,
                max_price=max_price if max_price > 0 else bid_price * 2,
                auto_increase_rate=auto_increase_rate,
                require_tee=require_tee,
                urgency=urgency,
                total_quantity=duration_hours * gpu_count,
            )
            
            book = self.order_books[gpu_type]
            book.add_bid(order)
            
            # 尝试撮合
            trades = self._match(gpu_type)
            
            return order, trades
    
    def _match(self, gpu_type: GPUResourceType) -> List[Trade]:
        """执行撮合"""
        book = self.order_books[gpu_type]
        trades = []
        
        while True:
            asks = book.get_sorted_asks()
            bids = book.get_sorted_bids()
            
            if not asks or not bids:
                break
            
            best_ask = asks[0]
            best_bid = bids[0]
            
            # 检查是否可以成交
            if best_bid.current_price() < best_ask.current_price():
                break
            
            # TEE 要求检查
            if best_bid.require_tee and not best_ask.has_tee:
                # 跳过此卖单，尝试下一个
                # 这里简化处理，实际需要更复杂的逻辑
                break
            
            # 确定成交价格（中间价）
            trade_price = (best_ask.current_price() + best_bid.current_price()) / 2
            
            # 确定成交数量
            trade_quantity = min(best_ask.remaining_quantity, best_bid.remaining_quantity)
            
            # 创建成交记录
            trade = Trade(
                ask_order_id=best_ask.order_id,
                bid_order_id=best_bid.order_id,
                miner_id=best_ask.miner_id,
                user_id=best_bid.user_id,
                gpu_type=gpu_type.value,
                quantity=trade_quantity,
                price=trade_price,
                total_value=trade_quantity * trade_price,
            )
            
            trades.append(trade)
            self.trades.append(trade)
            book.trades.append(trade)
            book.last_trade_price = trade_price
            
            # 防止交易历史无限增长
            if len(self.trades) > 50000:
                self.trades = self.trades[-25000:]
            if len(book.trades) > 10000:
                book.trades = book.trades[-5000:]
            
            # 更新订单
            best_ask.filled_quantity += trade_quantity
            best_ask.remaining_quantity -= trade_quantity
            if best_ask.remaining_quantity <= 0:
                best_ask.status = OrderStatus.FILLED
            else:
                best_ask.status = OrderStatus.PARTIAL
            
            best_bid.filled_quantity += trade_quantity
            best_bid.remaining_quantity -= trade_quantity
            if best_bid.remaining_quantity <= 0:
                best_bid.status = OrderStatus.FILLED
            else:
                best_bid.status = OrderStatus.PARTIAL
        
        return trades
    
    def get_order_book(self, gpu_type: GPUResourceType) -> OrderBookSnapshot:
        """获取订单簿"""
        with self._lock:
            return self.order_books[gpu_type].get_snapshot()
    
    def get_all_order_books(self) -> Dict[str, OrderBookSnapshot]:
        """获取所有订单簿"""
        with self._lock:
            return {
                gpu_type.value: book.get_snapshot()
                for gpu_type, book in self.order_books.items()
            }
    
    def get_market_price(self, gpu_type: GPUResourceType) -> Dict:
        """获取市场价格"""
        with self._lock:
            book = self.order_books[gpu_type]
            snapshot = book.get_snapshot()
            
            return {
                "gpu_type": gpu_type.value,
                "best_ask": snapshot.best_ask,
                "best_bid": snapshot.best_bid,
                "spread": snapshot.spread,
                "spread_percent": snapshot.spread_percent,
                "last_trade_price": book.last_trade_price,
                "mid_price": (snapshot.best_ask + snapshot.best_bid) / 2 if snapshot.best_ask and snapshot.best_bid else 0,
            }
    
    def get_recent_trades(
        self,
        gpu_type: GPUResourceType = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取最近成交"""
        with self._lock:
            trades = self.trades
            if gpu_type:
                trades = [t for t in trades if t.gpu_type == gpu_type.value]
            
            trades = sorted(trades, key=lambda t: t.executed_at, reverse=True)
            return [t.to_dict() for t in trades[:limit]]
    
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        with self._lock:
            for book in self.order_books.values():
                if book.cancel_order(order_id):
                    return True
            return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """获取订单状态"""
        with self._lock:
            for book in self.order_books.values():
                if order_id in book.asks:
                    return book.asks[order_id].to_dict()
                if order_id in book.bids:
                    return book.bids[order_id].to_dict()
            return None
    
    def get_user_orders(self, user_id: str) -> List[Dict]:
        """获取用户订单"""
        with self._lock:
            orders = []
            for book in self.order_books.values():
                for order in book.bids.values():
                    if order.user_id == user_id:
                        orders.append(order.to_dict())
            return orders
    
    def get_miner_orders(self, miner_id: str) -> List[Dict]:
        """获取矿工订单"""
        with self._lock:
            orders = []
            for book in self.order_books.values():
                for order in book.asks.values():
                    if order.miner_id == miner_id:
                        orders.append(order.to_dict())
            return orders
    
    def apply_idle_discount(self, hours_threshold: float = 1.0):
        """应用闲置折扣"""
        with self._lock:
            current_time = time.time()
            
            for book in self.order_books.values():
                for order in book.asks.values():
                    if order.status != OrderStatus.OPEN:
                        continue
                    
                    hours_idle = (current_time - order.created_at) / 3600
                    if hours_idle >= hours_threshold:
                        # 价格已经通过 current_price() 自动计算降价
                        order.updated_at = current_time
    
    def get_market_summary(self) -> Dict:
        """获取市场总结"""
        with self._lock:
            summary = {
                "timestamp": time.time(),
                "markets": {},
                "total_trades_24h": 0,
                "total_volume_24h": 0,
            }
            
            cutoff = time.time() - 86400
            
            for gpu_type, book in self.order_books.items():
                snapshot = book.get_snapshot()
                
                trades_24h = [t for t in book.trades if t.executed_at > cutoff]
                volume_24h = sum(t.total_value for t in trades_24h)
                
                summary["markets"][gpu_type.value] = {
                    "best_ask": snapshot.best_ask,
                    "best_bid": snapshot.best_bid,
                    "spread_percent": snapshot.spread_percent,
                    "ask_depth": snapshot.total_ask_quantity,
                    "bid_depth": snapshot.total_bid_quantity,
                    "trades_24h": len(trades_24h),
                    "volume_24h": volume_24h,
                    "last_price": book.last_trade_price,
                }
                
                summary["total_trades_24h"] += len(trades_24h)
                summary["total_volume_24h"] += volume_24h
            
            return summary


# ============== 自动做市商 (AMM) ==============

class AutoMarketMaker:
    """自动做市商 - 提供流动性"""
    
    def __init__(self, matching_engine: MatchingEngine):
        self.engine = matching_engine
        self.reserves: Dict[GPUResourceType, float] = defaultdict(float)  # 储备
        self.base_prices: Dict[GPUResourceType, float] = {}  # 基准价格
        self._lock = threading.RLock()
        
        # 初始化基准价格
        self._init_base_prices()
    
    def _init_base_prices(self):
        """初始化基准价格"""
        self.base_prices = {
            GPUResourceType.RTX_3060: 0.10,
            GPUResourceType.RTX_3080: 0.25,
            GPUResourceType.RTX_3090: 0.40,
            GPUResourceType.RTX_4060: 0.20,
            GPUResourceType.RTX_4080: 0.50,
            GPUResourceType.RTX_4090: 0.80,
            GPUResourceType.A100: 2.00,
            GPUResourceType.H100: 4.00,
            GPUResourceType.H200: 6.00,
        }
    
    def provide_liquidity(
        self,
        gpu_type: GPUResourceType,
        quantity: float,
        spread_percent: float = 5.0,
    ) -> Tuple[AskOrder, BidOrder]:
        """提供流动性"""
        with self._lock:
            # 获取市场价格或使用基准价格
            market = self.engine.get_market_price(gpu_type)
            if market["mid_price"] > 0:
                mid_price = market["mid_price"]
            else:
                mid_price = self.base_prices.get(gpu_type, 1.0)
            
            # 计算买卖价格
            half_spread = spread_percent / 100 / 2
            ask_price = mid_price * (1 + half_spread)
            bid_price = mid_price * (1 - half_spread)
            
            # 提交订单
            ask_order, _ = self.engine.submit_ask(
                miner_id="amm_maker",
                gpu_type=gpu_type,
                ask_price=ask_price,
                duration_hours=quantity,
                auto_discount_rate=0,
            )
            
            bid_order, _ = self.engine.submit_bid(
                user_id="amm_maker",
                gpu_type=gpu_type,
                bid_price=bid_price,
                duration_hours=quantity,
                auto_increase_rate=0,
            )
            
            self.reserves[gpu_type] += quantity
            
            return ask_order, bid_order
    
    def get_amm_price(
        self,
        gpu_type: GPUResourceType,
        quantity: float,
        is_buy: bool,
    ) -> float:
        """获取 AMM 价格（恒定乘积公式）"""
        with self._lock:
            reserve = self.reserves.get(gpu_type, 100)  # 默认储备
            base_price = self.base_prices.get(gpu_type, 1.0)
            
            # 简化的恒定乘积: price = k / reserve
            # 实际使用: price = base_price * (reserve / (reserve +/- quantity))
            
            if is_buy:
                # 买入导致价格上涨
                new_reserve = reserve - quantity
                if new_reserve <= 0:
                    return base_price * 10  # 极端情况
                price_impact = reserve / new_reserve
            else:
                # 卖出导致价格下跌
                new_reserve = reserve + quantity
                price_impact = reserve / new_reserve
            
            return base_price * price_impact


# ============== 全局实例 ==============

_matching_engine: Optional[MatchingEngine] = None
_amm: Optional[AutoMarketMaker] = None


def get_matching_engine() -> MatchingEngine:
    """获取撮合引擎单例"""
    global _matching_engine
    if _matching_engine is None:
        _matching_engine = MatchingEngine()
    return _matching_engine


def get_amm() -> AutoMarketMaker:
    """获取 AMM 单例"""
    global _amm
    if _amm is None:
        _amm = AutoMarketMaker(get_matching_engine())
    return _amm
