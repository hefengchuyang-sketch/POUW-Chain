"""
sandbox_executor.py - 沙箱执行环境（真实 Docker 容器版）

基于 Docker 容器的真实隔离执行环境：
- 真实容器隔离（Docker）
- 资源限制（CPU/内存/GPU）
- 网络隔离（--network none）
- 文件系统只读（--read-only）
- 执行超时控制
- 执行证明生成
- Docker 不可用时自动降级到模拟模式

安全特性：
- 任务在 Docker 容器中隔离运行
- --cap-drop ALL 移除所有 Linux 能力
- --security-opt no-new-privileges 禁止提权
- --pids-limit 防止 fork 炸弹
- 资源硬限制通过 cgroup 实现
"""

import subprocess
import json
import os
import re
import tempfile
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from enum import Enum
import uuid
import time
import hashlib
import logging
import sys

logger = logging.getLogger(__name__)


# ==================== 代码安全扫描器 ====================

class CodeScanner:
    """用户代码静态安全扫描器。

    在代码进入 Docker 容器之前，执行多层静态分析：
    1. 二进制文件检测（ELF/PE/Mach-O 伪装）
    2. 代码大小限制
    3. 危险函数/模块调用检测
    4. 代码混淆/注入模式检测
    5. 恶意模式匹配（fork 炸弹、反向 shell 等）
    """

    MAX_CODE_SIZE = 50 * 1024 * 1024  # 50 MB 代码大小上限
    MAX_LINE_COUNT = 200000            # 最大行数

    # 二进制文件魔术字节
    BINARY_SIGNATURES = [
        b'\x7fELF',          # Linux ELF
        b'MZ',               # Windows PE/EXE
        b'\xfe\xed\xfa',    # Mach-O (macOS)
        b'\xca\xfe\xba\xbe',  # Java class / Mach-O fat
        b'PK\x03\x04',       # ZIP (可能是伪装 jar/apk)
    ]

    # 危险模块 —— 禁止 import
    BLOCKED_MODULES = {
        'os', 'sys', 'subprocess', 'shutil', 'signal',
        'socket', 'http', 'urllib', 'ftplib', 'smtplib', 'telnetlib',
        'ctypes', 'cffi', 'multiprocessing', 'threading',
        'importlib', 'pkgutil', 'zipimport',
        'code', 'codeop', 'compile', 'compileall',
        'pickle', 'shelve', 'marshal',
        'tempfile', 'glob', 'pathlib', 'fileinput',
        'webbrowser', 'antigravity',
        'pty', 'termios', 'tty', 'resource',
        'gc', 'inspect', 'dis', 'ast',
        'builtins', '__builtin__',
    }

    # 危险代码模式（正则）
    DANGEROUS_PATTERNS = [
        # 系统调用
        (r'os\.system\s*\(', '检测到 os.system() 调用'),
        (r'os\.popen\s*\(', '检测到 os.popen() 调用'),
        (r'os\.exec[vlpe]*\s*\(', '检测到 os.exec*() 调用'),
        (r'os\.spawn[vlpe]*\s*\(', '检测到 os.spawn*() 调用'),
        (r'os\.fork\s*\(', '检测到 os.fork() 调用'),
        (r'subprocess\.', '检测到 subprocess 模块调用'),
        (r'shutil\.rmtree', '检测到 shutil.rmtree() 文件删除'),
        # 网络
        (r'socket\.socket\s*\(', '检测到 socket 创建'),
        (r'http\.server', '检测到 HTTP 服务器'),
        (r'reverse.{0,20}shell', '检测到疑似反向 Shell 模式'),
        # 代码注入
        (r'exec\s*\(\s*compile', '检测到 exec(compile(...)) 注入'),
        (r'eval\s*\(\s*compile', '检测到 eval(compile(...)) 注入'),
        (r"__import__\s*\(", '检测到动态 __import__() 调用'),
        (r'getattr.*__', '检测到通过 getattr 访问 dunder 属性'),
        # 沙箱逃逸：class hierarchy 攻击
        (r'\.__subclasses__', '检测到 __subclasses__ 类层级遍历'),
        (r'\.__globals__', '检测到 __globals__ 全局变量访问'),
        (r'\.__code__', '检测到 __code__ 字节码访问'),
        (r'\.__builtins__', '检测到 __builtins__ 访问'),
        (r'\.__bases__', '检测到 __bases__ 类继承链访问'),
        (r'\.__mro__', '检测到 __mro__ 方法解析顺序访问'),
        # 沙箱逃逸：字符串拼接构造 dunder 属性名
        (r'["\']__["\']\s*\+', '检测到字符串拼接构造 dunder 属性'),
        (r'\+\s*["\']__["\']', '检测到字符串拼接构造 dunder 属性'),
        (r'chr\s*\(.*95.*95', '检测到 chr() 构造下划线字符'),
        (r'\bvars\s*\(\s*\)', '检测到 vars() 内省调用'),
        # 编码混淆
        (r'base64\.b64decode\s*\(.*exec', '检测到 base64 解码执行'),
        (r'codecs\.decode.*exec', '检测到编码混淆执行'),
        (r'\\x[0-9a-fA-F]{2}.*\\x[0-9a-fA-F]{2}.*exec', '检测到十六进制混淆执行'),
        # fork 炸弹
        (r'while\s+(True|1)\s*:.*fork', '检测到疑似 fork 炸弹'),
        (r':\(\)\s*\{\s*:\|:', '检测到 Shell fork 炸弹'),
        # 文件系统攻击
        (r'open\s*\(\s*[\'"]/(?:etc|proc|sys|dev)', '检测到访问系统敏感路径'),
        (r'open\s*\(\s*[\'"]\.\.\/\.\.\/\.\.', '检测到路径穿越攻击'),
        # ctypes / FFI
        (r'ctypes\.', '检测到 ctypes FFI 调用'),
        (r'cffi\.', '检测到 CFFI 调用'),
        (r'CDLL\s*\(', '检测到动态链接库加载'),
    ]

    @classmethod
    def scan(cls, code: str) -> Tuple[bool, List[str]]:
        """扫描用户代码安全性。

        Returns:
            (is_safe: bool, warnings: list[str])
            如果 is_safe=False，代码必须被拒绝。
        """
        warnings = []

        # 1. 空代码检查
        if not code or not code.strip():
            return (True, [])  # 空代码是安全的

        # 2. 二进制文件检测
        code_bytes = code.encode('utf-8', errors='replace')
        for sig in cls.BINARY_SIGNATURES:
            if code_bytes[:len(sig)] == sig:
                return (False, ['拒绝：检测到二进制文件（非 Python 源代码）'])

        # 3. 大小检查
        if len(code_bytes) > cls.MAX_CODE_SIZE:
            return (False, [f'拒绝：代码超过 {cls.MAX_CODE_SIZE // 1024 // 1024}MB 大小限制'])

        lines = code.splitlines()
        if len(lines) > cls.MAX_LINE_COUNT:
            return (False, [f'拒绝：代码超过 {cls.MAX_LINE_COUNT} 行限制'])

        # 4. 非 UTF-8 可打印字符比例检测（高比例 = 可能是混淆或二进制伪装）
        non_printable = sum(1 for c in code if not c.isprintable() and c not in '\n\r\t')
        if len(code) > 100 and non_printable / len(code) > 0.1:
            return (False, ['拒绝：代码包含过多不可打印字符，疑似二进制伪装'])

        # 5. 危险 import 检测
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # 匹配 import xxx 和 from xxx import
            import_match = re.match(r'^(?:from\s+|import\s+)([a-zA-Z_][a-zA-Z0-9_.]*)', stripped)
            if import_match:
                mod_root = import_match.group(1).split('.')[0]
                if mod_root in cls.BLOCKED_MODULES:
                    warnings.append(f'拒绝：禁止导入危险模块 "{mod_root}"')

        # 6. 危险代码模式检测
        for pattern, desc in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                warnings.append(f'拒绝：{desc}')

        is_safe = len(warnings) == 0
        return (is_safe, warnings)


