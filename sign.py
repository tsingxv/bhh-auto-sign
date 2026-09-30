# -*- coding: utf-8 -*-
"""百合会论坛 (bbs.yamibo.com) 每日自动签到。

站点有瑞数（NOX）+ WAF JS 挑战，普通 HTTP 请求会被 405/403 拦截；
本脚本用 patchright（隐身版 Playwright）+ 真 Chrome + xvfb 有头模式完成挑战，
注入登录 Cookie 后执行打卡，并在打卡后复查页面确认真实结果。

环境变量：
  YAMIBO_COOKIE   必填（或保存为脚本同目录的 cookie.txt）。bbs.yamibo.com 的 Cookie 字符串
                  （至少含 EeqY_2132_auth 和 EeqY_2132_saltkey）
  SC3_SENDKEY     可选。Server酱³ SendKey，配置后把结果推送到手机
  SC3_UID         可选。不填则尝试从 SC3_SENDKEY 自动解析
  EXIT_WHEN_FAIL  可选。=on 时失败会以非 0 退出（用于触发 GitHub Actions 失败邮件）
  HEADLESS        可选。=0 使用有头模式（配合 xvfb-run，推荐），默认无头
  BROWSER_CHANNEL 可选。patchright 浏览器通道，默认 chrome，启动失败自动回退自带 chromium
"""

import os
import re
import sys
import time
from datetime import date

import requests

try:
    from patchright.sync_api import sync_playwright

    ENGINE = "patchright"
except ImportError:  # 本地未安装 patchright 时退回原版 playwright
    from playwright.sync_api import sync_playwright

    ENGINE = "playwright"

