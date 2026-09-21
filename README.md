# 学习通刷课助手 (chaoxing-autowatch)

把超星 / 学习通网页端的视频任务点接口逆向出来，封装成一个**给普通人用**的小工具：
扫码登录 → 读取课程 → 一键刷 / 自选刷。全程纯 HTTP，**不依赖浏览器、不需要 Playwright、不需要装驱动**。

同一套业务代码（`app.py` / `cx_client.py` / `templates/index.html`）同时供两端使用，
差异只在平台层：桌面端用 pywebview + DPAPI，安卓端用系统 WebView + Android Keystore。

## 下载

到 [Releases](../../releases) 下载，按你的设备选：

| 平台 | 文件 | 说明 |
|---|---|---|
| **Windows** | `学习通自动刷视频v1.0.exe` | 双击即用，自带 Python 运行时，不用装任何东西 |
| **Android** | `学习通自动刷视频v1.0.apk` | 装到手机上，后台静音刷，可息屏 |

> 两个产物是同一套逻辑，界面、上报行为完全一致。

**Windows 版**：窗口基于系统自带的 Edge WebView2（Win10 1803+ 默认有）；
万一没有，会自动改用默认浏览器打开 <http://127.0.0.1:8760>。
启动日志：`%USERPROFILE%\chaoxing-autowatch.log`。

**安卓版**：装机后会自动引导你做「保活三件套」——电池优化白名单、后台活动、
锁屏清理。**这一步别跳过**，否则系统会在息屏后杀进程。详见 `docs/` 里的使用说明。

## 功能

- **扫码登录**：跟手机 App 一样扫二维码，不需要输密码（也支持账号密码，凭据本地加密存储）
- **课程列表**：登录后自动拉取你在修的全部课程和任务点进度
- **一键刷 / 自选刷**：整门课一键跑，或者勾选章节自己挑
- **实时进度**：每个视频的上报次数、进度百分比实时回显
- **后台静音**：安卓端跑前台服务 + WakeLock，息屏、切后台都不中断
- **自动续播**：一个视频刷完自动跳下一个；卡住或读不到后端会自己退出并释放锁

## 从源码构建

### 桌面版

```bat
cd desktop
python -m pip install flask requests pywebview pyinstaller
python app.py            :: 直接跑，浏览器开 http://127.0.0.1:8760
python build_exe.py      :: 打包成单文件 exe
```

### 安卓版

需要 **JDK 17**、**Android SDK (compileSdk 34)**、**Gradle 8.7**、**Python 3.12**（Chaquopy 依赖）。

```bat
set ANDROID_TOOLS=D:\android     :: 你放 jdk17 / gradle-8.7 的目录
cd android
python build_apk.py              :: release
python build_apk.py debug        :: debug（开着 WebView 调试口，方便抓包）
```

`build_apk.py` 会先跑 `tools/sync_python.py`，把 `desktop/` 下的三个业务文件同步进
`app/src/main/python/`，保证业务代码只有一份真相。

## 目录结构

```
desktop/     Windows 版（Flask + pywebview + PyInstaller）
android/     安卓版（Chaquopy，把同一份 Python 打包进 APK）
docs/        逆向思路、接口清单、可行性结论、抓包样本
tools/       逆向期用的探针脚本（接口验证用，不参与运行时）
```

## 原理

逆向过程、完整接口清单、每个加密参数的来源都写在 [`docs/`](docs/) 里：

- [`docs/01-思路与方案.md`](docs/01-思路与方案.md) —— 怎么从网页端把上报链路拆出来
- [`docs/02-抓包结果-接口清单.md`](docs/02-抓包结果-接口清单.md) —— 全部接口 + 参数 + 加密字段
- [`docs/03-可行性结论.md`](docs/03-可行性结论.md) —— 验证结果

一句话：视频进度上报就是一个 GET，带上 `objectId` / `duration` / `playingTime` /
`clipTime` / `enc` / `attDurationEnc` 这些参数，`enc` 由 `md5(...)` 派生。
只要按真实播放的节奏滴灌上报，平台侧看到的就是正常播放。

## 免责声明

**仅供学习与接口研究使用。**

- 本工具不提供任何题库、不破解任何付费内容，只做「自动播放 + 按节奏上报进度」。
- 使用本工具可能违反你所在学校的规定或平台服务条款，**风险自负**。
- 作者不对因使用本工具导致的任何后果（包括但不限于成绩、纪律处分、账号封禁）负责。
- 请勿用于商业用途；请勿二次分发到公开平台。

如果你只是想学「一个网页应用的上报链路是怎么被拆解和复现的」，`docs/` 和 `tools/`
里的东西可能比工具本身更有用。

## License

MIT
