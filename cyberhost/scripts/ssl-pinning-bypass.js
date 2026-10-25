// desc: Universal SSL/TLS pinning bypass (TrustManager, OkHttp, Conscrypt, WebView)
// CyberHost APE — bundled Frida script. Authorized testing only.
//
//   cyberhost run frida -U -f <package> -l ssl-pinning-bypass.js --no-pause
//
// Disables common certificate-pinning implementations so an intercepting proxy
// (mitmproxy/ZAP/Burp) can read HTTPS during an authorized assessment.

'use strict';

Java.perform(function () {
    console.log('[CyberHost] SSL pinning bypass loaded');

    // --- 1. Default TrustManager (javax.net.ssl) ---------------------------
    try {
        var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
        var SSLContext = Java.use('javax.net.ssl.SSLContext');

        var TrustManagerImpl = Java.registerClass({
            name: 'com.cyberhost.TrustAll',
            implements: [X509TrustManager],
            methods: {
                checkClientTrusted: function () {},
                checkServerTrusted: function () {},
                getAcceptedIssuers: function () { return []; }
            }
        });

        var init = SSLContext.init.overload(
            '[Ljavax.net.ssl.KeyManager;',
            '[Ljavax.net.ssl.TrustManager;',
            'java.security.SecureRandom');
        init.implementation = function (km, tm, sr) {
            console.log('[CyberHost] overriding SSLContext.init TrustManager');
            init.call(this, km, [TrustManagerImpl.$new()], sr);
        };
        console.log('[CyberHost] hooked default TrustManager');
    } catch (e) { console.log('[CyberHost] TrustManager hook skipped: ' + e); }

    // --- 2. OkHttp3 CertificatePinner --------------------------------------
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List')
            .implementation = function () {
                console.log('[CyberHost] OkHttp3 CertificatePinner.check() bypassed');
                return;
            };
        console.log('[CyberHost] hooked OkHttp3 CertificatePinner');
    } catch (e) { console.log('[CyberHost] OkHttp3 hook skipped: ' + e); }

    // --- 3. TrustManagerImpl (Conscrypt, Android 7+) -----------------------
    try {
        var TMImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        TMImpl.checkTrustedRecursive.implementation = function () {
            console.log('[CyberHost] Conscrypt checkTrustedRecursive bypassed');
            return Java.use('java.util.ArrayList').$new();
        };
        console.log('[CyberHost] hooked Conscrypt TrustManagerImpl');
    } catch (e) { console.log('[CyberHost] Conscrypt hook skipped: ' + e); }

    // --- 4. WebViewClient onReceivedSslError -------------------------------
    try {
        var WebViewClient = Java.use('android.webkit.WebViewClient');
        WebViewClient.onReceivedSslError.implementation = function (view, handler) {
            console.log('[CyberHost] WebView SSL error proceeded');
            handler.proceed();
        };
        console.log('[CyberHost] hooked WebViewClient');
    } catch (e) { console.log('[CyberHost] WebView hook skipped: ' + e); }
});
