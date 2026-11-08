#!/usr/bin/env python3
"""Build the "AI news, explained by Aleks" blog (standard library only).

  python3 tools/build_blog.py

Reads content/blog/*.txt and writes
  blog/<slug>/index.html      one article per file
  blog/index.html             the hub (newest news first)
  index.html                  "AI news" nav link + "Latest from the AI news blog" strip (3 newest)
  llms.txt                    "## AI news blog" section
  sitemap.xml                 only while tools/i18n.py does not exist (it owns the sitemaps afterwards)

Article file format (content/blog/<slug>.txt):

  title: Headline (about 60 characters or fewer)
  dek: One-sentence summary used as the meta description (120-160 characters)
  news: One line naming the news item
  news_date: 2026-10-28            date of the news item (sort key)
  published: 2026-11-08            date the article was published
  topic: AI search                 short label shown on cards
  source: Title | Publisher | 2026-10-28 | https://...     (repeat; first = primary source)
  ---
  Markdown-ish body: paragraphs, ## / ### headings, "- " bullets, [text](url), **bold**, *italic*.
  ## FAQ
  ? Question
  Answer paragraph (one or more).

Honesty rules for authors: every news fact must come from a listed source that was opened and read;
no invented quotes, statistics, events or personal anecdotes. Opinions are fine.
"""
import datetime, glob, html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://farseev.com"
GA = "G-EVX69SN1TT"
PERSON_ID = SITE + "/#person"
BLOG_NAME = "AI news, explained by Aleks"
OG_IMAGE = SITE + "/og-image.png"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def esc(s):
    return html.escape(s, quote=True).replace("&#x27;", "'")


def long_date(iso):
    d = datetime.date.fromisoformat(iso)
    return "%d %s %d" % (d.day, d.strftime("%B"), d.year)


# ------------------------------------------------------------------ parsing
def parse(path):
    raw = read(path)
    head, _, body = raw.partition("\n---\n")
    meta = {"sources": []}
    for ln in head.splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        k, _, v = ln.partition(":")
        k, v = k.strip(), v.strip()
        if k == "source":
            t, pub, d, u = [x.strip() for x in v.split("|")]
            meta["sources"].append({"title": t, "publisher": pub, "date": d, "url": u})
        else:
            meta[k] = v
    meta["slug"] = os.path.splitext(os.path.basename(path))[0]
    body, _, faq = body.partition("\n## FAQ\n")
    meta["body_md"] = body.strip()
    qs = []
    for blk in re.split(r"\n(?=\? )", "\n" + faq.strip()):
        blk = blk.strip()
        if not blk.startswith("? "):
            continue
        q, _, a = blk[2:].partition("\n")
        qs.append((q.strip(), [p.strip() for p in re.split(r"\n\s*\n", a.strip()) if p.strip()]))
    meta["faq"] = qs
    for k in ("title", "dek", "news", "news_date", "published", "topic"):
        if not meta.get(k):
            sys.exit("%s: missing %s" % (path, k))
    if len(qs) != 3:
        sys.exit("%s: FAQ must have exactly 3 questions (found %d)" % (path, len(qs)))
    if not meta["sources"]:
        sys.exit("%s: no sources" % path)
    return meta


def inline(s):
    s = esc(s).replace("&#x27;", "'")
    def link(m):
        text, url = m.group(1), m.group(2)
        ext = url.startswith("http")
        return '<a href="%s"%s>%s</a>' % (url, ' target="_blank" rel="noopener"' if ext else "", text)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md(text):
    out = []
    for blk in re.split(r"\n\s*\n", text.strip()):
        lines = blk.strip().splitlines()
        if lines[0].startswith("### "):
            out.append("<h3>%s</h3>" % inline(lines[0][4:]))
            lines = lines[1:]
        elif lines[0].startswith("## "):
            out.append("<h2>%s</h2>" % inline(lines[0][3:]))
            lines = lines[1:]
        if not lines:
            continue
        if all(l.startswith("- ") for l in lines):
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(l[2:]) for l in lines))
        else:
            out.append("<p>%s</p>" % inline(" ".join(l.strip() for l in lines)))
    return "\n".join(out)


