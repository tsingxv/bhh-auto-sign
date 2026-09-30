# -*- coding: utf-8 -*-
"""bhh-auto-sign 可执行入口（打包 exe / 双击运行 / 作为 MAA 运行前脚本）。

流程：检查登录态（cookie.txt 或浏览器档案）→ 未登录则弹窗登录 → 执行签到。
输出同时写到控制台和脚本同目录的 bhh-auto-sign.log。

用法：
    双击运行                     首次会弹出登录窗口，登录一次即可
    MAA → 连接设置 → 运行前脚本   填本 exe 的完整路径
"""

import os
import sys
import time

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(BASE_DIR, "bhh-auto-sign.log")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def _profile_logged_in():
    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        from playwright.sync_api import sync_playwright
    import sign as signmod

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                signmod.USER_DATA_DIR,
                channel=os.environ.get("BROWSER_CHANNEL", "chrome"),
                headless=True,
                no_viewport=True,
            )
            page = ctx.new_page()
            page.goto(signmod.SIGN_PAGE, wait_until="domcontentloaded", timeout=60000)
            html = signmod.wait_real_page(page)
            ok = "需要先登录" not in html and "loginsubmit" not in html
            ctx.close()
            return ok
    except Exception:
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    logf = open(LOG_FILE, "a", encoding="utf-8")
    logf.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} 启动 =====\n")
    sys.stdout = _Tee(sys.stdout, logf)
    sys.stderr = _Tee(sys.stderr, logf)

    import sign as signmod

    have_cookie = os.path.exists(signmod.COOKIE_FILE) or os.environ.get("YAMIBO_COOKIE", "").strip()

    if not have_cookie and not _profile_logged_in():
        print("未检测到登录态：即将打开浏览器窗口，请登录百合会（建议勾选“记住我/自动登录”）。")
        import login as loginmod

        loginmod.main()

    signmod.run()


if __name__ == "__main__":
    main()
