#!/usr/bin/env bash
# Build the signed AppNote watch HAP and install it on the watch through DevEco Assistant on the phone.
#
#   scripts/deploy-watch.sh                # build + verify + push + install
#   scripts/deploy-watch.sh --no-build     # reuse the last signed HAP
#   scripts/deploy-watch.sh -s SERIAL      # phone serial (default: $ANDROID_SERIAL or the Pixel 9)
#
# Flow: hvigor assembleHap (signed with ../signing) -> hap-sign-tool verify-app -> adb push to /sdcard/haps/
#       -> DevEco Assistant > Apps > "Install" next to the file -> wait until "Installing..." is gone.
# DevEco Assistant gives no success toast, so check the watch afterwards.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH="$ROOT/watch"
DEVECO="${DEVECO_HOME:-$HOME/Applications/DevEco-Studio.app}/Contents"
JAVA="${JAVA_BIN:-$HOME/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/java}"
SERIAL="${ANDROID_SERIAL:-47291FDAQ000PC}"
HAP="$WATCH/entry/build/default/outputs/default/entry-default-signed.hap"
REMOTE_NAME="AppNote-debug.hap"
ASSISTANT="com.huawei.deveco.assistant"
BUILD=1

while [ $# -gt 0 ]; do
  case "$1" in
    -s) SERIAL="$2"; shift 2 ;;
    --no-build) BUILD=0; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
adb_() { adb -s "$SERIAL" "$@"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Prints "text|x|y" (centre) for every node with text in the current screen.
ui_nodes() {
  adb_ shell uiautomator dump /sdcard/gtpush-ui.xml >/dev/null 2>&1 || true
  adb_ pull /sdcard/gtpush-ui.xml "$TMP/ui.xml" >/dev/null 2>&1 || { : > "$TMP/ui.xml"; }
  python3 -I - "$TMP/ui.xml" <<'PY'
import re, sys
xml = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for m in re.finditer(r'text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
    if m[1]:
        x = (int(m[2]) + int(m[4])) // 2
        y = (int(m[3]) + int(m[5])) // 2
        print(f"{m[1]}|{x}|{y}")
PY
}
focus() { adb_ shell dumpsys window | grep -m1 mCurrentFocus || true; }
wait_s() { python3 -c "import time; time.sleep($1)"; }

# ---------------------------------------------------------------- build
if [ "$BUILD" = 1 ]; then
  step "Build signed HAP"
  STAMP="$TMP/stamp"; touch "$STAMP"
  (
    cd "$WATCH"
    export DEVECO_SDK_HOME="$DEVECO/sdk" NODE_HOME="$DEVECO/tools/node" PATH="$DEVECO/tools/node/bin:$PATH"
    node "$DEVECO/tools/hvigor/bin/hvigorw.js" --mode module -p module=entry@default -p product=default \
      -p buildMode=debug assembleHap --no-daemon 2>&1 \
      | grep -v -E 'sun\.misc\.Unsafe|fastjson2|consider reporting|will be removed|can not sign bin with codesign' \
      | grep -E 'ERROR|error|WARN|BUILD' || true
  )
  [ -f "$HAP" ] && [ "$HAP" -nt "$STAMP" ] || die "no fresh signed HAP at $HAP (build failed?)"
fi
[ -f "$HAP" ] || die "missing $HAP — run without --no-build"

step "Verify signature"
SIGN_TOOL="$(find "$DEVECO/sdk" -name hap-sign-tool.jar | head -1)"
VERIFY_OUT="$("$JAVA" -jar "$SIGN_TOOL" verify-app -inFile "$HAP" -outCertChain "$TMP/chain.cer" -outProfile "$TMP/profile.p7b" 2>&1 || true)"
case "$VERIFY_OUT" in
  *"verify-app success"*) echo "verify-app success" ;;
  *) die "signature verification failed for $HAP" ;;
esac
NOT_AFTER="$(openssl cms -verify -noverify -inform DER -in "$TMP/profile.p7b" 2>/dev/null \
  | python3 -I -c 'import json,sys,datetime; v=json.load(sys.stdin)["validity"]["not-after"]; print(datetime.datetime.fromtimestamp(v).strftime("%Y-%m-%d"), int((v-datetime.datetime.now().timestamp())//86400))' || true)"
if [ -n "$NOT_AFTER" ]; then
  read -r EXP DAYS <<<"$NOT_AFTER"
  echo "debug profile valid until $EXP ($DAYS days left)"
  [ "$DAYS" -ge 0 ] || die "debug profile expired — create a new .cer/.p7b in AppGallery Connect from signing/watch-debug.csr"
fi

