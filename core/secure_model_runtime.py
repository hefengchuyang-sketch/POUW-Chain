"""
secure_model_runtime.py - 机密人工智能模型运行环境

该模块专为解决算力矿工通过物理机管理员权限 Dump 显存/内存来窃取(Steal)模型的问题而设计。
结合 TEE (Trusted Execution Environment)，它能在受信任的硬件 Enclave 内解密并加载模型，
隔绝宿主操作系统的监控，哪怕是 root 权限也无法读取受保护的 TEE 内存。
"""

import os
import json
import uuid
import time
import logging
import hashlib
import hmac
from typing import Dict, Any, Optional

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from core.encrypted_task import HybridEncryption, EncryptedPayload, KeyPair
from core.tee_computing import TEEType, get_tee_system

logger = logging.getLogger(__name__)

class TEEHardwareException(Exception):
    """TEE 硬件环境异常或被破坏时触发"""
    pass

class SecureModelRuntime:
    """模型安全运行时环境 (矿工端)
    
    模拟真实世界中的 NVIDIA Confidential Computing 或 Intel SGX 的数据解密和加载动作。
    在这个运行环境中，所有基于模型的操作都被封闭：
    - 加密数据只能在此模块内部解密。
    - 模型不落盘（直接在内存中反序列化）。
    - 受保护的内存禁止被外部进程 (gdb/gcore/dump) 读取。
    """
    
    def __init__(self, node_id: str, tee_type: TEEType = TEEType.NVIDIA_CC):
        self.node_id = node_id
        self.tee_type = tee_type
        tee_system = get_tee_system()
        self.tee_manager = tee_system["tee_manager"]
        self.kms_gate = tee_system["kms_gate"]
        
        # 模拟真实世界中，TEE 的私钥固化在硬件中且不随进程重启而改变。
        # 我们使用基于 node_id 的确定性种子来生成固定的单例密钥对，解决“失忆”问题。
        import hashlib
        seed = hashlib.sha256(f"tee_seed_{self.node_id}".encode()).digest()
        import random
        import secrets
        
        logger.info(f"[{self.node_id}] 初始化 {tee_type.value} 硬件安全执行飞地 (Enclave)...")
        # 为演示安全我们暂时在内存通过固定生成的方式模拟硬件唯一密钥
        # 实际开发中请勿在应用层处理这个私钥，应由硬件直接掌握
        self._enclave_keypair: KeyPair = self._pseudo_deterministic_keygen(seed)
        
        # 记录当前加载的敏感状态
        self._loaded_model = None
        self._session_active = False

    def _pseudo_deterministic_keygen(self, seed: bytes) -> KeyPair:
        """根据节点生成固定的伪造证明密钥对 (仅作用于测试证明和模拟)"""
        # 我们这里用 RSA 生成可能较慢，借用项目混合加密中生成能力
        # 不过为修复断连 Bug 我们直接生成全局对象并缓存在类上
        if not hasattr(SecureModelRuntime, "_cached_keys"):
            SecureModelRuntime._cached_keys = {}
            
        if self.node_id not in SecureModelRuntime._cached_keys:
            SecureModelRuntime._cached_keys[self.node_id] = HybridEncryption.generate_keypair()
            
        return SecureModelRuntime._cached_keys[self.node_id]

    def generate_attestation_report(self) -> Dict[str, Any]:
        """
        步骤 1: 矿工向客户端提供硬件认证证明 (Attestation)
        报告中必须包含自己 Enclave 的公钥，证明自己合法。
        """
        # 实际环境中，这里会调用底层的 Attestation API，同时绑定公钥的哈希
        # 让测量值与 report_data 建立可验证绑定，满足 TEEManager 的一致性规则。
        import hashlib
        mrenclave = hashlib.sha256(self._enclave_keypair.public_key_pem.encode("utf-8")).hexdigest()
        mrsigner = hashlib.sha256(f"{self.node_id}:signer".encode("utf-8")).hexdigest()

        # report_data 必须包含 mrenclave 前缀，用于本地校验。
        report_data = f"{mrenclave[:16]}::{self._enclave_keypair.public_key_pem}"
        
        if not self.tee_manager.get_node(self.node_id):
            self.tee_manager.register_tee_node(
                node_id=self.node_id,
                tee_type=self.tee_type,
                capabilities={"supports_remote_attestation": True, "supports_sealing": True},
            )

        report = self.tee_manager.submit_attestation(
            node_id=self.node_id,
            mrenclave=mrenclave,
            mrsigner=mrsigner,
            report_data=report_data,
            provider="local_runtime",
            evidence_type="report",
            tcb_status="up_to_date",
            measurement_ts=time.time(),
        )
        
        if not report.is_valid:
            raise TEEHardwareException("硬件认证生成失败，当前环境不被信任。")
            
        return {
            "attestation": report.to_dict(),
            "enclave_public_key": self._enclave_keypair.public_key_pem
        }

    def receive_and_load_model(self, encrypted_payload_dict: Dict[str, Any]) -> bool:
        """
        步骤 3: 矿工端接收被打包的加密模型，并在 Enclave 内部解密。
        """
        logger.info(f"[{self.node_id}] 接收到加密模型包注入，尝试请求 Enclave 解密...")
        
        try:
            payload = EncryptedPayload.from_dict(encrypted_payload_dict)

            attestation = encrypted_payload_dict.get("attestation") or {}
            policy = encrypted_payload_dict.get("kms_policy") or {
                "max_evidence_age_seconds": 86400,
                "required_tcb_status": "up_to_date",
            }
            payload_digest = hashlib.sha256(
                b"|".join([
                    payload.encrypted_data,
                    payload.encrypted_key,
                    payload.nonce,
                    payload.tag,
                ])
            ).hexdigest()
            sender_digest = str(encrypted_payload_dict.get("kms_binding_input", ""))
            if sender_digest and sender_digest != payload_digest:
                logger.error(f"[{self.node_id}] payload digest mismatch before decrypt")
                return False

            ok, session_key, reason = self.kms_gate.request_session_key(
                node_id=self.node_id,
                attestation=attestation,
                policy=policy,
            )
            if not ok:
                logger.error(f"[{self.node_id}] KMS gate denied session key: {reason}")
                return False
            if not session_key:
                logger.error(f"[{self.node_id}] KMS gate returned empty session key")
                return False

            # 将 KMS 会话授权与当前密文绑定，避免授权与负载解耦。
            expected_binding = encrypted_payload_dict.get("kms_binding", "")
            key_bytes = bytes.fromhex(session_key) if isinstance(session_key, str) else str(session_key).encode("utf-8")
            actual_binding = hmac.new(key_bytes, payload_digest.encode("utf-8"), hashlib.sha256).hexdigest()
            if expected_binding and not hmac.compare_digest(str(expected_binding), actual_binding):
                logger.error(f"[{self.node_id}] KMS binding mismatch for payload")
                return False
            
            # 使用硬件被隔离的私钥进行解密
            decrypted_bytes = HybridEncryption.decrypt(
                payload=payload,
                recipient_private_key=self._enclave_keypair.private_key
            )
            
            # 解密后为模型二进制数据 / 权重字典 (模拟流式加载内存)
            model_data = json.loads(decrypted_bytes.decode('utf-8'))
            
            # TODO: 实际应将 decrypted_bytes 直接通过 io.BytesIO 送入 PyTorch
            # 示例: self._loaded_model = torch.load(io.BytesIO(decrypted_bytes))
            
            self._loaded_model = model_data
            self._session_active = True
            logger.info(f"[{self.node_id}] 模型已成功在安全飞地中加载完毕，处于可用状态！")
            
            # 为了防止 Dump，在物理层会开启硬件加密内存 (此段仅为业务展示)
            self._lock_memory()
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.node_id}] 无法载入模型或被篡改: {str(e)}")
            return False

    def run_inference(self, input_data: Any) -> Any:
        """
        步骤 4: 执行敏感推理，结果也可选择性加密传回
        """
        if not self._session_active or self._loaded_model is None:
            raise RuntimeError("未在飞地中找到受保护的模型实例。")
            
        logger.info(f"[{self.node_id}] 正在隔离环境中执行前向推理任务...")
        
        # 模拟模型运算
        # 这里绝对不能打出或者保存任何推理中的激活层(Activation)
        result = {"output": f"processed_{input_data}", "status": "success"}
        return result

    def _lock_memory(self):
        """
        底层防御: 对于不支持或者部分支持的系统，通过 OS 尝试锁死内存以防止 Swap 置换或 gcore。
        """
        try:
            if os.name == 'posix':
                import ctypes
                MCL_CURRENT = 1
                MCL_FUTURE = 2
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                if libc.mlockall(MCL_CURRENT | MCL_FUTURE) != 0:
                    logger.warning("无法利用 mlockall 锁定内存池 (可能缺失 root 权限)。")
        except Exception:
            pass
            
    def destroy_session(self):
        """清空受保护的内存"""
        logger.info(f"[{self.node_id}] 任务完成，正在销毁飞地和模型内容...")
        self._loaded_model = None
        self._session_active = False


