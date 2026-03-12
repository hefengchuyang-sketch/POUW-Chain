"""
Account 模块 - 账户与余额模型

.. deprecated::
    此模块为 Phase 2 遗留代码，生产环境使用 UTXO 模型 (utxo_store.py)
    和板块币账本 (sector_coin.py)。此类仅保留供 order_engine /
    distributed_engine 等未集成模块引用。新代码请勿使用。

Phase 2 实现：
- 维护各板块币余额 (block_balances)
- 维护主币余额 (main_balance)

Phase 3 扩展：
- MAIN 冻结机制 (frozen_main)
- 可用余额 = 总余额 - 冻结
"""

from typing import Dict


class Account:
    """账户模型，持有板块币与主币余额。

    Attributes:
        account_id: 账户唯一标识
        block_balances: 各板块币余额 {block_type: amount}
        main_balance: 主币 (MAIN) 总余额
        frozen_main: 冻结的 MAIN（用于订单预算）
    """

    def __init__(self, account_id: str):
        self.account_id = account_id
        self.block_balances: Dict[str, float] = {}
        self.main_balance: float = 0.0
        self.frozen_main: float = 0.0  # Phase 3: 冻结余额

    def get_block_balance(self, block_type: str) -> float:
        """获取指定板块币余额。"""
        return self.block_balances.get(block_type, 0.0)

    def credit_block_coin(self, block_type: str, amount: float):
        """增加板块币余额。"""
        self.block_balances[block_type] = self.get_block_balance(block_type) + amount

    def debit_block_coin(self, block_type: str, amount: float) -> bool:
        """扣减板块币余额，余额不足返回 False。"""
        current = self.get_block_balance(block_type)
        if current < amount:
            return False
        self.block_balances[block_type] = current - amount
        return True

    def credit_main(self, amount: float):
        """增加主币余额。"""
        self.main_balance += amount

    def debit_main(self, amount: float) -> bool:
        """扣减主币余额，余额不足返回 False。"""
        if self.available_main() < amount:
            return False
        self.main_balance -= amount
        return True

    # ========== Phase 3: MAIN 冻结机制 ==========

    def available_main(self) -> float:
        """返回可用 MAIN 余额（总余额 - 冻结）。"""
        return self.main_balance - self.frozen_main

    def freeze_main(self, amount: float) -> bool:
        """冻结 MAIN（用于订单预算）。

        Args:
            amount: 要冻结的数量

        Returns:
            是否成功（可用余额不足则失败）
        """
        if self.available_main() < amount:
            return False
        self.frozen_main += amount
        return True

    def unfreeze_main(self, amount: float) -> bool:
        """解冻 MAIN。

        Args:
            amount: 要解冻的数量

        Returns:
            是否成功
        """
        if self.frozen_main < amount:
            return False
        self.frozen_main -= amount
        return True

    def __repr__(self) -> str:
        if self.frozen_main > 0:
            return (f"Account({self.account_id}, blocks={self.block_balances}, "
                    f"MAIN={self.main_balance}, frozen={self.frozen_main})")
        return f"Account({self.account_id}, blocks={self.block_balances}, MAIN={self.main_balance})"