# ---------------------------------------------------------------- phone
step "Phone $SERIAL"
adb_ get-state >/dev/null 2>&1 || die "phone $SERIAL not connected (adb devices)"
if command -v adb-unlock >/dev/null; then adb-unlock -s "$SERIAL" || die "could not unlock the phone"; fi
adb_ shell pm path "$ASSISTANT" >/dev/null 2>&1 || die "$ASSISTANT is not installed on the phone"

step "Push HAP"
adb_ shell mkdir -p /sdcard/haps
adb_ push "$HAP" "/sdcard/haps/$REMOTE_NAME" | tail -1

step "Install through DevEco Assistant"
# Launcher activity (StartUpActivity → MainActivity); MainActivity itself is not exported. -S restarts it on the main screen.
LAUNCHER="$(adb_ shell cmd package resolve-activity --brief -a android.intent.action.MAIN \
  -c android.intent.category.LAUNCHER "$ASSISTANT" | tail -1 | tr -d '\r')"
case "$LAUNCHER" in */*) ;; *) die "cannot resolve DevEco Assistant launcher activity";; esac
adb_ shell cmd statusbar collapse >/dev/null 2>&1 || true   # a pulled-down notification shade steals focus
adb_ shell am start -S -n "$LAUNCHER" >/dev/null
for i in $(seq 1 15); do
  wait_s 1
  APPS="$(ui_nodes | grep -m1 '^Apps|' || true)"
  [ -n "$APPS" ] && break
  # lock screen / notification shade on top (screen went off, or the shade was pulled down): clear it, relaunch
  case "$(focus)" in
    *NotificationShade*)
      if command -v adb-unlock >/dev/null; then adb-unlock -s "$SERIAL" >/dev/null || true; fi
      adb_ shell cmd statusbar collapse >/dev/null 2>&1 || true
      adb_ shell am start -n "$LAUNCHER" >/dev/null ;;
  esac
done
[ -n "${APPS:-}" ] || die "DevEco Assistant main screen not found ($(focus))"
MAIN_NODES="$(ui_nodes)"
case "$MAIN_NODES" in
  *UDID*) echo "watch: $(grep -m1 -i 'watch' <<<"$MAIN_NODES" | cut -d'|' -f1 || true)" ;;
  *) echo "warning: DevEco Assistant shows no watch — is the watch connected to Huawei Health?" ;;
esac
IFS='|' read -r _ AX AY <<<"$APPS"
adb_ shell input tap "$AX" "$AY"

ROW=""; INSTALL=""
for i in $(seq 1 20); do
  wait_s 1
  FOCUS="$(focus)"
  case "$FOCUS" in *GrantPermissionsActivity*) die "DevEco Assistant is asking for storage permission — tap Allow on the phone, then rerun";; esac
  # the first tap can be lost (app still starting, screen just woke up): tap "Apps" again
  case "$FOCUS" in *assistant*MainActivity*) [ $((i % 4)) -eq 0 ] && adb_ shell input tap "$AX" "$AY";; esac
  NODES="$(ui_nodes)"
  ROW="$(grep -m1 "^$REMOTE_NAME|" <<<"$NODES" || true)"
  [ -n "$ROW" ] && break
done
[ -n "$ROW" ] || die "$REMOTE_NAME not listed in DevEco Assistant > Apps"
# The row's own "Install" button: same line as the file name, right half of the screen
# (the "Install" tab at the top is on a different line).
IFS='|' read -r _ _ RY <<<"$ROW"
INSTALL="$(awk -F'|' -v ry="$RY" '$1=="Install" && $2>540 && ($3-ry)<80 && (ry-$3)<80 {print; exit}' <<<"$NODES")"
[ -n "$INSTALL" ] || die "Install button for $REMOTE_NAME not found"
IFS='|' read -r _ IX IY <<<"$INSTALL"
adb_ shell input tap "$IX" "$IY"

SEEN=0
for i in $(seq 1 90); do
  wait_s 1
  TEXT="$(ui_nodes | cut -d'|' -f1 | tr '\n' ' ')"
  if grep -q -i -E 'fail|error|thất bại|lỗi' <<<"$TEXT"; then die "DevEco Assistant reported: $TEXT"; fi
  if grep -q 'Installing' <<<"$TEXT"; then
    SEEN=1
  elif [ "$SEEN" = 1 ]; then
    echo "install finished after ${i}s"
    break
  fi
  [ "$i" = 90 ] && die "still installing after 90s"
done
[ "$SEEN" = 1 ] || echo "warning: never saw \"Installing...\" — check DevEco Assistant on the phone"

step "Done"
echo "DevEco Assistant does not report success explicitly: open AppNote on the watch to confirm."
