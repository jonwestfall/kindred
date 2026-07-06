#!/usr/bin/env python3
"""Generate a local VAPID P-256 key pair for standards-based Web Push."""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = ROOT / "config/vapid_private.pem"


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    PRIVATE_PATH.write_bytes(private_pem)
    PRIVATE_PATH.chmod(0o600)
    public_bytes = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_key = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode()
    print(f"Wrote private key: {PRIVATE_PATH}")
    print("")
    print("Add these values to .env:")
    print(f"VAPID_PRIVATE_KEY={PRIVATE_PATH}")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print("VAPID_SUBJECT=mailto:you@example.com")


if __name__ == "__main__":
    main()

