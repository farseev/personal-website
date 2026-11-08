#!/usr/bin/env python3
"""farseev.com multilingual build (standard library only). Adapted from the exostride.sg tool.

English pages are the template and the source text: index.html, blog/index.html, blog/<slug>/index.html.
Every translatable piece of text (visible text runs, alt/aria/title attributes, meta description, OG/Twitter
text, JSON-LD text) is a *segment*, keyed by a hash of its English text. Translations live in
i18n/<code>.json ({id: text}); i18n/source.json holds the English, i18n/pages.json the ids per page.

Static language pages are written to /<code>/... (e.g. /ja/, /ja/blog/<slug>/). A page is published in a
language only when 100% of its segments are translated, and a language goes live when its home page is
complete. Until then the English page is used (and the home page keeps its in-browser dictionary for
zh/ja/ko/hi/ru, which stays as it was).

Commands
  python3 tools/i18n.py extract                 refresh i18n/source.json + i18n/pages.json
  python3 tools/i18n.py import-dict             import the home page's in-browser dictionary (zh, ja, ko, hi, ru)
                                                into the translation memory, where the English still matches
  python3 tools/i18n.py todo <code> [page ...]  print untranslated segments as  id<TAB>English
  python3 tools/i18n.py merge <code> <file>     merge  id<TAB>translation  lines (placeholders checked)
  python3 tools/i18n.py build [--prune]         render every complete language page, switcher, hreflang, sitemaps
  python3 tools/i18n.py status                  coverage per language

Inline markup inside a segment appears as <g1>…</g1> (paired tags) and <x1/> (void tags); keep them.
Elements marked translate="no" (names, paper titles, sources lists, the language menu) are never segments.
"""
import hashlib, html, json, os, re, sys, glob
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://farseev.com"
I18N = os.path.join(ROOT, "i18n")
TODAY = "2026-11-08"

# code, url dir, hreflang/html lang, og:locale, native name, "Language" label, Google Fonts family (or None)
LANGS = [
    ("en", "", "en", "en_US", "English", "Language", None),
    ("zh-hans", "zh-hans", "zh-Hans", "zh_CN", "简体中文", "语言", "Noto+Sans+SC:wght@400;500;700;900"),
    ("zh-hant", "zh-hant", "zh-Hant", "zh_TW", "繁體中文", "語言", "Noto+Sans+TC:wght@400;500;700;900"),
    ("ja", "ja", "ja", "ja_JP", "日本語", "言語", "Noto+Sans+JP:wght@400;500;700;900"),
    ("ko", "ko", "ko", "ko_KR", "한국어", "언어", "Noto+Sans+KR:wght@400;500;700;900"),
    ("th", "th", "th", "th_TH", "ไทย", "ภาษา", "Noto+Sans+Thai:wght@400;500;700;900"),
    ("vi", "vi", "vi", "vi_VN", "Tiếng Việt", "Ngôn ngữ", None),
    ("id", "id", "id", "id_ID", "Bahasa Indonesia", "Bahasa", None),
    ("ms", "ms", "ms", "ms_MY", "Bahasa Melayu", "Bahasa", None),
    ("hi", "hi", "hi", "hi_IN", "हिन्दी", "भाषा", "Noto+Sans+Devanagari:wght@400;500;700;900"),
    ("fil", "fil", "fil", "tl_PH", "Filipino", "Wika", None),
    ("es", "es", "es", "es_ES", "Español", "Idioma", None),
    ("fr", "fr", "fr", "fr_FR", "Français", "Langue", None),
    ("de", "de", "de", "de_DE", "Deutsch", "Sprache", None),
    ("pt", "pt", "pt", "pt_BR", "Português", "Idioma", None),
    ("ar", "ar", "ar", "ar_AR", "العربية", "اللغة", "Noto+Sans+Arabic:wght@400;500;700;900"),
    ("ru", "ru", "ru", "ru_RU", "Русский", "Язык", None),
]
L = {l[0]: dict(code=l[0], dir=l[1], tag=l[2], og=l[3], name=l[4], label=l[5], font=l[6]) for l in LANGS}
CODES = [l[0] for l in LANGS]
DICT_CODE = {"zh-hans": "zh", "ja": "ja", "ko": "ko", "hi": "hi", "ru": "ru"}  # home page in-browser dictionary
SHARED_IDS = {"person", "somin", "website"}

INLINE = {"a", "abbr", "b", "br", "code", "em", "i", "mark", "q", "s", "small", "span", "strong", "sub", "sup",
          "time", "u", "wbr", "img"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "param"}
SKIP = {"script", "style", "svg", "noscript", "template", "select"}
ATTRS = ("alt", "title", "aria-label", "placeholder")
META_NAMES = {"description", "twitter:title", "twitter:description", "twitter:image:alt"}
META_PROPS = {"og:title", "og:description", "og:image:alt", "article:section"}
LD_TEXT_KEYS = {"name", "headline", "description", "abstract", "text", "articleSection", "caption", "jobTitle",
                "disambiguatingDescription"}