def plain(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.replace("**", "").replace("*", "")


def words(a):
    t = plain(a["body_md"]) + " " + " ".join(q + " " + " ".join(ans) for q, ans in a["faq"])
    t = re.sub(r"^#+ ", "", t, flags=re.M)
    return len(t.split())


# ------------------------------------------------------------------ shared chrome
GA_SNIPPET = """<script async src="https://www.googletagmanager.com/gtag/js?id=%(ga)s"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','%(ga)s');
/* Same events as the home page: contact_click, venture_click, publication_click, social_click; plus source_click
   (links in an article's Sources list) and language_switch (language menu). No cookies are set here. */
document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a');if(!a)return;var h=a.getAttribute('href')||'';
 function ev(n,p){try{gtag('event',n,p)}catch(_){}}
 var sx=a.closest('[data-sec]'),sec=sx?sx.getAttribute('data-sec'):'page';
 if(/^mailto:|^tel:/.test(h))return ev('contact_click',{method:h.slice(0,h.indexOf(':')),section:sec});
 var host=(h.match(/^https?:\\/\\/(?:www\\.)?([^\\/]+)/)||[])[1]||'';if(!host||host==='farseev.com')return;
 if(a.closest('.sources'))return ev('source_click',{destination:host,section:'sources'});
 if(/somin\\.ai|accordion\\.sg|faithdriven\\.sg|orthodox\\.sg|touchigh\\.ai|defygroup\\.ai|fg\\.ventures/.test(host))return ev('venture_click',{destination:host,section:sec});
 if(/scholar\\.google|acm\\.org|doi\\.org|arxiv\\.org|forbes\\.com|e27\\.co|saltandlight|ceoinsightsasia|crunchbase|acmmm/.test(host))return ev('publication_click',{destination:host,section:sec});
 if(/linkedin|youtube|youtu\\.be|instagram|facebook|x\\.com|twitter/.test(host))return ev('social_click',{destination:host,section:sec});
},true);</script>""" % {"ga": GA}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
         '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />')

ICONS = """<link rel="icon" href="/favicon.ico" sizes="48x48" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />"""

LANGSW = ('<select class="lang-select" id="langSelect" aria-label="Language" translate="no">'
          '<option value="en" selected>English</option></select>')


def nav(active):
    items = [("/#about", "About", None), ("/#research", "Research", None), ("/blog/", "AI news", "blog"),
             ("/#talks", "Talks", None), ("/#connect", "Connect", None)]
    links = "".join('<a href="%s"%s>%s</a>' % (h, ' aria-current="page"' if k and k == active else "", t) for h, t, k in items)
    return """<header class="nav">
  <div class="nav-inner">
    <a href="/" class="mark" aria-label="Aleks Farseev — home" translate="no"><span class="a">Aleks&nbsp;</span><span class="b">Farseev</span></a>
    <nav class="nav-links" id="navLinks" aria-label="Main">%s</nav>
    <div class="nav-right">
      %s
      <button class="menu-btn" id="menuBtn" aria-label="Menu" aria-expanded="false"><span></span><span></span><span></span></button>
    </div>
  </div>
</header>""" % (links, LANGSW)


FOOTER = """<footer class="foot" data-sec="footer">
  <div class="wrap">
    <div class="foot-top">
      <div>
        <div class="mark" translate="no"><span class="a">Aleks&nbsp;</span><span class="b">Farseev</span></div>
        <p class="foot-tag">GenAI CEO, Professor in AI, keynote speaker and accordionist. Bridging deep research and real-world marketing from Singapore to the world.</p>
      </div>
      <div>
        <h6>Explore</h6>
        <ul>
          <li><a href="/">Home</a></li>
          <li><a href="/blog/">AI news blog</a></li>
          <li><a href="/#research">Research</a></li>
          <li><a href="/#publications">Publications</a></li>
          <li><a href="/#connect">Contact</a></li>
        </ul>
      </div>
      <div>
        <h6>Elsewhere</h6>
        <ul>
          <li><a href="https://www.linkedin.com/in/aiprof/" target="_blank" rel="noopener">LinkedIn</a></li>
          <li><a href="https://scholar.google.com/citations?user=ZJW7F18AAAAJ&amp;hl=en" target="_blank" rel="noopener">Google Scholar</a></li>
          <li><a href="https://www.forbes.com/councils/forbestechcouncil/people/aleksfarseev/" target="_blank" rel="noopener">Forbes</a></li>
          <li><a href="https://somin.ai/" target="_blank" rel="noopener">SOMIN.ai</a></li>
        </ul>
      </div>
    </div>
    <div class="foot-bot">
      <span>© <span id="yr">2026</span> Aleks Farseev · <span translate="no">法信夫</span></span>
      <span>Opinions are my own. News facts link to their sources.</span>
    </div>
  </div>
</footer>"""

