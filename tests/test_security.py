import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings
from app.security import create_access_token, hash_password, verify_password, verify_token


def test_hash_is_not_the_password():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2")


def test_same_password_hashes_differently_each_time():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_accepts_the_right_password_and_rejects_the_wrong_one():
    hashed = hash_password("right-password")
    assert verify_password("right-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_token_round_trip_returns_the_subject():
    token = create_access_token("42")
    assert verify_token(token) == "42"


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {"sub": "42", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert verify_token(expired) is None


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode({"sub": "1"}, "an-attackers-key-that-is-long-enough-32", algorithm="HS256")
    assert verify_token(forged) is None


def test_token_with_an_edited_payload_is_rejected():
    token = create_access_token("42")
    header, _payload, signature = token.split(".")
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": "1"}).encode()).rstrip(b"=").decode()
    )
    forged_token = f"{header}.{forged_payload}.{signature}"
    assert verify_token(forged_token) is None


@pytest.mark.parametrize("garbage", ["", "not-a-token", "a.b.c"])
def test_garbage_is_rejected_not_crashed(garbage):
    assert verify_token(garbage) is None


@pytest.mark.parametrize(
    "password, should_match",
    [("right-password", True), ("wrong-password", False), ("", False)],
)
def test_verify(password, should_match):
    hashed = hash_password("right-password")
    assert verify_password(password, hashed) is should_match


@pytest.mark.parametrize(
    "password, wrong_password",
    [
        ("", "  "),
        ("154@@AAbb", "154@@AAbB"),
        ("5497!SSaSDA", "5497!SsaSDA"),
        ("H#aSEwq?zxc454 ", "H#aSEwq?zXc454 "),
    ],
)
def test_verify_rejects_near_miss_passwords(password, wrong_password):
    hashed_password = hash_password(password)
    assert verify_password(wrong_password, hashed_password) is False
    assert verify_password(password, hashed_password) is True