LD_SKIP_TYPES = {"Organization", "WebSite", "CreativeWork", "CollegeOrUniversity"}
KEEP_RE = re.compile(r"^(?:(?:Prof\. )?Aleks(?:andr)? Farseev|SOMIN(?:\.ai)?|SoMin\.ai|Google Scholar|LinkedIn|Forbes|"
                     r"Crunchbase|e27|ACM Digital Library|Accordion Singapore|"
                     r"Orthodox Singapore|Faith Driven (?:SG|Singapore)|faithdriven\.sg|法信夫|AF|"
                     r"[\d\s.,:+×x–\-−%°~<>/()·→←↑↓|]*)$")
PH_RE = re.compile(r"</?g\d+>|<x\d+/>")
SUFFIX = " | Prof. Aleks Farseev"   # title suffix kept untranslated


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def sid(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def norm(s):
    return re.sub(r"[ \t\n\r\f\v]+", " ", s).strip(" \t\n\r\f\v")


def translatable(t):
    t = t.replace("\xa0", " ").strip()
    return bool(t) and bool(re.search(r"[^\W\d_]", t)) and not KEEP_RE.match(t)


# ---------------------------------------------------------------- parsing
class Tok:
    __slots__ = ("kind", "tag", "attrs", "start", "end", "raw", "el")

    def __init__(self, kind, tag, attrs, start):
        self.kind, self.tag, self.attrs, self.start, self.end, self.raw, self.el = kind, tag, attrs, start, None, None, None


class El:
    __slots__ = ("tag", "attrs", "open", "close", "children", "parent")

    def __init__(self, tag, attrs, open_i, parent):
        self.tag, self.attrs, self.open, self.close, self.children, self.parent = tag, dict(attrs), open_i, None, [], parent


class Parser(HTMLParser):
    def __init__(self, doc):
        super().__init__(convert_charrefs=False)
        self.lines = [0] + [m.end() for m in re.finditer("\n", doc)]
        self.toks = []

    def off(self):
        ln, col = self.getpos()
        return self.lines[ln - 1] + col

    def add(self, kind, tag=None, attrs=()):
        self.toks.append(Tok(kind, tag, attrs, self.off()))

    def handle_starttag(self, tag, attrs): self.add("start", tag, attrs)
    def handle_startendtag(self, tag, attrs): self.add("startend", tag, attrs)
    def handle_endtag(self, tag): self.add("end", tag)
    def handle_data(self, d): self.add("data")
    def handle_entityref(self, n): self.add("data")
    def handle_charref(self, n): self.add("data")
    def handle_comment(self, d): self.add("other")
    def handle_decl(self, d): self.add("other")
    def handle_pi(self, d): self.add("other")
    def unknown_decl(self, d): self.add("other")


def parse(doc):
    p = Parser(doc)
    p.feed(doc)
    p.close()
    toks = p.toks
    for i, t in enumerate(toks):
        t.end = toks[i + 1].start if i + 1 < len(toks) else len(doc)
        t.raw = doc[t.start:t.end]
    root = El("#root", (), -1, None)
    cur = root
    for i, t in enumerate(toks):
        if t.kind in ("start", "startend"):
            el = El(t.tag, t.attrs, i, cur)
            t.el = el
            cur.children.append(("el", el))
            if t.kind == "start" and t.tag not in VOID:
                cur = el
            else:
                el.close = i
        elif t.kind == "end":
            x = cur
            while x is not root and x.tag != t.tag:
                x = x.parent
            if x is not root:
                x.close = i
                cur = x.parent
        elif t.kind == "data":
            cur.children.append(("tok", i))
    return toks, root


# ---------------------------------------------------------------- segmentation
class Seg:
    __slots__ = ("kind", "text", "id", "a", "b", "tags", "lead", "trail", "suffix", "tok", "attr", "parent")


def text_of_children(toks, children, tagmap):
    out = []

    def ser(kind, x):
        if kind == "tok":
            out.append(html.unescape(toks[x].raw))
        else:
            n = len(tagmap) + 1
            if x.close is None or x.close == x.open or x.tag in VOID:
                tagmap.append(("x", x.open, None))
                out.append("<x%d/>" % n)
            else:
                tagmap.append(("g", x.open, x.close))
                out.append("<g%d>" % n)
                for c in x.children:
                    ser(*c)
                out.append("</g%d>" % n)
    for c in children:
        ser(*c)
    return "".join(out)


def no_translate(el):
    return el.tag in SKIP or el.attrs.get("translate") == "no"


def segments(doc):
    toks, root = parse(doc)
    segs = []
    blocked = set()  # token indexes inside translate="no" / skipped elements (no attribute segments there)

    def block(el):
        if el.close is not None:
            blocked.update(range(el.open, el.close + 1))
        else:
            blocked.add(el.open)

    def visit(el):
        if el is not root and no_translate(el):
            block(el)
            return
        runs, run = [], []
        for c in el.children:
            if (c[0] == "tok" or c[1].tag in INLINE) and not (c[0] == "el" and no_translate(c[1])):
                run.append(c)
            else:
                if run:
                    runs.append(("run", run)); run = []
                runs.append(("blk", c))
        if run:
            runs.append(("run", run))
        for kind, r in runs:
            if kind == "blk":
                if r[0] == "el":
                    visit(r[1])
                continue
            if any(k == "tok" and toks[x].raw.strip() for k, x in r):
                make_run_seg(r, el)
            else:
                for k, x in r:
                    if k == "el":
                        visit(x)

    def first_tok(c):
        return c[1] if c[0] == "tok" else c[1].open

    def last_tok(c):
        return c[1] if c[0] == "tok" else (c[1].close if c[1].close is not None else c[1].open)

    def make_run_seg(r, parent):
        while r and r[0][0] == "tok" and not toks[r[0][1]].raw.strip():
            r = r[1:]
        while r and r[-1][0] == "tok" and not toks[r[-1][1]].raw.strip():
            r = r[:-1]
        if not r:
            return
        tagmap = []
        t = norm(text_of_children(toks, r, tagmap))
        a, b = toks[first_tok(r[0])].start, toks[last_tok(r[-1])].end
        s = Seg()
        s.kind, s.a, s.b, s.tags, s.tok, s.attr, s.parent = "run", a, b, tagmap, None, None, parent
        s.lead = re.match(r"\s*", doc[a:b]).group(0)
        s.trail = re.search(r"\s*$", doc[a:b]).group(0)
        s.suffix = ""
        if t.endswith(SUFFIX) and not tagmap:
            t, s.suffix = t[: -len(SUFFIX)], SUFFIX
        s.text = t
        s.id = sid(t) if translatable(PH_RE.sub("", t)) else None
        segs.append(s)

    visit(root)
    for i, t in enumerate(toks):
        if t.kind not in ("start", "startend") or i in blocked:
            continue
        at = dict(t.attrs)
        names = [a for a in ATTRS if at.get(a)]
        if t.tag == "meta" and at.get("content") and (at.get("name") in META_NAMES or at.get("property") in META_PROPS):
            names.append("content")
        for a in names:
            val = norm(at[a])
            s = Seg()
            s.kind, s.tok, s.attr, s.tags, s.lead, s.trail, s.a, s.b, s.parent = "attr", i, a, [], "", "", None, None, None
            s.suffix = ""
            if val.endswith(SUFFIX):
                val, s.suffix = val[: -len(SUFFIX)], SUFFIX
            s.text = val
            s.id = sid(val) if translatable(val) else None
            segs.append(s)
    for i, t in enumerate(toks):
        if t.kind == "start" and t.tag == "script" and dict(t.attrs).get("type") == "application/ld+json":
            for val in ld_texts(json.loads(toks[i + 1].raw)):
                s = Seg()
                s.kind, s.tok, s.attr, s.tags, s.lead, s.trail, s.a, s.b, s.suffix, s.parent = "ld", i + 1, None, [], "", "", None, None, "", None
                s.text = val
                s.id = sid(val) if translatable(val) else None
                segs.append(s)
    return toks, segs


def ld_texts(d, skip=False):
    out = []
    if isinstance(d, dict):
        skip = skip or d.get("@type") in LD_SKIP_TYPES
        for k, v in d.items():
            if isinstance(v, str):
                if not skip and k in LD_TEXT_KEYS:
                    out.append(norm(v[: -len(SUFFIX)] if v.endswith(SUFFIX) else v))
            else:
                out += ld_texts(v, skip)
    elif isinstance(d, list):
        for v in d:
            out += ld_texts(v, skip)
    return out


# ---------------------------------------------------------------- pages
def en_pages():
    pages = ["index.html", "blog/index.html"]
    pages += sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "blog", "*", "index.html")))
    return pages