BASE = "https://bbs.yamibo.com"
SIGN_PAGE = f"{BASE}/plugin.php?id=zqlj_sign"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
if getattr(sys, "frozen", False):  # 打包为 exe 后以可执行文件所在目录为基准
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie.txt")
USER_DATA_DIR = os.environ.get("BROWSER_DATA_DIR", os.path.join(SCRIPT_DIR, "browser-data"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EXIT_OK = 0
EXIT_RETRYABLE = 1
EXIT_AUTH = 2

REAL_PAGE_MARKERS = (
    "formhash",
    "btna",
    "需要先登录",
    "我的打卡动态",
    "messagetext",
    "loginsubmit",
)
CHALLENGE_HTML_MARKERS = ("challenge-platform", "cf_chl_opt", "turnstile")
CHALLENGE_TITLES = ("请稍候…", "请稍候...", "Just a moment...", "Just a moment…")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_cookie_string(raw):
    """解析 cookie 字符串；容忍手工整理的格式：名=值 或 名:值，忽略无分隔符的杂行。"""
    cookies = []
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([\w\-.]+)\s*[=:]\s*(.+)$", part)
        if not m:
            continue
        name, value = m.group(1), m.group(2).strip()
        if not value:
            continue
        if re.search(r"nox|ssxmod", name, re.I):  # 瑞数动态 Cookie 交给浏览器重新生成
            continue
        cookies.append(
            {"name": name, "value": value, "domain": ".yamibo.com", "path": "/"}
        )
    return cookies


def is_challenge(page, html):
    if any(m in html for m in CHALLENGE_HTML_MARKERS):
        return True
    try:
        title = page.title().strip()
    except Exception:
        title = ""
    return title in CHALLENGE_TITLES


def try_pass_challenge(page):
    """尝试主动通过 Cloudflare 挑战：点击 Turnstile 复选框（框架内或坐标点击）。"""
    try:
        for fr in page.frames:
            if "challenges.cloudflare.com" in (fr.url or ""):
                for sel in ("input[type=checkbox]", "#challenge-stage", "label"):
                    try:
                        fr.locator(sel).first.click(timeout=1500)
                        return True
                    except Exception:
                        continue
    except Exception:
        pass
    try:
        box = page.locator('iframe[src*="challenges.cloudflare.com"]').first.bounding_box()
        if box:
            x = box["x"] + 30
            y = box["y"] + 30
            page.mouse.move(x, y, steps=12)
            page.mouse.click(x, y)
            return True
    except Exception:
        pass
    return False


def wait_real_page(page, timeout_s=60, challenge_budget_s=180):
    """等 JS 挑战执行完、跳转回真正的 Discuz 页面；挑战页期间尝试点击验证并额外等待。"""
    start = time.time()
    deadline = start + timeout_s
    challenge_start = None
    last_click = 0.0
    reloaded = False
    html = ""
    while True:
        page.wait_for_timeout(1000)
        try:
            html = page.content()
        except Exception:
            html = ""
        if any(m in html for m in REAL_PAGE_MARKERS):
            return html
        now = time.time()
        if is_challenge(page, html):
            if challenge_start is None:
                challenge_start = now
                deadline = max(deadline, now + challenge_budget_s)
                log("检测到 WAF 挑战页，尝试通过…")
            elapsed = now - challenge_start
            if not reloaded and elapsed > 75:
                reloaded = True
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    log("挑战仍未通过，刷新页面重试")
                except Exception:
                    pass
                continue
            if now - last_click > 9:
                last_click = now
                if try_pass_challenge(page):
                    log(f"已尝试点击挑战框（{int(elapsed)}s）")
        if now >= deadline:
            return html


def extract_stats(html):
    stats = []
    for kw in ("最近打卡", "本月打卡", "连续打卡", "累计打卡", "最近奖励", "累计奖励"):
        m = re.search(kw + r"：([^<\n]+)", html)
        if m:
            stats.append(f"{kw}：{m.group(1).strip()}")
    return stats


def extract_sign_url(html):
    m = re.search(r'href="([^"]*sign=[a-f0-9]{6,})"', html)
    if not m:
        m = re.search(r"(plugin\.php\?id=zqlj_sign(?:&amp;|&)sign=[a-f0-9]{6,})", html)
        if not m:
            return None
    url = m.group(1).replace("&amp;", "&")
    if url.startswith("http"):
        return url
    return f"{BASE}/{url.lstrip('/.')}"


def extract_message(html):
    m = re.search(r'<div[^>]*id="messagetext"[^>]*>.*?<p>(.*?)</p>', html, re.S)
    if not m:
        return ""
    inner = re.sub(r"<script.*?</script>", "", m.group(1), flags=re.S)
    return re.sub(r"<[^>]+>", "", inner).strip()


def push_serverchan3(message, stats):
    sendkey = os.environ.get("SC3_SENDKEY", "").strip()
    if not sendkey:
        return
    uid = os.environ.get("SC3_UID", "").strip()
    if not uid:
        m = re.match(r"^sctp(\d+)t", sendkey)
        uid = m.group(1) if m else ""
    if not uid:
        log("Server酱³：无法从 SendKey 解析 UID，跳过推送")
        return
    title = f"百合会签到 - {date.today().strftime('%Y-%m-%d')}"
    desp = "\n".join([message] + stats)
    try:
        r = requests.post(
            f"https://{uid}.push.ft07.com/send/{sendkey}.send",
            json={"title": title, "desp": desp},
            timeout=15,
        )
        log(f"Server酱³ 推送完成：HTTP {r.status_code}")
    except Exception as e:
        log(f"Server酱³ 推送异常：{e!r}")


def finish(code, message, stats):
    log("结果：" + " | ".join([message] + stats))
    push_serverchan3(message, stats)
    if code != EXIT_OK and os.environ.get("EXIT_WHEN_FAIL") == "on":
        sys.exit(1)
    sys.exit(0)


def run():
    cookie_raw = os.environ.get("YAMIBO_COOKIE", "").strip()
    cookie_source = "环境变量 YAMIBO_COOKIE"
    if not cookie_raw and os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8-sig") as f:
            cookie_raw = f.read().strip()
        cookie_source = "cookie.txt"
    cookies = parse_cookie_string(cookie_raw) if cookie_raw else []
    headless = os.environ.get("HEADLESS", "1") != "0"
    log(f"浏览器引擎：{ENGINE} | 有头模式：{not headless}")
    if not cookie_raw:
        log("未配置 YAMIBO_COOKIE/cookie.txt，使用浏览器档案的登录态（若尚未登录请先运行 login.py）")
    else:
        log(f"Cookie 来源：{cookie_source}")

    with sync_playwright() as p:
        browser = None
        if ENGINE == "patchright":
            # patchright 推荐：真 Chrome + 持久化上下文，且不覆盖 UA/视口
            launch_kwargs = {"headless": headless, "no_viewport": True}
            channel = os.environ.get("BROWSER_CHANNEL", "chrome")
            try:
                context = p.chromium.launch_persistent_context(
                    USER_DATA_DIR, channel=channel, **launch_kwargs
                )
                log(f"浏览器已启动：channel={channel}")
            except Exception as e:
                log(f"channel={channel} 启动失败（{e!r}），回退自带 chromium")
                context = p.chromium.launch_persistent_context(
                    USER_DATA_DIR, **launch_kwargs
                )
        else:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=UA,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1920, "height": 1080},
            )
        context.add_cookies(cookies)
        page = context.new_page()

        def close_all():
            try:
                context.close()
            except Exception:
                pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

        def goto_tolerant(url, retries=2):
            """容忍打卡结果页 3 秒后自动跳转导致的 ERR_ABORTED。"""
            for attempt in range(retries + 1):
                try:
                    return page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    if "ERR_ABORTED" in str(e) and attempt < retries:
                        page.wait_for_timeout(4000)
                        continue
                    if attempt >= retries:
                        raise
            return None

        def load(path, label):
            resp = goto_tolerant(path)
            html = wait_real_page(page)
            st = resp.status if resp else "?"
            log(f"{label} HTTP {st} | 标题：{page.title()} | 页面长度 {len(html)}")
            return html

        html = ""
        for attempt in (1, 2):
            suffix = "（重试）" if attempt == 2 else ""
            if attempt == 2:
                log("挑战未通过，经首页再试一次…")
            load(f"{BASE}/forum.php", f"论坛首页{suffix}")
            html = load(SIGN_PAGE, f"签到页{suffix}")
            if not (
                "__noxExpire" in html or is_challenge(page, html) or len(html) < 500
            ):
                break

        blocked = "__noxExpire" in html or is_challenge(page, html) or len(html) < 500
        if blocked:
            detail = [f"标题：{page.title()}", f"URL：{page.url}", f"HTML 片段：{html[:200]}"]
            try:
                lr = page.goto(
                    f"{BASE}/member.php?mod=logging&action=login",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                lhtml = wait_real_page(page, timeout_s=25, challenge_budget_s=60)
                if is_challenge(page, lhtml):
                    lstate = "挑战页"
                elif "loginsubmit" in lhtml or "formhash" in lhtml:
                    lstate = "可访问"
                else:
                    lstate = "未知"
                detail.append(f"登录页 HTTP {lr.status if lr else '?'} | 状态：{lstate}")
            except Exception as e:
                detail.append(f"登录页探测异常：{e!r}")
            close_all()
            if "__noxExpire" in html:
                finish(EXIT_RETRYABLE, "疑似被 NOX 拦截：页面停留在瑞数挑战页", detail)
            finish(EXIT_RETRYABLE, "WAF 挑战未通过（出口 IP 疑似机房风控）", detail)

        if "需要先登录" in html or "loginsubmit" in html or "mod=logging" in page.url:
            close_all()
            if not cookie_raw:
                finish(
                    EXIT_AUTH,
                    "未登录（游客视图）：请运行 login.py 完成一次登录（或配置 cookie.txt）",
                    [],
                )
            finish(
                EXIT_AUTH,
                "登录态失效：请重新运行 login.py 登录（或更新 cookie.txt）",
                [],
            )

        if "今日已打卡" in html and "点击打卡" not in html:
            stats = extract_stats(html)
            close_all()
            finish(EXIT_OK, "今日已打卡，无需重复签到", stats)

        sign_url = extract_sign_url(html)
        if not sign_url:
            close_all()
            finish(
                EXIT_RETRYABLE,
                "未能找到打卡入口（页面结构可能变化或被拦截）",
                [f"HTML 片段：{html[:200]}"],
            )

        log(f"执行打卡：{sign_url}")
        goto_tolerant(sign_url)
        html2 = wait_real_page(page)
        message = extract_message(html2)
        if message:
            log(f"打卡响应：{message}")
        if message and re.search(r"(请先登录|需要先登录|先登录|登录之后)", message):
            close_all()
            finish(
                EXIT_AUTH,
                "登录态失效（站点提示需先登录）：请重新运行 login.py（或更新 cookie.txt）",
                [],
            )

        page.wait_for_timeout(3500)
        log("复查签到状态…")
        goto_tolerant(SIGN_PAGE)
        html3 = wait_real_page(page)
        stats = extract_stats(html3)
        close_all()

        if "今日已打卡" in html3:
            suffix = f"（{message}）" if message else ""
            finish(EXIT_OK, f"签到成功{suffix}", stats)
        finish(
            EXIT_RETRYABLE,
            "打卡后复查未通过，请手动确认",
            stats + [f"HTML 片段：{html3[:200]}"],
        )


if __name__ == "__main__":
    try:
        run()
    except SystemExit:
        raise
    except Exception as e:
        log(f"未预期错误：{e!r}")
        if os.environ.get("EXIT_WHEN_FAIL") == "on":
            sys.exit(1)
        sys.exit(0)
