package com.hpp.chaoxingwatch;

import android.app.Application;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/**
 * 应用入口：只做四件事——起 Python、初始化凭据加密、建通知通道、把 Flask 拉起来。
 * 关键点：Flask 起在 Application 里而不是 Activity 里，所以窗口退了/进程还在时后端照跑。
 */
public class App extends Application {

    @Override
    public void onCreate() {
        super.onCreate();
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        Creds.init(this);
        Notifications.createChannels(this);
        Server.start(this);
    }
}
