import { CATEGORIES, preview } from '../../common/content.js';
import { goHome, goDetail, goExam } from '../../common/nav.js';

// NOTE: lite page methods must not be named render/show/subscribe (render is the compiled template).

export default {
    data: {
        cat: 0, // router param
        header: '',
        title0: '',
        preview0: '',
        title1: '',
        preview1: '',
        title2: '',
        preview2: ''
    },

    onInit() {
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        this.header = '< ' + c.name + ' - ' + c.en;
        this.title0 = c.items[0].title;
        this.preview0 = preview(c.items[0]);
        this.title1 = c.items[1].title;
        this.preview1 = preview(c.items[1]);
        this.title2 = c.items[2].title;
        this.preview2 = preview(c.items[2]);
    },

    goBack() {
        goHome();
    },

    onSwipe(e) {
        if (e && e.direction === 'right') {
            goHome();
        }
    },

    // exams with several sections (Viết, Nói) open their table of contents, single-page ones open directly
    openExamAt(i) {
        const c = CATEGORIES[this.cat] || CATEGORIES[0];
        if (c.items[i].pages.length > 1) {
            goExam(this.cat, i);
        } else {
            goDetail(this.cat, i, 0);
        }
    },

    openItem0() {
        this.openExamAt(0);
    },
    openItem1() {
        this.openExamAt(1);
    },
    openItem2() {
        this.openExamAt(2);
    }
};
