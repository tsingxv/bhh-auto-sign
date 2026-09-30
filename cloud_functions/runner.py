#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FunctionGraph 定制运行时循环：长轮询接收事件 → 执行签到 → 回传结果。

协议：GET  {RUNTIME_API_ADDR}/v1/runtime/invocation/request        （阻塞等待事件）
      POST {RUNTIME_API_ADDR}/v1/runtime/invocation/response/<id> （成功回传）
      POST {RUNTIME_API_ADDR}/v1/runtime/invocation/error/<id>    （失败回传）
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("RUNTIME_API_ADDR", "")
if API and not API.startswith("http"):
    API = "http://" + API


def log(msg):
    print(f"[runner] {msg}", flush=True)


def get_event():
    req = urllib.request.Request(f"{API}/v1/runtime/invocation/request")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def post(path, data=b""):
    req = urllib.request.Request(
        API + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def run_sign():
    env = dict(os.environ)
    env["HEADLESS"] = "1"
    env.setdefault("BROWSER_DATA_DIR", "/tmp/yamibo-browser-data")
    py = os.path.join(BASE, "python", "bin", "python3")
    proc = subprocess.run(
        [py, os.path.join(BASE, "src", "sign.py")],
        capture_output=True, text=True, env=env, timeout=600,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def main():
    if not API:
        # 本地调试模式：无 RUNTIME_API_ADDR 时直接跑一次
        code, out = run_sign()
        print(out)
        sys.exit(0 if code == 0 else 1)

    log("started, waiting for events...")
    while True:
        try:
            event = get_event()
        except Exception:
            time.sleep(1)
            continue
        rid = str(event.get("requestId") or event.get("request_id") or "")
        log(f"invocation {rid}")
        try:
            code, out = run_sign()
            body = json.dumps({"exit_code": code, "output": out[-4000:]}, ensure_ascii=False).encode()
            post(f"/v1/runtime/invocation/response/{rid}", body)
            log(f"responded {rid}")
        except Exception as e:
            try:
                post(f"/v1/runtime/invocation/error/{rid}", str(e).encode())
            except Exception:
                pass


if __name__ == "__main__":
    main()
