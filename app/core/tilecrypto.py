"""卫星瓦片（Esri）本地存储加密。

Esri World Imagery 服务条款仅允许在线浏览预览，为避免缓存瓦片被直接拷贝分发，
Esri 瓦片落盘前用 Fernet 对称加密，密钥按安装生成保存在用户配置目录。
仅软件内预览时解密到内存，不写出明文文件。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import CONFIG_DIR

logger = logging.getLogger(__name__)

KEY_FILE = CONFIG_DIR / "tile.key"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        logger.info("已生成瓦片加密密钥：%s", KEY_FILE)
    return Fernet(key)


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken:
        raise ValueError("瓦片解密失败（密钥不匹配或数据损坏）")
