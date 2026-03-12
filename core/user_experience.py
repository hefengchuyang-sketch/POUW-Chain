"""
用户体验与交互增强 v2.0
=====================

改进要点：
1. 任务管理界面数据层（统计/进度/状态跟踪）
2. 节点选择与控制（GPU/CPU/TPU/边缘设备）
3. 多语言国际化支持（i18n）
4. 实时通知与日志系统

本模块作为前端API数据层，提供所有用户界面所需的后端数据。
"""

import time
import uuid
import json
import sqlite3
import threading
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any, Callable
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============================================================
# 枚举定义
# ============================================================

class DeviceType(Enum):
    """设备类型"""
    GPU_NVIDIA = "gpu_nvidia"
    GPU_AMD = "gpu_amd"
    CPU = "cpu"
    TPU = "tpu"
    FPGA = "fpga"
    EDGE = "edge"                   # 边缘设备
    ASIC = "asic"


class NotificationType(Enum):
    """通知类型"""
    TASK_STATUS = "task_status"         # 任务状态变更
    TASK_COMPLETED = "task_completed"   # 任务完成
    TASK_FAILED = "task_failed"         # 任务失败
    NODE_STATUS = "node_status"         # 节点状态变更
    TRANSACTION = "transaction"         # 交易通知
    SECURITY_ALERT = "security_alert"   # 安全告警
    SYSTEM_UPDATE = "system_update"     # 系统更新
    GOVERNANCE = "governance"           # 治理通知
    REVENUE = "revenue"                 # 收益通知
    CONTRACT = "contract"               # 合约通知