def page_path(rel):
    return "/" + rel[: -len("index.html")]


def lang_path(code, path):
    d = L[code]["dir"]
    return ("/" + d + path) if d else path


def load_tm(code):
    p = os.path.join(I18N, code + ".json")
    return json.loads(read(p)) if os.path.exists(p) else {}


def save_tm(code, tm):
    write(os.path.join(I18N, code + ".json"), json.dumps(dict(sorted(tm.items())), ensure_ascii=False, indent=0) + "\n")


def filter_hub(doc, available):
    """Keep only article cards (and ItemList entries) whose language version exists."""
    doc = re.sub(r'<a class="pcard" href="/blog/([^/]+)/">.*?</a>\n?', lambda m: m.group(0) if m.group(1) in available else "", doc, flags=re.S)
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S)
    if m:
        d = json.loads(m.group(1))
        for nd in d.get("@graph", []):
            if nd.get("@type") == "Blog":
                nd["blogPost"] = [x for x in nd["blogPost"] if x["url"].rstrip("/").rsplit("/", 1)[1] in available]
            if nd.get("@type") == "CollectionPage":
                items = [x for x in nd["mainEntity"]["itemListElement"] if x["url"].rstrip("/").rsplit("/", 1)[1] in available]
                for i, x in enumerate(items):
                    x["position"] = i + 1
                nd["mainEntity"]["itemListElement"] = items
                nd["mainEntity"]["numberOfItems"] = len(items)
        doc = doc.replace(m.group(0), '<script type="application/ld+json">%s</script>' % json.dumps(d, ensure_ascii=False, separators=(",", ":")), 1)
    doc = re.sub(r'<span class="count">\d+</span>', '<span class="count">%d</span>' % len(available), doc, count=1)
    return doc


