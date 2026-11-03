"""Pull the "Ôn thi VSTEP" web app and turn its data into the watch app's content.js:
4 skills (Đọc / Nghe / Viết / Nói) x 3 exams (Đề 7 / 12 / 17). Each exam is a list of pages {label, text}.

    python3 scripts/import-vstep.py URL|path/to/index.html     (or set VSTEP_URL)

The site embeds everything in one inline script as `const D = {...}` (JSON). The watch has very little
RAM per app, so only what the user wants on the wrist is kept (no explanations, tips or notes):
  Đọc / Nghe  the 20 original questions (non-`extra` sections) + the document's answer, one page
  Viết        T1 prompt, T1 sample email, T2 prompt, T2 sample essay (paged)
  Nói         P1 Q/A per topic, P2 task + sample answer (template frame marked), P3 topic + sample, P3 follow-up Q/A
Paragraph prefixes #Q / #A / #F mark question (blue), answer (green) and template frame (red) on the watch.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "watch/entry/src/main/js/MainAbility/common/content.js"

# Characters the watch font may not have -> plain equivalents.
REPLACE = {
    "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...", "→": "->", "≈": "~",
    "•": "-", "·": "-", "×": "x", "↔": "<->", "←": "<-", " ": " ",
}


def load_html(src: str) -> str:
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={
            "ngrok-skip-browser-warning": "true",  # skip ngrok's browser interstitial
            "User-Agent": "gtpush-import/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8")
    return Path(src).read_text(encoding="utf-8")


def extract_data(html: str) -> dict:
    marker = "const D = "
    start = html.index(marker) + len(marker)
    data, _ = json.JSONDecoder().raw_decode(html, start)
    return data


def clean(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", str(s))           # markdown bold
    s = s.replace("**", "")                               # unpaired leftovers, e.g. from "**Mẹo:** ..."
    for a, b in REPLACE.items():
        s = s.replace(a, b)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


IPA_CHARS = "ˈˌəɪʊʃʒθðŋæɒʌɔːɜɛɑ"


def strip_ipa(s: str) -> str:
    """Drop /.../ phonetic transcriptions (the watch font has no IPA glyphs). Only slash-delimited
    runs that really contain IPA characters are removed, so 'A / B' or 'ý/đoạn' stay intact."""
    s = re.sub(r"\s*/[^/\n]{1,40}/", lambda m: "" if any(c in m.group(0) for c in IPA_CHARS) else m.group(0), s)
    return re.sub(r"[ \t]+([,.;:!?])", r"\1", s)


# Hidden paragraph prefixes the watch strips and turns into colours: frame red, question blue, answer green.
FRAME_MARK = "#F "
QUESTION_MARK = "#Q "
ANSWER_MARK = "#A "

# Explanations per speaking section (user's choices):
#   Part 2      yes — the full sample with its "(đưa ra lời giải thích)" BECAUSE-reasons, as in the key
#   Part 3      yes — the main talk stays complete, like a reading passage (ideas + their development)
#   Follow-up   yes — complete answers (set False to drop "because …", kept for "Why …?" questions)
P2_EXPLANATIONS = True
P3_EXPLANATIONS = True
FOLLOW_EXPLANATIONS = True

# Writing samples: the watch can't colour part of a line, so every red template phrase started a new line
# and cut sentences apart. User (2026-11-03): one colour, paragraphs as written. True restores the red phrases.
WRITING_FRAMES = False

# Opening greeting shown at the top of the first Part 1 page of every speaking exam:
# fixed phrases in the frame colour (red), the personal details as answer (green).
# The candidate's opener on the follow-up page, in the frame colour (red).
FOLLOW_OPENER = "Now, I am going to answer the follow-up questions."

SPEAKER_NAME = "Nguyen Thanh Dat"
SPEAKER_HOMETOWN = "Ha Noi"
GREETING = [
    (True, "Good afternoon. My name is"),
    (False, f"{SPEAKER_NAME}."),
    (True, "I am from"),
    (False, f"{SPEAKER_HOMETOWN}."),
]

def _norm(tok: str) -> str:
    return re.sub(r"[^a-z0-9']", "", tok.lower().replace("’", "'"))


def _template_words(template: str) -> list:
    """English fixed words of a template sentence, each a set of alternatives ('Thirdly/Finally')."""
    t = re.sub(r"\([^)]*\)", " ", template)              # (Vietnamese guidance)
    t = re.sub(r"[…]+|\.{2,}", " ", t)                    # ……… / ..... placeholders
    words = []
    for raw in t.split():
        alts = {_norm(a) for a in raw.split("/")}
        alts = {a for a in alts if a and a.isascii() and not a.isdigit()}
        if alts and all(re.fullmatch(r"[a-z0-9']+", a) for a in alts) and raw.isascii():
            words.append(alts)
    return words


def frame_segments(template: str, sample: str) -> list:
    """Split a sample sentence into [(is_frame, text)] by aligning it (LCS on words) with its template."""
    toks = sample.split()
    keys = [_norm(x) for x in toks]
    tw = _template_words(template)
    n, m = len(keys), len(tw)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if keys[i] and keys[i] in tw[j] else max(dp[i + 1][j], dp[i][j + 1])
    frame = [False] * n
    i = j = 0
    while i < n and j < m:
        if keys[i] and keys[i] in tw[j] and dp[i][j] == dp[i + 1][j + 1] + 1:
            frame[i] = True
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    for k in range(1, n - 1):            # absorb a 1-word gap inside the frame ("don't choose it BECAUSE")
        if not frame[k] and frame[k - 1] and frame[k + 1]:
            frame[k] = True
    if n >= 2 and not frame[-1] and frame[-2] and len(keys[-1]) <= 3:
        frame[-1] = True                 # ... and a short last word after it ("I don't choose it.")
    for k in range(n):                   # a lone matched word in the middle of content is not frame
        if frame[k] and k > 0 and not frame[k - 1] and (k + 1 == n or not frame[k + 1]) and len(keys[k]) <= 4:
            frame[k] = False
    segs = []
    for tok, f in zip(toks, frame):
        if segs and segs[-1][0] == f:
            segs[-1][1].append(tok)
        else:
            segs.append((f, [tok]))
    return [(f, " ".join(ws)) for f, ws in segs]


def drop_explanation(sentence: str) -> str:
    """'... is the best choice. I choose this BECAUSE <reason>' -> '... is the best choice.'
    "I don't choose option 1 - X - BECAUSE <reason>" -> "I don't choose option 1 - X."."""
    s = re.sub(r"\s*I choose this\s+because\b.*$", "", sentence, flags=re.I)
    s = re.sub(r"\s*,?\s*\bbecause\b.*$", "", s, flags=re.I)
    s = s.rstrip(" -,;")
    return s if s.endswith((".", "!", "?")) else s + "."


# Where a Part 3 idea's explanation/development starts: ", so …", ", which …", ", and as a result …", "because …"
DEVELOPMENT = re.compile(r"\s*(?:,\s*(?:and\s+)?as a result|,\s*so that|,?\s+so|,\s*which|,?\s+because|,\s*as|,\s*for example|,\s*since)\b", re.I)


def drop_development(sentence: str) -> str:
    """'Firstly, reading improves our knowledge, so we know more …' -> 'Firstly, reading improves our knowledge.'
    Never cuts inside the first two words (so 'So, …' openers survive)."""
    start = len(" ".join(sentence.split()[:2]))
    m = DEVELOPMENT.search(sentence, start)
    if not m:
        return sentence
    s = sentence[: m.start()].rstrip(" -,;")
    return s if s.endswith((".", "!", "?")) else s + "."


def p2_trim(tpl: str, s: str) -> str:
    """Part 2: drop the '(đưa ra lời giải thích)' BECAUSE-reasons."""
    return drop_explanation(s) if "giải thích" in tpl.lower() else s


def p3_trim(tpl: str, s: str) -> str:
    """Part 3: keep each idea without its 'Giải thích/phát triển ý', and the conclusion as just the topic."""
    t = tpl.lower()
    return drop_development(s) if ("giải thích" in t or "đọc lại câu chủ đề" in t) else s


def framed_sample(templates: list, samples: list, content_mark: str = "", trim=None) -> str:
    """Sample answer with its template frame marked: one paragraph per segment, blank line per sentence.
    Frame segments get FRAME_MARK, the filled-in content gets content_mark. trim(template, sentence)
    may shorten a sentence first (used to drop explanations)."""
    out = []
    for k, s in enumerate(samples):
        s = clean(strip_ipa(s))
        tpl = templates[k] if k < len(templates) else ""
        if trim and tpl:
            s = trim(tpl, s)
        segs = frame_segments(tpl, s) if tpl else [(False, s)]
        if out:
            out.append("")
        out += [(FRAME_MARK + t) if f else (content_mark + t) for f, t in segs]
    return "\n".join(out)


def drop_reason(question: str, answer: str) -> str:
    """Follow-up answer without its 'because …' explanation. Kept for 'Why …?' questions, where the
    reason IS the answer ('Why do people smoke?' -> '… because their friends do it')."""
    if re.match(r"\s*why\b", question, re.I):
        return answer
    s = re.sub(r"\s*,?\s+because\b.*$", "", answer, flags=re.I).rstrip(" -,;")
    return s if s.endswith((".", "!", "?")) else s + "."


def qa(q: str, a: str) -> str:
    return f"Q: {clean(strip_ipa(q))}\nA: {clean(strip_ipa(a))}"


def cut(s: str, n: int) -> str:
    s = clean(s)
    if len(s) <= n:
        return s
    sp = s.rfind(" ", 0, n - 3)
    return s[: sp if sp > n // 2 else n - 3].rstrip(",;: ") + "..."


def extract_js_array(html: str, name: str) -> list:
    """A `const NAME = [...]` data literal from the page's script, parsed as JSON (never executed)."""
    marker = f"const {name} = "
    i = html.index(marker) + len(marker)
    depth, j = 0, i
    while True:
        c = html[j]
        if c == '"':                                   # skip string contents (may hold brackets)
            j += 1
            while html[j] != '"':
                j += 2 if html[j] == "\\" else 1
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return json.loads(re.sub(r",\s*\]", "]", html[i:j + 1]))


