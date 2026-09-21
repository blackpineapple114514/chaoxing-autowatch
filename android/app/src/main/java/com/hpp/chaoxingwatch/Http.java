package com.hpp.chaoxingwatch;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** 极简 HTTP GET（只用来访问自家 127.0.0.1 后端，不走 TLS）。 */
final class Http {

    private Http() {
    }

    static String get(String url, int timeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(timeoutMs);
            c.setReadTimeout(timeoutMs);
            c.setRequestMethod("GET");
            int code = c.getResponseCode();
            InputStream in = (code >= 200 && code < 400) ? c.getInputStream() : c.getErrorStream();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            if (in != null) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = in.read(buf)) > 0) {
                    bo.write(buf, 0, n);
                }
                in.close();
            }
            if (code < 200 || code >= 400) {
                throw new IllegalStateException("HTTP " + code);
            }
            return new String(bo.toByteArray(), "UTF-8");
        } finally {
            c.disconnect();
        }
    }
}
