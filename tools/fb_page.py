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


# ===================== CAU HINH =====================

def load_config():
    """Doc page_id + token tu env, fallback sang fb_config.json."""
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
            "Thieu Page Access Token.\n"
            "  Cach 1: dat bien moi truong FB_PAGE_TOKEN\n"
            "  Cach 2: tao %s voi noi dung {\"page_id\": \"...\", \"page_token\": \"...\"}\n"
            "  (fb_config.json da nam trong .gitignore, khong bi commit)" % CONFIG_FILE
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
    sub.add_parser("info", help="Thong tin Page: ten, luot thich, nguoi theo doi")

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
        "info": cmd_info,
        "post": cmd_post,
        "photo": cmd_photo,
        "posts": cmd_posts,
    }
    handlers[args.cmd](args, page_id, token)


if __name__ == "__main__":
    main()
