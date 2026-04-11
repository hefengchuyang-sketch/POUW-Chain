# tests/integration/
# 集成测试（需要运行节点）
#
# 默认 pytest 不会执行集成测试；需要显式开启：
#   python -m pytest tests/integration/ -v --run-integration
#
# 若未启动节点（python main.py），用例会被自动 skip 而不是报错中断。
#
# 默认开发回归：
#   python -m pytest -q
