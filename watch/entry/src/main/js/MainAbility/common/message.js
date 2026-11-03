// Payload sent by the phone app through Wear Engine P2P: a UTF-8 string of at most 1 KB.
// Card:      {"title":"BTC","value":"68,420","sub":"+2.1%"}
// Paragraph: {"title":"Ghi chú","text":"Một đoạn văn dài ..."}   (any non-JSON string is a paragraph too)
// Every field is optional.
// Storage key of the last payload received from the phone: {"raw": "<payload>", "ts": <ms>}.
export const PHONE_STORAGE_KEY = 'last_payload';

function field(obj, key) {
    return obj[key] === undefined || obj[key] === null ? '' : String(obj[key]);
}

export function parsePayload(raw) {
    const out = { title: '', value: '', sub: '', text: '' };
    if (typeof raw !== 'string' || raw.length === 0) {
        return out;
    }
    try {
        const obj = JSON.parse(raw);
        if (obj !== null && typeof obj === 'object') {
            out.title = field(obj, 'title');
            out.value = field(obj, 'value');
            out.sub = field(obj, 'sub');
            out.text = field(obj, 'text');
            return out;
        }
    } catch (e) {
        // not JSON — fall through
    }
    out.text = raw;
    return out;
}

function pad(n) {
    return n < 10 ? '0' + n : '' + n;
}

export function formatTime(ms) {
    const d = new Date(ms);
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}
