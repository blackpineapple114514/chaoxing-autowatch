# -*- coding: utf-8 -*-
"""一键出 APK。

流程：同步桌面版业务代码 -> gradle assembleRelease -> 拷到 dist/。
用法：python build_apk.py            （release，推荐交付用）
      python build_apk.py debug      （debug，快速自测）
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                       # projects/chaoxing-autowatch
JAVA_HOME = r"C:\Users\hpp\android\jdk17"
GRADLE = r"C:\Users\hpp\android\gradle-8.7\bin\gradle.bat"
LOG = os.path.join(PROJ, "android", "build_android.log")
NAME = "学习通自动刷视频v1.0.9.apk"

VARIANT = (sys.argv[1] if len(sys.argv) > 1 else "release").lower()
TASK = "assembleRelease" if VARIANT == "release" else "assembleDebug"
# debug 包另起名字，免得自测时把交付用的 release 包覆盖掉。
OUT_NAME = NAME if VARIANT == "release" else "学习通自动刷视频v1.0.9-debug.apk"


def run(args, env=None, label=""):
    print(">>> %s" % (label or " ".join(args)))
    with open(LOG, "a", encoding="utf-8", errors="replace") as lf:
        lf.write("\n\n===== %s\n" % (label or args))
        lf.flush()
        p = subprocess.run(args, cwd=HERE, env=env, stdout=lf, stderr=subprocess.STDOUT)
    print("    exit=%s" % p.returncode)
    return p.returncode


def main():
    # 1) 同步业务代码（单一真相在 ../../app）
    if run([sys.executable, os.path.join(HERE, "tools", "sync_python.py")], label="同步 Python 源码"):
        raise SystemExit("同步失败")

    # 2) gradle
    env = dict(os.environ)
    env["JAVA_HOME"] = JAVA_HOME
    env["PATH"] = os.path.join(JAVA_HOME, "bin") + os.pathsep + \
        r"C:\Users\hpp\android\gradle-8.7\bin" + os.pathsep + env.get("PATH", "")
    # --no-daemon：本机 gradle daemon 起不来（java.net.BindException: Address already in use），
    # 不是偶发，必须关掉 daemon 才能 assembleRelease。
    if run([GRADLE, TASK, "--console=plain", "--no-daemon"], env=env, label="gradle " + TASK):
        raise SystemExit("构建失败，见 %s" % LOG)

    # 3) 拷产物
    src = os.path.join(HERE, "app", "build", "outputs", "apk", VARIANT,
                       "app-%s.apk" % VARIANT)
    if not os.path.exists(src):
        raise SystemExit("找不到产物 %s" % src)
    dst_dir = os.path.join(HERE, "dist")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, OUT_NAME)
    shutil.copy2(src, dst)
    print("\n产物: %s  (%.1f MB)" % (dst, os.path.getsize(dst) / 1048576.0))


if __name__ == "__main__":
    main()
