from __future__ import annotations

import base64
import re
import textwrap
from pathlib import Path

from nacl.signing import SigningKey, VerifyKey

from utils.db_utils import ensure_runtime_directories, project_path


KEY_ID = "mercari-ed25519-1"
PRIVATE_KEY_LABEL = "ED25519 PRIVATE KEY"
PUBLIC_KEY_LABEL = "ED25519 PUBLIC KEY"


def generate_keypair(private_path: str | Path | None = None, public_path: str | Path | None = None) -> dict[str, str]:
    ensure_runtime_directories()
    private_key_path = Path(private_path) if private_path else project_path("keys", "ed25519_private_key.pem")
    public_key_path = Path(public_path) if public_path else project_path("keys", "ed25519_public_key.pem")

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    private_key_path.write_text(_wrap_pem(PRIVATE_KEY_LABEL, signing_key.encode()), encoding="utf-8")
    public_key_path.write_text(_wrap_pem(PUBLIC_KEY_LABEL, verify_key.encode()), encoding="utf-8")

    return {"private_key_path": str(private_key_path), "public_key_path": str(public_key_path)}


def ensure_keypair() -> dict[str, str]:
    private_key_path = project_path("keys", "ed25519_private_key.pem")
    public_key_path = project_path("keys", "ed25519_public_key.pem")
    if not private_key_path.exists() or not public_key_path.exists():
        return generate_keypair(private_key_path, public_key_path)
    return {"private_key_path": str(private_key_path), "public_key_path": str(public_key_path)}


def load_private_key() -> SigningKey:
    ensure_keypair()
    raw_bytes = _read_pem_blob(project_path("keys", "ed25519_private_key.pem"), PRIVATE_KEY_LABEL)
    return SigningKey(raw_bytes)


def load_public_key() -> VerifyKey:
    ensure_keypair()
    raw_bytes = _read_pem_blob(project_path("keys", "ed25519_public_key.pem"), PUBLIC_KEY_LABEL)
    return VerifyKey(raw_bytes)


def sign_proof(canonical_json: str) -> str:
    signature = load_private_key().sign(canonical_json.encode("utf-8")).signature
    return _to_base64url(signature)


def verify_signature(canonical_json: str, signature: str) -> bool:
    try:
        signature_bytes = _from_base64url(signature)
        load_public_key().verify(canonical_json.encode("utf-8"), signature_bytes)
    except Exception:
        return False
    return True


def _wrap_pem(label: str, raw_bytes: bytes) -> str:
    body = "\n".join(textwrap.wrap(base64.b64encode(raw_bytes).decode("ascii"), 64))
    return f"-----BEGIN {label}-----\n{body}\n-----END {label}-----\n"


def _read_pem_blob(path: Path, label: str) -> bytes:
    text = path.read_text(encoding="utf-8")
    pattern = rf"-----BEGIN {re.escape(label)}-----\s*(.*?)\s*-----END {re.escape(label)}-----"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"Invalid PEM file: {path}")
    compact = re.sub(r"\s+", "", match.group(1))
    return base64.b64decode(compact)


def _to_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _from_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
