package com.hpp.chaoxingwatch;

import android.app.Activity;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 唯一界面：一个 WebView 加载本机 Flask 页面（与桌面版同一份 index.html）。
 * 平台层只做三件事——起服务等就绪、把 JS 桥挂上、返回键退后台而不是退出。
 */
public class MainActivity extends Activity {

    private WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
        }

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(this), "AndroidBridge");
        // 调试包开放 WebView 调试（adb forward tcp:9222 localabstract:webview_devtools_remote_*）,
        // release 包不开放。
        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true);
        }
        web.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(web);
        web.loadDataWithBaseURL(null, page("正在启动引擎…", "首次启动要解包 Python 运行时，约 3-10 秒。"),
                "text/html", "UTF-8", null);

        Thread t = new Thread(new Runnable() {
            @Override
            public void run() {
                final boolean ok = Server.waitReady(120000);
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (isFinishing() || web == null) {
                            return;
                        }
                        if (ok) {
                            web.loadUrl("http://127.0.0.1:" + Server.PORT + "/");
                        } else {
                            web.loadDataWithBaseURL(null,
                                    page("后端启动失败", Server.lastError), "text/html", "UTF-8", null);
                        }
                    }
                });
            }
        }, "server-wait");
        t.setDaemon(true);
        t.start();
    }

    private static String page(String title, String body) {
        String safe = body == null ? "" : body.replace("&", "&amp;").replace("<", "&lt;");
        return "<!DOCTYPE html><html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;padding:28px;color:#334155;background:#f7f8fa}"
                + "h2{color:#2563eb}pre{white-space:pre-wrap;font-size:12px;color:#64748b}</style></head>"
                + "<body><h2>" + title + "</h2><pre>" + safe + "</pre></body></html>";
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            moveTaskToBack(true);   // 退到后台，刷课继续（桌面版对应「收进托盘」）
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
