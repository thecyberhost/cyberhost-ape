# Practice targets

`cyberhost targets` manages legal, **intentionally vulnerable** Android apps
published by their authors for security education. They are fetched on demand
into `./targets/<name>/` (not committed to the repo), each with a generated
README describing what to practice.

| Name | What you practice |
|---|---|
| **diva** | insecure logging/storage, hardcoded secrets, SQLi, input validation |
| **insecurebankv2** | auth flaws, insecure storage, broken crypto, exported components, backend API |
| **androgoat** | OWASP MASVS categories across storage/crypto/network/platform |
| **pivaa** | modern DIVA successor; broad MASTG-style issues |
| **mastg-crackmes** | reverse engineering, root/tamper-detection bypass, native code |

## Usage

```
cyberhost> targets                   # list them
cyberhost> targets --install diva    # download one
cyberhost> targets --install all     # download all
cyberhost> targets --deploy diva     # adb-install to the connected device
```

## ⚠ Safety

These apps are **deliberately insecure**. Install them **only** on an emulator
or a dedicated test device you control, and **never** expose them to the
internet or any network you don't own. When you're done, uninstall them.
