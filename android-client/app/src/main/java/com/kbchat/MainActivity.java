package com.kbchat;

import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {
    private static final String PREFS = "kbchat";
    private static final String KEY_URL = "server_url";
    private static final String KEY_TOKEN = "token";

    private WebView webView;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        webView = findViewById(R.id.webview);
        ImageButton btnSettings = findViewById(R.id.btnSettings);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // 保持在应用内打开（同源导航）
                view.loadUrl(url);
                return true;
            }
        });

        btnSettings.setOnClickListener(v -> showSettings());

        String url = prefs.getString(KEY_URL, "");
        if (url == null || url.isEmpty()) {
            showSettings();
        } else {
            loadServer();
        }
    }

    private void loadServer() {
        String url = (prefs.getString(KEY_URL, "") == null ? "" : prefs.getString(KEY_URL, "")).trim();
        String token = (prefs.getString(KEY_TOKEN, "") == null ? "" : prefs.getString(KEY_TOKEN, "")).trim();
        if (url.isEmpty()) {
            showSettings();
            return;
        }
        String full = url;
        if (!token.isEmpty()) {
            full += (url.contains("?") ? "&" : "?") + "token=" + token;
        }
        webView.loadUrl(full);
    }

    private void showSettings() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(60, 40, 60, 10);

        TextView tvUrl = new TextView(this);
        tvUrl.setText("服务器地址");
        tvUrl.setTextSize(13);
        layout.addView(tvUrl);

        EditText etUrl = new EditText(this);
        etUrl.setHint("https://kb.your-domain.com");
        etUrl.setText(prefs.getString(KEY_URL, ""));
        layout.addView(etUrl);

        TextView tvToken = new TextView(this);
        tvToken.setText("访问令牌（服务器开启鉴权时必填）");
        tvToken.setTextSize(13);
        tvToken.setPadding(0, 18, 0, 0);
        layout.addView(tvToken);

        EditText etToken = new EditText(this);
        etToken.setHint("与服务器 SERVER_TOKEN 一致");
        etToken.setText(prefs.getString(KEY_TOKEN, ""));
        layout.addView(etToken);

        new AlertDialog.Builder(this)
                .setTitle("知识库助手 · 设置")
                .setView(layout)
                .setPositiveButton("保存并连接", (d, w) -> {
                    String u = etUrl.getText().toString().trim();
                    String t = etToken.getText().toString().trim();
                    prefs.edit().putString(KEY_URL, u).putString(KEY_TOKEN, t).apply();
                    loadServer();
                })
                .setNegativeButton("取消", null)
                .show();
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
