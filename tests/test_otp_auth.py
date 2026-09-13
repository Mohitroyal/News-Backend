import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure testing flag is set
os.environ["TESTING"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-testing-32-chars-long"

from app.main import app
from app.db.session import Base, get_db
from app.models.user import User
from app.models.otp import OTPVerification
from app.core.config import settings
from app.core.security import get_password_hash

# Setup in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_otp_auth.db"
test_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Clean up tables between tests
    db.query(OTPVerification).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# ─── 1. Send OTP Success ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_otp_success():
    with patch("app.services.msg91_service.msg91_service.send_otp", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (True, None, "msg_req_12345")
        
        response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "OTP sent successfully" in data["message"]
        
        # Verify DB has record with bcrypt hashed OTP (not plaintext)
        db = TestingSessionLocal()
        otp_rec = db.query(OTPVerification).filter(OTPVerification.phone_number == "+919876543210").first()
        assert otp_rec is not None
        assert otp_rec.consumed is False
        assert otp_rec.request_id == "msg_req_12345"
        assert len(otp_rec.otp_hash) > 20
        assert not otp_rec.otp_hash.isdigit()  # Must be a secure hash, NOT plain digits
        db.close()


# ─── 2. Invalid Phone Number Rejection ────────────────────────────────────────
def test_send_otp_invalid_phone():
    # Less than 10 digits
    res1 = client.post("/api/auth/send-otp", json={"phone": "12345"})
    assert res1.status_code == 422

    # Invalid starting digit (Indian numbers start with 6,7,8,9)
    res2 = client.post("/api/auth/send-otp", json={"phone": "1234567890"})
    assert res2.status_code == 422

    # Empty string
    res3 = client.post("/api/auth/send-otp", json={"phone": ""})
    assert res3.status_code == 422


# ─── 3. MSG91 Failure ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_otp_msg91_failure():
    with patch("app.services.msg91_service.msg91_service.send_otp", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (False, "Insufficient SMS balance", None)
        
        response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert response.status_code == 502
        data = response.json()
        assert data["success"] is False
        assert "Insufficient SMS balance" in data["message"]

        # Ensure failed OTP is not left active
        db = TestingSessionLocal()
        active_otps = db.query(OTPVerification).filter(
            OTPVerification.phone_number == "+919876543210",
            OTPVerification.consumed == False
        ).count()
        assert active_otps == 0
        db.close()


# ─── 4. Missing MSG91 Authkey ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_otp_missing_authkey():
    original_key = settings.MSG91_AUTHKEY
    try:
        settings.MSG91_AUTHKEY = None
        response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert response.status_code == 502
        data = response.json()
        assert data["success"] is False
        assert "not configured" in data["message"].lower()
    finally:
        settings.MSG91_AUTHKEY = original_key


# ─── 5. OTP Expiry ────────────────────────────────────────────────────────────
def test_verify_otp_expired():
    db = TestingSessionLocal()
    # Create an OTP expired 5 minutes ago
    past_time = datetime.now(timezone.utc) - timedelta(minutes=15)
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("123456"),
        purpose="login",
        created_at=past_time,
        expires_at=expired_time,
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    response = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "123456"})
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "expired" in data["message"].lower()


# ─── 6. Correct OTP Verification & Authentication Token Generation ────────────
def test_verify_otp_correct():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("654321"),
        purpose="login",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    response = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "654321"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "token" in data
    assert len(data["token"]) > 20
    assert data["token_type"] == "bearer"
    assert data["user"]["phone_number"] == "+919876543210"

    # Verify OTP is marked consumed
    db = TestingSessionLocal()
    updated_rec = db.query(OTPVerification).filter(OTPVerification.id == otp_record.id).first()
    assert updated_rec.consumed is True
    assert updated_rec.verified_at is not None
    db.close()


# ─── 7. Incorrect OTP ─────────────────────────────────────────────────────────
def test_verify_otp_incorrect():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("654321"),
        purpose="login",
        attempts=0,
        max_attempts=5,
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    response = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "111111"})
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Invalid OTP" in data["message"]
    assert "4 attempt(s) remaining" in data["message"]

    # Verify attempts incremented
    db = TestingSessionLocal()
    updated_rec = db.query(OTPVerification).filter(OTPVerification.id == otp_record.id).first()
    assert updated_rec.attempts == 1
    assert updated_rec.consumed is False
    db.close()


