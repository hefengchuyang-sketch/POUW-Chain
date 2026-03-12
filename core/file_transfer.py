"""
file_transfer.py - 大文件分块上传/下载管理器

解决的问题：
- 大数据集（ImageNet 150GB、COCO 25GB 等）无法通过单个 JSON-RPC 传输
- 大模型输出（ResNet 200MB、BERT 400MB、LLaMA 数 GB）无法通过 JSON 返回
- Base64 编码膨胀 33%，浏览器内存溢出

架构：
1. 上传：前端分块 → file_initUpload → file_uploadChunk × N → file_finalizeUpload
2. 任务创建时传文件引用 ID 而非嵌入 base64 数据
3. 下载：file_getOutputFiles → file_downloadChunk 分块取回
4. 自动清理过期文件

分块大小：4 MB（适合 JSON-RPC 传输）
"""

import os
import json
import time
import hashlib
import uuid
import shutil
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import base64

logger = logging.getLogger(__name__)

# E2E 加密支持
try:
    from core.e2e_encryption import (
        E2ESessionManager, e2e_encrypt_chunk, e2e_decrypt_chunk, HEADER_SIZE,
    )
    HAS_E2E = True
except ImportError:
    HAS_E2E = False

# ==================== 常量 ====================

CHUNK_SIZE = 4 * 1024 * 1024          # 4 MB 分块大小
MAX_UPLOAD_SIZE = 100 * 1024**3       # 100 GB 单文件上限
MAX_OUTPUT_SIZE = 50 * 1024**3        # 50 GB 输出上限
UPLOAD_EXPIRE_SECONDS = 2 * 3600      # 未完成上传 2 小时过期（防内存泄漏）
COMPLETED_EXPIRE_SECONDS = 7 * 24 * 3600  # 已完成文件 7 天过期


# ==================== 数据结构 ====================

@dataclass
class UploadSession:
    """分块上传会话。"""
    upload_id: str
    filename: str
    total_size: int
    checksum_sha256: str           # 期望的完整文件 SHA256（明文数据的哈希）
    chunk_count: int               # 总分块数
    received_chunks: set = field(default_factory=set)  # 已接收分块索引
    created_at: float = 0.0
    completed: bool = False
    file_ref: str = ""             # 完成后的文件引用 ID
    owner: str = ""                # 上传者 ID
    e2e_session_id: str = ""       # E2E 加密会话 ID（空 = 不加密）

    def to_dict(self) -> dict:
        d = asdict(self)
        d['received_chunks'] = list(self.received_chunks)
        return d


@dataclass
class FileInfo:
    """已上传文件的元数据。"""
    file_ref: str                  # 文件引用 ID（用于任务关联）
    filename: str                  # 原始文件名
    size: int                      # 文件大小（字节）
    checksum_sha256: str           # SHA256 校验
    upload_completed_at: float     # 上传完成时间
    owner: str = ""                # 所有者
    task_id: str = ""              # 关联任务 ID（可选）
    file_type: str = ""            # data / output / model

    def to_dict(self) -> dict:
        return asdict(self)


# ==================== 安全 ====================

# 允许的文件扩展名
ALLOWED_DATA_EXTENSIONS = {
    # 数据格式
    '.csv', '.tsv', '.json', '.jsonl', '.txt', '.xml', '.yaml', '.yml', '.toml',
    # 二进制数据
    '.npy', '.npz', '.h5', '.hdf5', '.parquet', '.arrow', '.feather',
    # ML 模型/权重
    '.pt', '.pth', '.onnx', '.pb', '.tflite', '.safetensors', '.bin', '.ckpt',
    # 压缩包
    '.zip', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.zst',
    # 图像数据集
    '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp',
    # 音频数据集
    '.wav', '.mp3', '.flac', '.ogg',
    # 其他
    '.msgpack', '.lmdb', '.tfrecord', '.idx',  # .pkl 已移除：pickle 反序列化可导致任意代码执行
}

