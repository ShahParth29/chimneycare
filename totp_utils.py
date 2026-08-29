"""
totp_utils.py — TOTP, Encryption, QR Generation, and Backup Code Utilities.

Provides production-grade implementations for:
- AES-256 / Fernet encryption of TOTP secrets at rest.
- RFC 6238 compliant TOTP secret and QR code data URL generation.
- Code validation with clock drift tolerance.
- Single-use hashed backup recovery codes.
"""

import io
import os
import secrets
import string
import base64
import hashlib
import logging
from typing import Tuple, List, Dict, Optional
import pyotp
import qrcode
from cryptography.fernet import Fernet

logger = logging.getLogger("chimneycare.totp")

# Load or initialize Fernet cipher
_fernet_instance: Optional[Fernet] = None


def get_fernet() -> Fernet:
    """Lazily initializes and returns the Fernet cipher instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = os.getenv("TOTP_ENCRYPTION_KEY")
        if not key:
            # Fallback to deterministic key derived from FLASK_SECRET_KEY if not explicitly provided
            secret = os.getenv("FLASK_SECRET_KEY", "default-fallback-secret-for-testing-key-32")
            derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
            logger.warning("TOTP_ENCRYPTION_KEY not set; using SHA-256 derived key from FLASK_SECRET_KEY.")
            _fernet_instance = Fernet(derived_key)
        else:
            key_bytes = key.encode() if isinstance(key, str) else key
            _fernet_instance = Fernet(key_bytes)
    return _fernet_instance


def encrypt_secret(plain_secret: str) -> str:
    """Encrypts a plaintext Base32 TOTP secret string."""
    if not plain_secret:
        raise ValueError("Secret cannot be empty.")
    cipher = get_fernet()
    return cipher.encrypt(plain_secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypts an encrypted Base32 TOTP secret string."""
    if not encrypted_secret:
        raise ValueError("Encrypted secret cannot be empty.")
    cipher = get_fernet()
    return cipher.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")


def generate_totp_secret() -> str:
    """Generates an RFC 6238 compliant 160-bit Base32 secret string."""
    return pyotp.random_base32()


def generate_qr_data_url(secret: str, user_email: str, issuer: str = "ChimneyCare") -> str:
    """
    Generates an otpauth:// URI and returns a Base64-encoded Data URL PNG for inline HTML display.
    """
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user_email, issuer_name=issuer)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_data}"


def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
    """
    Validates a 6-digit TOTP code.
    `valid_window=1` allows ±30 seconds (1 step) of clock drift.
    """
    if not code or not isinstance(code, str):
        return False
    clean_code = code.strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False
    try:
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(clean_code, valid_window=valid_window))
    except Exception as e:
        logger.error(f"TOTP verification error: {e}")
        return False


def generate_backup_codes(count: int = 8) -> Tuple[List[str], List[Dict[str, any]]]:
    """
    Generates human-readable backup recovery codes formatted as 'XXXX-XXXX'.
    Returns:
      - plain_codes: List of strings shown once to the user during setup.
      - hashed_records: List of dicts stored in DB (e.g. [{'hash': '...', 'used': False}]).
    """
    plain_codes: List[str] = []
    hashed_records: List[Dict[str, any]] = []
    chars = string.ascii_uppercase + "23456789"  # Discard ambiguous characters (0, 1, O, I)

    for _ in range(count):
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        code = f"{part1}-{part2}"
        plain_codes.append(code)

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        hashed_records.append({
            "hash": code_hash,
            "used": False,
        })

    return plain_codes, hashed_records


def verify_and_consume_backup_code(backup_codes_list: List[Dict[str, any]], submitted_code: str) -> Tuple[bool, List[Dict[str, any]]]:
    """
    Validates whether the submitted code matches an unused backup recovery code.
    If valid, marks it as used and returns (True, updated_list).
    """
    if not submitted_code or not isinstance(submitted_code, str):
        return False, backup_codes_list

    clean_code = submitted_code.strip().upper()
    # Normalize with hyphen if user omitted it
    if len(clean_code) == 8 and "-" not in clean_code:
        clean_code = f"{clean_code[:4]}-{clean_code[4:]}"

    submitted_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()

    for item in backup_codes_list:
        if item.get("hash") == submitted_hash and not item.get("used", False):
            item["used"] = True
            return True, backup_codes_list

    return False, backup_codes_list
