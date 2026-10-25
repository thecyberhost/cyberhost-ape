// desc: Observability hooks — crypto, shared-prefs, HTTP, logs, WebView
// CyberHost APE — bundled Frida script. Authorized testing only.
//
//   cyberhost run frida -U -f <package> -l common-hooks.js --no-pause
//
// Traces the API surfaces most useful during a mobile assessment: cipher usage,
// SharedPreferences reads/writes, URL connections, and logging. Read-only —
// it observes and prints, it does not alter behavior.

'use strict';

Java.perform(function () {
    console.log('[CyberHost] common hooks loaded');

    // --- Crypto: Cipher.doFinal -------------------------------------------
    try {
        var Cipher = Java.use('javax.crypto.Cipher');
        Cipher.doFinal.overload('[B').implementation = function (input) {
            var out = this.doFinal(input);
            console.log('[CyberHost][crypto] ' + this.getAlgorithm() +
                '  in=' + bytesToStr(input));
            return out;
        };
    } catch (e) {}

    // --- SharedPreferences -------------------------------------------------
    try {
        var SP = Java.use('android.app.SharedPreferencesImpl');
        SP.getString.implementation = function (k, d) {
            var v = this.getString(k, d);
            console.log('[CyberHost][prefs] get ' + k + ' = ' + v);
            return v;
        };
    } catch (e) {}

    // --- URL connections ---------------------------------------------------
    try {
        var URL = Java.use('java.net.URL');
        URL.openConnection.overload().implementation = function () {
            console.log('[CyberHost][http] ' + this.toString());
            return this.openConnection();
        };
    } catch (e) {}

    // --- Logging -----------------------------------------------------------
    try {
        var Log = Java.use('android.util.Log');
        ['d', 'i', 'w', 'e', 'v'].forEach(function (lvl) {
            Log[lvl].overload('java.lang.String', 'java.lang.String')
                .implementation = function (tag, msg) {
                    console.log('[CyberHost][log.' + lvl + '] ' + tag + ': ' + msg);
                    return this[lvl](tag, msg);
                };
        });
    } catch (e) {}

    function bytesToStr(arr) {
        try {
            return Java.use('java.lang.String').$new(arr);
        } catch (e) { return '<' + (arr ? arr.length : 0) + ' bytes>'; }
    }
});
