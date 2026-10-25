# Student Quickstart — your first APK analysis in 5 minutes

This walks you from a fresh unzip to reading an app's decompiled code and
scanning it for secrets. No prior setup required.

> **Only analyze apps you own or are authorized to test.** Use the bundled
> practice targets if you need something legal to learn on (see step 5).

## 0. Launch

Unzip the release and **double-click `CyberHost.bat`**. You'll see the banner and:

```
12 core tools loaded · 0 device(s) connected
cyberhost>
```

Type `help` any time. Tab-completion works on commands and tool names.

## 1. Get a device (optional but recommended)

Any emulator works. The quickest is an Android Studio AVD:

```
cyberhost> emulator list            # shows detected SDK + AVDs
cyberhost> emulator launch Pixel_6  # starts one
cyberhost> devices                  # confirm it's connected
```

No emulator? You can still do static analysis on an APK file — skip to step 3.

## 2. Get an APK

Either pull one off a connected device, or use a practice target (step 5).

```
cyberhost> use apkeep               # on-demand downloader (install apkeep first)
```

Or pull an installed app from the device with the device helper (see
`info platform-tools`).

## 3. Scan for secrets & endpoints

```
cyberhost> use apkleaks
cyberhost> target C:\path\to\app.apk
cyberhost> run
```

`apkleaks` prints URLs, API endpoints, and likely secrets it finds. Note the
output location it reports.

## 4. Decompile to Java and read the code

```
cyberhost> use jadx
cyberhost> run                      # CLI decompile (uses your target)
```

Prefer a GUI? `run jadx-gui` opens the graphical decompiler.

## 5. Practice legally

```
cyberhost> targets                      # list legal vulnerable apps
cyberhost> targets --install diva       # download DIVA
cyberhost> targets --deploy diva        # install it on your emulator
```

Each target lands in `./targets/<name>/` with a README explaining what to
practice. **These are intentionally vulnerable — keep them off real networks.**

## 6. Intercept HTTPS traffic

```
cyberhost> proxy on                                  # device → your host:8080
cyberhost> run mitmproxy                             # start the proxy
cyberhost> cert install <path-to>\mitmproxy-ca-cert.pem
```

If an app ignores the user CA (common on Android 7+), either:
- `install apk-mitm` and re-sign the APK to trust user CAs, or
- use a Frida pinning bypass: `scripts`, then
  `run frida -U -f <package> -l <script> --no-pause`.

## 7. Go dynamic with Frida

```
cyberhost> frida setup               # pushes the matching frida-server & runs it
cyberhost> scripts                   # list bundled hooks
cyberhost> run objection -g <package> explore
```

## Where things live

- Installed tools: `./tools/`
- Practice apps: `./targets/`
- Bundled Frida scripts: inside the `cyberhost/scripts/` package folder
- History: `./.cyberhost_history`

That's it — you've done static analysis, secret scanning, interception, and
runtime instrumentation. Explore `list` to see everything available.
