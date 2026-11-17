"""Send one test email with the current email settings.

Run inside the worker container (it has the email settings):
    docker exec imhire_phase5_app-p6-worker-1 python -m app.phase8.test_email you@example.com
"""
import os
import sys
from app.phase6_agents.worker import deliver


def main() -> int:
    if len(sys.argv) != 2 or '@' not in sys.argv[1]:
        print('Usage: python -m app.phase8.test_email you@example.com')
        return 2
    mode = os.getenv('PHASE6_DELIVERY_MODE', 'outbox').strip().lower()
    if mode == 'smtp' and os.getenv('PHASE6_SMTP_ENABLED') != 'YES':
        print('FAIL  PHASE6_SMTP_ENABLED is not YES, so nothing is sent. Run scripts\\email-setup.ps1 again.')
        return 1
    try:
        status, detail = deliver(sys.argv[1], 'Test email from Instant Mechanic Hire',
                                 'This is a test. If you can read it, candidate emails will be delivered.', mode)
    except Exception as exc:  # noqa: BLE001 - shown to the person running the check
        print(f'FAIL  {type(exc).__name__}: {exc}')
        if 'Authentication' in type(exc).__name__ or '535' in str(exc):
            print('      Gmail refused the login. Use an App Password (16 letters), not your normal password.')
        return 1
    if status == 'outbox':
        print('NOTE  Email mode is outbox: nothing was sent. Run scripts\\email-setup.ps1 to switch on Gmail.')
        return 1
    print(f'PASS  Gmail accepted the email for {sys.argv[1]}. Check that inbox (and the spam folder).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
