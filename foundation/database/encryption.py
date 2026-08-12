"""出生数据加密（PRD §8 红线：敏感数据必须加密存储）。

使用 Fernet（AES-128-CBC + HMAC-SHA256）对称加密。
- 密钥未配置 → 自动生成随机密钥（仅开发环境，生产必须显式设置 GS_ENCRYPTION_KEY）
- **密钥轮换**：Encryptor 持有一串密钥（keyring）。解密逐个尝试——
  迁移窗口期用 `GS_OLD_ENCRYPTION_KEYS` 挂上旧密钥，旧密文照常可解；
  新写入一律用最新密钥（keyring[0]），轮换脚本重加密后即可撤下旧密钥。
- 加解密失败 → 记日志 + 抛 ValueError（不静默吞错，避免读到损坏数据）
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from foundation.logger import get_logger

logger = get_logger("foundation.database.encryption")

#: 生产环境密钥的环境变量名
ENV_KEY_NAME = "GS_ENCRYPTION_KEY"
#: 旧密钥（逗号分隔，密钥轮换迁移窗口期用）。只参与解密，加密永远用最新密钥。
OLD_KEYS_ENV_NAME = "GS_OLD_ENCRYPTION_KEYS"


def _generate_key() -> str:
    """生成随机 Fernet key（开发模式 auto-gen）。"""
    return Fernet.generate_key().decode("ascii")


def _parse_old_keys(raw: str | None) -> list[str]:
    """逗号分隔的旧密钥字符串 → 列表（剥空白、跳过空项）。"""
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k and k.strip()]


class Encryptor:
    """Fernet 对称加密器（支持密钥轮换：keyring 逐个尝试解密）。

    - 传入 key → 使用该密钥（生产）。
    - 传入空 key → 自动生成随机密钥（开发）。同时从环境变量 GS_ENCRYPTION_KEY 读取优先。
    - old_keys（或环境变量 GS_OLD_ENCRYPTION_KEYS）→ 旧密钥只用于解密，不参与加密。
    """

    def __init__(self, key: str = "", old_keys: list[str] | None = None):
        key = key or os.getenv(ENV_KEY_NAME, "")
        if key:
            self._keyring = [Fernet(key.encode("ascii"))]
        else:
            generated = _generate_key()
            logger.warning(
                "未配置加密密钥（%s），使用随机密钥——仅适合开发，重启后数据不可解密",
                ENV_KEY_NAME,
            )
            self._keyring = [Fernet(generated.encode("ascii"))]

        # 旧密钥 append 到 keyring（只解密）。优先显式参数，其次环境变量。
        old_raw = os.getenv(OLD_KEYS_ENV_NAME, "")
        old_keys = list(old_keys or _parse_old_keys(old_raw))
        for old in old_keys:
            try:
                self._keyring.append(Fernet(old.encode("ascii")))
            except Exception as exc:  # noqa: BLE001 - 坏旧密钥不炸启动，跳过
                logger.warning("旧密钥解析失败，跳过: %s", exc)

    @property
    def fernet(self) -> Fernet:
        """最新密钥（写入用）。暴露供轮换脚本做密文对比/重加密。"""
        return self._keyring[0]

    def encrypt(self, plaintext: str) -> str:
        """明文 → Fernet 密文（token 本身是 url-safe base64 字符串）。"""
        try:
            return self._keyring[0].encrypt(plaintext.encode("utf-8")).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            logger.error("加密失败: %s", exc)
            raise ValueError(f"加密失败: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        """Fernet 密文 → 明文（逐个尝试 keyring，轮换期间旧密文照常可解）。"""
        last_err: Exception | None = None
        for fernet in self._keyring:
            try:
                return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
            except InvalidToken:
                continue  # 这个密钥解不开，试下一个
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        logger.error("解密失败：所有密钥均无法解密")
        raise ValueError("解密失败：所有密钥均无法解密") from last_err


__all__ = ["Encryptor", "ENV_KEY_NAME", "OLD_KEYS_ENV_NAME"]
