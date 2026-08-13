"""CLI tool tao license key (backup khi khong dung Telegram bot).

Cach dung:
    python license_tool.py --machine-id ABC123DEF456
    python license_tool.py --machine-id ABC123DEF456 --days 180
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.license import generate_license_key


def main():
    parser = argparse.ArgumentParser(
        description="Tao license key cho Media Download Studio")
    parser.add_argument("--machine-id", "-m", required=True,
                        help="Ma may 12 ky tu (hien tren app cua nguoi dung)")
    parser.add_argument("--days", "-d", type=int, default=365,
                        help="So ngay hieu luc (mac dinh: 365)")
    args = parser.parse_args()

    mid = args.machine_id.upper().strip()
    if len(mid) != 12:
        print(f"[!] Ma may phai dung 12 ky tu. Ban nhap: {mid} ({len(mid)} ky tu)")
        sys.exit(1)

    key, expiry = generate_license_key(mid, args.days)

    print()
    print("=" * 48)
    print("  LICENSE KEY DA TAO THANH CONG!")
    print("=" * 48)
    print(f"  Ma may  : {mid}")
    print(f"  Key     : {key}")
    print(f"  Het han : {expiry.strftime('%d/%m/%Y')}")
    print(f"  Hieu luc: {args.days} ngay")
    print("=" * 48)
    print()
    print("  Gui key tren cho nguoi dung de kich hoat app.")
    print()


if __name__ == "__main__":
    main()
