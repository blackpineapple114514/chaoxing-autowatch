# -*- coding: utf-8 -*-
"""一键打包成 exe。产物：dist/学习通刷课助手.exe"""
import os
import shutil
import PyInstaller.__main__ as pk

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "ChaoxingAutoWatch"
CN = "学习通自动刷视频v1.0.7"
VERSION_FILE = os.path.join(HERE, "version_info.txt")

args = [
    os.path.join(HERE, "gui.py"),
    "--noconfirm", "--clean",
    "--onefile",
    "--windowed",
    "--name", NAME,
    "--version-file", VERSION_FILE,
    "--distpath", os.path.join(HERE, "dist"),
    "--workpath", os.path.join(HERE, "build"),
    "--specpath", os.path.join(HERE, "build"),
    "--add-data", os.path.join(HERE, "templates") + os.pathsep + "templates",
    "--collect-all", "webview",
    "--collect-all", "clr_loader",
    "--hidden-import", "clr",
    "--hidden-import", "webview.platforms.edgechromium",
    "--hidden-import", "webview.platforms.winforms",
    "--hidden-import", "bottle",
]

# 本机 pip 环境里装了 torch/scipy/pandas 等巨型包，PyInstaller 会顺着把它们整包收进来
# （实测 pkg 涨到 2.7 GB 且构建失败）。应用本身完全不用它们，这里显式排除。
EXCLUDES = [
    "torch", "torchvision", "torchaudio", "scipy", "pandas", "matplotlib",
    "sympy", "numpy", "PIL", "cv2", "onnxruntime", "sklearn", "numba", "llvmlite",
    "av", "imageio", "imageio_ffmpeg", "open3d", "frida", "ddddocr", "ctranslate2",
    "tensorflow", "IPython", "notebook", "pytest", "PyQt5", "PySide2", "PySide6",
]
for _m in EXCLUDES:
    args += ["--exclude-module", _m]


print("building ...")
pk.run(args)

src = os.path.join(HERE, "dist", NAME + ".exe")
dst = os.path.join(HERE, "dist", CN + ".exe")
if os.path.exists(src):
    shutil.copyfile(src, dst)
    print("OK ->", dst, "(%.1f MB)" % (os.path.getsize(dst) / 1048576.0))
else:
    print("FAILED: exe not found")