KEEP_SINGLE = {"Dear", "Nowadays", "Regarding", "Although", "Besides", "Therefore"}


def template_phrases(text: str) -> list:
    """Fixed English phrases of one template line: placeholders (___, …, [..]), Vietnamese notes (..)
    and '/' alternatives split it; one phrase per sentence; 'Dear Julie' -> 'Dear'; example names dropped.
    'In conclusion, although' also yields 'In conclusion' so the opener alone is recognised."""
    t = re.sub(r"<[^>]+>", "", text)
    t = re.sub(r"^[^:]*[^\x00-\x7f][^:]*:\s*", "", t)       # Vietnamese label "Trang trọng hơn: …"
    t = clean(t).replace("Mr.", "Mr").replace("Mrs.", "Mrs")
    t = re.sub(r"\([^)]*\)", " | ", t)
    t = re.sub(r"\[[^\]]*\]", " | ", t)
    out = []
    for alt in re.split(r"\s*/\s*", t):
        for part in re.split(r"_{2,}|\.\.\.|\|", alt):
            for p in re.split(r"(?<=[.!?])\s+", part):
                p = p.strip(" ,;./!?")
                if re.match(r"Dear\b", p):
                    p = "Dear"
                if re.fullmatch(r"[A-Z][a-z]+", p) and p not in KEEP_SINGLE:
                    continue
                if len(p) < 4 or not p.isascii() or not re.search(r"[A-Za-z]", p):
                    continue
                out.append(p)
                if "I'm " in p:                                   # samples also write "I am"
                    out.append(p.replace("I'm ", "I am "))
                head = p.split(",")[0].strip()
                if head != p and len(head.split()) >= 2:
                    out.append(head)
    return out