PAGE_JS = """<script>
(function(){
  var b=document.getElementById('menuBtn'),n=document.getElementById('navLinks');
  if(b&&n){b.addEventListener('click',function(){var o=n.classList.toggle('open');b.setAttribute('aria-expanded',o?'true':'false');});}
  var y=document.getElementById('yr');if(y){y.textContent=new Date().getFullYear();}
  var s=document.getElementById('langSelect');
  if(s){s.addEventListener('change',function(){var o=this.options[this.selectedIndex],h=o.getAttribute('data-href');
    try{gtag('event','language_switch',{language:o.value,from:document.documentElement.lang})}catch(_){}
    if(h){location.href=h;}});}
})();
</script>"""


def head(title, desc, canonical, og_type, ld, extra_meta=""):
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>%(title)s</title>
%(ga)s
<meta name="description" content="%(desc)s" />
<meta name="author" content="Prof. Aleks Farseev" />
<meta name="robots" content="index, follow, max-image-preview:large" />
<meta name="theme-color" content="#0E1614" />
<link rel="canonical" href="%(canon)s" />
<link rel="alternate" hreflang="en" href="%(canon)s" />
<link rel="alternate" hreflang="x-default" href="%(canon)s" />
<meta property="og:type" content="%(ogt)s" />
<meta property="og:site_name" content="Prof. Aleks Farseev" />
<meta property="og:title" content="%(title)s" />
<meta property="og:description" content="%(desc)s" />
<meta property="og:url" content="%(canon)s" />
<meta property="og:image" content="%(img)s" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="Prof. Aleks Farseev — AI news, explained" />
<meta property="og:locale" content="en_US" />
%(extra)s<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="%(title)s" />
<meta name="twitter:description" content="%(desc)s" />
<meta name="twitter:image" content="%(img)s" />
%(icons)s
<script type="application/ld+json">%(ld)s</script>
%(fonts)s
<link rel="stylesheet" href="/assets/blog.css" />
</head>""" % {"title": esc(title), "desc": esc(desc), "canon": canonical, "ogt": og_type, "img": OG_IMAGE,
               "ga": GA_SNIPPET, "icons": ICONS, "fonts": FONTS, "extra": extra_meta,
               "ld": json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}


def person_stub():
    return {"@type": "Person", "@id": PERSON_ID, "name": "Aleks Farseev", "url": SITE + "/",
            "jobTitle": "Founder & CEO of SOMIN.ai; Guest Professor in AI",
            "sameAs": ["https://www.linkedin.com/in/aiprof/", "https://scholar.google.com/citations?user=ZJW7F18AAAAJ&hl=en"]}


def card(a, tag="h3"):
    return ('<a class="pcard" href="/blog/%s/"><span class="meta">%s · %s</span><%s>%s</%s><p>%s</p>'
            '<span class="go">Read →</span></a>') % (
        a["slug"], esc(a["topic"]), long_date(a["news_date"]), tag, esc(a["title"]), tag, esc(a["dek"]))


# ------------------------------------------------------------------ article page
def article_page(a, all_articles):
    url = "%s/blog/%s/" % (SITE, a["slug"])
    prim = a["sources"][0]
    faq_html = "".join("<details><summary>%s</summary>%s</details>" % (esc(q), "".join("<p>%s</p>" % inline(p) for p in ans))
                       for q, ans in a["faq"])
    src_html = "".join('<li translate="no"><a href="%s" target="_blank" rel="noopener">%s</a> — %s, %s</li>' % (
        esc(s["url"]), esc(s["title"]), esc(s["publisher"]), long_date(s["date"])) for s in a["sources"])
    others = [x for x in all_articles if x["slug"] != a["slug"]]
    same = [x for x in others if x["topic"] == a["topic"]]
    rel = (same + [x for x in others if x not in same])[:3]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "BlogPosting", "@id": url + "#article", "mainEntityOfPage": url, "url": url,
         "headline": a["title"], "description": a["dek"], "image": OG_IMAGE, "inLanguage": "en",
         "datePublished": a["published"], "dateModified": a.get("modified", a["published"]),
         "author": {"@id": PERSON_ID}, "publisher": {"@id": PERSON_ID},
         "isPartOf": {"@id": SITE + "/blog/#blog"}, "articleSection": a["topic"],
         "about": {"@type": "Thing", "name": a["news"]}, "wordCount": words(a),
         "citation": [{"@type": "CreativeWork", "name": s["title"], "url": s["url"], "publisher": s["publisher"],
                       "datePublished": s["date"]} for s in a["sources"]]},
        {"@type": "FAQPage", "@id": url + "#faq", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": " ".join(plain(p) for p in ans)}}
            for q, ans in a["faq"]]},
        {"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "AI news", "item": SITE + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": a["title"], "item": url}]},
        person_stub()]}
    extra = ('<meta property="article:published_time" content="%s" />\n<meta property="article:author" content="%s/" />\n'
             '<meta property="article:section" content="%s" />\n') % (a["published"], SITE, esc(a["topic"]))
    out = head(a["title"] + " | Prof. Aleks Farseev", a["dek"], url, "article", ld, extra)
    out += """
