"""Check the malware scanner end to end with the harmless EICAR test string."""
from app.phase4_ai.scanner import InfectedFile, ScanUnavailable, scan_bytes, scanner_configured


def main():
    if not scanner_configured():
        raise SystemExit("SCANNER NOT CONFIGURED (CLAMAV_HOST is empty)")
    try:
        if scan_bytes(b"%PDF-1.7 harmless test file") is not True:
            raise SystemExit("SCANNER FAILED: clean file was not accepted")
        # Built from two halves so this source file is not itself flagged.
        test_string = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()
        try:
            scan_bytes(test_string)
        except InfectedFile:
            print("SCANNER OK: clean file accepted, test virus blocked")
            return
        raise SystemExit("SCANNER FAILED: test virus was NOT blocked")
    except ScanUnavailable:
        raise SystemExit("SCANNER UNAVAILABLE (it needs a few minutes after start to load signatures)")


if __name__ == "__main__":
    main()