# ---------------------------------------------------------------- English source normalisation
SW_RE = re.compile(r'<select class="lang-select" id="langSelect".*?</select>', re.S)
SW_PH = '<select class="lang-select" id="langSelect" translate="no"></select>'

HOME_JS_OLD = """  var sel = document.getElementById('langSelect');
  var supported = ['en','zh','ja','ko','hi','ru'];
  var nav = (navigator.language || 'en').toLowerCase();
  var initial = 'en';
  for(var i=0;i<supported.length;i++){ if(nav.indexOf(supported[i])===0){ initial = supported[i]; break; } }
  sel.value = initial;
  setLang(initial);
  sel.addEventListener('change', function(){ setLang(this.value); });"""
HOME_JS_NEW = """  /* Static language pages (/zh-hans/, /ja/ ...) are linked from the menu (data-href). On the English page,
     languages that have no static page yet keep the in-browser dictionary (data-dict), as before. */
  var sel = document.getElementById('langSelect');
  var page = (document.documentElement.getAttribute('lang') || 'en').toLowerCase();
  var supported = ['en','zh','ja','ko','hi','ru'];
  function optFor(d){ for(var i=0;i<sel.options.length;i++){ var o=sel.options[i]; if((o.getAttribute('data-dict')||o.value)===d){ return o; } } return null; }
  if(page.indexOf('en')===0){
    var q = (location.search.match(/[?&]lang=([a-z]+)/) || [])[1];
    var nav = (q || navigator.language || 'en').toLowerCase();
    var initial = 'en';
    for(var i=0;i<supported.length;i++){ if(nav.indexOf(supported[i])===0){ initial = supported[i]; break; } }
    var io = optFor(initial);
    if(io && !io.getAttribute('data-href')){ sel.value = io.value; setLang(initial); }
  }
  sel.addEventListener('change', function(){
    var o = this.options[this.selectedIndex], h = o.getAttribute('data-href');
    try{ gtag('event','language_switch',{language:o.value,from:page}); }catch(_){}
    if(h){ location.href = h; } else { setLang(o.getAttribute('data-dict') || 'en'); }
  });"""


def normalise_en(doc, rel):
    doc = SW_RE.sub(SW_PH, doc, count=1)
    if rel == "index.html":
        doc = doc.replace(HOME_JS_OLD, HOME_JS_NEW)
        # names, paper titles, external article titles and client logos stay in their original language
        doc = doc.replace('<div class="pub-list reveal">', '<div class="pub-list reveal" translate="no">')
        doc = doc.replace('<div class="row reveal">', '<div class="row reveal" translate="no">')
        doc = doc.replace('<span class="src">', '<span class="src" translate="no">')
        doc = doc.replace('<span class="ttl">', '<span class="ttl" translate="no">')
        doc = doc.replace('<div class="pn">', '<div class="pn" translate="no">')
        doc = doc.replace('<a href="#top" class="mark" aria-label', '<a href="#top" class="mark" translate="no" aria-label')
        doc = doc.replace('<h1 class="mark reveal" aria-label', '<h1 class="mark reveal" translate="no" aria-label')
        doc = doc.replace('<div class="mark"><span class="a">', '<div class="mark" translate="no"><span class="a">')
    return doc


# ---------------------------------------------------------------- rendering
def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\xa0", "&nbsp;")


def rebuild_tag(tok, new_attrs):
    raw = tok.raw
    for name, val in new_attrs.items():
        raw, n = re.subn(r'(\s%s=")([^"]*)(")' % re.escape(name), lambda m: m.group(1) + val + m.group(3), raw, count=1)
    return raw


class Ctx:
    def __init__(self, code, avail):
        self.code, self.avail = code, avail

    def map_page(self, path):
        if self.code == "en" or path not in self.avail:
            return path
        return lang_path(self.code, path)

    def map_url(self, url):
        if not url.startswith(SITE + "/"):
            return url
        path, _, frag = url[len(SITE):].partition("#")
        if frag in SHARED_IDS or not path.endswith("/"):
            return url
        return SITE + self.map_page(path) + (("#" + frag) if frag else "")