<body>
%(nav)s
<main id="main">
<article>
  <header class="band on-dark" data-sec="article-header">
    <div class="read">
      <nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/blog/">AI news</a></li><li aria-current="page">%(short)s</li></ol></nav>
      <p class="eyebrow">AI news, explained · %(topic)s</p>
      <h1 class="h-display">%(title)s</h1>
      <p class="lead">%(dek)s</p>
      <p class="newsline"><span class="loc-dot"></span><span>The news: %(news)s (<time datetime="%(nd)s">%(ndl)s</time>)</span></p>
      <p class="byline"><span>By <b>Prof. Aleks Farseev</b></span><span class="dot"></span><time datetime="%(pub)s">%(publ)s</time><span class="dot"></span><span>%(mins)d min read</span></p>
    </div>
  </header>
  <div class="post" data-sec="article">
    <div class="read">
%(body)s
<h2 id="faq">FAQ</h2>
<div class="faq">%(faq)s</div>
<section class="sources" aria-labelledby="sources-h"><h2 id="sources-h">Sources</h2><ol>%(src)s</ol></section>
<div class="author"><div class="av" aria-hidden="true" translate="no">AF</div><div>
<p><b>Prof. Aleks Farseev</b> is the founder and CEO of SOMIN.ai and a Guest Professor in AI at NUS and INSEAD. His peer-reviewed research covers multi-source user profiling, personality-aware recommendation and explainable AI for marketing.</p>
<p class="links"><a href="/">About Aleks</a><a href="/#publications">Publications</a><a href="/blog/">More AI news</a></p>
</div></div>
    </div>
  </div>
</article>
<section class="section section--mist related" aria-labelledby="related-h" data-sec="related">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">Keep reading</p><h2 class="h-display" id="related-h" style="font-size:clamp(1.5rem,3vw,2.1rem)">More AI news, explained</h2></div>
    <div class="cards-3">%(rel)s</div>
  </div>
</section>
</main>
%(footer)s
%(js)s
</body>
</html>
""" % {"nav": nav("blog"), "title": esc(a["title"]), "short": esc(a["title"]), "topic": esc(a["topic"]),
       "dek": esc(a["dek"]), "news": esc(a["news"]), "nd": a["news_date"], "ndl": long_date(a["news_date"]),
       "pub": a["published"], "publ": long_date(a["published"]), "mins": max(3, round(words(a) / 220)),
       "body": md(a["body_md"]), "faq": faq_html, "src": src_html, "rel": "".join(card(x) for x in rel),
       "footer": FOOTER, "js": PAGE_JS}
    return out


# ------------------------------------------------------------------ hub
HUB_TITLE = "AI News, Explained by Aleks Farseev"
HUB_DESC = ("Prof. Aleks Farseev reads the week's AI news (models, agents, AI search, ads and regulation) "
            "and explains what it means for marketers, with links to every source.")


def hub_page(arts):
    url = SITE + "/blog/"
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Blog", "@id": url + "#blog", "url": url, "name": BLOG_NAME, "description": HUB_DESC, "inLanguage": "en",
         "author": {"@id": PERSON_ID}, "publisher": {"@id": PERSON_ID},
         "blogPost": [{"@type": "BlogPosting", "@id": "%s%s/#article" % (url, a["slug"]), "headline": a["title"],
                       "url": "%s%s/" % (url, a["slug"]), "datePublished": a["published"]} for a in arts]},
        {"@type": "CollectionPage", "@id": url + "#page", "url": url, "name": HUB_TITLE, "description": HUB_DESC,
         "isPartOf": {"@id": SITE + "/#website"}, "about": {"@id": PERSON_ID},
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(arts), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": "%s%s/" % (url, a["slug"]), "name": a["title"]}
             for i, a in enumerate(arts)]}},
        {"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "AI news", "item": url}]},
        person_stub()]}
    cards = "\n".join(card(a, "h2") for a in arts)
    out = head(HUB_TITLE + " | Prof. Aleks Farseev", HUB_DESC, url, "website", ld)
    out += """
