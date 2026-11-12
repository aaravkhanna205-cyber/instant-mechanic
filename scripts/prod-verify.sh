#!/usr/bin/env bash
# Security and health checks against the live site. Run on the server:
#   bash scripts/prod-verify.sh
. "$(dirname "$0")/prod-lib.sh"
set +e +o pipefail
failures=0
pass() { echo "PASS  $1"; }
fail() { echo "FAIL  $1"; failures=$((failures + 1)); }
warn() { echo "WARN  $1"; }
check() { if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (expected $3, got $2)"; fi; }
code() { curl -s -o /dev/null -m 20 -w '%{http_code}' "$@"; }
base="https://$DOMAIN"

echo "== Site and HTTPS: $base"
check "API health over HTTPS" "$(code "$base/api/health")" 200
ready="$(curl -s -m 20 "$base/api/ready")"
if grep -q '"status":"ready"' <<<"$ready"; then pass "Database and Redis ready"; else fail "Database and Redis ready"; fi
home="$(code "$base/")"
case "$home" in 200|301|302|303|307|308) pass "Home page answers ($home)" ;; *) fail "Home page answers (got $home)" ;; esac
check "http:// redirects to https://" "$(code "http://$DOMAIN/")" 308
headers="$(curl -sI -m 20 "$base/api/health")"
if grep -qi '^strict-transport-security:' <<<"$headers"; then pass "HSTS header present"; else fail "HSTS header present"; fi
if grep -qi '^x-content-type-options: *nosniff' <<<"$headers"; then pass "nosniff header present"; else fail "nosniff header present"; fi

echo "== Access control"
check "Anonymous /api/auth/me is refused" "$(code "$base/api/auth/me")" 401
check "Anonymous resume list is refused" "$(code "$base/api/phase4/resumes/mine")" 401
check "Login from a foreign website is refused" "$(code -X POST -H 'Origin: https://evil.example' -H 'Content-Type: application/json' -d '{"email":"nobody@example.com","password":"x"}' "$base/api/auth/login")" 403
for path in /docs /redoc /openapi.json; do
  status="$(code "$base$path")"
  if [ "$status" = "200" ]; then fail "API documentation $path is public"; else pass "API documentation $path is not public ($status)"; fi
done

echo "== Server exposure"
listening="$(ss -tln 2>/dev/null)"
for port in 5432 6379 3310 8000 3000; do
  if grep -Eq "[:.]${port}[[:space:]]" <<<"$listening"; then fail "Port $port is listening on the host"; else pass "Port $port is not exposed"; fi
done
if grep -q "Status: active" <<<"$(ufw status 2>/dev/null)"; then pass "Firewall active"; else fail "Firewall active (run as root to check)"; fi
check ".env.prod readable by owner only" "$(stat -c %a .env.prod)" 600

echo "== Malware scanner (harmless EICAR test string)"
dc exec -T api python - <<'PY'
from app.phase4_ai.scanner import InfectedFile, scan_bytes, scanner_configured
assert scanner_configured(), "CLAMAV_HOST not set"
assert scan_bytes(b"%PDF-1.7 harmless test file") is True, "clean file was not accepted"
test_string = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()
try:
    scan_bytes(test_string)
except InfectedFile:
    print("scanner blocked the test string")
else:
    raise SystemExit("scanner did NOT block the test string")
PY
if [ $? -eq 0 ]; then pass "Scanner accepts clean files and blocks malware"; else fail "Malware scanner (it needs a few minutes after first start to load signatures)"; fi

echo "== Database"
schema="$(dc exec -T api python -m scripts.verify_phase4 2>&1)"
if grep -q "PHASE 4 SCHEMA READY" <<<"$schema"; then pass "Migrations at latest version, pgvector on"; else fail "Database schema"; fi
if [ -n "$(find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.dump' -mtime -2 2>/dev/null | head -n 1)" ]; then pass "Backup from the last 2 days exists"; else warn "No recent backup. Run: bash scripts/prod-backup.sh"; fi

echo
if [ "$failures" -eq 0 ]; then
  echo "ALL AUTOMATED CHECKS PASSED"
  echo "Still to check by hand in a browser: sign in, upload a resume, recruiter evidence, sign out."
else
  echo "$failures CHECK(S) FAILED"
  exit 1
fi