def writing_phrases(html: str) -> dict:
    """Template phrases of the email (EMAIL_TPL) and the essay (ESSAY_TPL + per-type body frames)."""
    def rows_phrases(rows, cols):
        out = []
        for row in rows:
            for col in cols(row):
                for line in col if isinstance(col, list) else [col]:
                    out += template_phrases(line)
        return out
    # email: the model line plus its note column, which holds the formal variants
    # ("Thank you very much for your email about ___. / I am writing to tell you about ___.")
    email = rows_phrases(extract_js_array(html, "EMAIL_TPL"), lambda r: r[1:3])
    essay = rows_phrases(extract_js_array(html, "ESSAY_TPL"), lambda r: [r[1]])
    essay += rows_phrases(extract_js_array(html, "ESSAY_TYPES"), lambda r: r[2:])
    return {"email": email, "essay": essay}


def mark_frame(text: str, phrases: list) -> list:
    """[(is_frame, segment)]: template phrases found in the text (longest first, case-insensitive,
    word-bounded, non-overlapping, taking a comma/period right after them) vs the rest."""
    spans = []
    for p in sorted(set(phrases), key=len, reverse=True):
        pat = re.compile(r"(?<![A-Za-z])" + re.escape(p).replace(r"\ ", r"\s+") + r"(?![A-Za-z])[,.]?", re.I)
        for m in pat.finditer(text):
            if all(m.end() <= a or m.start() >= b for a, b in spans):
                spans.append((m.start(), m.end()))
    spans.sort()
    segs, pos = [], 0
    for a, b in spans:
        if a > pos:
            segs.append((False, text[pos:a]))
        segs.append((True, text[a:b]))
        pos = b
    if pos < len(text):
        segs.append((False, text[pos:]))
    return [(f, s.strip()) for f, s in segs if s.strip(" ,.")]


