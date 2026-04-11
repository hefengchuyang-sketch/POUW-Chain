"""
[M-07] 文件传输领域 RPC Handler

从 NodeRPCService 提取 file_* 相关 RPC 方法注册。
方法实现仍在 NodeRPCService 中，通过 self.svc 委托调用。
"""

from core.rpc_handlers import RPCHandlerBase, register_handler_class

try:
    from core.rpc_service import RPCPermission
except ImportError:
    from enum import IntEnum

    class RPCPermission(IntEnum):
        PUBLIC = 0
        USER = 1
        MINER = 2
        ADMIN = 3


@register_handler_class
class FileHandler(RPCHandlerBase):
    """文件传输处理器 - 分块上传下载与任务输出文件访问"""

    domain = "file"

    def register_methods(self):
        self.register(
            "file_initUpload", self.svc._file_init_upload,
            "初始化分块上传（返回 uploadId 和 chunkSize）",
            RPCPermission.USER,
        )
        self.register(
            "file_uploadChunk", self.svc._file_upload_chunk,
            "上传单个分块",
            RPCPermission.USER,
        )
        self.register(
            "file_finalizeUpload", self.svc._file_finalize_upload,
            "完成上传（校验并合并分块）",
            RPCPermission.USER,
        )
        self.register(
            "file_getUploadProgress", self.svc._file_get_upload_progress,
            "查询上传进度",
            RPCPermission.USER,
        )
        self.register(
            "file_getInfo", self.svc._file_get_info,
            "获取已上传文件信息",
            RPCPermission.USER,
        )
        self.register(
            "file_downloadChunk", self.svc._file_download_chunk,
            "分块下载文件",
            RPCPermission.USER,
        )
        self.register(
            "file_getTaskOutputs", self.svc._file_get_task_outputs,
            "获取任务输出文件清单",
            RPCPermission.USER,
        )
        self.register(
            "file_downloadTaskOutput", self.svc._file_download_task_output,
            "分块下载任务输出文件",
            RPCPermission.USER,
        )
        self.register(
            "file_cancelUpload", self.svc._file_cancel_upload,
            "取消上传并清理临时文件",
            RPCPermission.USER,
        )