def render(doc, rel, code, tm, avail, clusters, assets):
    """Return (html, missing_ids) for EN page rel rendered in language code."""
    ctx = Ctx(code, avail)
    en_path = page_path(rel)
    missing = set()
    if code != "en":
        toks, segs = segments(doc)

        def tr(seg):
            if seg.id is None:
                return seg.text
            v = tm.get(seg.id)
            if v is None:
                missing.add(seg.id)
                return seg.text
            return v

        newtag, attr_tr = {}, {}
        for s in segs:
            if s.kind == "attr":
                attr_tr.setdefault(s.tok, {})[s.attr] = tr(s) + s.suffix
        for i, t in enumerate(toks):
            if t.kind not in ("start", "startend"):
                continue
            at = dict(t.attrs)
            repl = {a: html.escape(v, quote=True) for a, v in attr_tr.get(i, {}).items()}
            v = at.get("href")
            if v and v.startswith("/") and not v.startswith("//"):
                path, _, frag = v.partition("#")
                if path.endswith("/"):
                    nv = ctx.map_page(path) + (("#" + frag) if frag else "")
                    if nv != v:
                        repl["href"] = nv
            newtag[i] = rebuild_tag(t, repl) if repl else t.raw
        edits, covered = [], []
        for s in segs:
            if s.kind != "run":
                continue
            txt = tr(s)
            pieces, pos = [], 0
            for m in PH_RE.finditer(txt):
                pieces.append(esc_text(txt[pos:m.start()]))
                ph = m.group(0)
                kind, o, c = s.tags[int(re.search(r"\d+", ph).group(0)) - 1]
                pieces.append(toks[c].raw if ph.startswith("</") else newtag.get(o, toks[o].raw))
                pos = m.end()
            pieces.append(esc_text(txt[pos:]))
            edits.append((s.a, s.b, s.lead + "".join(pieces) + esc_text(s.suffix) + s.trail))
            covered.append((s.a, s.b))
        for i, t in enumerate(toks):
            if t.kind in ("start", "startend") and newtag[i] != t.raw and not any(a <= t.start < b for a, b in covered):
                edits.append((t.start, t.end, newtag[i]))
        ld_map = {s.text: tr(s) for s in segs if s.kind == "ld"}
        for i, t in enumerate(toks):
            if t.kind == "start" and t.tag == "script" and dict(t.attrs).get("type") == "application/ld+json":
                d = ld_transform(json.loads(toks[i + 1].raw), ld_map, ctx, L[code]["tag"])
                edits.append((toks[i + 1].start, toks[i + 1].end, json.dumps(d, ensure_ascii=False, separators=(",", ":"))))
        edits.sort(key=lambda e: e[0])
        res, pos = [], 0
        for a, b, txt in edits:
            if a < pos:
                raise RuntimeError("overlapping edits in %s" % rel)
            res.append(doc[pos:a]); res.append(txt); pos = b
        res.append(doc[pos:])
        doc = "".join(res)
        doc = lang_extras(doc, rel, code, tm, assets)
    doc = head_fixups(doc, code, en_path, clusters.get(en_path, ["en"]))
    doc = doc.replace(SW_PH, switcher(code, en_path, clusters), 1)
    return doc, missing


def ld_transform(d, ld_map, ctx, tag, skip=False):
    if isinstance(d, dict):
        skip2 = skip or d.get("@type") in LD_SKIP_TYPES
        o = {}
        for k, v in d.items():
            if isinstance(v, str):
                if k == "inLanguage":
                    o[k] = tag
                elif not skip2 and k in LD_TEXT_KEYS:
                    suf = SUFFIX if v.endswith(SUFFIX) else ""
                    key = norm(v[: -len(suf)] if suf else v)
                    o[k] = ld_map.get(key, key) + suf
                elif v.startswith(SITE):
                    o[k] = ctx.map_url(v)
                else:
                    o[k] = v
            else:
                o[k] = ld_transform(v, ld_map, ctx, tag, skip2)
        return o
    if isinstance(d, list):
        return [ld_transform(v, ld_map, ctx, tag, skip) for v in d]
    return d


DATA_RE = re.compile(r"data:(image/(png|jpe?g|webp|gif|svg\+xml));base64,([A-Za-z0-9+/=]{2000,})")


def lang_extras(doc, rel, code, tm, assets):
    """Language-page-only changes: drop the in-browser dictionary, fill the local name, move embedded images
    into shared files (the English home page keeps its self-contained base64 images)."""
    if rel == "index.html":
        doc = re.sub(r"var T = \{\n.*?\n\};", "var T = {};", doc, count=1, flags=re.S)
        ln = tm.get("_localname")
        if ln:
            doc = doc.replace('<p class="localname" data-i18n="hero.localname"></p>',
                              '<p class="localname" data-i18n="hero.localname">%s</p>' % esc_text(ln), 1)

    def img(m):
        import base64
        ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(2), m.group(2))
        data = m.group(3)
        name = "/assets/img/home/%s.%s" % (hashlib.sha1(data.encode()).hexdigest()[:12], ext)
        if name not in assets:
            assets[name] = base64.b64decode(data)
        return name
    return DATA_RE.sub(img, doc)


