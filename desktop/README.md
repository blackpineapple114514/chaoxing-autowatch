# 学习通刷课助手（App）

把逆向出来的接口封装成一个**给普通人用**的桌面/网页应用：登录（扫码 / 账号密码）→ 读取课程 → 一键刷 / 自选刷。
纯 HTTP，不依赖浏览器、不需要 Playwright、不需要装驱动。

## 方式一：直接用打包好的 exe（推荐给普通用户）

双击 **`学习通刷课助手.exe`**（桌面已放一份，源在 `app/dist/`），会自动弹出应用窗口，无需装 Python。

- 单文件 47 MB，自带 Python 运行时 + Flask + 界面
- 窗口基于系统自带的 Edge WebView2；如果机器没有，会自动改用默认浏览器打开
- 启动日志在 `%USERPROFILE%\chaoxing-autowatch.log`

重新打包：`python build_exe.py`（需 `pyinstaller`、`pywebview`）

## 方式二：源码跑

```bat
cd projects\chaoxing-autowatch\app
python app.py
```

或双击 `启动刷课助手.bat`，然后浏览器打开 <http://127.0.0.1:8760>

依赖：`flask`、`requests`。

## 方式三：源码跑桌面窗口（不打包）

```bat
python gui.py
```

## 使用流程

1. **打开页面** → 自动显示学习通登录二维码。
2. 登录（两种模式，任选其一）：
   - **扫码登录（默认）**：用手机学习通 App 扫码 → 页面自动进入主界面。
   - **账号密码登录**：填学号/手机号 + 密码点「登录」。密码用 AES-CBC(key=`u2oh6Vu^HWe4_AES`) 加密后提交，只在本机内存过一手、不写日志。
     ⚠️ 扫码不好使时就用这个。⚠️ **别拿错密码反复试：连错 6 次账号会被冻结 15 分钟。**

3. 点 **「读取我的课程」** → 列出你所有课程。
4. 两种刷法：
   - **「一键刷全部」**：所有课程的全部任务点。
   - **「刷选中章节」**：先展开某门课的章节、勾掉不想刷的，再点。
5. 下方日志实时显示：当前课程 / 章节 / 视频、已上报次数、完成数、错误。

## 目录

```
app/
  app.py             Flask 后端（路由 + 后台刷课线程）
  cx_client.py       学习通纯 HTTP 客户端（登录/课程/章节/任务点/上报）
  gui.py             桌面窗口启动器（pywebview）
  build_exe.py       一键打包脚本
  templates/
    index.html       单页前端
  selftest.py        自检：用已有 cookie 跑通全部客户端逻辑
  启动刷课助手.bat
  dist/
    学习通刷课助手.exe  ← 打包产物
```

## 接口速查（全部实测可用）

| 环节 | 请求 |
|---|---|
| 登录页 | `GET passport2.chaoxing.com/login?fid=12&refer=...&space=2` → 解析 `uuid`/`enc` |
| 二维码 | `GET passport2.chaoxing.com/createqr?uuid=<uuid>&fid=-1` |
| 轮询登录 | `POST passport2.chaoxing.com/getauthstatus/v2` (enc/uuid) |
| 刷新二维码 | `POST passport2.chaoxing.com/refreshQRCode` |
| 课程列表 | `POST mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata` (`courseType=1`) |
| 章节树 | `GET mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse?courseid&clazzid&cpi` |
| 任务点 | `GET mooc1.chaoxing.com/mooc-ans/knowledge/cards?...&knowledgeid=` → `mArg.attachments` |
| 视频密钥 | `GET mooc1.chaoxing.com/ananas/status/{objectId}?k=&flag=normal&ro=0` → `dtoken` |
| 进度上报 | `GET {reportUrl}/{dtoken}?...&enc=<md5>` |

**上报签名**：`enc = md5("["+clazzId+"]["+userid+"]["+jobid+"]["+objectId+"]["+playingTime*1000+"][d_yHJ!$pdA~5]["+duration*1000+"]["+clipTime+"]")`

## 已知限制 / 注意

- **只处理视频任务点**。章节测验、讨论、阅读 PPT 等未实现。
- 账号有**多端登录风控**：刷课时最好别同时用手机端看课。
- `POST /api/login/password` body `{uname,password}` → `{ok,userid,name,verify}`（失败带 `status`/`error`）
- 会话会过期：重新登录即可。
- 账号密码模式**不支持**图形验证码 / 双因子（触发时请改用扫码）；连续输错 6 次会冻结 15 分钟。
- `selftest.py` 里内嵌了开发用的测试 cookie，**正式发布前请删掉**。
- 学习平台可能随时改接口/加验证（人脸抓拍 `videoFaceCaptureEnc` 目前传空）。

## 进度可视化（2026-09-21 01:57）
界面顶部有 **5 步步骤条**：① 登录 → ② 读取课程 → ③ 统计任务点 → ④ 刷课 → ⑤ 完成，
当前步高亮、已完成变绿；配一条**总进度条**（占刷课阶段的百分比）+ 一行实时说明。

刷课分**两阶段**：
1. **统计（planning）**：只读不写，把课程→章节→任务点全列一遍，得到总视频数 —— 所以进度条一开始就有分母。
2. **上报（brushing）**：逐个视频按时间轴上报，实时显示 `第 N/M 个视频（mm:ss / mm:ss）`。

`/api/brush/status` 的 job 字段：`phase, percent, videos_total, videos_done, videos_index,
chapters_total, chapters_done, courses_total, courses_done, cur_pos, cur_dur, reports, skipped, errors`。

⚠️ 开始刷课需要**点两次**按钮（第一次变成"再点一次确认"，8 秒内再点才真正开始）——避免误触真实改进度。
