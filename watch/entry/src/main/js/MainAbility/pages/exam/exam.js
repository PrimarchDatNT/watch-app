import { CATEGORIES } from '../../common/content.js';
import { goList, goDetail } from '../../common/nav.js';
import { wrapText } from '../../common/wrap.js';

// NOTE: lite page methods must not be named render/show/subscribe (render is the compiled template).

// Menu titles (keep in sync with .toc-line in exam.css): 276px lines at 22px ≈ 12.5em, minus a safety
// margin for the width estimate. Up to TOC_MAX_LINES lines, so every title in content.js fits whole.
const TOC_FONT_PX = 22;
const TOC_LINE_PX = 28;
const TOC_LINE_EM = 276 / TOC_FONT_PX * 0.95;
const TOC_MAX_LINES = 5;
const TOC_MIN_ROW_PX = 64; // keeps short rows an easy tap target
const TOC_GAP_PX = 10;

export default {
    data: {
        cat: 0,  // router params
        item: 0,
        header: '',
        rows: [] // {n, l1..l5, rh, ih}: title lines, row height, list-item height (rh + gap)
    },

    onInit() {
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        const exam = c.items[this.item] || c.items[0];
        this.header = '< ' + c.name + ' - ' + exam.title;
        const rows = [];
        for (let i = 0; i < exam.pages.length; i++) {
            let lines = wrapText(exam.pages[i].label, TOC_LINE_EM);
            if (lines.length > TOC_MAX_LINES) {
                // longer than the row allows: the rest joins the last line, which ellipsizes with "…"
                lines = lines.slice(0, TOC_MAX_LINES - 1).concat([lines.slice(TOC_MAX_LINES - 1).join(' ')]);
            }
            const rh = Math.max(TOC_MIN_ROW_PX, lines.length * TOC_LINE_PX + 20);
            rows.push({
                n: lines.length,
                l1: lines[0] || '', l2: lines[1] || '', l3: lines[2] || '', l4: lines[3] || '', l5: lines[4] || '',
                rh: rh,
                ih: rh + TOC_GAP_PX
            });
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
