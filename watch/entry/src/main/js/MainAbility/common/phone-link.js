// system.wearengine is loaded lazily and guarded: a static `import` turns into requireNative() at
// page load, and if this firmware lacks the module that throws and the whole page stays blank.
let wearengine = null;
function getWearEngine() {
    if (wearengine === null) {
        try {
            wearengine = requireNative('system.wearengine') || undefined;
        } catch (e) {
            wearengine = undefined;
        }
        console.info('GT Push: system.wearengine ' + (wearengine ? 'available' : 'NOT available'));
    }
    return wearengine;
}

// Identity of the phone app the watch accepts messages from.
// PHONE_FINGERPRINT = SHA-256 of the certificate that signs the Android app, uppercase hex, no colons.
// It is the Android *debug* key on this Mac; switch it when the phone app is signed with a release key.
export const PHONE_PKG = 'com.datnt.gtpush';
export const PHONE_FINGERPRINT = 'C0CE8BDE42E059CBA4D6F080ACED9789CCAE78A8CE0CA4D5A33220C9F13E8AA1';

// Wear Engine service versions on the watch that added setFingerprint / setPackageName.
const SERVICE_VERSION_FINGERPRINT = 302;
const SERVICE_VERSION_PACKAGE = 303;
const SDK_VERSION = '3';

function serviceVersion(done) {
    const we = getWearEngine();
    if (!we) {
        done(0);
        return;
    }
    try {
        we.getWearEngineVersion({
            sdkVersion: SDK_VERSION,
            complete: (v) => {
                if (!v) {
                    done(0);
                    return;
                }
                const parts = String(v).split('.');
                done(parseInt(parts[parts.length - 1], 10) || 0);
            }
        });
    } catch (e) {
        done(0);
    }
}

// Tells the watch-side Wear Engine which phone app is our peer, then subscribes to its messages.
// onMessage(text) is called for every message; onError(code) on failure.
export function listen(onMessage, onError) {
    if (typeof FeatureAbility === 'undefined') {
        onError(-1);
        return;
    }
    serviceVersion((version) => {
        console.info('GT Push: wearengine service version ' + version);
        const we = getWearEngine();
        try {
            if (we && version >= SERVICE_VERSION_PACKAGE) {
                we.setPackageName({ appName: PHONE_PKG });
            }
            if (we && version >= SERVICE_VERSION_FINGERPRINT) {
                we.setFingerprint({ appName: PHONE_PKG, appCert: PHONE_FINGERPRINT });
            }
        } catch (e) {
            console.error('GT Push: wearengine peer setup failed ' + e);
        }
        FeatureAbility.subscribeMsg({
            success: (data) => {
                // The first callback only acknowledges the subscription.
                if (!data || data.isRegister) {
                    return;
                }
                if (data.isFileType) {
                    console.info('GT Push: file messages are not handled');
                    return;
                }
                onMessage(data.message);
            },
            fail: (data, code) => {
                onError(code);
            }
        });
    });
}

export function stopListening() {
    if (typeof FeatureAbility !== 'undefined') {
        FeatureAbility.unsubscribeMsg();
    }
}