# ─── 8. OTP Reuse Prevention ──────────────────────────────────────────────────
def test_verify_otp_reuse_prevention():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("888888"),
        purpose="login",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    # First verification succeeds
    res1 = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "888888"})
    assert res1.status_code == 200

    # Second verification with same OTP must FAIL
    res2 = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "888888"})
    assert res2.status_code == 400
    assert "No active OTP found" in res2.json()["message"]


# ─── 9. Maximum Verification Attempts Lockout ─────────────────────────────────
def test_verify_otp_max_attempts():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("999999"),
        purpose="login",
        attempts=4,  # 4 attempts already used out of 5
        max_attempts=5,
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    # 5th failed attempt -> locks out
    response = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "000000"})
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Maximum verification attempts exceeded" in data["message"]

    # Ensure record is consumed/locked
    db = TestingSessionLocal()
    updated_rec = db.query(OTPVerification).filter(OTPVerification.id == otp_record.id).first()
    assert updated_rec.consumed is True
    db.close()


# ─── 10. OTP Resend Invalidation ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_otp_resend_invalidates_previous():
    with patch("app.services.msg91_service.msg91_service.send_otp", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (True, None, "req_1")

        # First send
        res1 = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert res1.status_code == 200

        db = TestingSessionLocal()
        first_otp = db.query(OTPVerification).filter(OTPVerification.phone_number == "+919876543210").first()
        # Fast-forward created_at to bypass 60s cooldown for testing resend
        first_otp.created_at = datetime.now(timezone.utc) - timedelta(seconds=65)
        db.commit()
        db.close()

        # Resend OTP
        mock_send.return_value = (True, None, "req_2")
        res2 = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert res2.status_code == 200

        db = TestingSessionLocal()
        # Previous OTP must now be marked consumed
        old_otp = db.query(OTPVerification).filter(OTPVerification.id == first_otp.id).first()
        assert old_otp.consumed is True

        # Only 1 active unconsumed OTP exists
        active_count = db.query(OTPVerification).filter(
            OTPVerification.phone_number == "+919876543210",
            OTPVerification.consumed == False
        ).count()
        assert active_count == 1
        db.close()


# ─── 11. Rate Limiting (Max 3 in 15 Minutes) ──────────────────────────────────
@pytest.mark.asyncio
async def test_otp_send_rate_limit():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    # Simulate 3 prior requests within the 15-minute window
    for i in range(3):
        otp = OTPVerification(
            id=uuid.uuid4(),
            phone_number="+919876543210",
            otp_hash="hash",
            purpose="login",
            consumed=True,
            created_at=now - timedelta(minutes=10 - i * 2),  # 10m, 8m, 6m ago
            expires_at=now + timedelta(minutes=5),
        )
        db.add(otp)
    db.commit()
    db.close()

    # 4th request must be rejected with 429
    response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
    assert response.status_code == 429
    data = response.json()
    assert data["success"] is False
    assert "Too many OTP requests" in data["message"]


# ─── 12. Database Failure Handling ────────────────────────────────────────────
def test_send_otp_database_failure():
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("DB Connection Terminated")):
        response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert response.status_code == 500
        assert "Failed to initiate OTP" in response.json()["detail"]


# ─── 13. MSG91 Gateway Timeout ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_otp_msg91_timeout():
    with patch("app.services.msg91_service.msg91_service.send_otp", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = (False, "SMS gateway timed out. Please try again.", None)

        response = client.post("/api/auth/send-otp", json={"phone": "9876543210"})
        assert response.status_code == 502
        assert "timed out" in response.json()["message"].lower()


# ─── 14. Authentication Token Generation & Access to Protected Endpoint ───────
def test_token_authenticates_protected_endpoint():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)
    otp_record = OTPVerification(
        id=uuid.uuid4(),
        phone_number="+919876543210",
        otp_hash=get_password_hash("777777"),
        purpose="login",
        created_at=now,
        expires_at=now + timedelta(minutes=10),
        consumed=False,
    )
    db.add(otp_record)
    db.commit()
    db.close()

    # 1. Verify OTP and get token
    verify_res = client.post("/api/auth/verify-otp", json={"phone": "9876543210", "otp": "777777"})
    assert verify_res.status_code == 200
    token = verify_res.json()["token"]

    # 2. Use token on protected endpoint /api/v1/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["success"] is True
    assert me_data["data"]["phone_number"] == "+919876543210"