def head_fixups(doc, code, en_path, cluster):
    lg = L[code]
    url = SITE + lang_path(code, en_path)
    attrs = 'lang="%s"' % lg["tag"] + (' dir="rtl"' if code == "ar" else "")
    doc = re.sub(r'<html lang="[^"]*"(?: dir="rtl")?>', "<html %s>" % attrs, doc, count=1)
    doc = re.sub(r'\n?<link rel="alternate" hreflang="[^"]*" href="[^"]*"\s*/?>', "", doc)
    alts = "".join('\n<link rel="alternate" hreflang="%s" href="%s%s" />' % (L[c]["tag"], SITE, lang_path(c, en_path)) for c in cluster)
    alts += '\n<link rel="alternate" hreflang="x-default" href="%s%s" />' % (SITE, en_path)
    doc = re.sub(r'<link rel="canonical" href="[^"]*"\s*/?>', lambda m: '<link rel="canonical" href="%s" />%s' % (url, alts), doc, count=1)
    doc = re.sub(r'<meta property="og:url" content="[^"]*"\s*/?>', '<meta property="og:url" content="%s" />' % url, doc, count=1)
    doc = re.sub(r'\n?<meta property="og:locale:alternate" content="[^"]*"\s*/?>', "", doc)
    others = "".join('\n<meta property="og:locale:alternate" content="%s" />' % L[c]["og"] for c in cluster if c != code)
    doc = re.sub(r'<meta property="og:locale" content="[^"]*"\s*/?>', lambda m: '<meta property="og:locale" content="%s" />%s' % (lg["og"], others), doc, count=1)
    if code != "en" and lg["font"]:
        doc = re.sub(r'(<link href="https://fonts\.googleapis\.com/css2\?family=Montserrat[^"]*?)(&display=swap")',
                     lambda m: m.group(1) + ("" if lg["font"].split(":")[0] in m.group(1) else "&family=" + lg["font"]) + m.group(2), doc, count=1)
    return doc


def switcher(code, en_path, clusters):
    shipped = clusters.get("/", ["en"])
    have = clusters.get(en_path, ["en"])
    opts = []
    for c in shipped:
        tgt = lang_path(c, en_path) if c in have else lang_path(c, "/")
        sel = c == code
        href = "" if sel else ' data-href="%s"' % tgt
        opts.append('<option value="%s" lang="%s"%s%s>%s</option>' % (c, L[c]["tag"], href, " selected" if sel else "", L[c]["name"]))
    if code == "en" and en_path == "/":
        for c, d in DICT_CODE.items():
            if c not in shipped:
                opts.append('<option value="%s" lang="%s" data-dict="%s">%s</option>' % (c, L[c]["tag"], d, L[c]["name"]))
    return '<select class="lang-select" id="langSelect" aria-label="%s" translate="no">%s</select>' % (L[code]["label"], "".join(opts))


# ---------------------------------------------------------------- commands
def templates():
    """EN template per page (switcher collapsed to a placeholder, home JS hooks in place)."""
    return {rel: normalise_en(read(os.path.join(ROOT, rel)), rel) for rel in en_pages()}


def cmd_extract(quiet=False, tpl=None):
    tpl = tpl or templates()
    src, pages = {}, {}
    for rel, doc in tpl.items():
        _, segs = segments(doc)
        ids = []
        for s in segs:
            if s.id:
                src[s.id] = s.text
                if s.id not in ids:
                    ids.append(s.id)
        pages[page_path(rel)] = ids
    write(os.path.join(I18N, "source.json"), json.dumps(dict(sorted(src.items())), ensure_ascii=False, indent=0) + "\n")
    write(os.path.join(I18N, "pages.json"), json.dumps(pages, ensure_ascii=False, indent=0) + "\n")
    if not quiet:
        print("%d pages, %d unique segments, %d words" % (len(pages), len(src), sum(len(v.split()) for v in src.values())))
    return src, pages


def hub_ids(tpl, avail_slugs):
    _, segs = segments(filter_hub(tpl["blog/index.html"], avail_slugs))
    return list(dict.fromkeys(s.id for s in segs if s.id))


def availability(code, pages, tm, tpl):
    if code == "en":
        return set(pages)
    if not all(i in tm for i in pages["/"]):
        return set()
    avail, slugs = {"/"}, set()
    for path, ids in pages.items():
        if path.startswith("/blog/") and path != "/blog/" and all(i in tm for i in ids):
            avail.add(path); slugs.add(path.split("/")[2])
    if slugs and all(i in tm for i in hub_ids(tpl, slugs)):
        avail.add("/blog/")
    return avail


