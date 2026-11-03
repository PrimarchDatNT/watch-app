import storage from '@system.storage';
import { CATEGORIES } from '../../common/content.js';
import { parsePayload, formatTime, PHONE_STORAGE_KEY } from '../../common/message.js';
import { wrapStyled } from '../../common/wrap.js';
import { goHome, goList, goDetail, goExam } from '../../common/nav.js';

// NOTE: lite page methods must not be named render/show/subscribe (render is the compiled template).

// Body text size (keep in sync with .line / .line-item in detail.css). Lines are 300px wide:
// 300px / 24px = 12.5em (list is 320px; the rest is margin for the width estimate).
const BODY_FONT_PX = 24;
const LINE_EM = 300 / BODY_FONT_PX;

export default {
    data: {
        cat: 0,      // router params
        item: 0,
        page: 0,
        src: 'note', // 'note' | 'phone'
        header: '',
        title: '',
        lines: [],
        footer: ''
    },

    onInit() {
        if (this.src === 'phone') {
            this.header = '< ' + this.$t('strings.home');
            this.loadPhone();
            return;
        }
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        const exam = c.items[this.item] || c.items[0];
        const pages = exam.pages;
        const pg = pages[this.page] || pages[0];
        this.lines = wrapStyled(pg.text, LINE_EM);
        if (pages.length > 1) {
            // a section of a multi-section exam: back to its table of contents
            this.header = '< ' + exam.title;
            this.title = pg.label;
            const last = this.page + 1 >= pages.length;
            this.footer = (this.page + 1) + '/' + pages.length + '  '
                + this.$t(last ? 'strings.toc' : 'strings.next') + ' >';
        } else {
            this.header = '< ' + c.name;
            this.title = exam.title;
            this.footer = (this.item + 1) + '/' + c.items.length + '  ' + this.$t('strings.next') + ' >';
        }
    },

    isMultiPage() {
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        const exam = c.items[this.item] || c.items[0];
        return exam.pages.length > 1;
    },

    applyPayload(raw, ts) {
        const p = parsePayload(raw);
        this.title = p.title || this.$t('strings.fromPhone');
        // card payloads (value/sub) are shown as text lines too
        const body = p.text.length > 0 ? p.text : [p.value, p.sub].filter((s) => s.length > 0).join('\n');
        this.lines = wrapStyled(body, LINE_EM);
        this.footer = formatTime(ts);
    },

    loadPhone() {
        storage.get({
            key: PHONE_STORAGE_KEY,
            success: (saved) => {
                try {
                    const s = JSON.parse(saved);
                    this.applyPayload(s.raw, s.ts);
                } catch (e) {
                    this.title = this.$t('strings.fromPhone');
                    this.lines = [];
                }
            }
        });
    },

    goBack() {
        if (this.src === 'phone') {
            goHome();
        } else if (this.isMultiPage()) {
            goExam(this.cat, this.item);
        } else {
            goList(this.cat);
        }
    },

    goNext() {
        if (this.src === 'phone') {
            return;
        }
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        const exam = c.items[this.item] || c.items[0];
        if (exam.pages.length > 1) {
            // next section, or back to the table of contents after the last one
            if (this.page + 1 < exam.pages.length) {
                goDetail(this.cat, this.item, this.page + 1);
            } else {
                goExam(this.cat, this.item);
            }
        } else {
            goDetail(this.cat, (this.item + 1) % c.items.length, 0);
        }
    },

    onSwipe(e) {
        if (e && e.direction === 'right') {
            this.goBack();
        }
    }
};
