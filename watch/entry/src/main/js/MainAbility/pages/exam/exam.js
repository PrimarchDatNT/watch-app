import { CATEGORIES } from '../../common/content.js';
import { goList, goDetail } from '../../common/nav.js';
import { wrapText } from '../../common/wrap.js';

// NOTE: lite page methods must not be named render/show/subscribe (render is the compiled template).

// Section titles get up to two lines in the menu: 268px text at 30px font ≈ 8.9em, minus a safety margin.
const TOC_LINE_EM = 8.5;

export default {
    data: {
        cat: 0,  // router params
        item: 0,
        header: '',
        rows: [] // {one, two, l1, l2}: one-line or two-line title (lite can't bind height, so both are fixed)
    },

    onInit() {
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        const exam = c.items[this.item] || c.items[0];
        this.header = '< ' + c.name + ' - ' + exam.title;
        const rows = [];
        for (let i = 0; i < exam.pages.length; i++) {
            const lines = wrapText(exam.pages[i].label, TOC_LINE_EM);
            if (lines.length <= 1) {
                rows.push({ one: true, two: false, l1: lines.length ? lines[0] : '', l2: '' });
            } else {
                // the rest goes on line 2; text-overflow: ellipsis cuts it with "…" if still too long
                rows.push({ one: false, two: true, l1: lines[0], l2: lines.slice(1).join(' ') });
            }
        }
        this.rows = rows;
    },

    openSection(idx) {
        goDetail(this.cat, this.item, idx);
    },

    goBack() {
        goList(this.cat);
    },

    onSwipe(e) {
        if (e && e.direction === 'right') {
            goList(this.cat);
        }
    }
};