def framed_paragraphs(paragraphs: list, phrases: list) -> str:
    """Sample text, blank line between paragraphs: each paragraph whole in green (#A), or with WRITING_FRAMES
    split into template phrases red (#F) and content green (#A)."""
    out = []
    for para in paragraphs:
        if out:
            out.append("")
        if WRITING_FRAMES:
            out += [(FRAME_MARK if f else ANSWER_MARK) + s for f, s in mark_frame(clean(para), phrases)]
        else:
            out.append(ANSWER_MARK + clean(para))
    return "\n".join(out)


# Question-type phrases shown as the red "frame" of a question (most specific first). Lowercase-insensitive
# except NOT / EXCEPT, which only count in capitals.
_I = re.I
READING_FRAMES = [
    (r"It can be inferred from the passage that", _I),
    (r"Based on the information in paragraphs? \d+(?:\s*and\s*\d+)?,?", _I),
    (r"According to (?:paragraph \d+|the passage),?", _I),
    (r"best expresses the essential information in the (?:bold|highlighted) sentence", _I),
    (r"Which of the following(?: statements)?", _I),
    (r"Which of the sentences", _I),
    (r"What does the passage mainly discuss", _I),
    (r"What is the (?:main idea|main purpose) of the passage", _I),
    (r"(?:main idea|main purpose) of the passage", _I),
    (r"Which title best fits the passage", _I),
    (r"Why does the author mention", _I),
    (r"The author (?:suggests|mentions|implies)(?: that)?", _I),
    (r"the (?:writer|author)'s attitude", _I),
    (r"what can be inferred about", _I),
    (r"(?:can|could) be inferred(?: from (?:the passage|paragraph \d+))?", _I),
    (r"all of the following(?: are true about| as)?", _I),
    (r"The (?:word|phrasal verb|phrase)", _I),
    (r"in (?:the )?(?:paragraphs?|lines?) \d+(?:\s*and\s*\d+)?,?", _I),
    (r"in the title", _I),
    (r"is closest in meaning to:?", _I),
    (r"refers to", _I),
    (r"means that", _I),
    (r"is true (?:of|about)", _I),
    (r"In relation to", _I),
    (r"Based on", _I),
    (r"\bNOT\b", 0),
    (r"\bEXCEPT\b", 0),
    (r"_{3}\s*\.?", 0),
]
QUESTION_WORD = (r"^(?:What time|What kind of|How many times|How many|How much|How old|What|Where|When|Who|Why|Which|How)\b", _I)
READING_FRAMES.append(QUESTION_WORD)        # lowest priority: plain wh-questions get their question word red
LISTENING_FRAMES = [
    QUESTION_WORD,
    (r"(?:probably )?do next", _I),
]


