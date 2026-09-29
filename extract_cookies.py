# -*- coding: utf-8 -*-
"""从已登录的浏览器档案（browser-data）中导出 bbs.yamibo.com 的全部 cookie（含 HttpOnly），
输出为可直接用作 YAMIBO_COOKIE 的单行字符串，保存到 cookie-export.txt。"""

import os
import re
import sys

try:
    from patchright.sync_api import sync_playwright
except ImportError:
    from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.environ.get("BROWSER_DATA_DIR", os.path.join(SCRIPT_DIR, "browser-data"))
OUT = os.path.join(SCRIPT_DIR, "cookie-export.txt")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel=os.environ.get("BROWSER_CHANNEL", "chrome"),
            headless=True,
            no_viewport=True,
        )
        cookies = context.cookies("https://bbs.yamibo.com/")
        context.close()

    keep = [c for c in cookies if not re.search(r"nox|ssxmod|_ga|_gid", c["name"], re.I)]
    line = "; ".join(f"{c['name']}={c['value']}" for c in keep)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(line + "\n")

    print("导出 cookie 数:", len(keep))
    for c in keep:
        print(f"  {c['name']} len={len(c['value'])}")
    print("已写入:", OUT)


if __name__ == "__main__":
    main()