class NotificationPriority(Enum):
    """通知优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Language(Enum):
    """支持的语言"""
    ZH_CN = "zh-CN"    # 简体中文
    ZH_TW = "zh-TW"    # 繁体中文
    EN_US = "en-US"     # 英语
    JA_JP = "ja-JP"     # 日语
    KO_KR = "ko-KR"     # 韩语
    ES_ES = "es-ES"     # 西班牙语
    FR_FR = "fr-FR"     # 法语
    DE_DE = "de-DE"     # 德语
    PT_BR = "pt-BR"     # 葡萄牙语(巴西)
    RU_RU = "ru-RU"     # 俄语
    AR_SA = "ar-SA"     # 阿拉伯语


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TaskDashboardData:
    """任务管理面板数据"""
    user_id: str
    # 概览
    total_tasks: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    # 费用
    total_spent: float = 0.0
    total_saved: float = 0.0        # 相比即时价的节省
    avg_cost_per_task: float = 0.0
    # 性能
    avg_completion_time_s: float = 0.0
    success_rate: float = 0.0
    # 趋势
    daily_tasks: List[Dict] = field(default_factory=list)
    daily_costs: List[Dict] = field(default_factory=list)
    # 任务列表
    recent_tasks: List[Dict] = field(default_factory=list)


@dataclass
class NodeSelectionCriteria:
    """节点选择条件"""
    # 设备类型
    device_types: List[DeviceType] = field(default_factory=list)
    # GPU要求
    min_gpu_count: int = 0
    gpu_models: List[str] = field(default_factory=list)
    min_gpu_memory_gb: float = 0.0
    # 性能要求
    min_compute_score: float = 0.0
    max_latency_ms: float = 500.0
    min_bandwidth_mbps: float = 10.0
    # 信誉要求
    min_reputation_score: float = 0.0
    min_uptime_ratio: float = 0.0
    # 区域
    preferred_regions: List[str] = field(default_factory=list)
    excluded_regions: List[str] = field(default_factory=list)
    # 安全
    min_verification_level: int = 0
    require_tee: bool = False
    require_hsm: bool = False
    # 排序
    sort_by: str = "score"          # score/price/latency/reputation


@dataclass
class Notification:
    """通知"""
    notification_id: str
    user_id: str
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.NORMAL
    title: str = ""
    message: str = ""
    data: Dict = field(default_factory=dict)
    read: bool = False
    created_at: float = 0.0
    expires_at: float = 0.0


@dataclass
class UserPreferences:
    """用户偏好设置"""
    user_id: str
    language: Language = Language.ZH_CN
    timezone: str = "Asia/Shanghai"
    # 通知偏好
    notification_enabled: bool = True
    notification_types: Set[NotificationType] = field(
        default_factory=lambda: set(NotificationType))
    email_notifications: bool = False
    push_notifications: bool = True
    # 界面偏好
    theme: str = "dark"             # dark/light/auto
    dashboard_layout: str = "default"
    items_per_page: int = 20
    # 默认节点选择
    default_device_types: List[DeviceType] = field(default_factory=list)
    default_regions: List[str] = field(default_factory=list)


# ============================================================
# 国际化翻译系统
# ============================================================

class I18nManager:
    """
    国际化管理器
    支持多语言翻译和动态语言切换
    """

    def __init__(self):
        self.translations: Dict[str, Dict[str, str]] = {}
        self._init_translations()

    def _init_translations(self):
        """初始化翻译数据"""
        self.translations = {
            "zh-CN": {
                # 通用
                "app.name": "POUW 算力市场",
                "app.welcome": "欢迎使用 POUW 多扇区算力链",
                # 任务
                "task.title": "任务管理",
                "task.create": "创建任务",
                "task.status.pending": "等待中",
                "task.status.running": "运行中",
                "task.status.completed": "已完成",
                "task.status.failed": "失败",
                "task.status.cancelled": "已取消",
                "task.progress": "进度",
                "task.cost": "费用",
                "task.duration": "时长",
                "task.node": "执行节点",
                # 节点
                "node.title": "节点管理",
                "node.select": "选择节点",
                "node.type.gpu": "GPU 节点",
                "node.type.cpu": "CPU 节点",
                "node.type.tpu": "TPU 节点",
                "node.type.edge": "边缘设备",
                "node.status.online": "在线",
                "node.status.offline": "离线",
                "node.status.busy": "繁忙",
                "node.reputation": "信誉评分",
                "node.uptime": "在线时长",
                # 市场
                "market.title": "算力市场",
                "market.price": "当前价格",
                "market.supply": "可用供给",
                "market.demand": "当前需求",
                "market.contract": "合约",
                "market.spot": "现货",
                "market.reserved": "预留",
                # 钱包
                "wallet.balance": "余额",
                "wallet.send": "发送",
                "wallet.receive": "接收",
                "wallet.history": "交易记录",
                # 治理
                "governance.title": "社区治理",
                "governance.proposal": "提案",
                "governance.vote": "投票",
                "governance.stake": "质押",
                # 通知
                "notification.title": "通知",
                "notification.read_all": "全部已读",
                "notification.settings": "通知设置",
                # 设置
                "settings.title": "设置",
                "settings.language": "语言",
                "settings.theme": "主题",
                "settings.security": "安全设置",
            },
            "en-US": {
                "app.name": "POUW Compute Market",
                "app.welcome": "Welcome to POUW Multi-Sector Chain",
                "task.title": "Task Management",
                "task.create": "Create Task",
                "task.status.pending": "Pending",
                "task.status.running": "Running",
                "task.status.completed": "Completed",
                "task.status.failed": "Failed",
                "task.status.cancelled": "Cancelled",
                "task.progress": "Progress",
                "task.cost": "Cost",
                "task.duration": "Duration",
                "task.node": "Compute Node",
                "node.title": "Node Management",
                "node.select": "Select Node",
                "node.type.gpu": "GPU Node",
                "node.type.cpu": "CPU Node",
                "node.type.tpu": "TPU Node",
                "node.type.edge": "Edge Device",
                "node.status.online": "Online",
                "node.status.offline": "Offline",
                "node.status.busy": "Busy",
                "node.reputation": "Reputation Score",
                "node.uptime": "Uptime",
                "market.title": "Compute Market",
                "market.price": "Current Price",
                "market.supply": "Available Supply",
                "market.demand": "Current Demand",
                "market.contract": "Contract",
                "market.spot": "Spot",
                "market.reserved": "Reserved",
                "wallet.balance": "Balance",
                "wallet.send": "Send",
                "wallet.receive": "Receive",
                "wallet.history": "Transaction History",
                "governance.title": "Community Governance",
                "governance.proposal": "Proposal",
                "governance.vote": "Vote",
                "governance.stake": "Stake",
                "notification.title": "Notifications",
                "notification.read_all": "Mark All Read",
                "notification.settings": "Notification Settings",
                "settings.title": "Settings",
                "settings.language": "Language",
                "settings.theme": "Theme",
                "settings.security": "Security Settings",
            },
            "ja-JP": {
                "app.name": "POUW コンピューティングマーケット",
                "app.welcome": "POUW マルチセクターチェーンへようこそ",
                "task.title": "タスク管理",
                "task.create": "タスク作成",
                "task.status.pending": "待機中",
                "task.status.running": "実行中",
                "task.status.completed": "完了",
                "task.status.failed": "失敗",
                "task.status.cancelled": "キャンセル",
                "task.progress": "進捗",
                "task.cost": "費用",
                "task.duration": "所要時間",
                "task.node": "計算ノード",
                "node.title": "ノード管理",
                "node.select": "ノード選択",
                "node.type.gpu": "GPUノード",
                "node.type.cpu": "CPUノード",
                "node.type.tpu": "TPUノード",
                "node.type.edge": "エッジデバイス",
                "market.title": "コンピューティングマーケット",
                "market.price": "現在価格",
                "wallet.balance": "残高",
                "governance.title": "コミュニティガバナンス",
                "notification.title": "通知",
                "settings.title": "設定",
                "settings.language": "言語",
            },
            "ko-KR": {
                "app.name": "POUW 컴퓨팅 마켓",
                "app.welcome": "POUW 멀티섹터 체인에 오신 것을 환영합니다",
                "task.title": "작업 관리",
                "task.create": "작업 생성",
                "task.status.pending": "대기 중",
                "task.status.running": "실행 중",
                "task.status.completed": "완료",
                "task.status.failed": "실패",
                "node.title": "노드 관리",
                "market.title": "컴퓨팅 마켓",
                "wallet.balance": "잔액",
                "governance.title": "커뮤니티 거버넌스",
                "notification.title": "알림",
                "settings.title": "설정",
                "settings.language": "언어",
            },
            "es-ES": {
                "app.name": "POUW Mercado de Computación",
                "app.welcome": "Bienvenido a POUW Multi-Sector Chain",
                "task.title": "Gestión de Tareas",
                "task.create": "Crear Tarea",
                "task.status.pending": "Pendiente",
                "task.status.running": "En ejecución",
                "task.status.completed": "Completado",
                "task.status.failed": "Fallido",
                "node.title": "Gestión de Nodos",
                "market.title": "Mercado de Computación",
                "wallet.balance": "Saldo",
                "governance.title": "Gobernanza Comunitaria",
                "notification.title": "Notificaciones",
                "settings.title": "Configuración",
                "settings.language": "Idioma",
            },
            "fr-FR": {
                "app.name": "POUW Marché du Calcul",
                "app.welcome": "Bienvenue sur POUW Multi-Sector Chain",
                "task.title": "Gestion des Tâches",
                "task.create": "Créer une Tâche",
                "task.status.pending": "En attente",
                "task.status.running": "En cours",
                "task.status.completed": "Terminé",
                "task.status.failed": "Échoué",
                "node.title": "Gestion des Nœuds",
                "market.title": "Marché du Calcul",
                "wallet.balance": "Solde",
                "governance.title": "Gouvernance Communautaire",
                "notification.title": "Notifications",
                "settings.title": "Paramètres",
                "settings.language": "Langue",
            },
            "de-DE": {
                "app.name": "POUW Rechenmarkt",
                "app.welcome": "Willkommen bei POUW Multi-Sector Chain",
                "task.title": "Aufgabenverwaltung",
                "task.status.pending": "Ausstehend",
                "task.status.running": "Läuft",
                "task.status.completed": "Abgeschlossen",
                "node.title": "Knotenverwaltung",
                "market.title": "Rechenmarkt",
                "wallet.balance": "Kontostand",
                "settings.language": "Sprache",
            },
            "pt-BR": {
                "app.name": "POUW Mercado de Computação",
                "app.welcome": "Bem-vindo ao POUW Multi-Sector Chain",
                "task.title": "Gerenciamento de Tarefas",
                "task.status.pending": "Pendente",
                "task.status.running": "Executando",
                "task.status.completed": "Concluído",
                "node.title": "Gerenciamento de Nós",
                "market.title": "Mercado de Computação",
                "wallet.balance": "Saldo",
                "settings.language": "Idioma",
            },
            "ru-RU": {
                "app.name": "POUW Рынок вычислений",
                "app.welcome": "Добро пожаловать в POUW Multi-Sector Chain",
                "task.title": "Управление задачами",
                "task.status.pending": "Ожидание",
                "task.status.running": "Выполняется",
                "task.status.completed": "Завершено",
                "node.title": "Управление узлами",
                "market.title": "Рынок вычислений",
                "wallet.balance": "Баланс",
                "settings.language": "Язык",
            },
            "ar-SA": {
                "app.name": "سوق الحوسبة POUW",
                "app.welcome": "مرحبًا بكم في POUW Multi-Sector Chain",
                "task.title": "إدارة المهام",
                "task.status.pending": "معلق",
                "task.status.running": "قيد التنفيذ",
                "task.status.completed": "مكتمل",
                "node.title": "إدارة العقد",
                "market.title": "سوق الحوسبة",
                "wallet.balance": "الرصيد",
                "settings.language": "اللغة",
            },
            "zh-TW": {
                "app.name": "POUW 算力市場",
                "app.welcome": "歡迎使用 POUW 多扇區算力鏈",
                "task.title": "任務管理",
                "task.create": "建立任務",
                "task.status.pending": "等待中",
                "task.status.running": "執行中",
                "task.status.completed": "已完成",
                "task.status.failed": "失敗",
                "node.title": "節點管理",
                "market.title": "算力市場",
                "wallet.balance": "餘額",
                "governance.title": "社區治理",
                "notification.title": "通知",
                "settings.title": "設定",
                "settings.language": "語言",
            },
        }

    def translate(self, key: str, language: str = "zh-CN",
                   **kwargs) -> str:
        """翻译文本"""
        lang_dict = self.translations.get(language, {})
        text = lang_dict.get(key)

        if text is None:
            # 回退到英语
            text = self.translations.get("en-US", {}).get(key)
        if text is None:
            # 回退到中文
            text = self.translations.get("zh-CN", {}).get(key, key)

        # 参数替换
        for k, v in kwargs.items():
            text = text.replace(f"{{{k}}}", str(v))

        return text

    def get_supported_languages(self) -> List[Dict]:
        """获取支持的语言列表"""
        language_names = {
            "zh-CN": ("简体中文", "Chinese (Simplified)"),
            "zh-TW": ("繁體中文", "Chinese (Traditional)"),
            "en-US": ("English", "English"),
            "ja-JP": ("日本語", "Japanese"),
            "ko-KR": ("한국어", "Korean"),
            "es-ES": ("Español", "Spanish"),
            "fr-FR": ("Français", "French"),
            "de-DE": ("Deutsch", "German"),
            "pt-BR": ("Português", "Portuguese"),
            "ru-RU": ("Русский", "Russian"),
            "ar-SA": ("العربية", "Arabic"),
        }
        return [
            {"code": code, "native_name": names[0], "english_name": names[1],
             "keys_count": len(self.translations.get(code, {}))}
            for code, names in language_names.items()
        ]

    def add_translation(self, language: str, key: str, value: str):
        """添加翻译条目"""
        if language not in self.translations:
            self.translations[language] = {}
        self.translations[language][key] = value


# ============================================================
# 实时通知系统
# ============================================================

class NotificationService:
    """
    实时通知服务

    功能：
    1. 多类型通知（任务/节点/交易/安全/治理）
    2. 优先级管理
    3. 通知偏好设置
    4. WebSocket 推送支持
    """

    def __init__(self, db_path: str = "data/notifications.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.notifications: Dict[str, List[Notification]] = {}  # user_id -> notifications
        self.subscribers: Dict[str, List[Callable]] = {}  # user_id -> callbacks
        self.user_preferences: Dict[str, UserPreferences] = {}
        self._init_db()

        logger.info("[通知服务] 初始化完成")

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    notification_type TEXT,
                    priority TEXT DEFAULT 'normal',
                    title TEXT,
                    message TEXT,
                    data_json TEXT,
                    read INTEGER DEFAULT 0,
                    created_at REAL,
                    expires_at REAL
                );

                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'zh-CN',
                    timezone TEXT DEFAULT 'Asia/Shanghai',
                    notification_enabled INTEGER DEFAULT 1,
                    theme TEXT DEFAULT 'dark',
                    items_per_page INTEGER DEFAULT 20,
                    config_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
                CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(notification_type);
                CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(read);
            """)

    def send_notification(self, user_id: str,
                           notification_type: NotificationType,
                           title: str, message: str,
                           priority: NotificationPriority = NotificationPriority.NORMAL,
                           data: Optional[Dict] = None,
                           ttl_hours: float = 72.0) -> str:
        """发送通知"""
        with self.lock:
            # 检查用户偏好
            prefs = self.user_preferences.get(user_id)
            if prefs and not prefs.notification_enabled:
                return ""
            if prefs and notification_type not in prefs.notification_types:
                return ""

            notification = Notification(
                notification_id=str(uuid.uuid4()),
                user_id=user_id,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                data=data or {},
                created_at=time.time(),
                expires_at=time.time() + ttl_hours * 3600
            )

            if user_id not in self.notifications:
                self.notifications[user_id] = []
            self.notifications[user_id].append(notification)

            # 限制数量
            if len(self.notifications[user_id]) > 1000:
                self.notifications[user_id] = self.notifications[user_id][-500:]

            # 持久化
            with self._get_db() as conn:
                conn.execute("""
                    INSERT INTO notifications
                    (notification_id, user_id, notification_type, priority,
                     title, message, data_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (notification.notification_id, user_id,
                      notification_type.value, priority.value,
                      title, message, json.dumps(data or {}),
                      notification.created_at, notification.expires_at))

            # 触发回调
            self._trigger_callbacks(user_id, notification)

            return notification.notification_id

    def _trigger_callbacks(self, user_id: str, notification: Notification):
        """触发WebSocket推送回调"""
        callbacks = self.subscribers.get(user_id, [])
        for callback in callbacks:
            try:
                callback({
                    "type": "notification",
                    "data": {
                        "id": notification.notification_id,
                        "type": notification.notification_type.value,
                        "priority": notification.priority.value,
                        "title": notification.title,
                        "message": notification.message,
                        "data": notification.data,
                        "created_at": notification.created_at,
                    }
                })
            except Exception as e:
                logger.error(f"[通知服务] 回调错误: {e}")

    def subscribe(self, user_id: str, callback: Callable):
        """订阅通知（WebSocket连接时调用）"""
        if user_id not in self.subscribers:
            self.subscribers[user_id] = []
        self.subscribers[user_id].append(callback)

    def unsubscribe(self, user_id: str, callback: Callable):
        """取消订阅"""
        if user_id in self.subscribers:
            self.subscribers[user_id] = [
                c for c in self.subscribers[user_id] if c != callback]

    def get_notifications(self, user_id: str, unread_only: bool = False,
                           notification_type: Optional[NotificationType] = None,
                           limit: int = 50) -> List[Dict]:
        """获取用户通知列表"""
        notifications = self.notifications.get(user_id, [])

        # 过滤
        filtered = notifications
        if unread_only:
            filtered = [n for n in filtered if not n.read]
        if notification_type:
            filtered = [n for n in filtered
                        if n.notification_type == notification_type]

        # 过期清理
        now = time.time()
        filtered = [n for n in filtered
                    if n.expires_at == 0 or n.expires_at > now]

        # 排序（优先级 > 时间）
        priority_order = {
            NotificationPriority.URGENT: 0,
            NotificationPriority.HIGH: 1,
            NotificationPriority.NORMAL: 2,
            NotificationPriority.LOW: 3,
        }
        filtered.sort(key=lambda n: (
            priority_order.get(n.priority, 2), -n.created_at))

        return [{
            "id": n.notification_id,
            "type": n.notification_type.value,
            "priority": n.priority.value,
            "title": n.title,
            "message": n.message,
            "data": n.data,
            "read": n.read,
            "created_at": n.created_at,
        } for n in filtered[:limit]]

    def mark_read(self, notification_id: str) -> bool:
        """标记通知已读"""
        for user_notifications in self.notifications.values():
            for n in user_notifications:
                if n.notification_id == notification_id:
                    n.read = True
                    with self._get_db() as conn:
                        conn.execute(
                            "UPDATE notifications SET read=1 WHERE notification_id=?",
                            (notification_id,))
                    return True
        return False

    def mark_all_read(self, user_id: str) -> int:
        """标记用户所有通知已读"""
        count = 0
        notifications = self.notifications.get(user_id, [])
        for n in notifications:
            if not n.read:
                n.read = True
                count += 1

        with self._get_db() as conn:
            conn.execute(
                "UPDATE notifications SET read=1 WHERE user_id=? AND read=0",
                (user_id,))

        return count

    def get_unread_count(self, user_id: str) -> Dict:
        """获取未读通知数量"""
        notifications = self.notifications.get(user_id, [])
        unread = [n for n in notifications if not n.read]

        by_type = {}
        for n in unread:
            t = n.notification_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total": len(unread),
            "by_type": by_type,
            "urgent": sum(1 for n in unread
                          if n.priority == NotificationPriority.URGENT),
        }

    def set_preferences(self, user_id: str, preferences: UserPreferences):
        """设置用户偏好"""
        self.user_preferences[user_id] = preferences

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences
                (user_id, language, timezone, notification_enabled,
                 theme, items_per_page, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, preferences.language.value,
                  preferences.timezone, preferences.notification_enabled,
                  preferences.theme, preferences.items_per_page,
                  json.dumps({
                      "default_device_types": [d.value for d in preferences.default_device_types],
                      "default_regions": preferences.default_regions,
                  })))


# ============================================================
# 实时日志查看器
# ============================================================

class LogViewer:
    """
    实时日志查看器

    提供：
    1. 结构化日志收集
    2. 按级别/模块/时间过滤
    3. WebSocket 实时推送
    4. 调试信息聚合
    """

    def __init__(self, max_logs: int = 5000):
        self.max_logs = max_logs
        self.logs: List[Dict] = []
        self.lock = threading.Lock()
        self.log_subscribers: List[Callable] = []

    def add_log(self, level: LogLevel, module: str,
                message: str, details: Optional[Dict] = None):
        """添加日志条目"""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": time.time(),
            "level": level.value,
            "module": module,
            "message": message,
            "details": details or {},
        }

        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-(self.max_logs // 2):]

        # 推送给订阅者
        for callback in self.log_subscribers:
            try:
                callback(entry)
            except Exception:
                pass

    def get_logs(self, level: Optional[LogLevel] = None,
                  module: Optional[str] = None,
                  since: Optional[float] = None,
                  limit: int = 100) -> List[Dict]:
        """查询日志"""
        with self.lock:
            filtered = self.logs

            if level:
                level_order = ["debug", "info", "warning", "error", "critical"]
                min_idx = level_order.index(level.value)
                filtered = [l for l in filtered
                            if level_order.index(l["level"]) >= min_idx]

            if module:
                filtered = [l for l in filtered if module in l["module"]]

            if since:
                filtered = [l for l in filtered if l["timestamp"] >= since]

            return filtered[-limit:]

    def subscribe_logs(self, callback: Callable):
        """订阅实时日志"""
        self.log_subscribers.append(callback)

    def unsubscribe_logs(self, callback: Callable):
        """取消订阅"""
        self.log_subscribers = [c for c in self.log_subscribers if c != callback]

    def get_log_stats(self) -> Dict:
        """获取日志统计"""
        with self.lock:
            stats = {"total": len(self.logs)}
            for level in LogLevel:
                stats[level.value] = sum(
                    1 for l in self.logs if l["level"] == level.value)

            # 最近1小时错误率
            recent = [l for l in self.logs
                      if l["timestamp"] > time.time() - 3600]
            if recent:
                errors = sum(1 for l in recent
                             if l["level"] in ("error", "critical"))
                stats["error_rate_1h"] = errors / len(recent)
            else:
                stats["error_rate_1h"] = 0

            return stats


# ============================================================
# 节点选择控制器
# ============================================================

class NodeSelectionController:
    """
    节点选择与控制

    功能：
    1. 多维度节点筛选（设备类型/性能/信誉/区域）
    2. 智能推荐
    3. 自定义选择偏好
    """

    def __init__(self):
        self.available_nodes: Dict[str, Dict] = {}  # node_id -> info

    def register_available_node(self, node_id: str, info: Dict):
        """注册可用节点"""
        info["node_id"] = node_id
        info.setdefault("device_type", "gpu_nvidia")
        info.setdefault("gpu_model", "")
        info.setdefault("gpu_count", 0)
        info.setdefault("gpu_memory_gb", 0)
        info.setdefault("cpu_cores", 0)
        info.setdefault("bandwidth_mbps", 100)
        info.setdefault("region", "")
        info.setdefault("latency_ms", 100)
        info.setdefault("reputation_score", 50)
        info.setdefault("uptime_ratio", 0.95)
        info.setdefault("verification_level", 1)
        info.setdefault("has_tee", False)
        info.setdefault("has_hsm", False)
        info.setdefault("price_per_hour", 1.0)
        info.setdefault("load_factor", 0.5)
        self.available_nodes[node_id] = info

    def search_nodes(self, criteria: NodeSelectionCriteria) -> List[Dict]:
        """根据条件搜索节点"""
        results = []

        for node_id, info in self.available_nodes.items():
            # 设备类型过滤
            if criteria.device_types:
                if info["device_type"] not in [d.value for d in criteria.device_types]:
                    continue

            # GPU过滤
            if criteria.min_gpu_count > 0 and info["gpu_count"] < criteria.min_gpu_count:
                continue
            if criteria.gpu_models and info["gpu_model"] not in criteria.gpu_models:
                continue
            if criteria.min_gpu_memory_gb > 0 and info["gpu_memory_gb"] < criteria.min_gpu_memory_gb:
                continue

            # 性能过滤
            if info["latency_ms"] > criteria.max_latency_ms:
                continue
            if info["bandwidth_mbps"] < criteria.min_bandwidth_mbps:
                continue

            # 信誉过滤
            if info["reputation_score"] < criteria.min_reputation_score:
                continue
            if info["uptime_ratio"] < criteria.min_uptime_ratio:
                continue

            # 区域过滤
            if criteria.preferred_regions and info["region"] not in criteria.preferred_regions:
                continue
            if criteria.excluded_regions and info["region"] in criteria.excluded_regions:
                continue

            # 安全过滤
            if info["verification_level"] < criteria.min_verification_level:
                continue
            if criteria.require_tee and not info["has_tee"]:
                continue
            if criteria.require_hsm and not info["has_hsm"]:
                continue

            # 计算综合评分
            score = self._calculate_score(info, criteria)
            results.append({**info, "match_score": round(score, 3)})

        # 排序
        sort_key_map = {
            "score": lambda x: -x["match_score"],
            "price": lambda x: x["price_per_hour"],
            "latency": lambda x: x["latency_ms"],
            "reputation": lambda x: -x["reputation_score"],
        }
        sort_fn = sort_key_map.get(criteria.sort_by, sort_key_map["score"])
        results.sort(key=sort_fn)

        return results

    def _calculate_score(self, info: Dict,
                          criteria: NodeSelectionCriteria) -> float:
        """计算节点匹配评分"""
        score = 0.0

        # 性能评分 (30%)
        latency_score = max(0, 1 - info["latency_ms"] / criteria.max_latency_ms)
        score += latency_score * 0.30

        # 信誉评分 (25%)
        rep_score = info["reputation_score"] / 100.0
        score += rep_score * 0.25

        # 可用性评分 (20%)
        availability = (1 - info["load_factor"]) * info["uptime_ratio"]
        score += availability * 0.20

        # 价格评分 (15%)
        price_score = max(0, 1 - info["price_per_hour"] / 20.0)
        score += price_score * 0.15

        # 安全评分 (10%)
        security = info["verification_level"] / 4.0
        if info["has_tee"]:
            security += 0.2
        if info["has_hsm"]:
            security += 0.2
        score += min(1, security) * 0.10

        return min(1.0, score)

    def get_recommendations(self, task_type: str = "general",
                             budget: float = 0.0) -> List[Dict]:
        """获取智能推荐节点"""
        # 根据任务类型设置推荐条件
        criteria_map = {
            "ai_training": NodeSelectionCriteria(
                device_types=[DeviceType.GPU_NVIDIA],
                gpu_models=["H100", "A100"],
                min_gpu_memory_gb=24.0,
                min_reputation_score=50.0,
                sort_by="score"
            ),
            "rendering": NodeSelectionCriteria(
                device_types=[DeviceType.GPU_NVIDIA, DeviceType.GPU_AMD],
                min_gpu_memory_gb=8.0,
                sort_by="price"
            ),
            "scientific": NodeSelectionCriteria(
                device_types=[DeviceType.GPU_NVIDIA, DeviceType.CPU],
                min_reputation_score=60.0,
                sort_by="score"
            ),
            "edge_inference": NodeSelectionCriteria(
                device_types=[DeviceType.EDGE, DeviceType.GPU_NVIDIA],
                max_latency_ms=50.0,
                sort_by="latency"
            ),
            "general": NodeSelectionCriteria(
                sort_by="score"
            ),
        }

        criteria = criteria_map.get(task_type, criteria_map["general"])
        nodes = self.search_nodes(criteria)

        # 如果有预算限制
        if budget > 0:
            nodes = [n for n in nodes if n["price_per_hour"] <= budget]

        return nodes[:10]  # 返回前10推荐
