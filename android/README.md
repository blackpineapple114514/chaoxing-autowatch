# Android 版（Chaquopy 真 APK）

把桌面的 `学习通自动刷视频` 移植成**真 APK**：手机本地跑，不用电脑、不用 Termux。
业务代码（`app.py` / `cx_client.py` / `templates/index.html`）**一行没重写**，
只换掉了平台层（窗口→WebView、DPAPI→Keystore、托盘/单实例→前台服务）。

## 为什么是 Chaquopy

| 方案 | 结论 |
|---|---|
| Chaquopy（选它） | 把 CPython 3.12 + Flask 打进 APK，原 Python 代码直接跑，APK 约 23 MB |
| Termux | 要用户手动装环境、敲命令，不算「发给同学就能装」 |
| 手机遥控电脑 | 夜里还得开着电脑，违背初衷 |
| Kivy/BeeWare | 要重写 UI 与网络层，工作量对不上收益 |

## 目录

```
android/
├── build_apk.py              # 一键出包（同步代码 → gradle → 拷产物）
├── settings.gradle           # 仓库与模块
├── build.gradle              # AGP 8.6.0 + Chaquopy 17.0.0
├── gradle.properties         # 指向本机 JDK17
├── local.properties          # Android SDK 路径
├── tools/sync_python.py      # 把 ../../app 的三个文件同步进来
└── app/
    ├── build.gradle          # minSdk 24 / targetSdk 34 / py3.12 / pip: flask+requests+cryptography
    ├── src/main/AndroidManifest.xml
    ├── src/main/java/com/hpp/chaoxingwatch/
    │   ├── App.java          # 起 Python + 建通知通道 + 拉起 Flask
    │   ├── Server.java       # 后台线程跑 app.serve()，持有本机令牌
    │   ├── MainActivity.java # WebView 装界面（就是桌面那份 index.html）
    │   ├── Bridge.java       # window.AndroidBridge：保活/通知/电池白名单
    │   ├── BrushService.java # ★ 抗杀后台主力：前台服务 + WakeLock + WiFi Lock
    │   ├── StopReceiver.java # 常驻通知上的「停止刷课」
    │   ├── Creds.java        # 记住登录 = Keystore AES-GCM
    │   ├── Notifications.java
    │   └── Http.java
    ├── src/main/python/      # ← sync_python.py 生成，勿手改
    └── src/main/res/
```

## 构建环境（本机已就位）

| 组件 | 路径 |
|---|---|
| JDK 17 | `<android-sdk-dir>\jdk17` |
| Android SDK | `<android-sdk-dir>\sdk`（platform-tools, platforms;android-34, build-tools;34.0.0） |
| Gradle 8.7 | `<android-sdk-dir>\gradle-8.7` |
| 构建用 Python | `python`（必须与 app 的 3.12 一致） |

出包：

```powershell
cd <repo>\android
python build_apk.py            # release，产物 dist\学习通自动刷视频v1.0.apk
python build_apk.py debug      # 快速自测
```

装到手机：

```powershell
<android-sdk-dir>\sdk\platform-tools\adb.exe install -r dist\学习通自动刷视频v1.0.apk
```

## 抗杀后台（★ 用户核心诉求）

刷课要连跑 6–7 小时，Android 默认会把后台进程清掉。这里做了五层：

1. **前台服务**（`BrushService`）：开刷即起，常驻通知「正在刷课」，系统不会随便收走。
   用 `foregroundServiceType="specialUse"` 而不是 `dataSync` —— 后者在 Android 15 上有
   **6 小时硬上限**，会正好卡在夜里刷到一半。
2. **PARTIAL_WAKE_LOCK**：熄屏后 CPU 继续跑。否则屏幕一黑，滴灌就停了。
   （带 12 小时上限，跑完自动释放，不白耗电。）
3. **WiFi Lock**：防止 WiFi 在休眠时降功耗断流。
4. **电池优化白名单**：界面上有「加入电池优化白名单」按钮，
   直接调 `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`。
5. **国产 ROM 引导**：界面上一段图文提示 + 「应用详情 / 自启动」按钮直达系统页。

**用户要做的**（界面里也写了）：

- 点「加入电池优化白名单」→ 允许
- 小米：省电策略改「无限制」；华为：应用启动管理改「手动管理」全开；
  OPPO/vivo：允许后台运行 + 在最近任务里给本应用加锁
- 开刷后出现「正在刷课」常驻通知，**不要划掉**（划掉 = 停服务）

## 状态

- [x] 工具链落地（JDK17/SDK34/Gradle 8.7）
- [x] 首次 `assembleDebug` 通过（23.2 MB，含 arm64-v8a + x86_64）
- [x] **模拟器实机验证**：装包 → Python 解包 → Flask 起在 `127.0.0.1:8760` → 页面加载 → 扫码登录自动起
- [x] **抗杀后台验证**：前台服务 `types=40000000`(specialUse) + PARTIAL_WAKE_LOCK + WiFiLock 均实测持有；
      退后台/灭屏 60 秒后进程与后端仍活
- [x] 修掉两个实机才暴露的 bug（轮询主线程 / 无限重试占锁）
- [x] 出 release APK：`dist\学习通自动刷视频v1.0.apk`（21.3 MB）
- [ ] 真机夜间连跑 6-7 小时（需真实账号）

## 怎么验（本机可复现）

模拟器（无头，需 WHPX）：

```powershell
$SDK="<android-sdk-dir>\sdk"
$env:ANDROID_HOME=$SDK
& "$SDK\emulator\emulator.exe" -avd cx34 -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect
```

装包 + 起应用：

```powershell
$adb="<android-sdk-dir>\sdk\platform-tools\adb.exe"
& $adb install -r dist\学习通自动刷视频v1.0.apk
& $adb shell am start -n com.hpp.chaoxingwatch/.MainActivity
& $adb forward tcp:8760 tcp:8760      # 然后浏览器开 http://127.0.0.1:8760 与手机内同一页面
```

看后台保活是否真的生效（关键三行）：

```powershell
& $adb shell "dumpsys activity services com.hpp.chaoxingwatch"   # isForeground=true / types=40000000
& $adb shell "dumpsys power"                                  # PARTIAL_WAKE_LOCK 'chaoxingwatch:brush'
& $adb logcat -b all | Select-String python.stderr             # Werkzeug 访问日志
```

最后一条最好用：服务该打的 `/api/brush/status_all` 如果**一次都不出现**，就说明轮询没生效
（2026-09-21 就是靠这个抓到「主线程网络」那个隐形 bug 的 —— 不报错、不崩，只是静默失效）。

## 平台差异备忘

| 能力 | 桌面 | Android |
|---|---|---|
| 界面 | pywebview 窗口 | WebView 加载 `http://127.0.0.1:8760` |
| 后端 | 同进程线程 | 同进程线程（在 `Application` 里起，所以窗口退了也在跑） |
| 凭据加密 | Windows DPAPI | Android Keystore AES-GCM |
| 「收进托盘」 | `NotifyIcon` + 隐藏窗口 | 返回键 `moveTaskToBack` + 前台服务 |
| 刷完提醒 | 提示音 + 通知 + 窗口置顶 | 提示音 + 高优先级通知 |
| 单实例 | 命名 Mutex | Android 天然单 Activity 栈 |
| 停止按钮（通知栏） | — | 通知 action → 本机令牌接口 |
