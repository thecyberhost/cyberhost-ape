// desc: Common root-detection bypass (su checks, package checks, build tags)
// CyberHost APE — bundled Frida script. Authorized testing only.
//
//   cyberhost run frida -U -f <package> -l root-detection-bypass.js --no-pause
//
// Neutralizes the most common root checks so a research build runs on a rooted
// test device/emulator during an authorized assessment.

'use strict';

Java.perform(function () {
    console.log('[CyberHost] root-detection bypass loaded');

    var suspicious = ['/system/bin/su', '/system/xbin/su', '/sbin/su',
        '/su/bin/su', '/system/app/Superuser.apk', '/data/local/xbin/su',
        '/data/local/bin/su', '/system/sd/xbin/su', '/data/local/su',
        '/magisk', '/sbin/magisk'];

    // File.exists() returning true for su paths
    try {
        var File = Java.use('java.io.File');
        File.exists.implementation = function () {
            var path = this.getAbsolutePath();
            for (var i = 0; i < suspicious.length; i++) {
                if (path.indexOf(suspicious[i]) !== -1) {
                    console.log('[CyberHost] hiding file check: ' + path);
                    return false;
                }
            }
            return this.exists();
        };
    } catch (e) { console.log('[CyberHost] File.exists hook skipped: ' + e); }

    // Runtime.exec('su' / 'which su')
    try {
        var Runtime = Java.use('java.lang.Runtime');
        Runtime.exec.overload('java.lang.String').implementation = function (cmd) {
            if (cmd && (cmd.indexOf('su') !== -1 || cmd.indexOf('which') !== -1)) {
                console.log('[CyberHost] blocking Runtime.exec: ' + cmd);
                cmd = 'echo';
            }
            return this.exec(cmd);
        };
    } catch (e) { console.log('[CyberHost] Runtime.exec hook skipped: ' + e); }

    // PackageManager root-app lookups
    try {
        var rootPkgs = ['com.topjohnwu.magisk', 'eu.chainfire.supersu',
            'com.noshufou.android.su', 'com.koushikdutta.superuser'];
        var ApplicationPackageManager = Java.use('android.app.ApplicationPackageManager');
        ApplicationPackageManager.getPackageInfo.overload('java.lang.String', 'int')
            .implementation = function (pkg, flags) {
                if (rootPkgs.indexOf(pkg) !== -1) {
                    console.log('[CyberHost] hiding root package: ' + pkg);
                    throw Java.use('android.content.pm.PackageManager$NameNotFoundException').$new(pkg);
                }
                return this.getPackageInfo(pkg, flags);
            };
    } catch (e) { console.log('[CyberHost] PackageManager hook skipped: ' + e); }

    // Build.TAGS = 'test-keys'
    try {
        var Build = Java.use('android.os.Build');
        Build.TAGS.value = 'release-keys';
        console.log('[CyberHost] Build.TAGS set to release-keys');
    } catch (e) { console.log('[CyberHost] Build.TAGS hook skipped: ' + e); }
});
