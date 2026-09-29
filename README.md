# bhh-auto-sign

百合会论坛（[bbs.yamibo.com](https://bbs.yamibo.com)，简称 bhh）每日自动签到，跑在 **GitHub Actions** 上，不需要自己开机挂机。

站点有瑞数（NOX）+ Cloudflare 的 JS 挑战，普通 HTTP 脚本会被 405/403 拦截；本项目用 **patchright（隐身版 Playwright）+ 真 Chrome** 完成挑战（含 Turnstile 点击），注入登录 Cookie 后执行打卡，并在打卡后复查页面确认真实结果。

## 部署到自己的账号

1. 点右上角 **Use this template → Create a new repository**，创建你自己的仓库（**建议选 Private**，原因见注意事项）
2. 获取百合会的登录 Cookie（二选一）：
   - **一键方式**：把代码下载到本地，运行 `refresh_cookie.py`，在弹出的浏览器里登录一次，脚本会自动把 Cookie 写入你仓库的 secret（见下文）
   - **手工方式**：浏览器登录 bbs.yamibo.com 后按 F12：
     - `Network` → 刷新页面 → 点任一 `bbs.yamibo.com` 请求 → 在 `请求标头` 里复制完整的 `cookie:` 值
     - 或 `Application` → `Cookies` → `https://bbs.yamibo.com`，复制 `EeqY_2132_saltkey` 与 `EeqY_2132_auth` 两个值，拼成：
       `EeqY_2132_saltkey=值1; EeqY_2132_auth=值2`
3. 在你自己的仓库进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：
   - 名称 `YAMIBO_COOKIE`
   - 值为上一步复制的完整 Cookie 字符串
4. 打开仓库 `Actions` 页启用工作流，选 `Auto Sign` → `Run workflow` 手动跑一次确认

之后每天北京时间 **00:37** 自动签到（也可随时手动触发）。

## 一键刷新 Cookie（可选）

Cookie 会过期（约数周~数月），失效时重新获取并更新 secret 即可：

```bash
pip install -r requirements.txt
patchright install chrome

# 指定你的仓库（在仓库目录内运行可自动识别）
set GITHUB_REPO=你的用户名/仓库名        # Windows CMD
export GITHUB_REPO=你的用户名/仓库名     # Linux / macOS / Git Bash

python refresh_cookie.py
```

脚本会弹出浏览器窗口，登录一次百合会，随后自动导出 Cookie 并加密写入你仓库的 `YAMIBO_COOKIE` secret。
（需要本机 git 已登录 GitHub，脚本通过 git 凭据访问 GitHub API。）

## 本地运行（可选，不依赖 GitHub）

```bash
python login.py     # 弹窗登录一次，登录态保存在 browser-data/ 目录
python sign.py      # 执行签到
```

或把完整 Cookie 存为脚本同目录的 `cookie.txt`（格式见 `cookie.txt.example`）后运行 `python sign.py`。

## 失败提醒（可选）

仓库 `Settings` → `Secrets and variables` → `Actions` → `Variables` 新建：

| 名称 | 值 | 效果 |
|---|---|---|
| `EXIT_WHEN_FAIL` | `on` | 签到失败时工作流标红，GitHub 默认会给账号发失败邮件 |

## 注意事项

- **Cookie 等同账号登录凭证**：部署仓库建议设为 **Private**；不要把 Cookie 或 secret 内容发到任何公开地方
- Cookie 过期后，日志会出现"登录态失效"，按上文刷新即可
- 实测（2026-09-29）：GitHub 托管 runner **携带有效 Cookie** 时可正常通过站点 WAF 并签到；不带 Cookie 的匿名请求会被 Cloudflare 挑战拦截
- 仅供个人学习与自动化使用；脚本每天只发起一次最小请求，请遵守站点规则

## 致谢

实现思路参考了开源项目：

- [jckling/Daily-Bonus](https://github.com/jckling/Daily-Bonus)（WAF 挑战处理、打卡后复查思路）
- [xixio2/yamibo-sign](https://github.com/xixio2/yamibo-sign)（Discuz 签到流程）
- [LittleSurvival/YamiboAutoSignBot](https://github.com/LittleSurvival/YamiboAutoSignBot)（Cookie 方案）

## License

[MIT](LICENSE)
