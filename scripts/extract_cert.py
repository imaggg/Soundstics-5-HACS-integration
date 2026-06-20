#!/usr/bin/env python3
"""Extract the SoundSticks 5 mTLS client certificate from the official
Harman Kardon One Android app, so it can be used by the SoundSticks 5
Home Assistant integration.

The certificate (assets/alice.p12 inside the APK) is identical across all
SoundSticks 5 WiFi units — it's a fixed client cert baked into the firmware,
not a per-device secret. This script never ships that certificate; it only
extracts it from an app package YOU provide.

Usage:
    python3 extract_cert.py path/to/harman-kardon-one.xapk
    python3 extract_cert.py path/to/harman-kardon-one.apk
    python3 extract_cert.py path/to/alice.p12 [--password PASSWORD]

Requires: pip install cryptography
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

from _cipher import find_p12_password

ALICE_ASSET_PATH = "assets/alice.p12"


def _find_in_zip(data: bytes, target: str) -> bytes | None:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        try:
            return zf.read(target)
        except KeyError:
            return None


def _p12_from_apk(apk_path: Path) -> bytes:
    data = apk_path.read_bytes()
    p12 = _find_in_zip(data, ALICE_ASSET_PATH)
    if p12 is None:
        raise SystemExit(f"{ALICE_ASSET_PATH} not found in {apk_path}")
    return p12


def _p12_from_xapk(xapk_path: Path) -> bytes:
    with zipfile.ZipFile(xapk_path) as outer:
        apk_names = [n for n in outer.namelist() if n.endswith(".apk")]
        if not apk_names:
            raise SystemExit(f"no .apk found inside {xapk_path}")
        for name in apk_names:
            apk_data = outer.read(name)
            p12 = _find_in_zip(apk_data, ALICE_ASSET_PATH)
            if p12 is not None:
                return p12
    raise SystemExit(f"no APK inside {xapk_path} contains {ALICE_ASSET_PATH}")


def _load_p12(path: Path) -> bytes:
    suffix = path.suffix.lower()
    if suffix == ".xapk":
        return _p12_from_xapk(path)
    if suffix == ".apk":
        return _p12_from_apk(path)
    if suffix == ".p12":
        return path.read_bytes()
    raise SystemExit(f"unsupported file type: {suffix} (expected .xapk, .apk, or .p12)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="path to .xapk, .apk, or .p12 file")
    parser.add_argument("--password", help="p12 password, if you already know it (skips auto-discovery)")
    parser.add_argument("--out-dir", type=Path, default=Path.cwd(), help="where to write cert.pem/key.pem (default: cwd)")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"file not found: {args.source}")

    print(f"Reading {args.source} ...")
    p12_data = _load_p12(args.source)
    print(f"Found alice.p12 ({len(p12_data)} bytes)")

    from cryptography.hazmat.primitives.serialization import pkcs12

    password = args.password
    if password is not None:
        try:
            key, cert, _ = pkcs12.load_key_and_certificates(p12_data, password.encode())
        except Exception as exc:
            raise SystemExit(f"provided password failed: {exc}") from exc
    else:
        print("Auto-discovering password ...")
        password = find_p12_password(p12_data)
        print(f"Password found: {password}")
        key, cert, _ = pkcs12.load_key_and_certificates(p12_data, password.encode())

    if key is None or cert is None:
        raise SystemExit("p12 did not contain both a private key and a certificate")

    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    args.out_dir.mkdir(parents=True, exist_ok=True)
    cert_path = args.out_dir / "cert.pem"
    key_path = args.out_dir / "key.pem"

    cert_path.write_bytes(cert.public_bytes(Encoding.PEM))
    key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    key_path.chmod(0o600)

    print(f"Wrote {cert_path}")
    print(f"Wrote {key_path}")
    print("\nPaste or upload these two files in the SoundSticks 5 integration setup in Home Assistant.")


if __name__ == "__main__":
    main()
