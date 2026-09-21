# -*- coding: utf-8 -*-
"""把桌面版的业务代码同步进 Android 模块（单一真相仍在 ../../app/）。

只复制三个文件：app.py / cx_client.py / templates/index.html。
它们已经打过「平台无关补丁」——Windows 走 DPAPI、Android 走 Keystore，业务逻辑零改动。
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
AND = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(AND), "app")
DST = os.path.join(AND, "app", "src", "main", "python")

FILES = ["app.py", "cx_client.py", os.path.join("templates", "index.html")]


def write_ui_html():
    """把 index.html 内嵌成 ui_html.py（base64，避开一切引号/转义坑）。

    Android 上模板文件未必能被 Jinja 的文件系统加载器认到，这份内嵌副本是兜底，
    保证页面一定出得来（桌面版不受影响，它直接读盘）。
    """
    import base64
    src = os.path.join(SRC, "templates", "index.html")
    raw = open(src, "rb").read()
    b64 = base64.b64encode(raw).decode("ascii")
    # 每 100 字符断一行，避免单行过长
    chunks = [b64[i:i + 100] for i in range(0, len(b64), 100)]
    body = "\n".join('    "%s"' % c for c in chunks)
    text = (
        "# -*- coding: utf-8 -*-\n"
        "\"\"\"自动生成，勿手改 —— 源文件 app/templates/index.html\n"
        "生成者：android/tools/sync_python.py\n\"\"\"\n"
        "import base64\n\n"
        "_B64 = (\n%s\n)\n\n"
        "INDEX_HTML = base64.b64decode(_B64).decode(\"utf-8\")\n" % body
    )
    dst = os.path.join(DST, "ui_html.py")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("  gen  %-24s %6d 字节 (源 %d 字节)" % ("ui_html.py", os.path.getsize(dst), len(raw)))


def main():
    for rel in FILES:
        s = os.path.join(SRC, rel)
        d = os.path.join(DST, rel)
        if not os.path.exists(s):
            raise SystemExit("缺少源文件: %s" % s)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        print("  sync %-24s %6d 字节" % (rel, os.path.getsize(d)))

    write_ui_html()

    # 清掉可能被带进来的 __pycache__
    for root, dirs, _ in os.walk(DST):
        for name in list(dirs):
            if name == "__pycache__":
                shutil.rmtree(os.path.join(root, name), ignore_errors=True)
                dirs.remove(name)
    print("同步完成 -> %s" % DST)


if __name__ == "__main__":
    main()
