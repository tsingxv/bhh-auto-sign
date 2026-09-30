# 华为云 FunctionGraph 部署（定制运行时）

百合会签到需要**真浏览器**通过 Cloudflare 挑战，所以本方案把 Python + Chromium（headless）
+ 依赖全部打包进"定制运行时" zip，云函数内直接运行签到脚本。

> ✅ **实测**：本函数包已在本地 Linux（WSL Ubuntu）完整跑通签到流程（自带 Chromium 启动、
> 过 WAF、签到页返回正常、退出码 0）；华为云侧未实测（包体积/冷启动/基础镜像差异）。
> 如遇到环境问题请提 Issue 反馈；若云函数环境确实跑不起来，可继续使用本仓库的
> **GitHub Actions 方案**（实测可用）。

## 一、准备

1. 华为云账号并开通 **函数工作流 FunctionGraph**（和对象存储 OBS）
2. 到本仓库 **Releases** 页面下载 `yamibo-functiongraph.zip`（≈200MB，包含运行时全部内容）

## 二、创建函数

1. FunctionGraph 控制台 → 创建函数 → 运行时选 **"定制运行时"**（如控制台提供"上传 ZIP"或
   "从 OBS 上传"两种入口，包较大建议先上传到 OBS 再选择）
2. 上传 `yamibo-functiongraph.zip`
3. 建议配置：
   | 配置项 | 值 |
   |---|---|
   | 内存 | 1024 MB（浏览器需要） |
   | 超时时间 | 300 秒 |
   | 环境变量 | `YAMIBO_COOKIE` = 你的完整 Cookie 字符串（必填，获取方法见仓库 README） |
   | 环境变量（可选） | `SC3_SENDKEY` = Server酱³ SendKey（推送签到结果） |

   > Cookie 获取：浏览器登录 bbs.yamibo.com 后 F12 → Network → 任一请求 → 请求标头里的完整 cookie 值。
   > 也可以在本仓库运行 `refresh_cookie.py` 获取（见主 README）。

## 三、测试

1. 在函数详情页创建**测试事件**（内容 `{}` 即可）并执行
2. 执行结果里应看到签到输出（`{"exit_code": 0, "output": "...签到成功/今日已打卡..."}`）
3. 首次冷启动较慢（浏览器解压 + 启动，约 20~60 秒），属正常现象

## 四、配置每日定时触发

1. 函数 → 触发器 → 创建触发器 → **定时触发器**
2. Cron 表达式填：`0 37 16 ? * * *`（每天 16:37 UTC = 北京时间 00:37）
   - 具体字段含义以控制台提示为准（华为云 Cron 一般为 秒 分 时 日 月 周 年）
3. 保存并启用

## 五、环境要求（系统库）

Playwright Chromium 依赖以下系统库。若华为云的基础镜像缺少这些库，需改用包含它们
的镜像，或在函数内自行补齐：

```
libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0
libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
libpango-1.0-0 libcairo2 fonts-liberation
```

（Ubuntu 24.04 上部分包名带 t64 后缀，如 `libasound2t64`。）

## 六、常见问题

- **执行超时**：把函数超时调到 300~600 秒；确认内存 ≥ 1024MB
- **浏览器启动失败**：函数环境缺少系统库时（提示 `libnss3` 等缺失），需要改用
  "定制运行时 + 自带库" 的更重方案，或退回 GitHub Actions 方案
- **Cookie 失效**：日志出现 `登录态失效`，重新获取 Cookie 更新环境变量即可
- **包上传失败**：确认走 OBS 上传通道（控制台上传入口对体积有限制）

## 七、目录结构（zip 内）

```
bootstrap          # 定制运行时入口（可执行）
runner.py          # 长轮询事件循环 → 调用签到 → 回传结果
python/            # 自带 CPython 3.12（linux x86_64）
deps/              # patchright / requests 等依赖
browsers/          # chromium-headless-shell
src/               # sign.py 等签到脚本
```
