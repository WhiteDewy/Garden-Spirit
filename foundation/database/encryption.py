"""出生数据加密（PRD §8 红线：敏感数据必须加密存储）。

使用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密。
- 密钥未配置 → 自动生成随机密钥（仅开发环境，生产必须显式设置 GS_ENCRYPTION_KEY）
- 加解密失败 → 记日志 + 抛 ValueError（不静默吞错，避免读到损坏数据）
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from foundation.logger import get_logger

logger = get_logger("foundation.database.encryption")

#: 生产环境密钥的环境变量名
ENV_KEY_NAME = "GS_ENCRYPTION_KEY"


def _generate_key() -> str:
    """生成随机 Fernet key（开发模式 auto-gen）。"""
    return Fernet.generate_key().decode("ascii")


class Encryptor:
    """Fernet 对称加密器。

    - 传入 key → 使用该密钥（生产）。
    - 传入空 key → 自动生成随机密钥（开发）。同时从环境变量 GS_ENCRYPTION_KEY 读取优先。
    """

    def __init__(self, key: str = ""):
        key = key or os.getenv(ENV_KEY_NAME, "")
        if key:
            self._fernet = Fernet(key.encode("ascii"))
        else:
            generated = _generate_key()
            logger.warning(
                "未配置加密密钥（%s），使用随机密钥——仅适合开发，重启后数据不可解密",
                ENV_KEY_NAME,
            )
            self._fernet = Fernet(generated.encode("ascii"))

    def encrypt(self, plaintext: str) -> str:
        """明文 → Fernet 密文（token 本身是 url-safe base64 字符串）。"""
        try:
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            logger.error("加密失败: %s", exc)
            raise ValueError(f"加密失败: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        """Fernet 密文 → 明文。"""
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            logger.error("解密失败：密钥不匹配或数据损坏")
            raise ValueError("解密失败：密钥不匹配或数据损坏") from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("解密失败: %s", exc)
            raise ValueError(f"解密失败: {exc}") from exc


__all__ = ["Encryptor", "ENV_KEY_NAME"]
