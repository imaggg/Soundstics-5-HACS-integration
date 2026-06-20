"""Port of soundsticks-app's internal/cert/decrypt.go.

Decrypts the base64 strings embedded in Harman Kardon One's libnativelib.so
to find the password protecting assets/alice.p12. Ported 1:1 from the Go
reference implementation (https://github.com/imaggg/soundsticks-app) —
keep in sync with that file if the cipher ever changes.
"""

from __future__ import annotations

import base64

_MASK32 = 0xFFFFFFFF


def decrypt_string(encoded: str, key: str = "x") -> str:
    """Decrypt one base64 string from libnativelib.so's encrypted string table.

    Layout: [8 bytes IV][4 bytes big-endian FNV-1a checksum][ciphertext].
    Raises ValueError if the input is malformed or fails the checksum.
    """
    if not key:
        raise ValueError("empty key")
    data = base64.b64decode(encoded)
    if len(data) < 12:
        raise ValueError(f"too short: {len(data)} bytes")

    iv = data[0:8]
    want_checksum = int.from_bytes(data[8:12], "big")
    ciphertext = data[12:]

    h = 0x811C9DC5
    for b in ciphertext:
        h = ((h ^ b) * 0x1000193) & _MASK32
    if h != want_checksum:
        raise ValueError(f"FNV checksum mismatch (got {h:08x} want {want_checksum:08x})")

    fnv_low = h & 0xFF

    kb = key.encode()
    kl = len(kb)
    s = bytearray(256)
    for i in range(256):
        s[i] = iv[i & 7] ^ kb[i % kl] ^ fnv_low ^ 0x5A

    prev = s[0]
    for rnd in range(1, 1001):
        mixed = ((prev << 1) & _MASK32) | ((prev & 0xFF) >> 7)
        prev = (iv[(rnd - 1) & 7] ^ rnd ^ mixed ^ prev) & _MASK32
        carry = prev
        for j in range(1, 256):
            b = s[j]
            mixed_b = ((b << 1) & _MASK32) | (b >> 7)
            carry = (carry ^ rnd ^ iv[(rnd - 1 + j) & 7] ^ b ^ mixed_b) & _MASK32
            s[j] = carry & 0xFF
    s[0] = prev & 0xFF

    if not ciphertext:
        return ""

    plain = bytearray(len(ciphertext))
    c0, iv0 = ciphertext[0], iv[0]
    plain[0] = (((c0 ^ iv0 ^ 1) << 5) | ((c0 ^ iv0) >> 3)) & 0xFF ^ s[0]

    for i in range(1, len(ciphertext)):
        x = ((ciphertext[i] ^ ciphertext[i - 1]) ^ (i + 1) ^ iv[i & 7]) & _MASK32
        plain[i] = (((x << 5) & _MASK32 | (x >> 3)) & 0xFF) ^ s[i & 0xFF]

    while plain and plain[-1] == 0:
        plain.pop()

    return plain.decode("utf-8", errors="ignore")


# Encrypted strings from libnativelib.so's FUN_000274f4 — one decrypts to the
# alice.p12 password. Order/content must match internal/cert/decrypt.go.
ENCRYPTED_STRINGS = [
    "eifddmdX43fNE0EVvAB0rGqlJwEpaNNc5CewrEhfsVgeS0CfbIxNSYDIpvo9wqSt41W2oA==",
    "f3mviQpI8d+9AFzoSe5yWZZhV+1zS+2OYmXpXW6R1ATwvGNoZvyoMD9JJYkoTOoqbxPtDw==",
    "EBGjspzB2dbinvUVNvoOnt1vGOqANoq/D1mlGP4hV2R/Z1Bhau27xUQb5lqMq4cOR9X6gQ==",
    "kSpTSBKiPGHYGVSsZMdeFZwvV4qSkvaHAezjgM1mVVc+DoYC+wMUBFtHUTME/lctvSZWCA==",
    "pIWH2NT68cThX5Pi3E1I71nSLxk9be54H4ENogTNEU3A8ORj1yVUOb1SPom979CcoKCV+w==",
    "QfR/UpgYuqCOtsyHL9YkX9TLEig39cvoqGDdf3mI0OKJFTxfoZvWlA00kDNP7y1n9cITqg==",
    "Hl2IGsuYmC3YanEURDbEzTKpjTLY9M1cdYaJNXGZCaKvxuqVr8OaGyKDjEgM5Kwn",
    "EzEWmVPxIClxmrw910OqKL49KihCFNBKM/oyIP+JoOj89Ui6sl7qUBm6yNIF6Rhg",
    "KLs6XVjpDn61H6cs8e9dss2R4Kr7kTcrk4A1OJBe",
    "AW9n9UJgevqQKrOtfUV5uxdTmq/xXS3TTs5dxIgRtOXx/+YbLEO5p/g5AkqFnOiz/iJb/g==",
    "SOnqE/D+v/JHltS+I49tZ2hzNEssVEUt+xq5wmD9pAUb+l3qLlZkTUN54mJDxhw08HOtAw==",
    "kW7WMyMTVL1U4MlzesEiP+8bcyaLp1PQx7EUskLZavXn4SOkOQVb6MexpjA=",
    "V5DnPprXwgQk6fP14EVmUECoiPVjzWfPkthfgqAd9MJwuIjdQ0/1RRjQ7XA=",
    "a1IptAW7x+081RPxToDQn7c28aB7CxY5RoY88nao6B3n7AvoO8l+09QMvlBmuMinHbzRiFuJBuO8XGxwzOhaPeduqUI7e+x5nHx8EA==",
    "Ls/CAqRwvStPokd8o0FTZiKm7e2P72g37ZvIiEOzGUQIhM8/hb0S5VUxEjojmWukUh73dyelQhVNefBiY8kLxPCk/1edN3IlbQ==",
    "3UaW8cbQliNYzy4LZsdO6VocJJELnIYbrkGSMG59zGvAllTZ6fT2KxTjgiBO9/RLqFxM2SsuPNn2STC6xMfsexpsphOxpCTB5usY2g==",
    "PqU/ShbwBjLAeiiguKtKE29cWzJJVzI9dV4aUw==",
    "H1JG9Jm8ZTurGOBYPm038CMYesVBRWVUPDyzMqXWLclr8NIP4qxlRh42qnil7Y57mHowNBhVFn0=",
    "houQvL2SQOVuiQVlE8bNdWB+wwY=",
    "vWrOPxfXl/mPQ8N7VYvvyMNngG5QUD7kMQu6gP0Y5YKZ7AMeMPGXTQ==",
    "8lHPu45LMHfDBNhHi41XnV9clRVn4g/PHeWdMxlfHM8mty6ntMie1B5dz8tKRId1B3xMFQ==",
    "CKq0vH+aIH890hDIf637g4ac5aXy1Wqkd3Erb3IjdNbqE+LrrbqfacudJehNRKrz71VvxA==",
]


def find_p12_password(p12_data: bytes) -> str:
    """Try every known encrypted string until one decrypts the given p12 data."""
    from cryptography.hazmat.primitives.serialization import pkcs12

    for enc in ENCRYPTED_STRINGS:
        try:
            candidate = decrypt_string(enc, "x")
        except ValueError:
            continue
        try:
            pkcs12.load_key_and_certificates(p12_data, candidate.encode())
            return candidate
        except Exception:
            continue
    raise ValueError("alice.p12: no known password matched")
