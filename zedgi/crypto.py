"""Client-side crypto for the ZedGi zero-knowledge model.

Ports the wire formats enforced server-side by ``app/Support/ecies.ts`` and
``app/Middleware/RequestSignature.ts`` so credentials are encrypted and requests
are signed before they leave the developer's process.

ECIES uses ECDH (X25519, or P-256 for legacy account keys) + HKDF-SHA256 +
AES-256-GCM via the ``cryptography`` package (install the ``zedgi[crypto]``
extra). HMAC-SHA256 + SHA-256 use the stdlib.

Blob layout (binary, then base64url) — must match app/Support/ecies.ts:
    0x01|0x02     (1 byte  — version: 0x01 X25519, 0x02 P-256)
    accountId     (16 bytes — account id hex, raw binary)
    keyVersion    (2 bytes  — uint16 big-endian)
    ephemeralPub  (32 bytes X25519 / 65 bytes P-256 — raw public key)
    iv            (12 bytes — AES-GCM nonce)
    ciphertext+tag(variable)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
from typing import Any, Dict

# HKDF domain-separation string for the client → gateway hop (see ecies.ts).
_HKDF_INFO_CLIENT_GATEWAY = b"zedgi-cred-client-gateway-v1"


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encrypt_credential(
    credential: Dict[str, Any],
    public_key_b64u: str,
    account_id_hex: str,
    key_version: int,
) -> str:
    """ECIES-encrypt a credential dict for the account public key.

    Returns the base64url blob for the ``x-zedgi-cred`` header.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import (
            X25519PrivateKey,
            X25519PublicKey,
        )
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes, serialization
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Credential encryption requires the 'cryptography' package. "
            "Install it with: pip install 'zedgi[crypto]'"
        ) from exc

    # The recipient key's length picks the curve (32 = X25519 v0x01, 65 = P-256
    # v0x02 uncompressed) — never a runtime default. A P-256 account key must be
    # used with P-256. Mirrors app/Support/ecies.ts and the TS SDK.
    recipient_raw = _b64u_decode(public_key_b64u)
    if len(recipient_raw) == 32:
        version = b"\x01"
        ephemeral_priv = X25519PrivateKey.generate()
        recipient_pub = X25519PublicKey.from_public_bytes(recipient_raw)
        ephemeral_pub_raw = ephemeral_priv.public_key().public_bytes_raw()
        shared = ephemeral_priv.exchange(recipient_pub)
    else:
        version = b"\x02"
        ephemeral_priv = ec.generate_private_key(ec.SECP256R1())
        recipient_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), recipient_raw)
        ephemeral_pub_raw = ephemeral_priv.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        shared = ephemeral_priv.exchange(ec.ECDH(), recipient_pub)

    aes_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"",
        info=_HKDF_INFO_CLIENT_GATEWAY,
    ).derive(shared)

    iv = os.urandom(12)
    ciphertext = AESGCM(aes_key).encrypt(iv, json.dumps(credential).encode("utf-8"), None)

    acc_bytes = bytes.fromhex(account_id_hex)
    if len(acc_bytes) != 16:
        raise ValueError("account_id must be 16 bytes (32 hex chars)")
    kv_bytes = struct.pack(">H", key_version)  # uint16 big-endian

    blob = version + acc_bytes + kv_bytes + ephemeral_pub_raw + iv + ciphertext
    return _b64u_encode(blob)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hmac_sign(message: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def random_nonce() -> str:
    """32-char lowercase hex (128-bit) single-use nonce."""
    return os.urandom(16).hex()