<body>
%(nav)s
<main id="main">
  <header class="band on-dark" data-sec="hub-header">
    <div class="wrap">
      <nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li aria-current="page">AI news</li></ol></nav>
      <p class="eyebrow">The AI news blog</p>
      <h1 class="h-display">AI news, explained by Aleks</h1>
      <p class="lead">Each article takes one real AI news item, links the primary source, and explains what it means for marketers through the lens of my research on user profiling, personality-aware recommendation and explainable AI.</p>
      <p class="byline"><span>By <b>Prof. Aleks Farseev</b></span><span class="dot"></span><span><span class="count">%(n)d</span> articles, newest news first</span></p>
    </div>
  </header>
  <section class="section" aria-label="Articles" data-sec="hub">
    <div class="wrap">
      <div class="hub-list">
%(cards)s
      </div>
    </div>
  </section>
</main>
%(footer)s
%(js)s
</body>
</html>
""" % {"nav": nav("blog"), "cards": cards, "n": len(arts), "footer": FOOTER, "js": PAGE_JS}
    return out


# ------------------------------------------------------------------ home page, llms.txt, sitemap
STRIP_START = "<!-- ============ AI NEWS BLOG (generated by tools/build_blog.py) ============ -->"
STRIP_END = "<!-- /AI NEWS BLOG -->"
DICT_ADD = {
    "nav.blog": ("AI News", "AI 新闻", "AIニュース", "AI 뉴스", "एआई समाचार", "Новости ИИ"),
    "blog.eyebrow": ("AI news blog", "AI 新闻博客", "AIニュースブログ", "AI 뉴스 블로그", "एआई समाचार ब्लॉग", "Блог новостей ИИ"),
    "blog.heading": ("Latest from the AI news blog", "AI 新闻博客最新文章", "AIニュースブログの最新記事", "AI 뉴스 블로그 최신 글",
                     "एआई समाचार ब्लॉग से नवीनतम", "Свежее в блоге новостей ИИ"),
    "blog.cta": ("All articles", "全部文章", "すべての記事", "모든 글", "सभी लेख", "Все статьи"),
}


def home_strip(arts):
    cards = "".join(
        '<a class="card" href="/blog/%s/" style="display:flex;flex-direction:column;gap:8px"><div class="idx">%s · %s</div><h4>%s</h4><p>%s</p></a>'
        % (a["slug"], esc(a["topic"]), long_date(a["news_date"]), esc(a["title"]), esc(a["dek"])) for a in arts[:3])
    return """%s
<section class="section" id="blog-latest" aria-labelledby="blog-latest-h">
  <div class="wrap">
    <div class="section-head reveal">
      <p class="eyebrow" data-i18n="blog.eyebrow">AI news blog</p>
      <h2 class="h-display" id="blog-latest-h" data-i18n="blog.heading">Latest from the AI news blog</h2>
    </div>
    <div class="cards-3 reveal">%s</div>
    <div class="btns reveal"><a class="btn btn-primary" href="/blog/"><span data-i18n="blog.cta">All articles</span><span class="arw">→</span></a></div>
  </div>