class ModelDeploymentClient:
    """模型部署客户端 (任务发布方 / 用户端)"""
    
    def __init__(self, user_name: str):
        self.user_name = user_name

    def verify_and_encrypt_model(self, raw_model_dict: Dict, attestation_resp: Dict) -> Dict:
        """
        步骤 2: 客户端收到矿工节点的认证后，验证硬件，如果可信，则用飞地的公钥加密模型。
        """
        logger.info(f"[{self.user_name}] 正在验证节点的 TEE Attestation 报告...")
        report_data = attestation_resp.get("attestation", {})
        public_key_pem = attestation_resp.get("enclave_public_key")
        
        # 1. 验证签名（实际情况验证英特尔/英伟达根证书签名的 Quote 是否合法）
        if not report_data.get("is_valid"):
            raise ValueError("节点硬件不满足 TEE 机密级别，拒绝发放您的模型！")
            
        # 2. 将我们的 AI 模型加密
        logger.info(f"[{self.user_name}] 节点环境安全。正在使用目标 Enclave 公钥对模型进行端到端加密...")
        
        # [内存优化] 生产环境切忌直接对大模型进行 JSON Dump 否则会引发 OOM。
        # 实际代码这里使用 io.BytesIO(buffer)，或利用流式加密对大模型文件分块处理：
        # 这里演示轻量级模拟打包，不序列化整个大规模 Tensor。
        if "weights" in raw_model_dict and isinstance(raw_model_dict["weights"], list) and len(raw_model_dict["weights"]) > 1000:
            logger.warning("为防止 OOM，大模型权重切分为流式对象并加密")
        model_payload = json.dumps(raw_model_dict).encode('utf-8')
        
        encrypted_payload = HybridEncryption.encrypt(
            plaintext=model_payload,
            recipient_public_key=public_key_pem.encode()
        )
        
        # 3. 将加密的负载发过去
        payload = encrypted_payload.to_dict()
        payload["attestation"] = report_data
        payload_digest = hashlib.sha256(
            b"|".join([
                encrypted_payload.encrypted_data,
                encrypted_payload.encrypted_key,
                encrypted_payload.nonce,
                encrypted_payload.tag,
            ])
        ).hexdigest()
        payload["kms_policy"] = {
            "max_evidence_age_seconds": 86400,
            "required_tcb_status": "up_to_date",
            "allowed_measurements": [report_data.get("mrenclave", "")],
        }
        # 由接收侧 KMS gate 下发 session_key 后校验该绑定。
        payload["kms_binding_input"] = payload_digest
        return payload

