"""Malware scanning of uploaded resumes through a ClamAV daemon (clamd).

Set CLAMAV_HOST (and optionally CLAMAV_PORT, default 3310) to enable scanning.
In production the upload endpoint refuses files unless scanning is configured,
and every scanner failure is treated as "do not accept the file" (fail closed).
"""
import os
import socket
import struct

CHUNK = 64 * 1024
CONNECT_TIMEOUT = 10
SCAN_TIMEOUT = 60


class ScanUnavailable(RuntimeError):
    """The scanner could not be reached or returned something unexpected."""


class InfectedFile(ValueError):
    """The scanner reported malware in the file."""


def scanner_configured() -> bool:
    return bool(os.getenv("CLAMAV_HOST", "").strip())


def scan_bytes(data: bytes) -> bool:
    """Scan data with clamd.

    Returns True when the file was scanned and is clean, False when no scanner
    is configured. Raises InfectedFile or ScanUnavailable otherwise.
    """
    host = os.getenv("CLAMAV_HOST", "").strip()
    if not host:
        return False
    try:
        port = int(os.getenv("CLAMAV_PORT", "3310"))
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT) as conn:
            conn.settimeout(SCAN_TIMEOUT)
            conn.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), CHUNK):
                part = data[start:start + CHUNK]
                conn.sendall(struct.pack("!I", len(part)) + part)
            conn.sendall(struct.pack("!I", 0))
            reply = b""
            while not reply.endswith(b"\0") and len(reply) < 4096:
                piece = conn.recv(4096)
                if not piece:
                    break
                reply += piece
    except (OSError, ValueError) as exc:
        raise ScanUnavailable("Malware scanner unavailable") from exc
    verdict = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
    if verdict.endswith("FOUND"):
        raise InfectedFile("Malware detected")
    if verdict.endswith("OK"):
        return True
    raise ScanUnavailable("Unexpected malware scanner reply")
