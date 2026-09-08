# -*- coding: utf-8 -*-
"""Dang ky webhook voi Telegram. Chay MOT LAN sau khi deploy len Render.

    python server/setup_webhook.py https://mds-license-server.onrender.com

Doc BOT_TOKEN va WEBHOOK_SECRET tu .env.local o thu muc goc.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    p = os.path.join(ROOT, ".env.local")
    if not os.path.isfile(p):
        return
    with open(p, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def call(token, method, payload=None):
    url = "https://api.telegram.org/bot%s/%s" % (token, method)
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    load_env()
    token = os.environ.get("BOT_TOKEN", "")
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if not token:
        sys.exit("Thieu BOT_TOKEN trong .env.local")
    if len(sys.argv) < 2:
        sys.exit("Dung: python server/setup_webhook.py https://<ten>.onrender.com")

    base = sys.argv[1].rstrip("/")
    payload = {
        "url": base + "/telegram/webhook",
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
    if secret:
        payload["secret_token"] = secret

    res = call(token, "setWebhook", payload)
    print("setWebhook :", "OK" if res.get("ok") else res)

    info = call(token, "getWebhookInfo")["result"]
    print("URL        :", info.get("url"))
    print("Cho xu ly  :", info.get("pending_update_count"), "su kien")
    if info.get("last_error_message"):
        print("Loi gan nhat:", info["last_error_message"])


if __name__ == "__main__":
    main()