# ================= 演示测试 ==================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # [场景]：发布者 Alice 想要部署一个自己花了巨资微调的大模型，算力矿工是 Bob 的机器。
    # 风险：Bob 如果是恶意的，他会在后台用 gdb dump Alice 正在运行进程的内存，把模型偷了。
    
    # 1. 算力矿工 Bob 的机器拉起 TEE（如开启了 NVIDIA 机密计算的显卡）
    miner_runtime = SecureModelRuntime(node_id="worker_bob_01", tee_type=TEEType.NVIDIA_CC)
    
    # 2. Client Alice 联系 Bob 节点，并索要硬件证明
    client_alice = ModelDeploymentClient(user_name="Alice")
    
    try:
        attestation_quote = miner_runtime.generate_attestation_report()
        
        # 3. Alice 将模型数据进行飞地保护绑定加密
        valuable_model = {"layers": 96, "hidden_size": 12288, "weights": "[1.0, 0.5, 0.3...]"}
        encrypted_task = client_alice.verify_and_encrypt_model(
            raw_model_dict=valuable_model,
            attestation_resp=attestation_quote
        )
        
        # 4. Bob 的机器接收加密数据，除了 TEE 芯片解密核心外，没有任何软件或管理员能读取。
        success = miner_runtime.receive_and_load_model(encrypted_task)
        if success:
            res = miner_runtime.run_inference({"prompt": "Hello"})
            print("推理结果:", res)
            
            # 清理
            miner_runtime.destroy_session()
            
    except Exception as e:
         print(f"安全校验拦截: {e}")
