package com.hpp.chaoxingwatch;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * 「记住登录」的 Android 实现（对应桌面的 DPAPI）。
 * <p>
 * AES-256/GCM 密钥由 Android Keystore 生成并保管（不落磁盘、应用卸载即销毁），
 * 密文放 SharedPreferences。拷走 pref 文件也解不开，换机自然失效。
 * <p>
 * 供 Python 侧通过 jclass 调用：save / load / has / drop。
 */
public final class Creds {

    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "chaoxing_autowatch_creds";
    private static final String PREFS = "chaoxing_creds";
    private static final String FIELD = "blob";
    private static final int IV_LEN = 12;

    private static Context appCtx;

    private Creds() {
    }

    public static void init(Context c) {
        appCtx = c.getApplicationContext();
    }

    private static SharedPreferences prefs() {
        return appCtx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        java.security.Key existing = ks.getKey(ALIAS, null);
        if (existing instanceof SecretKey) {
            return (SecretKey) existing;
        }
        KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return kg.generateKey();
    }

    /** 保存明文 JSON（内部加密）。返回是否成功。 */
    public static boolean save(String plain) {
        try {
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.ENCRYPT_MODE, key());
            byte[] iv = c.getIV();
            byte[] ct = c.doFinal(plain.getBytes(StandardCharsets.UTF_8));
            byte[] blob = new byte[iv.length + ct.length];
            System.arraycopy(iv, 0, blob, 0, iv.length);
            System.arraycopy(ct, 0, blob, iv.length, ct.length);
            return prefs().edit()
                    .putString(FIELD, Base64.encodeToString(blob, Base64.NO_WRAP))
                    .commit();
        } catch (Exception e) {
            return false;
        }
    }

    /** 读回明文 JSON；解不开/没有则返回 null。 */
    public static String load() {
        try {
            String s = prefs().getString(FIELD, null);
            if (s == null) {
                return null;
            }
            byte[] blob = Base64.decode(s, Base64.NO_WRAP);
            if (blob.length <= IV_LEN) {
                return null;
            }
            byte[] iv = new byte[IV_LEN];
            System.arraycopy(blob, 0, iv, 0, IV_LEN);
            byte[] ct = new byte[blob.length - IV_LEN];
            System.arraycopy(blob, IV_LEN, ct, 0, ct.length);
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            return new String(c.doFinal(ct), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }

    public static boolean has() {
        return prefs().getString(FIELD, null) != null;
    }

    public static void drop() {
        prefs().edit().remove(FIELD).apply();
    }
}
