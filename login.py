# -*- coding: utf-8 -*-
"""交互式登录助手：在独立浏览器配置（browser-data）里登录一次百合会。

登录态会保存在该配置里，之后 sign.py（定时任务）直接复用，无需再提供 cookie。
建议登录时勾选“记住我/自动登录”，可保持较长时间免登录。

用法：双击或运行 `python login.py`，在弹出的浏览器窗口里完成登录，
程序检测到登录成功后会自动退出。
"""

import os
import sys
import time

try:
    from patchright.sync_api import sync_playwright
except ImportError:
    from playwright.sync_api import sync_playwright

if getattr(sys, "frozen", False):  # 打包为 exe 后以可执行文件所在目录为基准
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = os.environ.get("BROWSER_DATA_DIR", os.path.join(SCRIPT_DIR, "browser-data"))
BASE = "https://bbs.yamibo.com"
LOGIN_PAGE = f"{BASE}/member.php?mod=logging&action=login"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            channel=os.environ.get("BROWSER_CHANNEL", "chrome"),
            headless=False,
            no_viewport=True,
        )
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=60000)
        print("请在浏览器窗口中登录百合会（建议勾选“记住我/自动登录”），登录成功后本程序会自动检测并退出。", flush=True)

        deadline = time.time() + 900
        ok = False
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            try:
                url = page.url
                html = page.content()
            except Exception:
                continue
            if "space-uid-" in html or "action=logout" in html or "我的打卡动态" in html:
                ok = True
                break
        if ok:
            print("已检测到登录成功，登录态已保存，之后 sign.py 可直接使用。", flush=True)
        else:
            print("等待超时（15 分钟）：未检测到登录成功。", flush=True)
        context.close()


if __name__ == "__main__":
    main()
