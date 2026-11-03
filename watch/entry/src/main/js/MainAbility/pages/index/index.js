import storage from '@system.storage';
import { parsePayload, PHONE_STORAGE_KEY } from '../../common/message.js';
import { listen, stopListening } from '../../common/phone-link.js';
import { CATEGORIES } from '../../common/content.js';
import { goList, goPhone } from '../../common/nav.js';

// NOTE: lite page methods must not be named render/show/subscribe (render is the compiled template).

const CLOCK_REFRESH_MS = 15000;
let clockTimer = null;

function pad2(n) {
    return n < 10 ? '0' + n : '' + n;
}

export default {
    data: {
        clock: '',
        name0: '',
        name1: '',
        name2: '',
        name3: '',
        hasPhone: false,
        phoneLine: ''
    },

    onInit() {
        this.name0 = CATEGORIES[0].name;
        this.name1 = CATEGORIES[1].name;
        this.name2 = CATEGORIES[2].name;
        this.name3 = CATEGORIES[3].name;
        this.updateClock();
        clockTimer = setInterval(() => {
            this.updateClock();
        }, CLOCK_REFRESH_MS);
        try {
            this.loadPhone();
        } catch (e) {
            console.error('GT Push: loadPhone failed ' + e);
        }
        try {
            this.connectPhone();
        } catch (e) {
            console.error('GT Push: connectPhone failed ' + e);
        }
    },

    onDestroy() {
        if (clockTimer !== null) {
            clearInterval(clockTimer);
            clockTimer = null;
        }
        stopListening();
    },

    updateClock() {
        const d = new Date();
        this.clock = pad2(d.getHours()) + ':' + pad2(d.getMinutes());
    },

    openCat0() {
        goList(0);
    },
    openCat1() {
        goList(1);
    },
    openCat2() {
        goList(2);
    },
    openCat3() {
        goList(3);
    },
    openPhone() {
        goPhone();
    },

    setPhoneLine(raw) {
        const p = parsePayload(raw);
        const label = p.title || p.value || p.text;
        this.phoneLine = this.$t('strings.fromPhone') + ': ' + label;
        this.hasPhone = true;
    },

    loadPhone() {
        storage.get({
            key: PHONE_STORAGE_KEY,
            success: (saved) => {
                if (!saved) {
                    return;
                }
                try {
                    const s = JSON.parse(saved);
                    if (typeof s.raw === 'string' && s.raw.length > 0) {
                        this.setPhoneLine(s.raw);
                    }
                } catch (e) {
                    console.error('GT Push: bad saved payload');
                }
            }
        });
    },

    // A new message from the phone is saved and opened right away.
    connectPhone() {
        listen(
            (raw) => {
                storage.set({
                    key: PHONE_STORAGE_KEY,
                    value: JSON.stringify({ raw: raw, ts: new Date().getTime() }),
                    complete: () => {
                        goPhone();
                    }
                });
            },
            (code) => {
                console.error('GT Push: phone link unavailable, code ' + code);
            }
        );
    }
};