# 禁止的文件名模式（防路径穿越）
BLOCKED_FILENAME_CHARS = {'..', '/', '\\', '\x00'}


def validate_filename(filename: str) -> bool:
    """验证文件名安全性。"""
    if not filename or len(filename) > 255:
        return False
    for blocked in BLOCKED_FILENAME_CHARS:
        if blocked in filename:
            return False
    # 检查扩展名
    ext = os.path.splitext(filename.lower())[1]
    if ext and ext not in ALLOWED_DATA_EXTENSIONS:
        return False
    return True


# ==================== 分块文件管理器 ====================

class ChunkedFileManager:
    """大文件分块上传/下载管理器。

    文件存储结构：
        data/
        ├── uploads/              # 上传中的临时文件
        │   └── {upload_id}/
        │       ├── meta.json     # 上传元数据
        │       └── chunks/       # 分块文件
        │           ├── 000000
        │           ├── 000001
        │           └── ...
        ├── files/                # 已完成的文件
        │   └── {file_ref}/
        │       ├── meta.json     # 文件元数据
        │       └── data          # 实际文件数据
        └── outputs/              # 任务输出文件
            └── {task_id}/
                ├── manifest.json # 输出文件清单
                ├── result.json   # 执行结果元数据
                └── files/        # 输出文件
    """

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.uploads_dir = os.path.join(base_dir, "uploads")
        self.files_dir = os.path.join(base_dir, "files")
        self.outputs_dir = os.path.join(base_dir, "outputs")

        # 创建目录
        for d in [self.uploads_dir, self.files_dir, self.outputs_dir]:
            os.makedirs(d, exist_ok=True)

        # 活跃上传会话（内存索引）
        self._sessions: Dict[str, UploadSession] = {}
        # 文件索引
        self._files: Dict[str, FileInfo] = {}
        self._lock = threading.Lock()

        # 加载已有文件索引
        self._load_file_index()

        # E2E 加密会话管理
        self.e2e_manager = E2ESessionManager() if HAS_E2E else None

        logger.info(f"ChunkedFileManager initialized: {base_dir}, {len(self._files)} files indexed, E2E={'enabled' if HAS_E2E else 'disabled'}")

    # ==================== 上传流程 ====================

    def init_upload(
        self,
        filename: str,
        total_size: int,
        checksum_sha256: str,
        owner: str = "",
    ) -> dict:
        """初始化分块上传。

        Args:
            filename: 文件名
            total_size: 文件总大小（字节）
            checksum_sha256: 文件完整的 SHA256 哈希（小写 hex）
            owner: 上传者 ID

        Returns:
            {upload_id, chunk_size, chunk_count}
        """
        # 验证
        if not validate_filename(filename):
            raise ValueError(f"非法文件名: {filename}")

        if total_size <= 0 or total_size > MAX_UPLOAD_SIZE:
            raise ValueError(
                f"文件大小无效: {total_size} 字节 "
                f"(上限 {MAX_UPLOAD_SIZE // 1024**3}GB)"
            )

        if not checksum_sha256 or len(checksum_sha256) != 64:
            raise ValueError("需要有效的 SHA256 校验和 (64 字符 hex)")

        # 磁盘空间检查：需要至少文件大小 + 1GB 安全余量
        try:
            disk_usage = shutil.disk_usage(self.base_dir)
            required = total_size + 1024**3  # 文件大小 + 1GB 余量
            if disk_usage.free < required:
                free_gb = disk_usage.free / 1024**3
                need_gb = total_size / 1024**3
                raise ValueError(
                    f"磁盘空间不足: 可用 {free_gb:.1f}GB, 需要 {need_gb:.1f}GB + 1GB 余量"
                )
        except OSError:
            pass  # 无法检测时跳过（如网络驱动器）

        # 计算分块数
        chunk_count = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        # 创建会话
        upload_id = uuid.uuid4().hex[:16]
        session = UploadSession(
            upload_id=upload_id,
            filename=filename,
            total_size=total_size,
            checksum_sha256=checksum_sha256.lower(),
            chunk_count=chunk_count,
            created_at=time.time(),
            owner=owner,
        )

        # 创建临时目录
        session_dir = os.path.join(self.uploads_dir, upload_id)
        chunks_dir = os.path.join(session_dir, "chunks")
        os.makedirs(chunks_dir, exist_ok=True)

        # 保存元数据
        meta_path = os.path.join(session_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f)

        with self._lock:
            self._sessions[upload_id] = session

        logger.info(
            f"Upload init: {upload_id} | file={filename} | "
            f"size={total_size / 1024**2:.1f}MB | chunks={chunk_count}"
        )

        return {
            "uploadId": upload_id,
            "chunkSize": CHUNK_SIZE,
            "chunkCount": chunk_count,
        }

    def upload_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        chunk_data_b64: str,
    ) -> dict:
        """上传单个分块。

        Args:
            upload_id: 上传会话 ID
            chunk_index: 分块索引（从 0 开始）
            chunk_data_b64: Base64 编码的分块数据

        Returns:
            {received, total, progress}
        """
        with self._lock:
            session = self._sessions.get(upload_id)
        if not session:
            raise ValueError(f"上传会话不存在: {upload_id}")
        if session.completed:
            raise ValueError(f"上传已完成: {upload_id}")
        if chunk_index < 0 or chunk_index >= session.chunk_count:
            raise ValueError(
                f"分块索引越界: {chunk_index} (总共 {session.chunk_count} 块)"
            )

        # 解码分块数据
        try:
            chunk_bytes = base64.b64decode(chunk_data_b64)
        except Exception:
            raise ValueError("分块数据 Base64 解码失败")

        # 验证分块大小
        expected_size = CHUNK_SIZE
        if chunk_index == session.chunk_count - 1:
            # 最后一块可能较小
            expected_size = session.total_size - chunk_index * CHUNK_SIZE
        if len(chunk_bytes) != expected_size:
            raise ValueError(
                f"分块 {chunk_index} 大小不匹配: "
                f"期望 {expected_size}, 实际 {len(chunk_bytes)}"
            )

        # 写入分块文件
        chunk_path = os.path.join(
            self.uploads_dir, upload_id, "chunks", f"{chunk_index:06d}"
        )
        with open(chunk_path, "wb") as f:
            f.write(chunk_bytes)

        with self._lock:
            session.received_chunks.add(chunk_index)
            received = len(session.received_chunks)

        progress = received / session.chunk_count * 100

        return {
            "received": received,
            "total": session.chunk_count,
            "progress": round(progress, 1),
        }

    def finalize_upload(self, upload_id: str) -> dict:
        """完成上传：合并分块、校验 SHA256、生成文件引用。

        Returns:
            {fileRef, filename, size, checksum}
        """
        with self._lock:
            session = self._sessions.get(upload_id)
        if not session:
            raise ValueError(f"上传会话不存在: {upload_id}")
        if session.completed:
            raise ValueError(f"上传已完成: {upload_id}")

        # 检查所有分块是否已接收
        missing = set(range(session.chunk_count)) - session.received_chunks
        if missing:
            raise ValueError(
                f"缺少 {len(missing)} 个分块: "
                f"{sorted(list(missing))[:10]}..."
            )

        # 创建目标文件目录
        file_ref = uuid.uuid4().hex[:16]
        file_dir = os.path.join(self.files_dir, file_ref)
        os.makedirs(file_dir, exist_ok=True)
        data_path = os.path.join(file_dir, "data")

        # 合并分块 + 计算 SHA256
        sha256 = hashlib.sha256()
        total_written = 0

        with open(data_path, "wb") as outf:
            for i in range(session.chunk_count):
                chunk_path = os.path.join(
                    self.uploads_dir, upload_id, "chunks", f"{i:06d}"
                )
                with open(chunk_path, "rb") as cf:
                    while True:
                        block = cf.read(65536)
                        if not block:
                            break
                        outf.write(block)
                        sha256.update(block)
                        total_written += len(block)

        actual_checksum = sha256.hexdigest()

        # 校验
        if total_written != session.total_size:
            # 清理并报错
            shutil.rmtree(file_dir, ignore_errors=True)
            raise ValueError(
                f"文件大小不匹配: 期望 {session.total_size}, "
                f"实际 {total_written}"
            )

        if actual_checksum != session.checksum_sha256:
            shutil.rmtree(file_dir, ignore_errors=True)
            raise ValueError(
                f"SHA256 校验失败: 期望 {session.checksum_sha256[:16]}..., "
                f"实际 {actual_checksum[:16]}..."
            )

        # 保存文件元数据
        file_info = FileInfo(
            file_ref=file_ref,
            filename=session.filename,
            size=total_written,
            checksum_sha256=actual_checksum,
            upload_completed_at=time.time(),
            owner=session.owner,
            file_type="data",
        )

        meta_path = os.path.join(file_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(file_info.to_dict(), f)

        # 更新索引
        with self._lock:
            self._files[file_ref] = file_info
            session.completed = True
            session.file_ref = file_ref

        # 清理临时分块
        session_dir = os.path.join(self.uploads_dir, upload_id)
        shutil.rmtree(session_dir, ignore_errors=True)

        logger.info(
            f"Upload finalized: {file_ref} | file={session.filename} | "
            f"size={total_written / 1024**2:.1f}MB | sha256={actual_checksum[:16]}..."
        )

        return {
            "fileRef": file_ref,
            "filename": session.filename,
            "size": total_written,
            "checksum": actual_checksum,
        }

    # ==================== 文件读取 ====================

    def get_file_path(self, file_ref: str) -> Optional[str]:
        """获取已上传文件的磁盘路径（供 Docker 挂载）。"""
        data_path = os.path.join(self.files_dir, file_ref, "data")
        if os.path.exists(data_path):
            return data_path
        return None

    def get_file_info(self, file_ref: str) -> Optional[dict]:
        """获取文件元数据。"""
        with self._lock:
            info = self._files.get(file_ref)
        if info:
            return info.to_dict()
        # 尝试从磁盘加载
        meta_path = os.path.join(self.files_dir, file_ref, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def download_chunk(
        self,
        file_ref: str,
        offset: int,
        length: int = CHUNK_SIZE,
    ) -> dict:
        """分块下载文件。

        Args:
            file_ref: 文件引用 ID
            offset: 读取偏移量（字节）
            length: 读取长度（最大 CHUNK_SIZE）

        Returns:
            {data: base64, offset, length, totalSize, hasMore}
        """
        data_path = self.get_file_path(file_ref)
        if not data_path:
            raise ValueError(f"文件不存在: {file_ref}")

        length = min(length, CHUNK_SIZE)
        file_size = os.path.getsize(data_path)

        if offset < 0 or offset >= file_size:
            raise ValueError(f"偏移量越界: {offset} (文件大小 {file_size})")

        actual_length = min(length, file_size - offset)

        with open(data_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(actual_length)

        return {
            "data": base64.b64encode(chunk).decode("ascii"),
            "offset": offset,
            "length": len(chunk),
            "totalSize": file_size,
            "hasMore": (offset + len(chunk)) < file_size,
        }

    # ==================== 任务输出管理 ====================

    def save_task_outputs(
        self,
        task_id: str,
        output_dir: str,
        max_total_size: int = MAX_OUTPUT_SIZE,
    ) -> dict:
        """将任务容器的输出目录保存到持久存储。

        扫描 output_dir 中的所有文件（不仅仅是 result.json），
        支持保存训练好的模型权重等大文件。

        Args:
            task_id: 任务 ID
            output_dir: Docker 容器输出目录
            max_total_size: 输出总大小上限

        Returns:
            {taskId, files: [{name, size, fileRef}], totalSize, resultJson}
        """
        task_output_dir = os.path.join(self.outputs_dir, task_id)
        files_dir = os.path.join(task_output_dir, "files")
        os.makedirs(files_dir, exist_ok=True)

        manifest = {
            "taskId": task_id,
            "files": [],
            "totalSize": 0,
            "savedAt": time.time(),
            "resultJson": None,
        }

        total_size = 0

        # 扫描输出目录中的所有文件
        if not os.path.exists(output_dir):
            return manifest

        for entry in os.scandir(output_dir):
            if not entry.is_file():
                continue

            file_size = entry.stat().st_size
            total_size += file_size

            if total_size > max_total_size:
                logger.warning(
                    f"Task {task_id} output exceeded size limit "
                    f"({total_size / 1024**3:.1f}GB > {max_total_size / 1024**3:.1f}GB)"
                )
                break

            # result.json 特殊处理 - 读取内容
            if entry.name == "result.json":
                try:
                    with open(entry.path, "r", encoding="utf-8") as f:
                        manifest["resultJson"] = json.load(f)
                except Exception:
                    pass

            # 复制文件到持久存储
            dest_path = os.path.join(files_dir, entry.name)
            shutil.copy2(entry.path, dest_path)

            # 计算哈希
            sha256 = hashlib.sha256()
            with open(dest_path, "rb") as f:
                while True:
                    block = f.read(65536)
                    if not block:
                        break
                    sha256.update(block)

            file_ref = f"{task_id}:{entry.name}"
            file_info = {
                "name": entry.name,
                "size": file_size,
                "fileRef": file_ref,
                "checksum": sha256.hexdigest(),
            }
            manifest["files"].append(file_info)

        manifest["totalSize"] = total_size

        # 保存 manifest
        manifest_path = os.path.join(task_output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        logger.info(
            f"Task outputs saved: {task_id} | "
            f"{len(manifest['files'])} files | "
            f"{total_size / 1024**2:.1f}MB total"
        )

        return manifest

    def get_task_output_manifest(self, task_id: str) -> Optional[dict]:
        """获取任务输出文件清单。"""
        manifest_path = os.path.join(
            self.outputs_dir, task_id, "manifest.json"
        )
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def download_task_output_chunk(
        self,
        task_id: str,
        filename: str,
        offset: int,
        length: int = CHUNK_SIZE,
    ) -> dict:
        """分块下载任务输出文件。"""
        # 安全校验：防止路径穿越
        safe_name = os.path.basename(filename)
        if safe_name != filename:
            raise ValueError("文件名包含非法字符")

        file_path = os.path.join(
            self.outputs_dir, task_id, "files", safe_name
        )
        if not os.path.exists(file_path):
            raise ValueError(f"输出文件不存在: {filename}")

        file_size = os.path.getsize(file_path)
        length = min(length, CHUNK_SIZE)

        if offset < 0 or offset >= file_size:
            raise ValueError(f"偏移量越界: {offset}")

        actual_length = min(length, file_size - offset)

        with open(file_path, "rb") as f:
            f.seek(offset)
            chunk = f.read(actual_length)

        return {
            "data": base64.b64encode(chunk).decode("ascii"),
            "offset": offset,
            "length": len(chunk),
            "totalSize": file_size,
            "hasMore": (offset + len(chunk)) < file_size,
        }

    # ==================== 清理 ====================

    def cleanup_expired(self):
        """清理过期的上传会话和文件。"""
        now = time.time()
        cleaned_uploads = 0
        cleaned_files = 0

        # 清理未完成的上传
        with self._lock:
            expired_sessions = [
                sid for sid, s in self._sessions.items()
                if not s.completed and (now - s.created_at) > UPLOAD_EXPIRE_SECONDS
            ]
            for sid in expired_sessions:
                del self._sessions[sid]

        for sid in expired_sessions:
            session_dir = os.path.join(self.uploads_dir, sid)
            shutil.rmtree(session_dir, ignore_errors=True)
            cleaned_uploads += 1

        # 清理过期的已完成文件
        with self._lock:
            expired_files = [
                fid for fid, f in self._files.items()
                if (now - f.upload_completed_at) > COMPLETED_EXPIRE_SECONDS
            ]
            for fid in expired_files:
                del self._files[fid]

        for fid in expired_files:
            file_dir = os.path.join(self.files_dir, fid)
            shutil.rmtree(file_dir, ignore_errors=True)
            cleaned_files += 1

        if cleaned_uploads or cleaned_files:
            logger.info(
                f"Cleanup: {cleaned_uploads} expired uploads, "
                f"{cleaned_files} expired files"
            )

    def _load_file_index(self):
        """从磁盘加载已有的文件索引。"""
        if not os.path.exists(self.files_dir):
            return
        for entry in os.scandir(self.files_dir):
            if not entry.is_dir():
                continue
            meta_path = os.path.join(entry.path, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    file_info = FileInfo(**data)
                    self._files[file_info.file_ref] = file_info
                except Exception as e:
                    logger.warning(f"Failed to load file meta {meta_path}: {e}")

    def get_upload_progress(self, upload_id: str) -> Optional[dict]:
        """查询上传进度。"""
        with self._lock:
            session = self._sessions.get(upload_id)
        if not session:
            return None
        received = len(session.received_chunks)
        return {
            "uploadId": upload_id,
            "filename": session.filename,
            "totalSize": session.total_size,
            "chunkCount": session.chunk_count,
            "receivedChunks": received,
            "progress": round(received / session.chunk_count * 100, 1) if session.chunk_count > 0 else 0,
            "completed": session.completed,
            "fileRef": session.file_ref,
        }

    def cancel_upload(self, upload_id: str) -> bool:
        """取消上传会话并清理临时文件。"""
        with self._lock:
            session = self._sessions.pop(upload_id, None)
        if not session:
            return False
        session_dir = os.path.join(self.uploads_dir, upload_id)
        shutil.rmtree(session_dir, ignore_errors=True)
        logger.info(f"Upload cancelled: {upload_id}")
        return True

    def clear_task_outputs(self, task_id: str) -> bool:
        """清理指定任务的输出文件（任务重新分配时调用）。"""
        output_dir = os.path.join(self.outputs_dir, task_id)
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
            logger.info(f"Cleared outputs for task: {task_id}")
            return True
        return False

    # ==================== E2E 端到端加密 ====================

    def e2e_create_session(self) -> dict:
        """创建 E2E 加密会话，返回会话 ID 和公钥。
        
        前端在上传前调用此方法获取服务端临时公钥，
        然后用自己的公钥调用 e2e_handshake 完成密钥协商。
        
        Returns:
            {sessionId, publicKey (hex)}
        """
        if not self.e2e_manager:
            raise RuntimeError("E2E 加密不可用（需要 cryptography 库）")
        
        session = self.e2e_manager.create_session()
        return {
            "sessionId": session.session_id,
            "publicKey": session.my_public_key.hex(),
        }

    def e2e_handshake(self, session_id: str, peer_public_key_hex: str) -> dict:
        """完成 E2E 密钥协商。
        
        前端将自己的公钥发送过来，完成 ECDH 协商。
        之后此会话可加密/解密数据块。
        
        Args:
            session_id: e2e_create_session 返回的 sessionId
            peer_public_key_hex: 对方的 X25519 公钥（hex 编码）
        
        Returns:
            {sessionId, ready: True}
        """
        if not self.e2e_manager:
            raise RuntimeError("E2E 加密不可用")
        
        peer_pub = bytes.fromhex(peer_public_key_hex)
        self.e2e_manager.complete_handshake(session_id, peer_pub)
        return {"sessionId": session_id, "ready": True}

    def e2e_encrypt_download_chunk(
        self,
        file_ref: str,
        offset: int,
        length: int,
        session_id: str,
        chunk_index: int,
    ) -> dict:
        """加密下载：读取文件块 → E2E 加密后返回。
        
        服务器读取明文数据块后，用 E2E 会话密钥加密再返回给客户端。
        客户端用自己的私钥 + 服务端公钥重建会话密钥解密。
        
        Returns:
            {data: base64(加密数据), offset, length, totalSize, hasMore, e2e: True}
        """
        if not self.e2e_manager:
            raise RuntimeError("E2E 加密不可用")
        
        session = self.e2e_manager.get_session(session_id)
        if not session or not session.is_ready:
            raise ValueError(f"E2E 会话无效或未完成握手: {session_id}")
        
        # 读取明文块
        data_path = self.get_file_path(file_ref)
        if not data_path:
            raise ValueError(f"文件不存在: {file_ref}")
        
        length = min(length, CHUNK_SIZE)
        file_size = os.path.getsize(data_path)
        
        if offset < 0 or offset >= file_size:
            raise ValueError(f"偏移量越界: {offset}")
        
        actual_length = min(length, file_size - offset)
        
        with open(data_path, "rb") as f:
            f.seek(offset)
            plaintext = f.read(actual_length)
        
        # E2E 加密
        encrypted = e2e_encrypt_chunk(plaintext, session.session_key, chunk_index)
        
        return {
            "data": base64.b64encode(encrypted).decode("ascii"),
            "offset": offset,
            "length": len(plaintext),
            "totalSize": file_size,
            "hasMore": (offset + len(plaintext)) < file_size,
            "e2e": True,
        }

    def e2e_upload_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        encrypted_data_b64: str,
        session_id: str,
    ) -> dict:
        """E2E 加密上传：接收加密块 → 解密 → 存储明文。
        
        前端用 E2E 会话密钥加密数据块后上传，
        服务端解密后按正常流程存储（仅传输过程加密）。
        
        Returns:
            {received, total, progress}
        """
        if not self.e2e_manager:
            raise RuntimeError("E2E 加密不可用")
        
        session = self.e2e_manager.get_session(session_id)
        if not session or not session.is_ready:
            raise ValueError(f"E2E 会话无效或未完成握手: {session_id}")
        
        with self._lock:
            upload_session = self._sessions.get(upload_id)
        if not upload_session:
            raise ValueError(f"上传会话不存在: {upload_id}")
        if upload_session.completed:
            raise ValueError(f"上传已完成: {upload_id}")
        if chunk_index < 0 or chunk_index >= upload_session.chunk_count:
            raise ValueError(f"分块索引越界: {chunk_index}")
        
        # 解码 Base64
        encrypted_bytes = base64.b64decode(encrypted_data_b64)
        
        # E2E 解密
        plaintext = e2e_decrypt_chunk(encrypted_bytes, session.session_key, chunk_index)
        
        # 验证解密后的块大小
        expected_size = CHUNK_SIZE
        if chunk_index == upload_session.chunk_count - 1:
            expected_size = upload_session.total_size - chunk_index * CHUNK_SIZE
        if len(plaintext) != expected_size:
            raise ValueError(
                f"E2E 解密后分块 {chunk_index} 大小不匹配: "
                f"期望 {expected_size}, 实际 {len(plaintext)}"
            )
        
        # 写入明文数据
        chunk_path = os.path.join(
            self.uploads_dir, upload_id, "chunks", f"{chunk_index:06d}"
        )
        with open(chunk_path, "wb") as f:
            f.write(plaintext)
        
        with self._lock:
            upload_session.received_chunks.add(chunk_index)
            upload_session.e2e_session_id = session_id
            received = len(upload_session.received_chunks)
        
        progress = received / upload_session.chunk_count * 100
        return {
            "received": received,
            "total": upload_session.chunk_count,
            "progress": round(progress, 1),
            "e2e": True,
        }

    def e2e_close_session(self, session_id: str) -> dict:
        """关闭 E2E 会话（传输完成后销毁密钥材料）。"""
        if self.e2e_manager:
            self.e2e_manager.remove_session(session_id)
        return {"sessionId": session_id, "closed": True}