</section>
%s""" % (STRIP_START, cards, STRIP_END)


def update_home(arts):
    p = os.path.join(ROOT, "index.html")
    h = read(p)
    strip = home_strip(arts)
    if STRIP_START in h:
        h = re.sub(re.escape(STRIP_START) + r".*?" + re.escape(STRIP_END), lambda m: strip, h, count=1, flags=re.S)
    else:
        anchor = "<!-- ============ MUSIC / ACCORDION ============ -->"
        assert anchor in h, "home anchor missing"
        h = h.replace(anchor, strip + "\n\n" + anchor, 1)
    if 'data-i18n="nav.blog"' not in h:
        h = h.replace('<a href="#research" data-i18n="nav.research">Research</a>',
                      '<a href="#research" data-i18n="nav.research">Research</a>\n      <a href="/blog/" data-i18n="nav.blog">AI News</a>', 1)
        h = h.replace('<li><a href="#research" data-i18n="nav.research">Research</a></li>',
                      '<li><a href="#research" data-i18n="nav.research">Research</a></li>\n          <li><a href="/blog/" data-i18n="nav.blog">AI News</a></li>', 1)
    if 'hreflang="x-default"' not in h:
        h = h.replace('<link rel="canonical" href="https://farseev.com/" />',
                      '<link rel="canonical" href="https://farseev.com/" />\n<link rel="alternate" hreflang="en" href="https://farseev.com/" />\n'
                      '<link rel="alternate" hreflang="x-default" href="https://farseev.com/" />', 1)
    if '"nav.blog":' not in h:
        rows = "".join('"%s":{en:%s,zh:%s,ja:%s,ko:%s,hi:%s,ru:%s},\n' % ((k,) + tuple(json.dumps(x, ensure_ascii=False) for x in v))
                       for k, v in DICT_ADD.items())
        h = h.replace("var T = {\n", "var T = {\n" + rows, 1)
    write(p, h)


def update_llms(arts):
    p = os.path.join(ROOT, "llms.txt")
    t = read(p)
    lines = ["## AI news blog", "",
             "- [AI news, explained by Aleks](%s/blog/): hub of articles in which Aleks explains one real AI news item each, "
             "with links to the primary sources and to his research" % SITE]
    for a in arts:
        lines.append("- [%s](%s/blog/%s/): %s" % (a["title"], SITE, a["slug"], a["dek"]))
    block = "\n".join(lines) + "\n\n"
    if "## AI news blog\n" in t:
        t = re.sub(r"## AI news blog\n.*?\n\n(?=## |\Z)", lambda m: block, t, count=1, flags=re.S)
    else:
        t = t.replace("## Ventures", block + "## Ventures", 1)
    write(p, t)


def write_sitemap(arts):
    if os.path.exists(os.path.join(ROOT, "tools", "i18n.py")):
        return  # tools/i18n.py writes sitemap.xml (index) and per-language sitemaps
    rows = [("/", "2026-11-08", "monthly", "1.0"), ("/blog/", max(a["published"] for a in arts), "weekly", "0.9")]
    rows += [("/blog/%s/" % a["slug"], a.get("modified", a["published"]), "monthly", "0.7") for a in arts]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<!-- sitemap.xml — Prof. Aleks Farseev. -->",
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, lm, cf, pr in rows:
        xml.append("  <url>\n    <loc>%s%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>%s</changefreq>\n    <priority>%s</priority>\n  </url>" % (SITE, path, lm, cf, pr))
    xml.append("</urlset>")
    write(os.path.join(ROOT, "sitemap.xml"), "\n".join(xml) + "\n")


def load_articles():
    arts = [parse(p) for p in sorted(glob.glob(os.path.join(ROOT, "content", "blog", "*.txt")))]
    arts.sort(key=lambda a: (a["news_date"], a["slug"]), reverse=True)
    return arts


def main():
    arts = load_articles()
    for a in arts:
        write(os.path.join(ROOT, "blog", a["slug"], "index.html"), article_page(a, arts))
    write(os.path.join(ROOT, "blog", "index.html"), hub_page(arts))
    update_home(arts)
    update_llms(arts)
    write_sitemap(arts)
    ws = [words(a) for a in arts]
    print("built %d articles + hub (words: min %d, max %d)" % (len(arts), min(ws), max(ws)))
    for a, w in zip(arts, ws):
        flag = "" if 700 <= w <= 1100 else "  <-- out of 700-1100"
        tl = "" if len(a["title"]) <= 62 else "  <-- title %d chars" % len(a["title"])
        dl = "" if 110 <= len(a["dek"]) <= 165 else "  <-- dek %d chars" % len(a["dek"])
        print("  %-48s %4d words%s%s%s" % (a["slug"], w, flag, tl, dl))


if __name__ == "__main__":
    main()