def cmd_import_dict():
    """Seed the translation memory from the home page's in-browser dictionary (var T = {...})."""
    tpl = templates()
    doc = tpl["index.html"]
    m = re.search(r"var T = \{\n(.*?)\n\};", doc, re.S)
    if not m:
        sys.exit("dictionary not found")
    T = {}
    for ln in m.group(1).splitlines():
        mm = re.match(r'^"([^"]+)":(\{.*\}),?\s*$', ln.strip())
        if mm:
            body = re.sub(r'([{,])(en|zh|ja|ko|hi|ru):', r'\1"\2":', mm.group(2))
            T[mm.group(1)] = json.loads(body)
    toks, segs = segments(doc)
    # English text of every data-i18n element, as it appears in the HTML
    key_of_open = {}
    for i, t in enumerate(toks):
        if t.kind == "start" and dict(t.attrs).get("data-i18n"):
            key_of_open[i] = dict(t.attrs)["data-i18n"]
    stats = {}
    for code, d in DICT_CODE.items():
        tm = load_tm(code)
        n = 0
        if T.get("hero.localname", {}).get(d) and "_localname" not in tm:
            tm["_localname"] = T["hero.localname"][d]
        for s in segs:
            if not s.id or s.id in tm or s.kind != "run":
                continue
            k = s.parent.attrs.get("data-i18n") if s.parent is not None else None
            if k and k in T and norm(T[k].get("en", "")) == s.text and T[k].get(d):
                tm[s.id] = T[k][d]; n += 1
                continue
            # segment made of data-i18n inline elements plus symbols only (e.g. "<g1>View Google Scholar</g1><g2>→</g2>")
            txt, ok, used = s.text, True, False
            for gi, (kind, o, c) in enumerate(s.tags):
                k = key_of_open.get(o)
                if kind != "g" or not k:
                    continue
                inner = re.search(r"<g%d>(.*?)</g%d>" % (gi + 1, gi + 1), txt)
                if inner and k in T and norm(T[k].get("en", "")) == inner.group(1) and T[k].get(d):
                    txt = txt.replace(inner.group(0), "<g%d>%s</g%d>" % (gi + 1, T[k][d], gi + 1)); used = True
            rest = re.sub(r"<g(\d+)>.*?</g\1>", "", txt)
            if used and not re.search(r"[^\W\d_]", PH_RE.sub("", rest)):
                tm[s.id] = txt; n += 1
        save_tm(code, tm)
        stats[code] = n
    print("imported from the home page dictionary:", ", ".join("%s %d" % kv for kv in stats.items()))


def cmd_todo(code, which):
    tpl = templates()
    src, pages = cmd_extract(quiet=True, tpl=tpl)
    tm = load_tm(code)
    seen = set()
    for path in (which or list(pages)):
        if not path.startswith("/"):
            path = "/" + path.strip("/") + "/" if path.strip("/") else "/"
        ids = hub_ids(tpl, {p.split("/")[2] for p in pages if p.startswith("/blog/") and p != "/blog/"}) if path == "/blog/" else pages[path]
        for i in ids:
            if i not in tm and i not in seen:
                seen.add(i)
                print("%s\t%s" % (i, src[i]))


def check_ph(en, tr):
    return sorted(PH_RE.findall(en)) == sorted(PH_RE.findall(tr))


def cmd_merge(code, f):
    src = json.loads(read(os.path.join(I18N, "source.json")))
    tm = load_tm(code)
    bad = n = 0
    for ln in read(f).splitlines():
        if not ln.strip() or "\t" not in ln:
            continue
        i, t = [x.strip() for x in ln.split("\t", 1)]
        if i not in src:
            print("unknown id", i); bad += 1; continue
        if not t or not check_ph(src[i], t):
            print("placeholder mismatch or empty", i, src[i][:60], "||", t[:60]); bad += 1; continue
        tm[i] = t; n += 1
    save_tm(code, tm)
    print("merged %d, rejected %d -> i18n/%s.json (%d entries)" % (n, bad, code, len(tm)))


def cmd_status():
    tpl = templates()
    src, pages = cmd_extract(quiet=True, tpl=tpl)
    need = set(i for ids in pages.values() for i in ids)
    for code in CODES[1:]:
        tm = load_tm(code)
        av = availability(code, pages, tm, tpl)
        home = len(set(pages["/"]) & set(tm))
        print("%-8s %4d/%4d segments  home %3d/%3d  %2d/%2d pages live" % (
            code, len(need & set(tm)), len(need), home, len(set(pages["/"])), len(av), len(pages)))


