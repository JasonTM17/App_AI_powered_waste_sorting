"""Build the internal no-login desktop demo beside the production app."""

from __future__ import annotations

from build_exe import BUILD, ROOT, build


def main() -> int:
    result = build(
        app_name="TrashSorterProDemo",
        entrypoint=ROOT / "app" / "demo_main.py",
        workpath=BUILD / "pyinstaller-demo",
        create_shortcuts=False,
    )
    if result == 0:
        guide = ROOT / "dist" / "TrashSorterProDemo" / "HUONG-DAN-MO-DEMO.txt"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text(
            "TRASH SORTER PRO - BAN DEMO NOI BO\n\n"
            "1. Giu nguyen toan bo thu muc TrashSorterProDemo.\n"
            "2. Mo TrashSorterProDemo.exe de chay, khong can dang nhap.\n"
            "3. Cam camera/Arduino truoc khi thu phan cung.\n"
            "4. Ban Demo chi dung de kiem thu noi bo, khong dung de van hanh chinh thuc.\n",
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
