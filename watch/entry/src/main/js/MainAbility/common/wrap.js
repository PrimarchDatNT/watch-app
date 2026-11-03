// Lite `text` has no line-height and no auto-growing height, so long text is wrapped here
// into lines and each line is rendered as its own list-item (the list scrolls).
// Widths are estimates in em (1em = font-size); MAX_EM keeps a safety margin so a line never
// overflows its text box and gets clipped.

const NARROW = ' .,:;!|\'`ilIjtf()[]{}';   // ~0.3em
const SEMI = 'r-"/\\';                      // ~0.4em
const WIDE = 'mwMW@%&';                     // ~0.9em

function charEm(ch) {
    const code = ch.charCodeAt(0);
    if (code >= 0x2E80) {
        return 1.0; // CJK, full width
    }
    if (NARROW.indexOf(ch) >= 0) {
        return 0.3;
    }
    if (SEMI.indexOf(ch) >= 0) {
        return 0.4;
    }
    if (WIDE.indexOf(ch) >= 0) {
        return 0.9;
    }
    if (code >= 65 && code <= 90) {
        return 0.68; // A-Z
    }
    if (code >= 48 && code <= 57) {
        return 0.58; // 0-9
    }
    if (code < 128) {
        return 0.56; // other ASCII lowercase / symbols
    }
    return 0.64; // Vietnamese and other accented Latin
}

function widthEm(s) {
    let w = 0;
    for (let i = 0; i < s.length; i++) {
        w += charEm(s.charAt(i));
    }
    return w;
}

// Splits a word that is wider than a whole line into pieces that fit.
function breakWord(word, maxEm, out) {
    let piece = '';
    let w = 0;
    for (let i = 0; i < word.length; i++) {
        const ch = word.charAt(i);
        const cw = charEm(ch);
        if (w + cw > maxEm && piece.length > 0) {
            out.push(piece);
            piece = '';
            w = 0;
        }
        piece += ch;
        w += cw;
    }
    return piece;
}

// Hidden 3-char prefixes added by scripts/import-vstep.py, stripped before display:
// '#F ' template frame (red), '#Q ' question/task (blue), '#A ' answer content (green).
const MARK_LEN = 3;
const MARKS = { '#F ': 'f', '#Q ': 'q', '#A ': 'a' };

function markOf(paragraph) {
    const k = MARKS[paragraph.substring(0, MARK_LEN)];
    return k === undefined ? '' : k;
}

// Paragraph kind: a hidden mark, or a visible "Q: ..." / "A: ..." prefix; '' for plain text.
function kindOf(paragraph) {
    const mark = markOf(paragraph);
    if (mark.length > 0) {
        return mark;
    }
    if (paragraph.indexOf('Q:') === 0) {
        return 'q';
    }
    if (paragraph.indexOf('A:') === 0) {
        return 'a';
    }
    return '';
}

// Like wrapText, but every line is {t: text, c: kind, q, a, n} so the template can colour questions
// and answers differently; continuation lines keep the kind of their paragraph. Lite cannot bind
// `class`, so the template picks one of three <text if="..."> by the booleans q / a / n.
export function wrapStyled(text, maxEm) {
    const out = [];
    const paragraphs = String(text).split('\n');
    for (let p = 0; p < paragraphs.length; p++) {
        const kind = kindOf(paragraphs[p]);
        const para = markOf(paragraphs[p]).length > 0 ? paragraphs[p].substring(MARK_LEN) : paragraphs[p];
        const lines = para.length > 0 ? wrapText(para, maxEm) : [''];
        for (let i = 0; i < lines.length; i++) {
            out.push({ t: lines[i], c: kind, q: kind === 'q', a: kind === 'a', f: kind === 'f', n: kind === '' });
        }
    }
    while (out.length > 0 && out[out.length - 1].t.length === 0) {
        out.pop();
    }
    return out;
}

// Greedy word wrap. '\n' starts a new line, an empty line in the input stays an empty line.
export function wrapText(text, maxEm) {
    const lines = [];
    const paragraphs = String(text).split('\n');
    for (let p = 0; p < paragraphs.length; p++) {
        const words = paragraphs[p].split(' ');
        let line = '';
        let lineEm = 0;
        for (let i = 0; i < words.length; i++) {
            const word = words[i];
            if (word.length === 0) {
                continue;
            }
            const wordEm = widthEm(word);
            const spaceEm = line.length > 0 ? charEm(' ') : 0;
            if (lineEm + spaceEm + wordEm <= maxEm) {
                line = line.length > 0 ? line + ' ' + word : word;
                lineEm += spaceEm + wordEm;
                continue;
            }
            if (line.length > 0) {
                lines.push(line);
            }
            if (wordEm > maxEm) {
                line = breakWord(word, maxEm, lines);
                lineEm = widthEm(line);
            } else {
                line = word;
                lineEm = wordEm;
            }
        }
        lines.push(line);
    }
    // drop trailing empty lines
    while (lines.length > 0 && lines[lines.length - 1].length === 0) {
        lines.pop();
    }
    return lines;
}