# ==================== 容器内任务执行脚本模板 ====================
# 此脚本在 Docker 容器内部运行，用于：
# 1. 读取宿主机挂载的任务数据和用户代码
# 2. 在容器隔离环境中执行用户代码
# 3. 输出结果哈希和执行证明到输出卷
#
# 安全警告：TASK_RUNNER_TEMPLATE 使用 r''' 原始字符串，
# 写入容器时通过 f.write(TASK_RUNNER_TEMPLATE) 直接输出，
# 不要在此模板中使用 f-string 或 .format() 插入外部变量——
# 所有运行时参数（代码、超时等）通过 task_config.json 传入。
#
TASK_RUNNER_TEMPLATE = r'''#!/usr/bin/env python3
"""POUW Sandbox Task Runner - runs inside Docker container."""
import json
import hashlib
import time
import os
import sys
import traceback

# ===== 安全 import 机制 =====
# 白名单模块：只允许导入这些模块（及其子模块）
_ALLOWED_MODULES = {
    # 内置安全模块
    "json", "math", "random", "re", "string", "collections",
    "itertools", "functools", "operator", "copy", "decimal", "fractions",
    "statistics", "datetime", "time", "enum", "dataclasses", "typing",
    "abc", "io", "struct", "base64", "hashlib", "hmac",
    "csv", "textwrap", "difflib", "pprint", "numbers",
    "bisect", "heapq", "array", "queue",
    # 科学计算
    "numpy", "np", "pandas", "pd", "scipy",
    "sklearn", "scikit_learn",
    # 深度学习
    "torch", "torchvision", "torchaudio",
    "tensorflow", "tf", "keras",
    "transformers", "datasets", "tokenizers",
    "accelerate", "safetensors", "einops", "timm",
    # 可视化
    "matplotlib", "seaborn", "plotly",
    # 图像处理
    "PIL", "pillow", "cv2",
    # 数据格式
    "h5py", "zarr", "pyarrow", "polars",
    "yaml", "toml", "msgpack", "jsonlines",
    # ML 工具
    "xgboost", "lightgbm", "catboost",
    "onnx", "onnxruntime",
    # 实用
    "tqdm", "pydantic",
}

# 绝对禁止的模块
_BLOCKED_MODULES = {
    "os", "sys", "subprocess", "shutil", "signal",
    "socket", "http", "urllib", "ftplib", "smtplib", "telnetlib",
    "ctypes", "cffi", "multiprocessing", "threading",
    "importlib", "pkgutil", "zipimport",
    "code", "codeop", "compile", "compileall",
    "pickle", "shelve", "marshal",
    "tempfile", "glob", "pathlib", "fileinput",
    "webbrowser", "antigravity",
    "pty", "termios", "tty", "resource",
    "gc", "inspect", "dis", "ast",
    "builtins", "__builtin__",
}

_real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """安全 import 过滤器：只允许白名单中的模块。"""
    root_module = name.split('.')[0]
    # 显式禁止危险模块
    if root_module in _BLOCKED_MODULES:
        raise ImportError(
            f"Module '{root_module}' is blocked in POUW sandbox for security reasons"
        )
    # 检查白名单
    if root_module not in _ALLOWED_MODULES:
        raise ImportError(
            f"Module '{root_module}' is not in the allowed module list. "
            f"Contact platform admin to request adding it."
        )
    return _real_import(name, globals, locals, fromlist, level)

# 禁止访问的 dunder 属性（防止 class hierarchy 沙箱逃逸）
_BLOCKED_ATTRS = frozenset({
    '__subclasses__', '__bases__', '__mro__', '__class__',
    '__globals__', '__code__', '__closure__', '__func__',
    '__self__', '__module__', '__dict__', '__builtins__',
    '__loader__', '__spec__', '__qualname__',
    '__reduce__', '__reduce_ex__', '__getstate__',
    '__init_subclass__', '__set_name__',
    '__del__', '__delattr__', '__setattr__',
})

_real_getattr = getattr

def _safe_getattr(obj, name, *default):
    """安全 getattr：阻止访问可用于沙箱逃逸的 dunder 属性。"""
    if isinstance(name, str) and name in _BLOCKED_ATTRS:
        raise AttributeError(f"Access to '{name}' is blocked in POUW sandbox")
    return _real_getattr(obj, name, *default) if default else _real_getattr(obj, name)

def _safe_type(*args):
    """安全 type：仅允许单参数（查询类型），禁止三参数（动态创建类）。"""
    if len(args) == 1:
        return type(args[0])
    raise TypeError("Dynamic class creation via type() is blocked in POUW sandbox")


def main():
    start_time = time.time()
    output = {
        "success": False,
        "result": None,
        "result_hash": "",
        "proof": "",
        "execution_time_ms": 0,
        "error": "",
    }

    try:
        # 1. Read task input data
        task_data = {}
        data_path = "/workspace/input/task_data.json"
        if os.path.exists(data_path):
            with open(data_path, "r") as f:
                task_data = json.load(f)

        # 2. Read task metadata
        meta = {}
        meta_path = "/workspace/input/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)

        # 3. Execute user task code (with filtered import + restricted builtins)
        safe_builtins = {
            "print": print, "range": range, "len": len,
            "int": int, "float": float, "str": str, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
            "pow": pow, "enumerate": enumerate, "zip": zip,
            "map": map, "filter": filter, "sorted": sorted, "reversed": reversed,
            "isinstance": isinstance, "type": _safe_type, "hasattr": hasattr, "getattr": _safe_getattr,
            "repr": repr, "hash": hash, "id": id, "callable": callable,
            "True": True, "False": False, "None": None,
            "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "KeyError": KeyError,
            "IndexError": IndexError, "RuntimeError": RuntimeError,
            "__import__": _safe_import,  # 白名单过滤 import
        }
        local_vars = {"task_data": task_data, "result": None}
        
        # Provide helper functions for saving output files
        # Users can call save_file("model.pt", bytes_data) to save model weights
        _saved_files = []
        
        def _save_output_file(filename, data):
            """Save a file to the output directory.
            
            Args:
                filename: Output filename (e.g., 'model.pt', 'predictions.csv')
                data: bytes or str data to write
            """
            safe_name = os.path.basename(filename)
            if safe_name != filename or '..' in filename:
                raise ValueError("Invalid output filename")
            out_path = os.path.join("/workspace/output", safe_name)
            os.makedirs("/workspace/output", exist_ok=True)
            mode = "wb" if isinstance(data, bytes) else "w"
            with open(out_path, mode) as f:
                f.write(data)
            file_size = os.path.getsize(out_path)
            _saved_files.append({"name": safe_name, "size": file_size})
            return out_path
        
        local_vars["save_file"] = _save_output_file
        local_vars["save_model"] = _save_output_file  # alias
        local_vars["OUTPUT_DIR"] = "/workspace/output"
        
        task_path = "/workspace/input/task.py"
        if os.path.exists(task_path):
            with open(task_path, "r") as f:
                task_code = f.read()
            exec(task_code, {"__builtins__": safe_builtins}, local_vars)
        else:
            local_vars["result"] = {
                "status": "no_task_code",
                "message": "No task.py found in input",
            }

        result = local_vars.get("result")

        # 4. Generate result hash (deterministic)
        result_str = json.dumps(result, sort_keys=True, default=str)
        result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:32]

        # 5. Generate execution proof
        task_hash = meta.get("task_data_hash", "unknown")
        proof_input = "{}:{}:{}".format(result_hash, task_hash, time.time())
        proof = hashlib.sha256(proof_input.encode()).hexdigest()[:24]

        elapsed_ms = (time.time() - start_time) * 1000

        output["success"] = True
        output["result"] = result
        output["result_hash"] = result_hash
        output["proof"] = proof
        output["execution_time_ms"] = elapsed_ms

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        output["error"] = "task_execution_failed"
        output["execution_time_ms"] = elapsed_ms
        traceback.print_exc()

    # Write result to output volume
    # result.json contains ONLY metadata (small), large outputs saved as separate files
    MAX_RESULT_JSON_BYTES = 50 * 1024 * 1024  # 50 MB for result.json metadata
    os.makedirs("/workspace/output", exist_ok=True)
    
    # Catalog all output files (user may have saved model weights via save_file())
    output_files = []
    total_output_size = 0
    output_dir = "/workspace/output"
    for entry_name in os.listdir(output_dir):
        entry_path = os.path.join(output_dir, entry_name)
        if os.path.isfile(entry_path) and entry_name != "result.json":
            fsize = os.path.getsize(entry_path)
            total_output_size += fsize
            file_hash = hashlib.sha256()
            with open(entry_path, "rb") as fh:
                while True:
                    blk = fh.read(65536)
                    if not blk:
                        break
                    file_hash.update(blk)
            output_files.append({
                "name": entry_name,
                "size": fsize,
                "sha256": file_hash.hexdigest()[:32],
            })
    
    output["output_files"] = output_files
    output["total_output_size"] = total_output_size
    
    # Write result.json (metadata + small result)
    result_json = json.dumps(output, default=str)
    if len(result_json) > MAX_RESULT_JSON_BYTES:
        # 保存完整结果到独立文件（可通过分块下载获取）
        full_result_path = "/workspace/output/result_full.json"
        with open(full_result_path, "w") as ff:
            ff.write(result_json)
        # result.json 中只保留文件清单和截断标记
        output["result"] = {"_truncated": True, "message": "Result too large, saved to result_full.json"}
        result_json = json.dumps(output, default=str)
    with open("/workspace/output/result.json", "w") as f:
        f.write(result_json)

    # Summary to stdout
    print(json.dumps({
        "success": output["success"],
        "hash": output.get("result_hash", ""),
    }))


if __name__ == "__main__":
    main()
'''


