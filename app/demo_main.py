"""Internal desktop demo entry point without the Admin login gate."""

from __future__ import annotations

from app.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(require_admin_login=False))
