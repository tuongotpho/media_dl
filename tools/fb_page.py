# -*- coding: utf-8 -*-
"""Cong cu quan ly Fanpage Facebook cho Media Download Studio.

Token KHONG BAO GIO duoc hardcode trong file nay. Script doc cau hinh theo
thu tu uu tien:

  1. Bien moi truong  FB_PAGE_ID / FB_PAGE_TOKEN
  2. File fb_config.json o thu muc goc (da nam trong .gitignore)

Vi du:
    set FB_PAGE_TOKEN=EAA...            (Windows CMD)
    $env:FB_PAGE_TOKEN="EAA..."         (PowerShell)
    export FB_PAGE_TOKEN=EAA...         (bash)

    python tools/fb_page.py token-info
    python tools/fb_page.py info
    python tools/fb_page.py post -m "Da co ban 1.0.1" -l https://media-download-free.web.app/
    python tools/fb_page.py photo -i assets/social/facebook-cover.png -c "Anh bia moi"
    python tools/fb_page.py posts -n 5
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_VERSION = os.environ.get("FB_API_VERSION", "v23.0")
GRAPH = "https://graph.facebook.com"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(ROOT, "fb_config.json")
ENV_FILE = os.path.join(ROOT, ".env.local")


# ===================== CAU HINH =====================

def load_env_file(path=ENV_FILE):
    """Nap KEY=value tu .env.local vao os.environ (khong ghi de bien co san)."""
    if not os.path.isfile(path):
        return
    seen = set()
    with open(path, "r", encoding="utf-8-sig") as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                print("CANH BAO: %s dong %d khong co ten bien, bo qua. "
                      "Dinh dang dung la KEY=value." % (os.path.basename(path), n),
                      file=sys.stderr)
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in seen:
                print("CANH BAO: %s dong %d lap lai bien %s, dung gia tri dau tien."
                      % (os.path.basename(path), n, key), file=sys.stderr)
                continue
            seen.add(key)
            if key and key not in os.environ:
                os.environ[key] = val


def load_config():
    """Doc page_id + token tu env / .env.local, fallback sang fb_config.json."""
    load_env_file()
    cfg = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            die("Khong doc duoc fb_config.json: %s" % e)

    page_id = os.environ.get("FB_PAGE_ID") or cfg.get("page_id")
    token = os.environ.get("FB_PAGE_TOKEN") or cfg.get("page_token")

    if not token:
        die(
            "Thieu Page Access Token. Chon 1 trong 3 cach:\n"
            "  1. Dat bien moi truong FB_PAGE_TOKEN\n"
            "  2. Tao file .env.local o thu muc goc voi dong: FB_PAGE_TOKEN=EAA...\n"
            "  3. Tao %s voi noi dung {\"page_id\": \"...\", \"page_token\": \"...\"}\n"
            "  (ca .env.local lan fb_config.json deu da nam trong .gitignore)" % CONFIG_FILE
        )
    if not page_id:
        page_id = "me"  # Page token mac dinh tro ve chinh Page do
    return page_id, token


def die(msg):
    print("LOI: " + msg, file=sys.stderr)
    sys.exit(1)


def mask(token):
    """Chi hien dau/cuoi token khi can in ra man hinh."""
    return token[:6] + "..." + token[-4:] if len(token) > 12 else "***"


# ===================== GOI GRAPH API =====================

def call(path, token, params=None, data=None, files=None, method=None):
    """Goi Graph API. Token luon di trong header, khong nam tren URL."""
    params = dict(params or {})
    url = "%s/%s/%s" % (GRAPH, API_VERSION, path.lstrip("/"))
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {"Authorization": "Bearer " + token}
    body = None

    if files:
        boundary = uuid.uuid4().hex
        body = encode_multipart(data or {}, files, boundary)
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    elif data:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=body, headers=headers,
                                 method=method or ("POST" if body else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw)["error"]
            die("Graph API %s: %s (code %s, type %s)" % (
                e.code, err.get("message"), err.get("code"), err.get("type")))
        except (ValueError, KeyError):
            die("Graph API %s: %s" % (e.code, raw[:500]))
    except urllib.error.URLError as e:
        die("Khong ket noi duoc Graph API: %s" % e.reason)


def encode_multipart(fields, files, boundary):
    out = []
    for k, v in fields.items():
        out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                    % (boundary, k, v)).encode("utf-8"))
    for name, path in files.items():
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            content = f.read()
        out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                    "Content-Type: %s\r\n\r\n" % (boundary, name, fn, ctype)).encode("utf-8"))
        out.append(content)
        out.append(b"\r\n")
    out.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(out)


# ===================== LENH =====================

def cmd_token_info(args, page_id, token):
    """Kiem tra token con song khong, het han khi nao, co quyen gi."""
    res = call("debug_token", token, params={"input_token": token})
    d = res.get("data", {})
    exp = d.get("expires_at", 0)
    print("Token       : %s" % mask(token))
    print("Hop le      : %s" % ("CO" if d.get("is_valid") else "KHONG"))
    print("Loai        : %s" % d.get("type"))
    print("App ID      : %s" % d.get("app_id"))
    print("Het han     : %s" % ("KHONG BAO GIO (long-lived)" if exp == 0 else
                                __import__("datetime").datetime.fromtimestamp(exp)))
    print("Quyen       : %s" % ", ".join(d.get("scopes", [])))
    if exp:
        print("\nCANH BAO: token nay se het han. Doi sang long-lived Page token.")


def cmd_pages(args, page_id, token):
    """Liet ke cac Page ma token nay quan ly (KHONG in page token)."""
    res = call("me/accounts", token, params={"fields": "id,name,username,tasks"})
    items = res.get("data", [])
    if not items:
        die("Token nay khong quan ly Page nao. Kiem tra lai quyen pages_show_list.")
    print("Cac Page ban quan ly:\n")
    for p in items:
        print("  Ten      : %s" % p.get("name"))
        print("  Page ID  : %s" % p.get("id"))
        print("  Username : %s" % (p.get("username") or "(chua dat)"))
        print("  Quyen    : %s" % ", ".join(p.get("tasks", [])))
        print()
    print("Chay:  python tools/fb_page.py link --page-id <PAGE_ID>")
    print("de lay Page token va luu vao .env.local.")


def write_env(updates, path=ENV_FILE):
    """Ghi/cap nhat KEY=value trong .env.local, giu nguyen cac dong khac."""
    lines = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else None
        if key in updates:
            out.append("%s=%s" % (key, updates[key]))
            seen.add(key)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append("%s=%s" % (k, v))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(l for l in out if l.strip()) + "\n")


def cmd_link(args, page_id, token):
    """Doi user token -> Page token (vinh vien neu co app secret) va luu lai."""
    app_id = os.environ.get("FB_APP_ID")
    app_secret = os.environ.get("FB_APP_SECRET")
    user_token = token

    if app_id and app_secret:
        print("Buoc 1: doi sang long-lived user token (60 ngay)...")
        res = call("oauth/access_token", token, params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        })
        user_token = res["access_token"]
        print("        OK -> %s" % mask(user_token))
    else:
        print("CANH BAO: thieu FB_APP_ID / FB_APP_SECRET trong .env.local.")
        print("          Page token lay ra se het han theo user token hien tai.")
        print("          Them app secret roi chay lai de co token vinh vien.\n")

    print("Buoc 2: lay Page token...")
    res = call("me/accounts", user_token, params={"fields": "id,name,access_token"})
    pages = res.get("data", [])
    if args.page_id:
        pages = [p for p in pages if p.get("id") == args.page_id]
        if not pages:
            die("Khong thay Page ID %s trong danh sach ban quan ly." % args.page_id)
    if len(pages) > 1:
        die("Co %d Page. Chay 'pages' roi chon bang --page-id." % len(pages))

    pg = pages[0]
    page_token = pg["access_token"]
    print("        OK -> Page '%s' (%s)" % (pg.get("name"), pg.get("id")))

    updates = {"FB_PAGE_ID": pg["id"], "FB_PAGE_TOKEN": page_token}
    if user_token != token:
        updates["FB_USER_TOKEN"] = user_token
    write_env(updates)
    print("\nDa luu vao .env.local: %s" % ", ".join(sorted(updates)))
    print("Page token: %s (do dai %d)" % (mask(page_token), len(page_token)))
    print("\nKiem tra lai bang: python tools/fb_page.py token-info")


def cmd_info(args, page_id, token):
    fields = "id,name,username,link,fan_count,followers_count,about,category,verification_status"
    p = call(page_id, token, params={"fields": fields})
    print("Ten         : %s" % p.get("name"))
    print("Username    : %s" % p.get("username"))
    print("Page ID     : %s" % p.get("id"))
    print("Link        : %s" % p.get("link"))
    print("Luot thich  : %s" % p.get("fan_count"))
    print("Nguoi theo  : %s" % p.get("followers_count"))
    print("Hang muc    : %s" % p.get("category"))
    print("Gioi thieu  : %s" % (p.get("about") or "(chua dat)"))


def cmd_post(args, page_id, token):
    data = {"message": args.message}
    if args.link:
        data["link"] = args.link
    if args.draft:
        data["published"] = "false"
    res = call("%s/feed" % page_id, token, data=data)
    pid = res.get("id", "")
    print("Da dang bai: %s" % pid)
    if pid and "_" in pid:
        print("Xem tai    : https://www.facebook.com/%s" % pid.replace("_", "/posts/"))


def cmd_photo(args, page_id, token):
    if not os.path.isfile(args.image):
        die("Khong tim thay file anh: %s" % args.image)
    data = {}
    if args.caption:
        data["caption"] = args.caption
    if args.draft:
        data["published"] = "false"
    res = call("%s/photos" % page_id, token, data=data, files={"source": args.image})
    print("Da tai anh len: post_id=%s photo_id=%s"
          % (res.get("post_id", "-"), res.get("id", "-")))


def cmd_posts(args, page_id, token):
    res = call("%s/posts" % page_id, token, params={
        "fields": "id,created_time,message,permalink_url,shares",
        "limit": args.limit,
    })
    items = res.get("data", [])
    if not items:
        print("Page chua co bai dang nao.")
        return
    for p in items:
        msg = (p.get("message") or "(khong co text)").replace("\n", " ")
        print("- %s | %s" % (p.get("created_time", "")[:16], msg[:70]))
        print("  %s" % p.get("permalink_url", ""))


# ===================== CLI =====================

def main():
    ap = argparse.ArgumentParser(
        description="Quan ly Fanpage Facebook (token doc tu FB_PAGE_TOKEN hoac fb_config.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("token-info", help="Kiem tra token con song, het han khi nao, quyen gi")
    sub.add_parser("pages", help="Liet ke cac Page ma token dang quan ly")
    sub.add_parser("info", help="Thong tin Page: ten, luot thich, nguoi theo doi")

    p = sub.add_parser("link", help="Doi user token -> Page token va luu vao .env.local")
    p.add_argument("--page-id", help="Chi dinh Page ID neu ban quan ly nhieu Page")

    p = sub.add_parser("post", help="Dang bai text (kem link neu co)")
    p.add_argument("-m", "--message", required=True, help="Noi dung bai dang")
    p.add_argument("-l", "--link", help="Link dinh kem")
    p.add_argument("--draft", action="store_true", help="Luu nhap, khong dang cong khai")

    p = sub.add_parser("photo", help="Dang anh kem chu thich")
    p.add_argument("-i", "--image", required=True, help="Duong dan file anh")
    p.add_argument("-c", "--caption", help="Chu thich")
    p.add_argument("--draft", action="store_true", help="Luu nhap, khong dang cong khai")

    p = sub.add_parser("posts", help="Liet ke cac bai dang gan day")
    p.add_argument("-n", "--limit", type=int, default=10)

    args = ap.parse_args()
    page_id, token = load_config()

    handlers = {
        "token-info": cmd_token_info,
        "pages": cmd_pages,
        "link": cmd_link,
        "info": cmd_info,
        "post": cmd_post,
        "photo": cmd_photo,
        "posts": cmd_posts,
    }
    handlers[args.cmd](args, page_id, token)


if __name__ == "__main__":
    main()
