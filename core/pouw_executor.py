"""
PoUWExecutor 模块 - 真实 PoUW 计算执行器

Phase 5 实现 + Docker 容器支持：
- 执行真实计算任务（非模拟）
- 内置类型：矩阵乘法、线性回归、梯度下降、哈希搜索
- 扩展类型：自定义代码执行、Docker 容器任务
- 可选集成 SandboxExecutor 实现容器隔离
- 使用 numpy 进行矩阵运算，返回真实 score
- 无需 torch，仅用标准库 + numpy
"""

import hashlib
import time
import math
import json
import os
import secrets
import logging
import sys
import threading
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

# 尝试导入 numpy，若不可用则使用纯 Python 实现
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class RealTaskType(Enum):
    """真实任务类型。"""
    MATRIX_MULTIPLY = "matrix_multiply"
    LINEAR_REGRESSION = "linear_regression"
    GRADIENT_DESCENT = "gradient_descent"
    HASH_SEARCH = "hash_search"
    CUSTOM_CODE = "custom_code"         # 自定义 Python 代码
    DOCKER_TASK = "docker_task"         # Docker 容器化任务
    CONFIDENTIAL_MODEL = "confidential_model" # TEE 机密模型任务


@dataclass
class RealPoUWTask:
    """真实 PoUW 任务定义。

    Attributes:
        task_id: 任务 ID
        task_type: 任务类型
        params: 任务参数
        difficulty: 难度（影响计算量）
        expected_threshold: 预期分数阈值
    """
    task_id: str
    task_type: RealTaskType
    params: Dict[str, Any]
    difficulty: int = 1
    expected_threshold: float = 0.5


@dataclass
class RealPoUWResult:
    """真实 PoUW 执行结果。

    Attributes:
        task_id: 任务 ID
        miner_id: 执行矿工
        result: 计算结果
        score: 真实分数（0.0-1.0）
        execution_time: 执行时间（秒）
        verified: 是否通过验证
        computation_proof: 计算证明（用于审计）
    """
    task_id: str
    miner_id: str
    result: Any
    score: float
    execution_time: float
    verified: bool
    computation_proof: str = ""


