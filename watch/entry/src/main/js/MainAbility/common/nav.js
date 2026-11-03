import router from '@system.router';

// Lite has only router.replace (no page stack, no router.back), so "back" is an explicit replace
// to the parent page. Params arrive as page data fields (they must be declared in the page's data).
export function goHome() {
    router.replace({ uri: 'pages/index/index' });
}

export function goList(cat) {
    router.replace({ uri: 'pages/category/category', params: { cat: cat } });
}

export function goExam(cat, item) {
    router.replace({ uri: 'pages/exam/exam', params: { cat: cat, item: item } });
}

export function goDetail(cat, item, page) {
    router.replace({ uri: 'pages/detail/detail', params: { cat: cat, item: item, page: page || 0, src: 'note' } });
}

export function goPhone() {
    router.replace({ uri: 'pages/detail/detail', params: { cat: -1, item: -1, page: 0, src: 'phone' } });
}