def mark_patterns(text: str, patterns: list) -> list:
    """[(is_frame, segment)] for regex frames: earlier patterns win overlaps; adjacent frames merge;
    punctuation-only pieces (like a lone '?') stick to the previous segment."""
    spans = []
    for pat, flags in patterns:
        for m in re.finditer(r"(?<![A-Za-z])(?:" + pat + r")(?![A-Za-z])", text, flags):
            if m.end() > m.start() and all(m.end() <= a or m.start() >= b for a, b in spans):
                spans.append((m.start(), m.end()))
    spans.sort()
    raw, pos = [], 0
    for a, b in spans:
        if a > pos:
            raw.append((False, text[pos:a]))
        raw.append((True, text[a:b]))
        pos = b
    if pos < len(text):
        raw.append((False, text[pos:]))
    # a short gap (<= 2 words, no quotes) between two frames joins them ("statements | is | NOT"),
    # except right after "The word/phrase/phrasal verb", where the gap IS the word being asked about
    for k in range(1, len(raw) - 1):
        f, s = raw[k]
        if (not f and raw[k - 1][0] and raw[k + 1][0] and len(s.split()) <= 2
                and not re.search(r"[\"']", s) and not re.search(r"(?:word|phrase|verb)\s*$", raw[k - 1][1], re.I)):
            raw[k] = (True, s)
    segs = []
    for f, s in raw:
        s = s.strip()
        if not s:
            continue
        if segs and (segs[-1][0] == f or not re.search(r"[A-Za-z0-9\"']", s)):
            segs[-1] = (segs[-1][0], segs[-1][1] + ("" if re.match(r"[?.,:;!]", s) else " ") + s)
        else:
            segs.append((f, s))
    return segs


def question_qa(q: dict, frames: list) -> str:
    """Numbered question (question-type frame red, the rest blue) + the correct option's text (green),
    exactly as the document's key (`ans`). No A/B/C/D letters, no explanations (`expl`) or notes (`warn`)."""
    text = re.sub(r"_{3,}", "___", clean(q["q"]))
    lines = [(FRAME_MARK if f else QUESTION_MARK) + s for f, s in mark_patterns(text, frames)]
    lines[0] = lines[0][:3] + f"{q['n']}. " + lines[0][3:]
    return "\n".join(lines) + f"\n{ANSWER_MARK}{clean(q['opts'][q['ans']])}"


def quiz_item(exam: dict, sub: str, frames: list) -> dict:
    """Only the original exam questions (sections without the site's `extra` flag), all on ONE
    scrollable page (the user wants the 20 questions at once, not split)."""
    qs = [q for s in exam["sections"] if not s.get("extra") for q in s["questions"]]
    text = "\n\n".join(question_qa(q, frames) for q in qs)
    return {"title": f'Đề {exam["id"]}', "sub": f"{len(qs)} câu - {sub}", "pages": [{"label": "", "text": text}]}


def essay_prompt(lines: list) -> str:
    """The line that states the essay question (not 'You should spend/write ...' boilerplate)."""
    for line in lines:
        if re.search(r"write an essay|discuss|to what extent|do you agree", line, re.I):
            return line
    useful = [l for l in lines if not re.match(r"\s*You should (spend|write)", l)]
    return max(useful or lines, key=len)


def page(label: str, text: str) -> dict:
    """A section page. Never truncated: the watch page scrolls, and answers must stay complete."""
    return {"label": label, "text": text}


def first_sentence(text: str) -> str:
    """First sentence; titles like 'Mr.' / 'Mrs.' don't end it ("Write an email to Mr. and Mrs. James.")."""
    return re.split(r"(?<!Mr\.)(?<!Mrs\.)(?<!Ms\.)(?<!Dr\.)(?<=[.?!])\s+", clean(text).strip())[0]


def simple_task1(prompt: list) -> str:
    """Only the question, no hints (user): the "Write an email …" sentence ("Write an email responding to Julie.")."""
    for line in prompt:
        if re.match(r"\s*Write an email", line, re.I):
            return first_sentence(line)
    return first_sentence(prompt[1] if len(prompt) > 1 else prompt[0])


def simple_task2(prompt: list) -> str:
    """Only the essay question, shortened: "Now, write an essay to an educated reader to discuss X. Include …"
    -> "Discuss X." (no type description, no word count, no 'include reasons' hint)."""
    q = first_sentence(essay_prompt(prompt))
    q = re.sub(r"^(?:Now,\s*)?write an essay (?:to|for) (?:an )?educated readers? to\s+", "", q, flags=re.I)
    return q[:1].upper() + q[1:]


