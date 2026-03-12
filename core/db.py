"""SQLite 数据库工具 — 统一配置 WAL 模式和性能优化。"""

import sqlite3
from contextlib import contextmanager


def connect(db_path: str, row_factory=sqlite3.Row) -> sqlite3.Connection:
    """创建带 WAL 模式和性能优化的 SQLite 连接。

    Args:
        db_path: 数据库文件路径
        row_factory: 行工厂（默认 sqlite3.Row）

    Returns:
        已配置的 sqlite3.Connection
    """
    conn = sqlite3.connect(db_path)
    if row_factory:
        conn.row_factory = row_factory
    # WAL 模式 — 支持并发读写，减少锁冲突
    conn.execute("PRAGMA journal_mode=WAL")
    # 同步模式 NORMAL — WAL 模式下兼顾性能和安全
    conn.execute("PRAGMA synchronous=NORMAL")
    # 外键约束
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def connection(db_path: str, row_factory=sqlite3.Row):
    """上下文管理器 — 自动提交/关闭连接。

    用法::

        with db.connection("data.db") as conn:
            conn.execute("INSERT INTO ...")
    """
    conn = connect(db_path, row_factory)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