class PoUWExecutor:
    """真实 PoUW 计算执行器。

    执行真实的计算任务，返回基于实际计算结果的分数。

    执行模式：
    - 内置任务（MATRIX_MULTIPLY 等）：直接在进程内使用 numpy 执行
    - 自定义代码（CUSTOM_CODE）：在进程内受限环境执行
    - Docker 任务（DOCKER_TASK）：通过 SandboxExecutor 在容器中执行

    Attributes:
        min_score_threshold: 最低分数阈值
    """

    def __init__(
        self,
        min_score_threshold: float = 0.5,
        sandbox=None,
    ):
        """初始化 PoUW 执行器。

        Args:
            min_score_threshold: 最低分数阈值
            sandbox: 可选的 SandboxExecutor 实例（用于 Docker 任务）
        """
        self.min_score_threshold = min_score_threshold
        self._task_counter = 0
        self._counter_lock = threading.Lock()
        self._sandbox = sandbox  # Optional[SandboxExecutor]

    @staticmethod
    def _digest_obj(obj: Any) -> str:
        """稳定序列化后做 SHA256 摘要。"""
        try:
            payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        except Exception:
            payload = str(obj)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _build_structured_proof(
        self,
        task: RealPoUWTask,
        result: Any,
        raw_proof: str,
        execution_time: float,
    ) -> str:
        """构建不可伪造导向的结构化证明，保留 raw_proof 兼容旧链路。"""
        input_view = dict(task.params or {})
        reveal_secret = input_view.pop("challenge_reveal", "")

        proof_payload = {
            "version": "pouw_proof_v2",
            "task_id": task.task_id,
            "task_type": task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type),
            "input_digest": self._digest_obj(input_view),
            "challenge": task.params.get("challenge", ""),
            "challenge_commitment": task.params.get("challenge_commitment", ""),
            "challenge_reveal": reveal_secret,
            "trace_digest": self._digest_obj({
                "raw_proof": raw_proof,
                "execution_ms": int(max(execution_time, 0.0) * 1000),
                "difficulty": task.difficulty,
                "threshold": task.expected_threshold,
            }),
            "output_digest": self._digest_obj(result),
            "timestamp_ms": int(time.time() * 1000),
            "window_start_ms": int(task.params.get("challenge_window_start_ms", 0) or 0),
            "window_end_ms": int(task.params.get("challenge_window_end_ms", 0) or 0),
            "raw_proof": raw_proof,
        }

        proof_hash_src = dict(proof_payload)
        proof_payload["proof_hash"] = self._digest_obj(proof_hash_src)
        return "proof_json=" + json.dumps(proof_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def generate_task(
        self,
        task_type: RealTaskType,
        difficulty: int = 1,
        **kwargs,
    ) -> RealPoUWTask:
        """生成真实 PoUW 任务。

        Args:
            task_type: 任务类型
            difficulty: 难度等级 (1-10)
            **kwargs: 额外参数
                - code: 自定义代码（CUSTOM_CODE/DOCKER_TASK）
                - data: 任务数据（CUSTOM_CODE/DOCKER_TASK）
                - image: Docker 镜像（DOCKER_TASK）

        Returns:
            RealPoUWTask 实例
        """
        with self._counter_lock:
            self._task_counter += 1
            entropy = kwargs.get("entropy") or (
                f"{time.time_ns()}:{os.getpid()}:{secrets.token_hex(8)}:{self._task_counter}"
            )
            entropy_hash = hashlib.sha256(str(entropy).encode()).hexdigest()[:12]
            task_id = f"real_task_{self._task_counter:04d}_{entropy_hash}"

        # 限制难度范围
        difficulty = max(1, min(10, difficulty))

        task_seed = str(kwargs.get("task_seed", ""))
        prev_hash = str(kwargs.get("prev_hash", ""))
        block_height = int(kwargs.get("block_height", 0) or 0)
        miner_id = str(kwargs.get("miner_id", ""))
        challenge_window = int(kwargs.get("challenge_window", int(time.time() // 30)))
        window_start_ms = int(kwargs.get("challenge_window_start_ms", challenge_window * 30000))
        window_end_ms = int(kwargs.get("challenge_window_end_ms", window_start_ms + 30000))

        challenge_material = f"{prev_hash}:{block_height}:{challenge_window}:{miner_id}:{task_type.value}:{task_seed}:{entropy_hash}"
        challenge = hashlib.sha256(challenge_material.encode()).hexdigest()
        challenge_reveal = secrets.token_hex(16)
        challenge_commitment = hashlib.sha256(f"{challenge}:{challenge_reveal}".encode()).hexdigest()

        if task_type == RealTaskType.MATRIX_MULTIPLY:
            params, threshold = self._gen_matrix_multiply(difficulty)

        elif task_type == RealTaskType.LINEAR_REGRESSION:
            params, threshold = self._gen_linear_regression(difficulty)

        elif task_type == RealTaskType.GRADIENT_DESCENT:
            params, threshold = self._gen_gradient_descent(difficulty)

        elif task_type == RealTaskType.HASH_SEARCH:
            params, threshold = self._gen_hash_search(
                difficulty,
                task_seed=task_seed,
                challenge=challenge,
            )

        elif task_type == RealTaskType.CUSTOM_CODE:
            params, threshold = self._gen_custom_code(kwargs)

        elif task_type == RealTaskType.DOCKER_TASK:
            params, threshold = self._gen_docker_task(kwargs)

        elif task_type == RealTaskType.CONFIDENTIAL_MODEL:
            # Stub for confidential model
            params = {
                "model_id": kwargs.get("model_id", "stub_model"),
                "data": kwargs.get("data", {})
            }
            threshold = 0.5
            
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        params.update({
            "challenge": challenge,
            "challenge_commitment": challenge_commitment,
            "challenge_reveal": challenge_reveal,
            "challenge_window": challenge_window,
            "challenge_window_start_ms": window_start_ms,
            "challenge_window_end_ms": window_end_ms,
            "challenge_context_hash": hashlib.sha256(
                f"{prev_hash}:{block_height}:{challenge_window}:{miner_id}".encode()
            ).hexdigest(),
        })

        return RealPoUWTask(
            task_id=task_id,
            task_type=task_type,
            params=params,
            difficulty=difficulty,
            expected_threshold=threshold,
        )

    # ==================== 任务生成器 ====================

    def _gen_matrix_multiply(self, difficulty: int) -> Tuple[Dict, float]:
        """生成矩阵乘法任务参数。"""
        size = 10 * difficulty
        if HAS_NUMPY:
            A = np.random.randn(size, size).tolist()
            B = np.random.randn(size, size).tolist()
        else:
            A = [[hash(f"{i}{j}") % 100 / 50 - 1 for j in range(size)] for i in range(size)]
            B = [[hash(f"{j}{i}") % 100 / 50 - 1 for j in range(size)] for i in range(size)]
        return {"A": A, "B": B, "size": size}, 0.8

    def _gen_linear_regression(self, difficulty: int) -> Tuple[Dict, float]:
        """生成线性回归任务参数。"""
        n_samples = 50 * difficulty
        if HAS_NUMPY:
            X = np.random.randn(n_samples, 1).tolist()
            true_w, true_b = 2.5, 1.0
            y = [(x[0] * true_w + true_b + np.random.randn() * 0.1) for x in X]
        else:
            import random
            X = [[random.gauss(0, 1)] for _ in range(n_samples)]
            true_w, true_b = 2.5, 1.0
            y = [x[0] * true_w + true_b + random.gauss(0, 0.1) for x in X]
        return {"X": X, "y": y, "n_samples": n_samples}, 0.7

    def _gen_gradient_descent(self, difficulty: int) -> Tuple[Dict, float]:
        """生成梯度下降优化任务参数。"""
        target = [1.0, 2.0, 3.0]
        return {
            "target": target,
            "initial": [0.0, 0.0, 0.0],
            "learning_rate": 0.1,
            "max_iterations": 100 * difficulty,
        }, 0.9

    def _gen_hash_search(self, difficulty: int, task_seed: str = "", challenge: str = "") -> Tuple[Dict, float]:
        """生成哈希前缀搜索任务参数。"""
        prefix_len = min(difficulty + 1, 4)
        prefix = "0" * prefix_len
        seed_material = task_seed or secrets.token_hex(12)
        random_seed = hashlib.sha256(f"{seed_material}:{challenge}:{self._task_counter}".encode()).hexdigest()
        data = f"block_data_{random_seed[:24]}"
        return {
            "data": data,
            "prefix": prefix,
            "max_nonce": 100000 * difficulty,
        }, 0.5

    def _gen_custom_code(self, kwargs: Dict) -> Tuple[Dict, float]:
        """生成自定义代码任务参数。"""
        code = kwargs.get("code", "result = {'status': 'empty'}")
        data = kwargs.get("data", {})
        return {"code": code, "data": data}, 0.5

    def _gen_docker_task(self, kwargs: Dict) -> Tuple[Dict, float]:
        """生成 Docker 容器任务参数。"""
        code = kwargs.get("code", "result = {'status': 'empty'}")
        data = kwargs.get("data", {})
        image = kwargs.get("image", "python:3.11.12-slim")
        return {
            "code": code,
            "data": data,
            "image": image,
        }, 0.5

    # ==================== 任务执行 ====================

    def execute_task(
        self,
        task: RealPoUWTask,
        miner_id: str,
    ) -> RealPoUWResult:
        """执行真实 PoUW 任务。

        Args:
            task: 任务定义
            miner_id: 执行矿工 ID

        Returns:
            RealPoUWResult 实例
        """
        # 任务参数校验
        if not self._validate_task(task):
            return RealPoUWResult(
                task_id=task.task_id,
                miner_id=miner_id,
                result={"error": "Task validation failed"},
                score=0.0,
                execution_time=0.0,
                verified=False,
                computation_proof="validation_failed",
            )

        # ====== 集群派发拦截 ======
        try:
            from core.cluster_manager import is_master, dispatch_task_to_cluster
            if is_master():
                # 如果当前节点是 Master，就不在本地执行，直接转发给子机集群！
                return dispatch_task_to_cluster(task, miner_id)
        except ImportError:
            pass
        # ========================

        start_time = time.perf_counter()

        try:
            if task.task_type == RealTaskType.MATRIX_MULTIPLY:
                result, score, proof = self._execute_matrix_multiply(task)

            elif task.task_type == RealTaskType.LINEAR_REGRESSION:
                result, score, proof = self._execute_linear_regression(task)

            elif task.task_type == RealTaskType.GRADIENT_DESCENT:
                result, score, proof = self._execute_gradient_descent(task)

            elif task.task_type == RealTaskType.HASH_SEARCH:
                result, score, proof = self._execute_hash_search(task)

            elif task.task_type == RealTaskType.CUSTOM_CODE:
                result, score, proof = self._execute_custom_code(task)

            elif task.task_type == RealTaskType.DOCKER_TASK:
                result, score, proof = self._execute_docker_task(task, miner_id)

            elif task.task_type == RealTaskType.CONFIDENTIAL_MODEL:
                result, score, proof = self._execute_confidential_model(task, miner_id)

            else:
                result, score, proof = None, 0.0, "unknown_task"

        except Exception as e:
            logger.error(f"PoUW task {task.task_id} execution error: {e}")
            result = {"error": "Task execution failed"}
            score = 0.0
            proof = f"exec_error:{type(e).__name__}"

        execution_time = time.perf_counter() - start_time
        effective_threshold = max(task.expected_threshold, self.min_score_threshold)
        verified = score >= effective_threshold
        structured_proof = self._build_structured_proof(task, result, str(proof), execution_time)

        return RealPoUWResult(
            task_id=task.task_id,
            miner_id=miner_id,
            result=result,
            score=score,
            execution_time=execution_time,
            verified=verified,
            computation_proof=structured_proof,
        )

    def _validate_task(self, task: RealPoUWTask) -> bool:
        """校验任务参数有效性。"""
        if not task.task_id:
            return False
        if not task.params:
            return False
        if task.difficulty < 1 or task.difficulty > 10:
            return False

        # 自定义代码类型必须提供 code 参数
        if task.task_type in (RealTaskType.CUSTOM_CODE, RealTaskType.DOCKER_TASK):
            code = task.params.get("code", "")
            if not code or not isinstance(code, str):
                return False
            # 代码长度限制（1MB）
            if len(code) > 1024 * 1024:
                return False

        return True

    # ==================== 内置任务类型执行 ====================

    # 内置任务参数上限（防止 DoS）
    MAX_MATRIX_SIZE = 200
    MAX_HASH_NONCE = 10_000_000
    MAX_GD_ITERATIONS = 10_000

    def _execute_matrix_multiply(
        self, task: RealPoUWTask
    ) -> Tuple[Any, float, str]:
        """执行矩阵乘法任务。"""
        A = task.params["A"]
        B = task.params["B"]
        size = task.params["size"]

        if not isinstance(size, int) or size <= 0 or size > self.MAX_MATRIX_SIZE:
            return {"error": "Invalid matrix size"}, 0.0, "invalid_size"

        if HAS_NUMPY:
            A_np = np.array(A)
            B_np = np.array(B)
            C = np.dot(A_np, B_np)
            result = C.tolist()
            # 分数基于矩阵范数的合理性（n×n 标准正态矩阵乘积的 Frobenius 范数 ≈ n^1.5）
            norm = float(np.linalg.norm(C))
            expected_norm = size ** 1.5
            score = min(1.0, 1.0 / (1.0 + abs(norm - expected_norm) / max(expected_norm, 1.0)))
        else:
            # 纯 Python 矩阵乘法
            result = [[0] * size for _ in range(size)]
            for i in range(size):
                for j in range(size):
                    for k in range(size):
                        result[i][j] += A[i][k] * B[k][j]
            # 简单分数
            norm = sum(sum(abs(x) for x in row) for row in result) / (size * size)
            score = min(1.0, 0.5 + 0.5 / (1.0 + abs(norm - 1.0)))

        # 计算证明：结果矩阵的哈希
        proof = hashlib.sha256(str(result[:2]).encode()).hexdigest()[:16]
        return result, score, f"matrix_hash={proof}"

    def _execute_linear_regression(
        self, task: RealPoUWTask
    ) -> Tuple[Any, float, str]:
        """执行线性回归任务。"""
        X = task.params["X"]
        y = task.params["y"]
        n = len(X)

        if n == 0 or len(y) != n:
            return {"error": "Invalid regression data"}, 0.0, "invalid_data"

        # 简单最小二乘法：y = wx + b
        sum_x = sum(x[0] for x in X)
        sum_y = sum(y)
        sum_xy = sum(X[i][0] * y[i] for i in range(n))
        sum_x2 = sum(x[0] ** 2 for x in X)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-10:
            w, b = 0.0, sum_y / n
        else:
            w = (n * sum_xy - sum_x * sum_y) / denom
            b = (sum_y - w * sum_x) / n

        # 计算 R^2 分数
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((y[i] - (w * X[i][0] + b)) ** 2 for i in range(n))

        if ss_tot > 0:
            r2 = 1 - ss_res / ss_tot
            score = max(0.0, min(1.0, r2))
        else:
            score = 1.0 if ss_res < 1e-10 else 0.0

        result = {"w": w, "b": b, "r2": score}
        proof = f"w={w:.4f},b={b:.4f}"
        return result, score, proof

    def _execute_gradient_descent(
        self, task: RealPoUWTask
    ) -> Tuple[Any, float, str]:
        """执行梯度下降优化任务。"""
        target = task.params["target"]
        params = list(task.params["initial"])
        lr = task.params["learning_rate"]
        max_iter = min(task.params["max_iterations"], self.MAX_GD_ITERATIONS)

        if not target or len(params) != len(target):
            return {"error": "Invalid gradient descent parameters"}, 0.0, "invalid_params"

        # 简单梯度下降：最小化 ||params - target||^2
        for _ in range(max_iter):
            for i in range(len(params)):
                grad = 2 * (params[i] - target[i])
                params[i] -= lr * grad

        # 计算接近度作为分数
        distance = sum((params[i] - target[i]) ** 2 for i in range(len(params)))
        distance = math.sqrt(distance)
        score = max(0.0, 1.0 - distance / len(target))

        result = {"final_params": params, "distance": distance}
        proof = f"dist={distance:.6f}"
        return result, score, proof

    def _execute_hash_search(
        self, task: RealPoUWTask
    ) -> Tuple[Any, float, str]:
        """执行哈希前缀搜索任务。"""
        data = task.params["data"]
        prefix = task.params["prefix"]
        max_nonce = min(task.params["max_nonce"], self.MAX_HASH_NONCE)

        nonce = 0
        found = False
        result_hash = ""

        while nonce < max_nonce:
            h = hashlib.sha256(f"{data}{nonce}".encode()).hexdigest()
            if h.startswith(prefix):
                result_hash = h
                found = True
                break
            nonce += 1

        if found:
            score = 1.0
            result = {"nonce": nonce, "hash": result_hash}
        else:
            score = 0.0
            result = {"nonce": nonce, "hash": None}

        proof = f"nonce={nonce}"
        return result, score, proof

    # ==================== 扩展任务类型执行 ====================

    # AST 节点白名单 — 仅允许安全的语法结构
    _ALLOWED_AST_NODES = {
        # 基本结构
        'Module', 'Expression', 'Interactive',
        # 语句
        'Assign', 'AugAssign', 'AnnAssign', 'Return',
        'For', 'While', 'If', 'With', 'Raise',
        'Pass', 'Break', 'Continue', 'Expr',
        # 表达式
        'BoolOp', 'NamedExpr', 'BinOp', 'UnaryOp', 'IfExp',
        'Dict', 'Set', 'ListComp', 'SetComp', 'DictComp', 'GeneratorExp',
        'Compare', 'Call', 'FormattedValue', 'JoinedStr',
        'Constant', 'Attribute', 'Subscript', 'Starred',
        'Name', 'List', 'Tuple', 'Slice',
        # 操作符
        'And', 'Or', 'Add', 'Sub', 'Mult', 'Div', 'Mod', 'Pow',
        'LShift', 'RShift', 'BitOr', 'BitXor', 'BitAnd', 'FloorDiv',
        'Invert', 'Not', 'UAdd', 'USub',
        'Eq', 'NotEq', 'Lt', 'LtE', 'Gt', 'GtE', 'Is', 'IsNot', 'In', 'NotIn',
        # 上下文
        'Load', 'Store', 'Del',
        # comprehension 辅助
        'comprehension',
        # arguments 辅助（用于 lambda）
        'arguments', 'arg', 'Lambda',
        # FunctionDef（允许定义函数，但不允许 import/class）
        'FunctionDef',
        # 异常处理（仅允许 try/except，不允许自定义异常类）
        'Try', 'ExceptHandler', 'TryStar',
    }

    # 禁止访问的属性名（沙箱逃逸向量 — 用于 AST 层检测）
    _FORBIDDEN_ATTRS = frozenset({
        '__class__', '__bases__', '__subclasses__', '__mro__',
        '__globals__', '__code__', '__func__',
        '__init__', '__new__', '__del__',
        '__import__', '__builtins__', '__loader__',
        '__spec__', '__dict__', '__getattr__',
        '__reduce__', '__reduce_ex__',
        '__qualname__', '__module__', '__wrapped__',
        '__closure__', '__annotations__',
        # 防止通过 format_map / vars 等间接访问
        'gi_frame', 'gi_code', 'f_globals', 'f_locals', 'f_builtins',
        'co_consts', 'co_names',
    })

    # 禁止调用的函数名
    _FORBIDDEN_CALLS = frozenset({
        'exec', 'eval', 'compile', 'open', '__import__',
        'getattr', 'setattr', 'delattr', 'hasattr',
        'globals', 'locals', 'vars', 'dir',
        'breakpoint', 'input', 'exit', 'quit',
        'type', 'super', 'object',
        'memoryview', 'bytearray',
        # 防止 chr/ord 构造绕过
        'chr', 'ord',
        # 防止 format 字符串进行运行时属性访问
        'format_map',
        # 防止类型内省
        'isinstance', 'issubclass',
        'id', 'hash', 'repr',
    })

    # 禁止的方法调用名（ast.Attribute 上的 Call）
    _FORBIDDEN_METHODS = frozenset({
        'format', 'format_map',  # 运行时属性解析攻击向量
        '__format__',
    })

    @classmethod
    def _ast_check(cls, code: str) -> Optional[str]:
        """AST 级别安全检查。

        解析代码为 AST，遍历所有节点检查：
        1. 是否包含禁止的节点类型（Import, ClassDef 等）
        2. 是否访问禁止的属性（__class__, __bases__ 等）
        3. 是否调用禁止的函数（exec, eval, getattr 等）

        Returns:
            None 如果安全，否则返回违规描述字符串
        """
        import ast

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return "Syntax error in submitted code"

        for node in ast.walk(tree):
            node_type = type(node).__name__

            # 1. 节点类型白名单检查
            if node_type not in cls._ALLOWED_AST_NODES:
                return f"Forbidden syntax: {node_type}"

            # 2. 属性访问检查
            if isinstance(node, ast.Attribute):
                attr_name = node.attr
                if attr_name in cls._FORBIDDEN_ATTRS:
                    return f"Forbidden attribute: {attr_name}"
                # 任何以双下划线开头+结尾的属性一律禁止（dunder 方法）
                if attr_name.startswith('__') and attr_name.endswith('__'):
                    return f"Forbidden dunder attribute: {attr_name}"

            # 3. 函数调用检查
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in cls._FORBIDDEN_CALLS:
                    return f"Forbidden call: {func.id}"
                if isinstance(func, ast.Attribute):
                    if func.attr in cls._FORBIDDEN_CALLS:
                        return f"Forbidden method call: {func.attr}"
                    if func.attr in cls._FORBIDDEN_METHODS:
                        return f"Forbidden method call: {func.attr}"

            # 4. Name 节点检查（变量名引用）
            if isinstance(node, ast.Name):
                if node.id in cls._FORBIDDEN_CALLS:
                    # 仅当作为表达式直接引用时阻止（如传递 exec 引用）
                    if isinstance(node.ctx, ast.Load):
                        if node.id in {'exec', 'eval', 'compile', '__import__',
                                        'getattr', 'setattr', 'delattr',
                                        'globals', 'locals', 'vars', 'breakpoint'}:
                            return f"Forbidden name reference: {node.id}"

            # 5. 字符串常量中的逃逸检查（防御 eval("__import__('os')") 等）
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value
                for forbidden in cls._FORBIDDEN_ATTRS:
                    if forbidden in s:
                        return f"Forbidden string content: {forbidden}"

        return None

    # 沙箱递归深度限制（防止栈溢出 DoS）
    _SANDBOX_RECURSION_LIMIT = 50

    def _exec_with_timeout(
        self,
        code: str,
        globals_dict: Dict[str, Any],
        locals_dict: Dict[str, Any],
        timeout_seconds: int,
    ) -> None:
        """在当前线程内执行代码并基于 trace 实现软超时。

        安全措施：
        - trace 回调中断纯 Python 无限循环
        - tracer 级别调用深度计数防止栈溢出（线程安全，不修改全局 recursionlimit）
        """
        deadline = time.time() + max(1, int(timeout_seconds))
        max_depth = self._SANDBOX_RECURSION_LIMIT
        call_depth = [0]

        def _timeout_tracer(frame, event, arg):
            if event == "line" and time.time() > deadline:
                raise TimeoutError(f"Custom code execution timeout ({timeout_seconds}s)")
            if event == "call":
                call_depth[0] += 1
                if call_depth[0] > max_depth:
                    raise RecursionError("Sandbox recursion limit exceeded")
            elif event == "return":
                call_depth[0] -= 1
            return _timeout_tracer

        old_trace = sys.gettrace()
        try:
            sys.settrace(_timeout_tracer)
            exec(code, globals_dict, locals_dict)
        finally:
            sys.settrace(old_trace)

    def _execute_custom_code(
        self, task: RealPoUWTask
    ) -> Tuple[Any, float, str]:
        """在受限环境中执行自定义 Python 代码。

        安全措施（多层防御）：
        1. AST 级别白名单检查：仅允许安全语法结构
        2. 禁止 Import / ClassDef / Global / Nonlocal 等危险节点
        3. 禁止访问所有 dunder 属性（阻止 __class__.__bases__ 链式逃逸）
        4. 禁止调用 getattr/eval/exec/chr/ord 等危险函数
        5. 内置函数严格白名单
        6. 执行超时保护

        注意：此模式不提供与 Docker 相同的隔离级别，
        生产环境应使用 DOCKER_TASK 类型。
        """
        code = task.params.get("code", "")
        data = task.params.get("data", {})

        # AST 深度安全检查
        violation = self._ast_check(code)
        if violation:
            return (
                {"error": f"Code security check failed: {violation}"},
                0.0,
                f"blocked:{violation}",
            )

        # 受限的内置函数白名单
        safe_builtins = {
            "print": print,
            "range": range,
            "len": len,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "pow": pow,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "reversed": reversed,
            "True": True,
            "False": False,
            "None": None,
            "__import__": None,  # 禁止 import
        }

        local_vars = {
            "task_data": data,
            "result": None,
        }

        # 自定义代码超时（默认 5 秒，上限 60 秒）
        timeout_seconds = task.params.get("timeout_seconds", 5)
        try:
            timeout_seconds = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = 5
        timeout_seconds = max(1, min(60, timeout_seconds))

        try:
            self._exec_with_timeout(
                code,
                {"__builtins__": safe_builtins},
                local_vars,
                timeout_seconds=timeout_seconds,
            )
            result = local_vars.get("result")
            # 分数基于是否成功产生结果
            score = 1.0 if result is not None else 0.0
            result_str = json.dumps(result, sort_keys=True, default=str)
            # 结果大小限制（10MB）
            if len(result_str) > 10 * 1024 * 1024:
                return {"error": "Result too large"}, 0.0, "result_too_large"
            proof_hash = hashlib.sha256(result_str.encode()).hexdigest()[:16]
            return result, score, f"custom_hash={proof_hash}"

        except TimeoutError:
            return {"error": "Execution timeout"}, 0.0, "exec_failed:TimeoutError"
        except RecursionError:
            return {"error": "Recursion limit exceeded"}, 0.0, "exec_failed:RecursionError"
        except MemoryError:
            return {"error": "Memory limit exceeded"}, 0.0, "exec_failed:MemoryError"
        except Exception:
            # 不泄漏内部异常信息
            return {"error": "Custom code execution failed"}, 0.0, "exec_failed"

    def _execute_docker_task(
        self,
        task: RealPoUWTask,
        miner_id: str,
    ) -> Tuple[Any, float, str]:
        """通过 SandboxExecutor 在 Docker 容器中执行任务。

        需要在构造 PoUWExecutor 时传入 sandbox 参数。
        如果没有 sandbox 或 Docker 不可用，自动降级到 in-process 执行。
        """
        code = task.params.get("code", "")
        data = task.params.get("data", {})
        image = task.params.get("image", "python:3.11.12-slim")
        requirements = task.params.get("requirements", "")
        extra_meta = getattr(task, "_extra_meta", None)

        # 如果有 P2P 直传的数据目录，将其设为输入引用路径
        if extra_meta:
            p2p_dir = extra_meta.get("p2p_data_dir", "")
            if p2p_dir and os.path.isdir(p2p_dir):
                # 找到 P2P 传入的最大文件作为输入数据
                p2p_files = [os.path.join(p2p_dir, f) for f in os.listdir(p2p_dir)
                             if os.path.isfile(os.path.join(p2p_dir, f))]
                if p2p_files:
                    biggest = max(p2p_files, key=os.path.getsize)
                    extra_meta = dict(extra_meta)
                    extra_meta["input_data_ref_path"] = biggest
                    logger.info(f"使用 P2P 直传数据: {biggest}")

        if not self._sandbox:
            # 无 SandboxExecutor 时拒绝执行 Docker 任务（不安全降级）
            logger.error(f"Docker 任务 {task.task_id} 无法执行：SandboxExecutor 未配置")
            return {"error": "SandboxExecutor not available, cannot execute Docker task"}, 0.0, "no_sandbox"

        try:
            # 计算任务数据哈希
            data_str = json.dumps(data, sort_keys=True, default=str)
            task_data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

            # 如果有重新分配，清理旧的输出文件
            if extra_meta and hasattr(self._sandbox, '_file_manager') and self._sandbox._file_manager:
                self._sandbox._file_manager.clear_task_outputs(task.task_id)

            # 创建沙箱上下文
            ctx = self._sandbox.create_context(
                miner_id=miner_id,
                job_id=task.task_id,
                task_data_hash=task_data_hash,
                task_code=code,
                task_data=data,
                docker_image=image,
                requirements=requirements,
                extra_meta=extra_meta,
            )

            # 执行（simulate_computation=False 触发真实执行）
            sandbox_result = self._sandbox.execute(
                ctx.context_id,
                simulate_computation=False,
            )

            # 清理上下文
            self._sandbox.cleanup_context(ctx.context_id)

            if sandbox_result and sandbox_result.success:
                result = sandbox_result.output_data or {
                    "result_hash": sandbox_result.result_hash,
                }
                score = 1.0
                proof = f"docker_proof={sandbox_result.proof_data}"
            else:
                error_msg = sandbox_result.error_message if sandbox_result else "No result"
                result = {"error": error_msg}
                score = 0.0
                proof = "docker_failed"

            return result, score, proof

        except Exception as e:
            logger.error(f"Docker task {task.task_id} error: {e}")
            return {"error": "Docker task execution failed"}, 0.0, f"docker_error:{type(e).__name__}"

    def _execute_confidential_model(
        self,
        task: RealPoUWTask,
        miner_id: str,
    ) -> Tuple[Any, float, str]:
        """执行 TEE 机密模型任务"""
        from core.secure_model_runtime import SecureModelRuntime
        from core.tee_computing import TEEType

        encrypted_payload = task.params.get("encrypted_payload")
        input_data = task.params.get("input_data", {})

        if not encrypted_payload:
            return {"error": "Missing encrypted payload"}, 0.0, "no_payload"

        try:
            # 初始化 TEE 运行时
            runtime = SecureModelRuntime(node_id=miner_id, tee_type=TEEType.NVIDIA_CC)
            # 接收并解密模型
            success = runtime.receive_and_load_model(encrypted_payload)
            if not success:
                return {"error": "Failed to load/decrypt model in TEE"}, 0.0, "tee_load_error"
            
            # 运行推理
            result_data = runtime.run_inference(input_data)
            
            # 清理飞地环境
            runtime.destroy_session()
            
            # 直接返回满分和 TEE 认证标识作为 proof
            return result_data, 1.0, f"tee_verified_inference"
        except Exception as e:
            logger.error(f"TEE Model execution failed: {e}")
            return {"error": f"TEE execution failed: {str(e)}"}, 0.0, f"tee_error:{type(e).__name__}"

    # ==================== 结果验证 ====================

    def verify_result(
        self, task: RealPoUWTask, result: RealPoUWResult
    ) -> bool:
        """验证 PoUW 结果。

        Args:
            task: 原始任务
            result: 执行结果

        Returns:
            是否验证通过
        """
        # 基本验证：分数达到阈值
        effective_threshold = max(task.expected_threshold, self.min_score_threshold)
        if result.score < effective_threshold:
            return False

        # 针对特定任务类型的额外验证
        structured_payload = None
        if isinstance(result.computation_proof, str) and result.computation_proof.startswith("proof_json="):
            try:
                structured_payload = json.loads(result.computation_proof[len("proof_json="):])
            except Exception:
                return False

            required = {
                "task_id", "task_type", "input_digest", "challenge", "challenge_commitment",
                "challenge_reveal", "trace_digest", "output_digest", "timestamp_ms", "proof_hash"
            }
            if not required.issubset(set(structured_payload.keys())):
                return False
            if structured_payload.get("task_id") != task.task_id:
                return False

            # 最小可验证子集：校验 challenge 承诺关系。
            reveal = structured_payload.get("challenge_reveal", "")
            challenge = structured_payload.get("challenge", "")
            commitment = structured_payload.get("challenge_commitment", "")
            if challenge and reveal and commitment:
                expected_commitment = hashlib.sha256(f"{challenge}:{reveal}".encode()).hexdigest()
                if expected_commitment != commitment:
                    return False

            payload_copy = dict(structured_payload)
            proof_hash = payload_copy.pop("proof_hash", "")
            if self._digest_obj(payload_copy) != proof_hash:
                return False

        if task.task_type == RealTaskType.HASH_SEARCH:
            if isinstance(result.result, dict) and result.result.get("hash"):
                prefix = task.params["prefix"]
                return result.result["hash"].startswith(prefix)
            return False

        if task.task_type == RealTaskType.LINEAR_REGRESSION:
            # 验证回归参数的合理性
            if isinstance(result.result, dict):
                w = result.result.get("w", 0)
                r2 = result.result.get("r2", 0)
                # w 应接近 2.5（真实参数），R^2 应较高
                if abs(w) > 100:  # 不合理的权重
                    return False
                if r2 < 0:  # 负 R^2 说明模型很差
                    return False

        if task.task_type == RealTaskType.GRADIENT_DESCENT:
            # 验证最终参数接近目标
            if isinstance(result.result, dict):
                dist = result.result.get("distance", float("inf"))
                if dist > len(task.params.get("target", [])):
                    return False

        if task.task_type == RealTaskType.CUSTOM_CODE:
            # 自定义代码：检查是否有错误输出
            if isinstance(result.result, dict) and "error" in result.result:
                return False

        if task.task_type == RealTaskType.DOCKER_TASK:
            # Docker 任务：检查执行是否成功
            if isinstance(result.result, dict) and "error" in result.result:
                return False

        if task.task_type == RealTaskType.CONFIDENTIAL_MODEL:
            # TEE 模型：检查是否有错
            if isinstance(result.result, dict) and "error" in result.result:
                return False
            # 可以通过验证 proof 中是否含有 tee 标志进一步确认
            if "tee_verified_inference" not in result.computation_proof:
                return False

        return result.verified

    def __repr__(self) -> str:
        sandbox_mode = "with_sandbox" if self._sandbox else "standalone"
        return (
            f"PoUWExecutor(threshold={self.min_score_threshold}, "
            f"mode={sandbox_mode})"
        )