def writing_title_t1(email: list) -> str:
    """Menu title like "P1: Sports": the email's recipient from its "Dear …," line ("T1: Email to Julie")."""
    m = re.match(r"\s*Dear\s+(.+?)[,.]?\s*$", clean(email[0])) if email else None
    return f"T1: Email to {m.group(1)}" if m else "T1: Đề + email mẫu"


def writing_title_t2(essay: list) -> str:
    """Menu title: the essay topic, i.e. what fills "Nowadays, ___ has become" in the sample's opening."""
    m = re.match(r"\s*Nowadays,\s*(.+?)\s+has become\b", clean(essay[0])) if essay else None
    return f"T2: {m.group(1)[:1].upper()}{m.group(1)[1:]}" if m else "T2: Đề + bài mẫu"


def writing_item(exam: dict, phrases: dict) -> dict:
    """One page per Task 1 email sample (the key has two), then the essay, like Speaking's "Đề + đáp án":
    the short task (blue) then the full sample in green (template phrases red only with WRITING_FRAMES).
    No tips/explanations (user asked)."""
    t1, t2 = exam["t1"], exam["t2"]
    task1 = QUESTION_MARK + simple_task1(t1["prompt"])
    emails = [s if isinstance(s, list) else [s] for s in t1.get("samples") or []]
    pages = []
    for k, email in enumerate(emails):
        label = writing_title_t1(email) + (f" (mẫu {k + 1})" if k else "")
        pages.append({"label": label, "text": task1 + "\n\n" + framed_paragraphs(email, phrases["email"])})
    if not pages:
        pages.append({"label": writing_title_t1([]), "text": task1})
    task2 = [QUESTION_MARK + simple_task2(t2["prompt"])]
    essay = [p["en"] for p in t2.get("essay", [])]
    text2 = "\n".join(task2) + ("\n\n" + framed_paragraphs(essay, phrases["essay"]) if essay else "")
    pages.append({"label": writing_title_t2(essay), "text": text2})
    sub = f"{len(emails)} email + bài luận mẫu" if len(emails) > 1 else "Email + bài luận mẫu"
    return {"title": f'Đề {exam["id"]}', "sub": sub, "pages": pages}


def p2_task(p2: dict) -> str:
    """Part 2 task as written in the exam, in English (user: no Vietnamese summary): the situation,
    then its three options as "- …" lines, all question blue."""
    lines = [f"{QUESTION_MARK}Situation: {clean(p2['situation'])}"]
    lines += [f"{QUESTION_MARK}- {clean(o)}" for o in p2.get("options", [])]
    return "\n".join(lines)


def p3_task(p3: dict, expl: dict) -> str:
    """Part 3 task as shown in the exam, in English: the topic + the mind map's three main points
    (without the 'Your own ideas' branch), all question blue."""
    lines = [f"{QUESTION_MARK}Topic: {clean(p3['topic'])}"]
    ideas = [clean(x.get("idea", "")) for x in (expl or {}).get("p3", {}).get("ideas", [])]
    lines += [f"{QUESTION_MARK}- {i}" for i in ideas if i and "own idea" not in i.lower()]
    return "\n".join(lines)