def cmd_build():
    tpl = templates()
    src, pages = cmd_extract(quiet=True, tpl=tpl)
    tms = {c: load_tm(c) for c in CODES[1:]}
    avail = {"en": set(pages)}
    for c in CODES[1:]:
        avail[c] = availability(c, pages, tms[c], tpl)
    clusters = {path: [c for c in CODES if path in avail[c]] for path in pages}
    written, assets = [], {}
    for rel, base in tpl.items():
        en_path = page_path(rel)
        for c in CODES:
            if en_path not in avail[c]:
                continue
            doc = base
            if en_path == "/blog/" and c != "en":
                doc = filter_hub(doc, {p.split("/")[2] for p in avail[c] if p.startswith("/blog/") and p != "/blog/"})
            out, missing = render(doc, rel, c, tms.get(c, {}), avail[c], clusters, assets)
            if missing:
                raise RuntimeError("%s %s missing %d" % (c, en_path, len(missing)))
            write(os.path.join(ROOT, lang_path(c, en_path).lstrip("/"), "index.html"), out)
            written.append(lang_path(c, en_path))
    for name, data in assets.items():
        p = os.path.join(ROOT, name.lstrip("/"))
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
    stale = []
    for c in CODES[1:]:
        for f in glob.glob(os.path.join(ROOT, L[c]["dir"], "**", "index.html"), recursive=True):
            rp = "/" + os.path.relpath(f, ROOT)[: -len("index.html")]
            if rp not in written:
                if "--prune" in sys.argv:
                    os.remove(f)
                else:
                    stale.append(rp)
    if stale:
        sys.exit("refusing to drop %d existing language pages (missing translations?): %s — translate them or rerun with --prune"
                 % (len(stale), ", ".join(stale[:5])))
    write_sitemaps(pages, avail, clusters)
    write_robots(avail)
    write_llms(avail)
    print("built %d pages; languages live: %s" % (len(written), ", ".join("%s(%d)" % (c, len(avail[c])) for c in CODES if avail[c])))


def lastmod(path):
    if path.startswith("/blog/") and path != "/blog/":
        m = re.search(r'"dateModified":"([\d-]+)"', read(os.path.join(ROOT, path.lstrip("/"), "index.html")))
        if m:
            return m.group(1)
    return TODAY


def write_sitemaps(pages, avail, clusters):
    files = []
    for c in CODES:
        if not avail[c]:
            continue
        rows = []
        for path in pages:
            if path not in avail[c]:
                continue
            alts = "".join('<xhtml:link rel="alternate" hreflang="%s" href="%s%s"/>' % (L[x]["tag"], SITE, lang_path(x, path)) for x in clusters[path])
            alts += '<xhtml:link rel="alternate" hreflang="x-default" href="%s%s"/>' % (SITE, path)
            pr = "1.0" if path == "/" else ("0.9" if path == "/blog/" else "0.7")
            cf = "monthly" if path == "/" else ("weekly" if path == "/blog/" else "monthly")
            rows.append("<url><loc>%s%s</loc>%s<lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority></url>" % (
                SITE, lang_path(c, path), alts, lastmod(path), cf, pr))
        name = "sitemap-%s.xml" % c
        write(os.path.join(ROOT, name), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(rows) + "\n</urlset>\n")
        files.append(name)
    for f in glob.glob(os.path.join(ROOT, "sitemap-*.xml")):
        if os.path.basename(f) not in files:
            os.remove(f)
    idx = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- sitemap.xml — Prof. Aleks Farseev (index; generated by tools/i18n.py) -->\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(
        "<sitemap><loc>%s/%s</loc><lastmod>%s</lastmod></sitemap>" % (SITE, f, TODAY) for f in files) + "\n</sitemapindex>\n"
    write(os.path.join(ROOT, "sitemap.xml"), idx)


def write_robots(avail):
    p = os.path.join(ROOT, "robots.txt")
    t = read(p)
    lines = ["Sitemap: %s/sitemap.xml" % SITE] + ["Sitemap: %s/sitemap-%s.xml" % (SITE, c) for c in CODES if avail[c]]
    t = re.sub(r"(?:Sitemap: [^\n]*\n?)+", "\n".join(lines) + "\n", t, count=1)
    write(p, t)


def write_llms(avail):
    p = os.path.join(ROOT, "llms.txt")
    t = read(p)
    live = [c for c in CODES[1:] if avail[c]]
    block = ""
    if live:
        rows = ["## Other languages", ""]
        for c in live:
            n = len([x for x in avail[c] if x.startswith("/blog/") and x != "/blog/"])
            rows.append("- [%s](%s%s)%s" % (L[c]["name"], SITE, lang_path(c, "/"),
                        (" · [AI news blog](%s%s) (%d articles)" % (SITE, lang_path(c, "/blog/"), n)) if "/blog/" in avail[c] else ""))
        block = "\n".join(rows) + "\n\n"
    if "## Other languages\n" in t:
        t = re.sub(r"## Other languages\n.*?\n\n(?=## |\Z)", lambda m: block, t, count=1, flags=re.S)
    elif block:
        t = t.replace("## Ventures", block + "## Ventures", 1)
    write(p, t)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    {"extract": lambda: cmd_extract(), "import-dict": cmd_import_dict, "status": cmd_status, "build": cmd_build,
     "todo": lambda: cmd_todo(a[1], a[2:]), "merge": lambda: cmd_merge(a[1], a[2])}.get(a[0], lambda: print(__doc__))()
