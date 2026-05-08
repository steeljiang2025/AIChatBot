"""STE-18：core/security 单元测试（纯函数，零 IO，零 DB）。

覆盖：
- bcrypt 哈希与校验
- access / refresh token 签发与解码
- 篡改 / 过期 / 类型不符 / 垃圾输入一律 InvalidTokenError
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core import security

# ---- bcrypt ----


def test_hash_password_returns_non_plaintext() -> None:
    pwd = "S3cret-Pwd!"
    hashed = security.hash_password(pwd)
    assert hashed != pwd
    # bcrypt 哈希通常以 $2b$ / $2a$ 开头且 ≥ 60 字符
    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))
    assert len(hashed) >= 60


def test_hash_password_is_non_deterministic() -> None:
    """同一密码两次哈希应得到不同结果（bcrypt 自带 salt）。"""
    pwd = "S3cret-Pwd!"
    assert security.hash_password(pwd) != security.hash_password(pwd)


def test_verify_password_accepts_correct_password() -> None:
    pwd = "S3cret-Pwd!"
    assert security.verify_password(pwd, security.hash_password(pwd)) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = security.hash_password("right-pwd")
    assert security.verify_password("wrong-pwd", hashed) is False


# ---- access token ----


def test_create_access_token_round_trip() -> None:
    token = security.create_access_token(
        user_id="user-1",
        tenant_id="tenant-1",
        roles=["analyst", "viewer"],
    )
    claims = security.decode_token(token, expected_type="access")
    assert claims["sub"] == "user-1"
    assert claims["tenant_id"] == "tenant-1"
    assert claims["roles"] == ["analyst", "viewer"]
    assert claims["type"] == "access"
    assert "exp" in claims and "iat" in claims
    assert claims["exp"] > claims["iat"]


def test_create_refresh_token_round_trip() -> None:
    token = security.create_refresh_token(user_id="user-1", tenant_id="tenant-1")
    claims = security.decode_token(token, expected_type="refresh")
    assert claims["sub"] == "user-1"
    assert claims["tenant_id"] == "tenant-1"
    assert claims["type"] == "refresh"
    # refresh 不带 roles
    assert "roles" not in claims or claims["roles"] == []


# ---- 失败路径 ----


def test_decode_token_rejects_wrong_type_access_as_refresh() -> None:
    access = security.create_access_token(user_id="u1", tenant_id="t1", roles=[])
    with pytest.raises(security.InvalidTokenError):
        security.decode_token(access, expected_type="refresh")


def test_decode_token_rejects_wrong_type_refresh_as_access() -> None:
    refresh = security.create_refresh_token(user_id="u1", tenant_id="t1")
    with pytest.raises(security.InvalidTokenError):
        security.decode_token(refresh, expected_type="access")


def test_decode_token_rejects_tampered_signature() -> None:
    token = security.create_access_token(user_id="u1", tenant_id="t1", roles=[])
    # 反转最后一个字符（签名段），打破 HMAC
    last = token[-1]
    flipped = "B" if last != "B" else "C"
    tampered = token[:-1] + flipped
    with pytest.raises(security.InvalidTokenError):
        security.decode_token(tampered, expected_type="access")


def test_decode_token_rejects_expired() -> None:
    expired = security.create_access_token(
        user_id="u1",
        tenant_id="t1",
        roles=[],
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(security.InvalidTokenError):
        security.decode_token(expired, expected_type="access")


def test_decode_token_rejects_garbage() -> None:
    with pytest.raises(security.InvalidTokenError):
        security.decode_token("not.a.jwt", expected_type="access")


def test_decode_token_rejects_empty_string() -> None:
    with pytest.raises(security.InvalidTokenError):
        security.decode_token("", expected_type="access")
