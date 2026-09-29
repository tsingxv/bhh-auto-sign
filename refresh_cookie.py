# -*- coding: utf-8 -*-
"""一键刷新 GitHub 仓库的 YAMIBO_COOKIE：打开登录窗口 → 登录 → 导出 cookie → 写入 secret。

用法：
    set GITHUB_REPO=你的用户名/仓库名     # Windows；Linux/macOS 用 export
    python refresh_cookie.py

在目标仓库的目录内运行时，会自动从 git remote 推断仓库名，无需设置 GITHUB_REPO。
"""

import base64
import os
import re
import subprocess
import sys
import time

import requests
from nacl import encoding, public

try:
    from patchright.sync_api import sync_playwright
except ImportError:
    from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.environ.get("BROWSER_DATA_DIR", os.path.join(SCRIPT_DIR, "browser-data"))
BASE = "https://bbs.yamibo.com"
LOGIN_PAGE = f"{BASE}/member.php?mod=logging&action=login"
SECRET_NAME = "YAMIBO_COOKIE"


def resolve_repo():
    repo = os.environ.get("GITHUB_REPO", "").strip()
    if repo:
        return repo.strip("/")
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=SCRIPT_DIR, capture_output=True, text=True,
        )
        m = re.search(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?\s*$", out.stdout.strip())
        if m:
            return m.group(1)
    except Exception:
        pass
    raise SystemExit("请先用环境变量指定目标仓库，例如：set GITHUB_REPO=你的用户名/仓库名")


def login_and_export():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel=os.environ.get("BROWSER_CHANNEL", "chrome"),
            headless=False,
            no_viewport=True,
        )
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=60000)
        print("请在弹出的浏览器窗口中登录百合会（已登录会自动跳过）；程序检测到登录后自动继续。", flush=True)

        deadline = time.time() + 900
        ok = False
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            try:
                html = page.content()
            except Exception:
                continue
            if "space-uid-" in html or "action=logout" in html or "我的打卡动态" in html:
                ok = True
                break
        if not ok:
            context.close()
            raise SystemExit("等待登录超时（15 分钟），未导出 cookie。")

        cookies = context.cookies(BASE + "/")
        context.close()

    keep = [c for c in cookies if not re.search(r"nox|ssxmod|_ga|_gid", c["name"], re.I)]
    if not any(c["name"].endswith("_auth") for c in keep):
        raise SystemExit("未找到登录 cookie（_auth），请确认已在窗口中登录成功。")
    return "; ".join(f"{c['name']}={c['value']}" for c in keep)


def get_github_token():
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
    )
    for line in out.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise SystemExit("无法从 git credential 取到 GitHub token（本机需已登录过 GitHub）。")


def encrypt(public_key: str, secret_value: str) -> str:
    pk = public.PublicKey(public_key.encode(), encoding.Base64Encoder())
    return base64.b64encode(public.SealedBox(pk).encrypt(secret_value.encode())).decode()


def set_secret(repo, value):
    token = get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "refresh-cookie",
    }
    key = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=30,
    ).json()
    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{SECRET_NAME}",
        headers=headers,
        json={"encrypted_value": encrypt(key["key"], value), "key_id": key["key_id"]},
        timeout=30,
    )
    if r.status_code not in (201, 204):
        raise SystemExit(f"写入 secret 失败：HTTP {r.status_code} {r.text[:200]}")
    print(f"已更新 {repo} 的 {SECRET_NAME} secret（HTTP {r.status_code}）", flush=True)


def main():
    repo = resolve_repo()
    print(f"目标仓库：{repo}", flush=True)
    value = login_and_export()
    print(f"已导出 cookie，长度 {len(value)}", flush=True)
    set_secret(repo, value)
    print("完成：云端签到已就绪。", flush=True)


if __name__ == "__main__":
    main()