def speaking_item(exam: dict, expl: dict = None) -> dict:
    """Sections: one Q&A page per Part 1 topic (the first one opens with the greeting), P2 task (English) +
    sample, P3 topic + main points + sample, P3 follow-up Q&A (opened by FOLLOW_OPENER)."""
    pages = []
    greeting = "\n".join((FRAME_MARK if frame else ANSWER_MARK) + text for frame, text in GREETING)
    for i, topic in enumerate(exam["p1"]):
        name = clean(topic["title"]).replace("Now, let's talk about", "").strip(" .")
        name = name[:1].upper() + name[1:]
        # the examiner's topic opener ("Now, let's talk about sports.") heads each topic, in question blue
        body = QUESTION_MARK + clean(topic["title"]) + "\n\n" + "\n\n".join(qa(q["q"], q["a"]) for q in topic["qs"])
        if i == 0:
            body = greeting + "\n\n" + body
        pages.append(page(f"P1: {name}", body))
    # Part 2 on one page: the original English task (blue), then the sample answer (green) with its
    # template frame (red).
    p2 = exam["p2"]
    task = p2_task(p2)
    answer = framed_sample(p2.get("template", []), p2.get("sample", []), ANSWER_MARK,
                           None if P2_EXPLANATIONS else p2_trim)
    # titled by its topic like "P1: Sports": the situation's first sentence (no short topic exists for P2)
    p2_topic = re.split(r"(?<=[.?!])\s", clean(p2["situation"]))[0].rstrip(".")
    pages.append(page(f"P2: {p2_topic}", task + ("\n\n" + answer if answer else "")))
    p3 = exam["p3"]
    # Part 3 coloured like Part 2: task (topic + mind-map branches) blue, answer green, template frame red.
    if p3.get("sample"):
        task = p3_task(p3, expl)
        answer = framed_sample(p3.get("template", []), p3["sample"], ANSWER_MARK,
                               None if P3_EXPLANATIONS else p3_trim)
        pages.append(page(f"P3: {clean(p3['topic']).rstrip('.')}", task + "\n\n" + answer))
    if p3.get("follow"):
        follow = [(f["q"], f["a"] if FOLLOW_EXPLANATIONS else drop_reason(f["q"], clean(strip_ipa(f["a"]))))
                  for f in p3["follow"]]
        body = FRAME_MARK + FOLLOW_OPENER + "\n\n" + "\n\n".join(qa(q, a) for q, a in follow)
        pages.append(page("P3: Follow-up questions", body))
    return {"title": f'Đề {exam["id"]}', "sub": "Part 3: " + cut(p3["topic"], 40), "pages": pages}


def build(D: dict, phrases: dict) -> list:
    return [
        {"name": "Đọc", "en": "Reading", "icon": "reading",
         "items": [quiz_item(e, "Passage 1-2", READING_FRAMES) for e in D["reading"]]},
        {"name": "Nghe", "en": "Listening", "icon": "listening",
         "items": [quiz_item(e, "Part 1-2", LISTENING_FRAMES) for e in D["listening"]]},
        {"name": "Viết", "en": "Writing", "icon": "writing",
         "items": [writing_item(e, phrases) for e in D["writing"]["full"]]},
        {"name": "Nói", "en": "Speaking", "icon": "speaking",
         "items": [speaking_item(e, D.get("sexpl", {}).get(e["id"])) for e in D["speaking"]["full"]]},
    ]


def write_js(cats: list) -> None:
    for c in cats:
        if len(c["items"]) != 3:
            raise SystemExit(f'{c["name"]}: expected 3 exams, got {len(c["items"])} (the pages show exactly 3)')
    js = (
        "// GENERATED by scripts/import-vstep.py from the \"Ôn thi VSTEP\" web app — do not edit by hand, re-run the script.\n"
        "// 4 skills x 3 exams; each exam is a list of pages {label, text} sized for the watch\n"
        "// (answer keys, tips, prompts; Writing adds the sample essay over several pages).\n"
        "export const CATEGORIES = " + json.dumps(cats, ensure_ascii=False, indent=2) + ";\n\n"
        "// One-line preview of an exam for the category page.\n"
        "export function preview(item) {\n"
        "    if (item.sub) {\n"
        "        return item.sub;\n"
        "    }\n"
        "    const flat = String(item.pages[0].text).split('\\n').join(' ');\n"
        "    return flat.length > 40 ? flat.substring(0, 40) : flat;\n"
        "}\n"
    )
    OUT.write_text(js, encoding="utf-8")


def main() -> None:
    # the source URL is deliberately not stored in the repo (it points at the user's own machine)
    src = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VSTEP_URL", "")
    if not src:
        raise SystemExit("usage: import-vstep.py URL|index.html   (or set VSTEP_URL)")
    html = load_html(src)
    cats = build(extract_data(html), writing_phrases(html))
    write_js(cats)
    total = 0
    for c in cats:
        for it in c["items"]:
            sizes = [len(p["text"]) for p in it["pages"]]
            total += sum(sizes)
            labels = ", ".join(f'{p["label"] or "-"}:{len(p["text"])}' for p in it["pages"])
            print(f'{c["name"]:5} {it["title"]:6} pages[{labels}]  sub="{it["sub"]}"')
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {total} chars of text)")


if __name__ == "__main__":
    main()