# ==================== 进程内模式安全函数（模块级） ====================

_MODULE_BLOCKED_ATTRS = frozenset({
    '__subclasses__', '__bases__', '__mro__', '__class__',
    '__globals__', '__code__', '__closure__', '__func__',
    '__self__', '__module__', '__dict__', '__builtins__',
    '__loader__', '__spec__', '__qualname__',
    '__reduce__', '__reduce_ex__', '__getstate__',
    '__init_subclass__', '__set_name__',
    '__del__', '__delattr__', '__setattr__',
})

def _module_safe_getattr(obj, name, *default):
    """进程内模式安全 getattr。"""
    if isinstance(name, str) and name in _MODULE_BLOCKED_ATTRS:
        raise AttributeError(f"Access to '{name}' is blocked in POUW sandbox")
    return getattr(obj, name, *default) if default else getattr(obj, name)

def _module_safe_type(*args):
    """进程内模式安全 type。"""
    if len(args) == 1:
        return type(args[0])
    raise TypeError("Dynamic class creation via type() is blocked in POUW sandbox")


# ==================== 数据类型定义 ====================

class ExecutionEnvironment(Enum):
    """执行环境类型。"""
    CONTAINER = "container"         # Docker 容器隔离
    VM = "vm"                       # 虚拟机（预留）
    TEE = "tee"                     # 可信执行环境（预留）
    FHE = "fhe"                     # 全同态加密（预留）
    ZK = "zk"                       # 零知识证明（预留）


