# signing/ (not in git)

Everything here except this file is git-ignored. To build a signed watch HAP you need, in this folder:

| File | What | Where from |
|---|---|---|
| `watch-debug.p12` | signing key (EC P-256, alias `watchdebug`) | generated locally with `keytool` |
| `keystore-password.txt` | its password | generated locally |
| `watch-debug.csr` | certificate request for that key | `keytool -certreq` |
| `watch-debug.cer` | debug certificate | AppGallery Connect → Certificates (upload the CSR) |
| `watch-debug.p7b` | debug HAP provision profile (bundle `com.datnt.gtpush.watch` + the watch UDID) | AppGallery Connect → Profiles |
| `material/` | key material that encrypts the passwords in `watch/build-profile.json5` | generated locally (hvigor `DecipherUtil` format) |
| `device-udid.txt` | the watch UDID | DevEco Assistant → Lite Wearable |

The debug certificate/profile expire after ~14 days: re-create them in AppGallery Connect from the **same** CSR
so the key (and the watch app's Wear Engine fingerprint) stays the same.
