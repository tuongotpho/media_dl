"""Script xoa license va reset trang thai ve 'Chua Kich Hoat' de test.

Chay: python reset_license.py
"""
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
lic_file = os.path.join(base_dir, "license.dat")
app_file = os.path.join(base_dir, "approved_keys.json")
tg_file = os.path.join(base_dir, "time_guard.dat")
tr_file = os.path.join(base_dir, "trial_used.dat")

deleted = False

for path in [lic_file, app_file, tg_file, tr_file]:
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"[OK] Da xoa file: {os.path.basename(path)}")
            deleted = True
        except Exception as e:
            print(f"[!] Khong xoa duoc {os.path.basename(path)}: {e}")

# Xoa trong Windows Registry neu co
if os.name == 'nt':
    try:
        import winreg
        key_path = r"SOFTWARE\MediaDownloadStudio\Trial"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        print("[OK] Da reset Registry trial key")
    except Exception:
        pass

if not deleted:
    print("[INFO] Ung dung hien tai dang o trang thai 'Chua Kich Hoat'.")
else:
    print("\n[DONE] Da reset thanh cong! F5 lai trang web de kiem tra trang thai Chua Kich Hoat.")
