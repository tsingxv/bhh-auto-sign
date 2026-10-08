# bhh-auto-sign

百合会论坛（[bbs.yamibo.com](https://bbs.yamibo.com)，简称 bhh）每日自动签到。

站点有瑞数（NOX）+ Cloudflare 的 JS 挑战，普通 HTTP 脚本会被 405/403 拦截；本项目用 **patchright（隐身版 Playwright）+ 真 Chrome** 完成挑战（含 Turnstile 点击），注入登录 Cookie 后执行打卡，并在打卡后复查页面确认真实结果。

**四种用法任选：**

| 方式 | 适合谁 | 需要什么 |
|---|---|---|
| [① GitHub Actions 托管](#方式一github-actions-托管推荐) | 不想开电脑 | GitHub 账号（免费） |
| [② 本地 exe（可配合 MAA 触发）](#方式二本地-exe可配合-maa-触发) | 电脑常开、玩明日方舟用 MAA | 下载 exe 即用 |
| [③ 华为云 FunctionGraph](#方式三华为云-functiongraph) | 想放云函数 | 华为云账号（见 [cloud_functions/](cloud_functions/README.md)） |
| [④ 源码本地运行](#方式四源码本地运行可选) | 开发者 | Python 3.9+ |

---

## 方式一：GitHub Actions 托管（推荐）

1. 点右上角 **Use this template → Create a new repository**，创建你自己的仓库（**建议选 Private**，原因见注意事项）
2. 获取百合会的登录 Cookie（二选一）：
   - **一键方式**：把代码下载到本地，运行 `refresh_cookie.py`，在弹出的浏览器里登录一次，脚本会自动把 Cookie 写入你仓库的 secret（见下文）
   - **手工方式**：浏览器登录 bbs.yamibo.com 后按 F12：
     - `Network` → 刷新页面 → 点任一 `bbs.yamibo.com` 请求 → 在 `请求标头` 里复制完整的 `cookie:` 值
     - 或 `Application` → `Cookies` → `https://bbs.yamibo.com`，复制 `EeqY_2132_saltkey` 与 `EeqY_2132_auth` 两个值，拼成：
       `EeqY_2132_saltkey=值1; EeqY_2132_auth=值2`
3. 在你自己的仓库进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`：
   - 名称 `YAMIBO_COOKIE`，值为上一步复制的完整 Cookie 字符串
4. 打开仓库 `Actions` 页启用工作流，选 `Auto Sign` → `Run workflow` 手动跑一次确认

之后每天北京时间 **00:37** 自动签到（也可随时手动触发）。

---

## 方式二：本地 exe（可配合 MAA 触发）

1. 到本仓库 [Releases](../../releases) 下载 `bhh-auto-sign.exe`，放到任意目录（如 `D:\bhh-sign\`）
2. **双击运行**：首次会弹出浏览器窗口要求登录百合会（勾选"记住我"，登录一次即可，之后不再弹）；随后自动完成签到
   - 结果会同时打印在窗口里并写入同目录的 `bhh-auto-sign.log`
3. **配合 MAA**：MAA → 设置 → 连接设置 → **运行前脚本**，填入 exe 的完整路径。
   之后每次 MAA 连接模拟器时会自动帮你签到（无窗口，静默完成）

> 想自己重新打包：把源码放到本地后运行 `build_exe.bat` 即可（需已装 Python 和 Chrome）。

---

## 方式三：华为云 FunctionGraph

把 Python + Chromium + 依赖整体打包为"定制运行时"，在华为云函数内运行签到，
可配定时触发器每天自动执行。完整步骤见 **[cloud_functions/README.md](cloud_functions/README.md)**，
对应的函数包 `yamibo-functiongraph.zip` 在 [Releases](../../releases) 下载。

> 说明：本函数包的结构与运行逻辑已在本地 Linux 环境验证通过；华为云侧未实测，
> 如遇到环境问题欢迎提 Issue。若云函数跑不起来，可继续用方式一（实测可用）。

---

## 方式四：源码本地运行（可选）

```bash
pip install -r requirements.txt
python login.py     # 弹窗登录一次，登录态保存在 browser-data/ 目录
python sign.py      # 执行签到
```

或把完整 Cookie 存为脚本同目录的 `cookie.txt`（格式见 `cookie.txt.example`）后运行 `python sign.py`；
双击 / 自动化运行可直接用 `python app.py`（自动判断登录态并签到）。

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

## 失败提醒（可选）

仓库 `Settings` → `Secrets and variables` → `Actions` → `Variables` 新建：

| 名称 | 值 | 效果 |
|---|---|---|
| `EXIT_WHEN_FAIL` | `on` | 签到失败时工作流标红，GitHub 默认会给账号发失败邮件 |
| Secret `SC3_SENDKEY` | Server酱³ SendKey | 每次签到后把结果推送到手机（exe / 云函数模式同样支持该环境变量） |

## 注意事项

- **Cookie 等同账号登录凭证**：部署仓库建议设为 **Private**；不要把 Cookie 或 secret 内容发到任何公开地方
- Cookie 过期后，日志会出现"登录态失效"，按上文刷新即可
- 实测（2026-09-29）：GitHub 托管 runner **携带有效 Cookie** 时可正常通过站点 WAF 并签到；不带 Cookie 的匿名请求会被 Cloudflare 挑战拦截
- GitHub 定时任务实际启动常比 cron 晚 2–6 小时，可能撞上百合会凌晨的每日维护窗口；工作流会每 10 分钟自动重试，维护结束即签到
- 仅供个人学习与自动化使用；脚本每天只发起一次最小请求，请遵守站点规则

## 常见问题

| 现象 | 处理 |
|---|---|
| 日志出现"WAF 挑战未通过" | 多为偶发风控，重跑一次；持续出现先确认 Cookie 是否失效 |
| 日志出现"站点每日维护中" | 站点维护中，脚本以退出码 3 结束，工作流每 10 分钟自动重试（最多 10 次），无需处理；整轮都没签上才会标红发邮件 |
| exe 双击一闪而过 | 属正常（跑完自动退出），结果在 `bhh-auto-sign.log` |
| MAA 启动变慢 | 运行前脚本是同步执行的，浏览器启动需要十几秒，属正常 |

## 致谢

实现思路参考了开源项目：

- [jckling/Daily-Bonus](https://github.com/jckling/Daily-Bonus)（WAF 挑战处理、打卡后复查思路）
- [xixio2/yamibo-sign](https://github.com/xixio2/yamibo-sign)（Discuz 签到流程）
- [LittleSurvival/YamiboAutoSignBot](https://github.com/LittleSurvival/YamiboAutoSignBot)（Cookie 方案）

## License

[MIT](LICENSE)