class SandboxStatus(Enum):
    """沙箱状态。"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SandboxConfig:
    """沙箱配置。"""
    environment: ExecutionEnvironment = ExecutionEnvironment.CONTAINER
    max_cpu_percent: float = 80.0       # 最大 CPU 利用率
    max_memory_gb: float = 8.0          # 最大内存 (GB)
    max_gpu_percent: float = 90.0       # 最大 GPU 利用率
    timeout_seconds: float = 300.0      # 超时时间 (秒)
    enable_network: bool = False        # 是否允许网络访问
    enable_filesystem: bool = False     # 是否允许文件系统写入


@dataclass
class ExecutionContext:
    """执行上下文。"""
    context_id: str
    miner_id: str
    job_id: str
    task_data_hash: str                 # 任务数据哈希（非明文）
    config: SandboxConfig
    status: SandboxStatus = SandboxStatus.IDLE
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result_hash: Optional[str] = None
    proof_data: Optional[str] = None    # 执行证明
    resource_usage: Dict[str, float] = field(default_factory=dict)
    # --- 扩展字段（可选，向后兼容）---
    task_code: Optional[str] = None             # 任务 Python 代码
    task_data: Optional[Dict[str, Any]] = None  # 任务输入数据（JSON）
    requirements: Optional[str] = None          # requirements.txt 内容
    docker_image: Optional[str] = None          # Docker 镜像名
    built_image: Optional[str] = None           # 依赖预装后的镜像名
    container_id: Optional[str] = None          # Docker 容器 ID
    work_dir: Optional[str] = None              # 宿主机临时工作目录
    extra_meta: Optional[Dict[str, Any]] = None # 大文件引用、资源配置等扩展元数据


@dataclass
class SandboxResult:
    """沙箱执行结果。"""
    context_id: str
    miner_id: str
    job_id: str
    success: bool
    result_hash: str                    # 结果哈希
    proof_data: str                     # 执行证明
    execution_time_ms: float
    resource_usage: Dict[str, float]
    environment: ExecutionEnvironment
    error_message: str = ""
    output_data: Optional[Any] = None   # 实际输出数据（可选）


# ==================================================================
#                     Docker 容器管理器
# ==================================================================

class DockerManager:
    """Docker 容器生命周期管理。

    负责：
    - 检测 Docker 守护进程
    - 镜像安全验证与拉取
    - 构建安全加固的 docker run 命令
    - 运行和终止容器
    - 收集容器资源使用统计
    """

    DEFAULT_IMAGE = "python:3.11-slim"

    # 预批准的安全镜像白名单
    APPROVED_IMAGES = {
        "python:3.11-slim",
        "python:3.10-slim",
        "python:3.11-alpine",
        "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        "pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime",
        "tensorflow/tensorflow:2.15.0",
        "tensorflow/tensorflow:2.14.0-gpu",
        "nvidia/cuda:12.1.0-runtime-ubuntu22.04",
        "continuumio/miniconda3:latest",
        "ubuntu:22.04",
    }

    def __init__(self):
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """Docker 守护进程是否可用。"""
        if self._available is None:
            self._available = self._check_docker()
        return self._available

    def reset_cache(self):
        """重置可用性缓存（用于重新检测）。"""
        self._available = None

    def _check_docker(self) -> bool:
        """检测 Docker 守护进程是否运行。"""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def is_image_approved(self, image: str) -> bool:
        """检查镜像是否在白名单中。

        支持精确匹配和基础镜像名匹配（忽略 tag 差异）。
        """
        if image in self.APPROVED_IMAGES:
            return True
        # 基础镜像名匹配
        base_image = image.split(":")[0] if ":" in image else image
        for approved in self.APPROVED_IMAGES:
            approved_base = approved.split(":")[0] if ":" in approved else approved
            if base_image == approved_base:
                return True
        return False

    def add_approved_image(self, image: str):
        """动态添加批准镜像（运行时扩展白名单）。"""
        self.APPROVED_IMAGES.add(image)

    def pull_image(self, image: str) -> bool:
        """拉取 Docker 镜像。"""
        try:
            logger.info(f"Pulling Docker image: {image}")
            result = subprocess.run(
                ["docker", "pull", image],
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error(f"Failed to pull image {image}: {e}")
            return False

    def image_exists(self, image: str) -> bool:
        """检查镜像是否已在本地存在。"""
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def build_run_command(
        self,
        image: str,
        config: SandboxConfig,
        work_dir: str,
        container_name: str,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """构建安全加固的 docker run 命令。

        安全措施清单：
        - --network none: 禁止网络访问
        - --read-only: 只读根文件系统
        - --cap-drop ALL: 移除所有 Linux Capabilities
        - --security-opt no-new-privileges: 禁止提权
        - --pids-limit: 限制进程数（防 fork 炸弹）
        - --memory/--memory-swap: 内存硬限制（cgroup）
        - --cpu-quota: CPU 使用限制
        - --ipc private: 禁用共享内存
        """
        cmd = ["docker", "run"]

        # 容器名称（便于管理和清理）
        cmd.extend(["--name", container_name])

        # 运行完毕自动删除
        cmd.append("--rm")

        # ========== 安全隔离 ==========

        # 网络隔离
        if not config.enable_network:
            cmd.extend(["--network", "none"])

        # 只读文件系统
        if not config.enable_filesystem:
            cmd.append("--read-only")
            # 允许 /tmp 写入（任务可能需要临时文件）
            tmp_size_mb = 256
            if extra_meta and "tmp_size_mb" in extra_meta:
                tmp_size_mb = max(256, min(10240, int(extra_meta["tmp_size_mb"])))
            cmd.extend(["--tmpfs", f"/tmp:rw,noexec,nosuid,size={tmp_size_mb}m"])

        # 安全加固
        cmd.extend(["--cap-drop", "ALL"])
        cmd.extend(["--security-opt", "no-new-privileges"])
        cmd.extend(["--ipc", "private"])
        cmd.extend(["--pids-limit", "128"])

        # ========== 资源限制 ==========

        # CPU 限制（百分比 -> cgroup quota, 100000 us period）
        cpu_quota = int(config.max_cpu_percent * 1000)
        cmd.extend(["--cpu-quota", str(cpu_quota)])
        cmd.extend(["--cpu-period", "100000"])

        # 内存硬限制
        memory_bytes = int(config.max_memory_gb * 1024 * 1024 * 1024)
        cmd.extend(["--memory", str(memory_bytes)])
        cmd.extend(["--memory-swap", str(memory_bytes)])  # 禁止 swap 超额

        # GPU 支持（需要 nvidia-container-toolkit）
        if config.max_gpu_percent > 0:
            try:
                check = subprocess.run(
                    ["docker", "info", "--format", "{{.Runtimes}}"],
                    capture_output=True, text=True, timeout=5,
                )
                if "nvidia" in check.stdout.lower():
                    cmd.extend(["--gpus", "all"])
            except (subprocess.TimeoutExpired, OSError):
                pass  # GPU 不可用，静默跳过

        # ========== 挂载卷 ==========

        input_dir = os.path.join(work_dir, "input")
        output_dir = os.path.join(work_dir, "output")

        # 输入目录只读挂载
        cmd.extend(["-v", f"{input_dir}:/workspace/input:ro"])
        # 输出目录读写挂载
        cmd.extend(["-v", f"{output_dir}:/workspace/output:rw"])

        # 大数据文件引用：单独挂载到 /workspace/input/data/（只读）
        if extra_meta and extra_meta.get("input_data_ref_path"):
            data_file_path = extra_meta["input_data_ref_path"]
            if os.path.isfile(data_file_path):
                data_dir = os.path.join(work_dir, "data_ref")
                os.makedirs(data_dir, exist_ok=True)
                link_path = os.path.join(data_dir, os.path.basename(data_file_path))
                # 优先 symlink → 硬链接 → 小文件复制
                linked = False
                for link_fn in (os.symlink, os.link):
                    try:
                        link_fn(data_file_path, link_path)
                        linked = True
                        break
                    except OSError:
                        continue
                if not linked:
                    file_size = os.path.getsize(data_file_path)
                    if file_size > 4 * 1024 * 1024 * 1024:  # >4GB 不复制
                        logger.warning(f"Cannot link {data_file_path} ({file_size} bytes), skipping mount")
                    else:
                        shutil.copy2(data_file_path, link_path)
                        linked = True
                if linked:
                    cmd.extend(["-v", f"{data_dir}:/workspace/input/data:ro"])

        # 工作目录
        cmd.extend(["-w", "/workspace"])

        # ========== 镜像和入口命令 ==========
        cmd.append(image)
        cmd.extend(["python", "/workspace/input/task_runner.py"])

        return cmd

    def run_container(
        self,
        cmd: List[str],
        timeout: float,
    ) -> Dict[str, Any]:
        """运行容器并同步等待完成。

        Args:
            cmd: docker run 命令列表
            timeout: 超时秒数

        Returns:
            dict: {returncode, stdout, stderr, timeout}
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:10000],    # 限制输出大小
                "stderr": result.stderr[:5000],
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Container execution timeout",
                "timeout": True,
            }
        except OSError as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Container execution failed",
                "timeout": False,
            }

    def kill_container(self, container_name: str):
        """强制终止并删除容器。"""
        try:
            subprocess.run(
                ["docker", "kill", container_name],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass
        # 确保容器被删除（以防 --rm 未生效）
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    # ==================== 依赖预构建 ====================

    # 允许在构建阶段安装的包白名单前缀（防止恶意包）
    ALLOWED_PKG_PREFIXES = {
        "numpy", "pandas", "scipy", "scikit-learn", "sklearn",
        "torch", "torchvision", "torchaudio", "tensorflow",
        "keras", "transformers", "datasets", "tokenizers",
        "matplotlib", "seaborn", "plotly", "pillow", "opencv-python",
        "requests", "httpx", "aiohttp", "flask", "fastapi",
        "pydantic", "cryptography", "hashlib", "tqdm",
        "jsonlines", "pyyaml", "toml", "msgpack",
        "h5py", "zarr", "lmdb", "pyarrow", "polars",
        "onnx", "onnxruntime", "tensorrt",
        "xgboost", "lightgbm", "catboost",
        "huggingface-hub", "safetensors", "accelerate",
        "einops", "timm", "albumentations",
        "boto3", "google-cloud-storage", "minio",
    }

    def validate_requirements(self, requirements_txt: str) -> tuple:
        """验证 requirements.txt 内容安全性（严格白名单）。

        Returns:
            (is_valid: bool, sanitized_lines: list[str], rejected: list[str])
        """
        import re
        sanitized = []
        rejected = []
        for raw_line in requirements_txt.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            # 禁止 -r / --requirement / -f / --find-links / -i / --index-url 等选项
            if line.startswith("-"):
                rejected.append(line)
                continue
            # 提取包名（去掉版本号）
            pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("!=")[0].split("~=")[0].split("[")[0].strip().lower()
            # 格式校验
            if not re.match(r'^[a-z0-9][a-z0-9._-]*$', pkg_name):
                rejected.append(line)
                continue
            # 严格白名单匹配：包名必须在 ALLOWED_PKG_PREFIXES 中
            if pkg_name not in self.ALLOWED_PKG_PREFIXES:
                rejected.append(f"{line}  # not in whitelist")
                continue
            sanitized.append(line)
        return (len(rejected) == 0, sanitized, rejected)

    def build_deps_image(
        self,
        base_image: str,
        requirements_lines: List[str],
        tag_suffix: str,
    ) -> Optional[str]:
        """构建包含 Python 依赖的 Docker 镜像（有网络的构建阶段）。

        流程：
        1. 创建临时目录，写入 Dockerfile + requirements.txt
        2. docker build（此阶段有网络，可 pip install）
        3. 返回新镜像名（或 None 表示失败）
        4. 清理临时目录

        安全措施：
        - requirements.txt 已经过白名单严格过滤
        - --only-binary :all: 禁止执行 setup.py（仅安装预编译 wheel）
        - --no-deps 防止拉入未审核的传递依赖
        - 仅从 PyPI 下载（固定 index-url）
        - 构建超时 10 分钟
        - 构建完成后网络无法再次使用（运行阶段 --network none）
        """
        build_dir = tempfile.mkdtemp(prefix="pouw_deps_build_")
        image_tag = f"pouw-task-deps:{tag_suffix}"

        try:
            # 写入 requirements.txt
            req_path = os.path.join(build_dir, "requirements.txt")
            with open(req_path, "w", encoding="utf-8") as f:
                f.write("\n".join(requirements_lines))

            # 写入安全化 Dockerfile
            # --only-binary :all: → 仅安装预编译 wheel，阻止 setup.py 执行
            # --no-deps → 不安装传递依赖（需用户显式声明）
            # --index-url 固定到官方 PyPI
            dockerfile_content = (
                f"FROM {base_image}\n"
                "COPY requirements.txt /tmp/requirements.txt\n"
                "RUN pip install --no-cache-dir --disable-pip-version-check "
                "--only-binary :all: --no-deps "
                "--index-url https://pypi.org/simple/ "
                "-r /tmp/requirements.txt && rm /tmp/requirements.txt\n"
            )
            df_path = os.path.join(build_dir, "Dockerfile")
            with open(df_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content)

            # docker build
            logger.info(f"Building deps image: {image_tag}")
            result = subprocess.run(
                ["docker", "build", "-t", image_tag, "."],
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
                cwd=build_dir,
            )

            if result.returncode == 0:
                logger.info(f"Deps image built: {image_tag}")
                return image_tag
            else:
                logger.error(
                    f"Failed to build deps image: {result.stderr[:1000]}"
                )
                return None

        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error(f"Deps image build error: {e}")
            return None
        finally:
            try:
                shutil.rmtree(build_dir)
            except OSError:
                pass

    def cleanup_deps_image(self, image_tag: str):
        """清理依赖镜像（任务完成后回收磁盘空间）。"""
        try:
            subprocess.run(
                ["docker", "rmi", image_tag],
                capture_output=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    def get_container_stats(self, container_name: str) -> Dict[str, float]:
        """获取运行中容器的资源使用统计。"""
        try:
            result = subprocess.run(
                [
                    "docker", "stats", container_name,
                    "--no-stream", "--format",
                    "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|")
                cpu_str = parts[0].replace("%", "").strip()
                mem_str = parts[2].replace("%", "").strip() if len(parts) > 2 else "0"
                return {
                    "cpu_percent": float(cpu_str) if cpu_str else 0.0,
                    "memory_percent": float(mem_str) if mem_str else 0.0,
                }
        except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
            pass
        return {"cpu_percent": 0.0, "memory_percent": 0.0}


# ==================================================================
#                      沙箱执行器（主类）
# ==================================================================

class SandboxExecutor:
    """沙箱执行器 -- 基于 Docker 容器的真实隔离执行环境。

    执行模式（自动选择）：
    1. Docker 容器模式（生产）：有 task_code + Docker 可用 + simulate=False
    2. 进程内受限执行（开发）：有 task_code + Docker 不可用 + simulate=False
    3. 模拟模式（兼容）：无 task_code 或 simulate=True

    接口完全向后兼容 -- 现有调用方无需任何修改。
    """

    def __init__(
        self,
        default_config: Optional[SandboxConfig] = None,
        log_fn: Optional[Callable[[str], None]] = None,
        force_simulate: bool = False,
        file_manager=None,
    ):
        """初始化沙箱执行器。

        Args:
            default_config: 默认沙箱配置
            log_fn: 日志输出函数
            force_simulate: 强制使用模拟模式（用于测试）
            file_manager: ChunkedFileManager 实例（用于持久化大文件输出）
        """
        self.default_config = default_config or SandboxConfig()
        self.contexts: Dict[str, ExecutionContext] = {}
        self.results: List[SandboxResult] = []
        self._log_fn = log_fn or (lambda x: None)
        self._docker = DockerManager()
        self._force_simulate = force_simulate
        self._file_manager = file_manager

        # 检测执行模式
        if not force_simulate and self._docker.available:
            self._use_docker = True
            self._log("Docker detected - real container execution enabled")
        else:
            self._use_docker = False
            mode_reason = "forced" if force_simulate else "Docker not available"
            self._log(f"Simulation mode ({mode_reason})")

    @property
    def docker_available(self) -> bool:
        """Docker 容器执行是否可用。"""
        return self._use_docker and not self._force_simulate

    @property
    def docker_manager(self) -> DockerManager:
        """获取 Docker 管理器（用于高级操作如添加镜像白名单）。"""
        return self._docker

    def _log(self, msg: str):
        self._log_fn(f"[SANDBOX] {msg}")

    # ==================== 上下文管理 ====================

    def create_context(
        self,
        miner_id: str,
        job_id: str,
        task_data_hash: str,
        config: Optional[SandboxConfig] = None,
        task_code: Optional[str] = None,
        task_data: Optional[Dict[str, Any]] = None,
        docker_image: Optional[str] = None,
        requirements: Optional[str] = None,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> ExecutionContext:
        """创建执行上下文。

        Args:
            miner_id: 矿工 ID
            job_id: 任务 ID
            task_data_hash: 任务数据哈希
            config: 沙箱配置（可选，使用默认配置）
            task_code: 任务 Python 代码（可选，提供时启用真实执行）
            task_data: 任务输入数据（可选，JSON 可序列化的 dict）
            docker_image: Docker 镜像名（可选，默认 python:3.11-slim）
            requirements: requirements.txt 内容（可选，自动预装依赖）
            extra_meta: 扩展元数据（大文件引用、资源配置等）

        Returns:
            ExecutionContext 实例
        """
        # 验证 Docker 镜像安全性
        image = docker_image or DockerManager.DEFAULT_IMAGE
        if docker_image and not self._docker.is_image_approved(docker_image):
            self._log(
                f"WARNING: Image '{docker_image}' not in approved list, "
                f"falling back to {DockerManager.DEFAULT_IMAGE}"
            )
            image = DockerManager.DEFAULT_IMAGE

        # 用 extra_meta 中的资源配置覆盖默认 SandboxConfig（单次合并，避免互相覆盖）
        effective_config = config or self.default_config
        if extra_meta and ("max_memory_gb" in extra_meta or "timeout_seconds" in extra_meta):
            effective_config = SandboxConfig(
                environment=effective_config.environment,
                max_cpu_percent=effective_config.max_cpu_percent,
                max_memory_gb=extra_meta.get("max_memory_gb", effective_config.max_memory_gb),
                max_gpu_percent=effective_config.max_gpu_percent,
                timeout_seconds=extra_meta.get("timeout_seconds", effective_config.timeout_seconds),
                enable_network=effective_config.enable_network,
                enable_filesystem=effective_config.enable_filesystem,
            )

        # 防御性拷贝，防止调用方后续修改影响已创建的上下文
        meta_copy = dict(extra_meta) if extra_meta else None

        ctx = ExecutionContext(
            context_id=uuid.uuid4().hex[:12],
            miner_id=miner_id,
            job_id=job_id,
            task_data_hash=task_data_hash,
            config=effective_config,
            task_code=task_code,
            task_data=task_data,
            requirements=requirements,
            docker_image=image,
            extra_meta=meta_copy,
        )
        self.contexts[ctx.context_id] = ctx

        mode = "docker" if (self.docker_available and task_code) else "simulation"
        self._log(
            f"Context created: {ctx.context_id} | miner={miner_id} | "
            f"env={ctx.config.environment.value} | mode={mode}"
        )
        return ctx

    # ==================== Docker 真实执行 ====================

    def _prepare_work_dir(self, ctx: ExecutionContext) -> str:
        """准备容器挂载的工作目录。

        目录结构：
            work_dir/
            +-- input/              (只读挂载到容器 /workspace/input)
            |   +-- task_runner.py  (执行框架脚本)
            |   +-- task.py         (用户任务代码)
            |   +-- task_data.json  (任务输入数据)
            |   +-- meta.json       (任务元数据)
            +-- output/             (读写挂载到容器 /workspace/output)
                +-- result.json     (执行结果)
        """
        work_dir = tempfile.mkdtemp(prefix=f"pouw_sandbox_{ctx.context_id}_")
        input_dir = os.path.join(work_dir, "input")
        output_dir = os.path.join(work_dir, "output")
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # 写入任务执行框架
        runner_path = os.path.join(input_dir, "task_runner.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(TASK_RUNNER_TEMPLATE)

        # 写入用户任务代码
        if ctx.task_code:
            task_path = os.path.join(input_dir, "task.py")
            with open(task_path, "w", encoding="utf-8") as f:
                f.write(ctx.task_code)

        # 写入任务输入数据
        data_path = os.path.join(input_dir, "task_data.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(ctx.task_data or {}, f, ensure_ascii=False)

        # 写入任务元数据
        meta_path = os.path.join(input_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "context_id": ctx.context_id,
                "miner_id": ctx.miner_id,
                "job_id": ctx.job_id,
                "task_data_hash": ctx.task_data_hash,
                "environment": ctx.config.environment.value,
            }, f)

        ctx.work_dir = work_dir
        return work_dir

    def _execute_docker(self, ctx: ExecutionContext) -> SandboxResult:
        """在 Docker 容器中执行任务（真实隔离）。

        完整流程：
        1. 准备工作目录（写入代码+数据）
        2. 确保镜像存在（必要时拉取）
        3. 构建安全的 docker run 命令
        4. 运行容器并等待完成
        5. 读取容器输出的 result.json
        6. 构造 SandboxResult
        7. 清理临时文件
        """
        container_name = f"pouw_sandbox_{ctx.context_id}"

        try:
            # 0. 执行前代码安全扫描
            if ctx.task_code:
                is_safe, scan_warnings = CodeScanner.scan(ctx.task_code)
                if not is_safe:
                    msg = "; ".join(scan_warnings)
                    self._log(f"CODE REJECTED by scanner: {msg}")
                    ctx.status = SandboxStatus.FAILED
                    ctx.end_time = time.time()
                    return SandboxResult(
                        context_id=ctx.context_id,
                        miner_id=ctx.miner_id,
                        job_id=ctx.job_id,
                        success=False,
                        result_hash="",
                        proof_data="",
                        execution_time_ms=0,
                        resource_usage={},
                        environment=ctx.config.environment,
                        error_message=f"代码安全扫描未通过: {msg}",
                    )
                if scan_warnings:
                    self._log(f"Code scan warnings: {scan_warnings}")

            # 1. 准备工作目录
            work_dir = self._prepare_work_dir(ctx)
            self._log(f"Work dir prepared: {work_dir}")

            # 2. 确保基础镜像可用
            image = ctx.docker_image or DockerManager.DEFAULT_IMAGE
            if not self._docker.image_exists(image):
                self._log(f"Pulling image: {image}")
                if not self._docker.pull_image(image):
                    raise RuntimeError(f"Failed to pull Docker image: {image}")

            # 2.5 如果有 requirements.txt，构建包含依赖的镜像（有网络）
            if ctx.requirements and ctx.requirements.strip():
                is_valid, sanitized, rejected = self._docker.validate_requirements(ctx.requirements)
                if rejected:
                    self._log(f"Rejected packages: {rejected}")
                if sanitized:
                    self._log(f"Building deps image with {len(sanitized)} packages...")
                    built = self._docker.build_deps_image(
                        base_image=image,
                        requirements_lines=sanitized,
                        tag_suffix=ctx.context_id,
                    )
                    if built:
                        ctx.built_image = built
                        image = built  # 后续断网执行使用预装好依赖的镜像
                        self._log(f"Deps image ready: {built}")
                    else:
                        self._log("WARNING: Deps build failed, running with base image")

            # 3. 构建 docker run 命令（断网执行）
            cmd = self._docker.build_run_command(
                image=image,
                config=ctx.config,
                work_dir=work_dir,
                container_name=container_name,
                extra_meta=ctx.extra_meta,
            )
            self._log(f"Starting container: {container_name}")

            # 4. 运行容器
            ctx.status = SandboxStatus.RUNNING
            ctx.container_id = container_name
            run_result = self._docker.run_container(
                cmd=cmd,
                timeout=ctx.config.timeout_seconds + 30,  # 额外 30 秒启动开销
            )

            # 5. 处理超时
            if run_result["timeout"]:
                ctx.status = SandboxStatus.TIMEOUT
                self._docker.kill_container(container_name)
                raise RuntimeError("Container execution timeout")

            # 6. 读取执行结果
            result_path = os.path.join(work_dir, "output", "result.json")
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as f:
                    task_output = json.load(f)
            else:
                # 容器没有写入结果文件，从 stdout 恢复
                stdout_hash = hashlib.sha256(
                    run_result["stdout"].encode()
                ).hexdigest()[:32]
                proof_src = f"{stdout_hash}:{ctx.task_data_hash}:{time.time()}"
                task_output = {
                    "success": run_result["returncode"] == 0,
                    "result": None,
                    "result_hash": stdout_hash,
                    "proof": hashlib.sha256(proof_src.encode()).hexdigest()[:24],
                    "execution_time_ms": 0,
                    "error": (
                        run_result["stderr"][:500]
                        if run_result["returncode"] != 0
                        else ""
                    ),
                }

            # 7. 持久化输出文件（模型权重等大文件）
            output_dir = os.path.join(work_dir, "output")
            output_files_info = task_output.get("output_files", [])
            if output_files_info and self._file_manager:
                try:
                    saved = self._file_manager.save_task_outputs(
                        task_id=ctx.job_id,
                        output_dir=output_dir,
                    )
                    self._log(f"Saved {saved} output files for task {ctx.job_id}")
                except Exception as save_err:
                    self._log(f"WARNING: Failed to save output files: {save_err}")

            # 8. 构建 SandboxResult
            ctx.status = SandboxStatus.COMPLETED
            ctx.end_time = time.time()
            ctx.result_hash = task_output.get("result_hash", "")
            ctx.proof_data = task_output.get("proof", "")

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=task_output.get("success", False),
                result_hash=task_output.get("result_hash", ""),
                proof_data=task_output.get("proof", ""),
                execution_time_ms=task_output.get("execution_time_ms", 0),
                resource_usage={
                    "cpu_percent": 0.0,
                    "memory_gb": 0.0,
                    "gpu_percent": 0.0,
                },
                environment=ctx.config.environment,
                error_message=task_output.get("error", ""),
                output_data=task_output.get("result"),
            )

            self.results.append(result)
            self._log(
                f"Docker OK: {ctx.context_id} | success={result.success} | "
                f"time={result.execution_time_ms:.0f}ms | "
                f"hash={result.result_hash[:16]}"
            )
            return result

        except Exception as e:
            ctx.status = SandboxStatus.FAILED
            ctx.end_time = time.time()
            self._docker.kill_container(container_name)

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=False,
                result_hash="",
                proof_data="",
                execution_time_ms=0,
                resource_usage=ctx.resource_usage,
                environment=ctx.config.environment,
                error_message="docker_execution_failed",
            )
            self.results.append(result)
            self._log(f"Docker FAIL: {ctx.context_id} | error={e}")
            return result

        finally:
            # 清理临时工作目录
            if ctx.work_dir and os.path.exists(ctx.work_dir):
                try:
                    shutil.rmtree(ctx.work_dir)
                    ctx.work_dir = None
                except OSError as cleanup_err:
                    logger.warning(f"Failed to cleanup work dir: {cleanup_err}")
            # 清理构建的依赖镜像（回收磁盘空间）
            if ctx.built_image:
                self._docker.cleanup_deps_image(ctx.built_image)
                ctx.built_image = None

    # ==================== 进程内受限执行（降级模式）====================

    def _execute_in_process(self, ctx: ExecutionContext) -> SandboxResult:
        """进程内受限执行（Docker 不可用时的降级方案）。

        WARNING: 进程内执行无法提供与 Docker 相同的隔离级别。
        仅用于开发/测试环境，生产环境应使用 Docker 模式。
        """
        self._log("WARNING: In-process execution (no Docker isolation)")
        start_time = time.time()

        try:
            # 受限的内置函数白名单（禁止文件/网络/系统操作）
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
                "frozenset": frozenset,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "pow": pow,
                "divmod": divmod,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "type": _module_safe_type,
                "hasattr": hasattr,
                "getattr": _module_safe_getattr,
                "callable": callable,
                "repr": repr,
                "hash": hash,
                "id": id,
                "True": True,
                "False": False,
                "None": None,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
                "RuntimeError": RuntimeError,
                "StopIteration": StopIteration,
                "ZeroDivisionError": ZeroDivisionError,
                "__import__": None,  # 禁止 import
            }

            local_vars = {
                "task_data": ctx.task_data or {},
                "result": None,
            }

            # 执行用户代码（受限环境 + 超时保护）
            _timeout_sec = int(min(ctx.config.timeout_seconds, 300))  # in-process 最多5分钟
            deadline = time.time() + max(1, _timeout_sec)

            def _timeout_tracer(frame, event, arg):
                if event == "line" and time.time() > deadline:
                    raise TimeoutError(f"In-process execution timeout ({_timeout_sec}s)")
                return _timeout_tracer

            old_trace = sys.gettrace()
            try:
                # 通过 trace 回调在纯 Python 无限循环中中断执行（跨平台）
                sys.settrace(_timeout_tracer)
                exec(ctx.task_code, {"__builtins__": safe_builtins}, local_vars)
            finally:
                sys.settrace(old_trace)

            task_result = local_vars.get("result")
            
            # 结果大小检查（in-process 模式限制 50MB）
            result_str = json.dumps(task_result, sort_keys=True, default=str)
            if len(result_str) > 50 * 1024 * 1024:
                task_result = {"_truncated": True, "message": "In-process result exceeds 50MB"}
                result_str = json.dumps(task_result, sort_keys=True, default=str)
            
            result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:32]

            elapsed_ms = (time.time() - start_time) * 1000
            proof_input = f"{result_hash}:{ctx.task_data_hash}:{time.time()}"
            proof_data = hashlib.sha256(proof_input.encode()).hexdigest()[:24]

            ctx.status = SandboxStatus.COMPLETED
            ctx.end_time = time.time()
            ctx.result_hash = result_hash
            ctx.proof_data = proof_data

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=True,
                result_hash=result_hash,
                proof_data=proof_data,
                execution_time_ms=elapsed_ms,
                resource_usage={"cpu_percent": 0, "memory_gb": 0, "gpu_percent": 0},
                environment=ctx.config.environment,
                output_data=task_result,
            )
            self.results.append(result)
            self._log(f"In-process OK: {ctx.context_id} | time={elapsed_ms:.0f}ms")
            return result

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            ctx.status = SandboxStatus.FAILED
            ctx.end_time = time.time()

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=False,
                result_hash="",
                proof_data="",
                execution_time_ms=elapsed_ms,
                resource_usage={},
                environment=ctx.config.environment,
                error_message="inprocess_execution_failed",
            )
            self.results.append(result)
            self._log(f"In-process FAIL: {ctx.context_id} | error={e}")
            return result

    # ==================== 模拟执行（向后兼容）====================

    def _execute_simulated(self, ctx: ExecutionContext) -> SandboxResult:
        """纯模拟执行（无任务代码时的兼容模式）。

        向后兼容原有调用方式 -- 不需要 task_code，
        生成模拟的资源使用数据和结果哈希。
        """
        import random

        try:
            ctx.status = SandboxStatus.RUNNING

            # 模拟执行时间和资源消耗
            execution_time = random.uniform(50, 500)
            ctx.resource_usage = {
                "cpu_percent": random.uniform(30, ctx.config.max_cpu_percent),
                "memory_gb": random.uniform(1, min(4, ctx.config.max_memory_gb)),
                "gpu_percent": random.uniform(0, ctx.config.max_gpu_percent),
            }

            # 检查模拟的资源限制
            if ctx.resource_usage["cpu_percent"] > ctx.config.max_cpu_percent:
                raise RuntimeError("CPU limit exceeded")
            if ctx.resource_usage["memory_gb"] > ctx.config.max_memory_gb:
                raise RuntimeError("Memory limit exceeded")

            # 检查超时
            if execution_time / 1000 > ctx.config.timeout_seconds:
                ctx.status = SandboxStatus.TIMEOUT
                raise RuntimeError("Execution timeout")

            # 生成结果哈希
            result_data = f"{ctx.task_data_hash}:{ctx.miner_id}:{time.time()}"
            result_hash = hashlib.sha256(result_data.encode()).hexdigest()[:32]

            # 生成执行证明（与 Docker 模式格式一致）
            proof_input = f"{result_hash}:{ctx.task_data_hash}:{time.time()}"
            proof_data = hashlib.sha256(proof_input.encode()).hexdigest()[:24]

            ctx.status = SandboxStatus.COMPLETED
            ctx.end_time = time.time()
            ctx.result_hash = result_hash
            ctx.proof_data = proof_data

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=True,
                result_hash=result_hash,
                proof_data=proof_data,
                execution_time_ms=execution_time,
                resource_usage=ctx.resource_usage,
                environment=ctx.config.environment,
            )
            self.results.append(result)
            self._log(f"Simulated OK: {ctx.context_id} | hash={result_hash[:16]}")
            return result

        except Exception as e:
            ctx.status = SandboxStatus.FAILED
            ctx.end_time = time.time()

            result = SandboxResult(
                context_id=ctx.context_id,
                miner_id=ctx.miner_id,
                job_id=ctx.job_id,
                success=False,
                result_hash="",
                proof_data="",
                execution_time_ms=0,
                resource_usage=ctx.resource_usage,
                environment=ctx.config.environment,
                error_message="simulated_execution_failed",
            )
            self.results.append(result)
            self._log(f"Simulated FAIL: {ctx.context_id} | error={e}")
            return result

    # ==================== 主执行入口 ====================

    def execute(
        self,
        context_id: str,
        simulate_computation: bool = True,
    ) -> Optional[SandboxResult]:
        """在沙箱中执行任务。

        执行模式自动选择：
        - 有 task_code + Docker 可用 + simulate=False -> Docker 容器隔离执行
        - 有 task_code + Docker 不可用 + simulate=False -> 进程内受限执行
        - 无 task_code 或 simulate=True -> 模拟执行（向后兼容）

        Args:
            context_id: 执行上下文 ID
            simulate_computation: 强制模拟模式（默认 True，向后兼容）

        Returns:
            SandboxResult 或 None（上下文不存在时）
        """
        if context_id not in self.contexts:
            self._log(f"Context {context_id} not found")
            return None

        ctx = self.contexts[context_id]
        ctx.status = SandboxStatus.INITIALIZING
        ctx.start_time = time.time()

        self._log(f"Execute: {ctx.context_id} | env={ctx.config.environment.value}")

        # 决定执行模式
        has_code = bool(ctx.task_code)
        # 有真实代码时自动选择真实执行（除非强制模拟）
        want_real = has_code and not simulate_computation
        use_docker = self._use_docker and not self._force_simulate

        if has_code and want_real and use_docker:
            # 模式 1: Docker 容器真实执行（生产推荐）
            return self._execute_docker(ctx)
        elif has_code and want_real:
            # 模式 2: 进程内受限执行（开发降级）
            return self._execute_in_process(ctx)
        else:
            # 模式 3: 纯模拟（无真实代码时的兼容回退）
            self._log(f"WARN: Simulated execution for {ctx.context_id} (no task_code or forced simulate)")
            return self._execute_simulated(ctx)

    # ==================== 证明验证 ====================

    def verify_proof(
        self,
        result_hash: str,
        proof_data: str,
        environment: ExecutionEnvironment,
    ) -> bool:
        """验证执行证明。

        验证规则：
        - 证明必须为 24 字符的十六进制字符串（SHA256 前缀）
        - 结果哈希必须非空

        注：TEE/ZK/FHE 类型的密码学验证由对应硬件/库实现，
        此处仅做格式校验。
        """
        if not proof_data or len(proof_data) < 16:
            return False

        if not result_hash:
            return False

        # 验证证明格式：24 字符十六进制
        if len(proof_data) != 24:
            return False

        try:
            int(proof_data, 16)
        except ValueError:
            return False

        return True

    # ==================== 上下文清理 ====================

    def cleanup_context(self, context_id: str):
        """清理执行上下文及关联的所有资源。

        清理内容：
        - 终止可能仍在运行的 Docker 容器
        - 删除临时工作目录
        - 释放上下文内存
        """
        if context_id in self.contexts:
            ctx = self.contexts[context_id]

            # 终止可能仍在运行的 Docker 容器
            if ctx.container_id:
                self._docker.kill_container(ctx.container_id)

            # 清理临时工作目录
            if ctx.work_dir and os.path.exists(ctx.work_dir):
                try:
                    shutil.rmtree(ctx.work_dir)
                except OSError:
                    pass

            del self.contexts[context_id]
            self._log(f"Cleaned up: {context_id}")

    def get_active_contexts(self) -> List[ExecutionContext]:
        """获取所有活跃的执行上下文。"""
        return [
            ctx for ctx in self.contexts.values()
            if ctx.status in [SandboxStatus.INITIALIZING, SandboxStatus.RUNNING]
        ]

    def __repr__(self) -> str:
        active = len(self.get_active_contexts())
        mode = "docker" if self._use_docker else "simulation"
        return (
            f"SandboxExecutor(mode={mode}, "
            f"contexts={len(self.contexts)}, active={active})"
        )
