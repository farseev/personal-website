#!/usr/bin/env python3
"""Site checker for farseev.com (stdlib only).   python3 tools/check_site.py

Checks every *.html page in the repo:
  - exactly one <h1>
  - every JSON-LD block parses; a FAQPage's question count matches the visible <summary> count
    (pages whose FAQPage has no visible FAQ at all are reported as a WARNING, not an error)
  - canonical present, absolute and self-referencing
  - hreflang alternates: targets exist, cluster includes self and x-default, <html lang> matches its own
    entry, cluster identical (reciprocal) on every page it lists; dir="rtl" on Arabic
  - every internal href/src (relative or root-relative) resolves to a file, #anchors exist on the target
  - absolute https://farseev.com/ links resolve
  - sitemap.xml and sitemap-*.xml parse and every <loc> exists on disk
Exit code 1 on any error.
"""
import html, json, os, re, sys, glob
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://farseev.com"
errors, warnings = [], []


def err(page, msg):
    errors.append("%s: %s" % (os.path.relpath(page, ROOT), msg))


def warn(page, msg):
    warnings.append("%s: %s" % (os.path.relpath(page, ROOT), msg))


def url_to_file(url):
    p = urlsplit(url)
    if p.netloc and p.netloc != "farseev.com":
        return None
    path = unquote(p.path) or "/"
    f = os.path.join(ROOT, path.lstrip("/"))
    if path.endswith("/"):
        f = os.path.join(f, "index.html")
    return f


def file_to_url(f):
    rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return SITE + "/" + rel


ids_cache = {}


def ids_of(f):
    if f not in ids_cache:
        try:
            ids_cache[f] = set(re.findall(r'\sid="([^"]+)"', open(f, encoding="utf-8").read()))
        except OSError:
            ids_cache[f] = set()
    return ids_cache[f]


def main():
    pages = [p for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)
             if "/.git/" not in p and "/tools/" not in p and "/content/" not in p]
    clusters = {}
    for f in sorted(pages):
        h = open(f, encoding="utf-8").read()
        n = len(re.findall(r"<h1[\s>]", h))
        if n != 1:
            err(f, "%d <h1> elements" % n)
        faq_q = 0
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
            try:
                d = json.loads(m.group(1))
            except ValueError as e:
                err(f, "JSON-LD does not parse: %s" % e)
                continue
            nodes = d.get("@graph", [d]) if isinstance(d, dict) else d
            for nd in nodes:
                if isinstance(nd, dict) and nd.get("@type") == "FAQPage":
                    faq_q += len(nd.get("mainEntity", []))
        shown = len(re.findall(r"<summary[\s>]", h))
        if faq_q and shown == 0:
            warn(f, "FAQPage schema (%d questions) but no visible FAQ on the page" % faq_q)
        elif faq_q and faq_q != shown:
            err(f, "FAQPage has %d questions, page shows %d" % (faq_q, shown))
        lang = re.search(r'<html lang="([^"]+)"', h)
        lang = lang.group(1) if lang else None
        if lang and lang.startswith("ar") and 'dir="rtl"' not in h[:400]:
            err(f, 'Arabic page without dir="rtl"')
        c = re.search(r'<link rel="canonical" href="([^"]+)"', h)
        if not c:
            err(f, "no canonical")
        elif c.group(1) != file_to_url(f):
            err(f, "canonical %s is not self (%s)" % (c.group(1), file_to_url(f)))
        alts = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', h)
        if not alts:
            err(f, "no hreflang")
        else:
            codes = dict(alts)
            if "x-default" not in codes:
                err(f, "no x-default hreflang")
            if file_to_url(f) not in codes.values():
                err(f, "hreflang cluster does not include self")
            elif lang and codes.get(lang) != file_to_url(f):
                err(f, "html lang %s does not match own hreflang entry" % lang)
            for code, u in alts:
                t = url_to_file(u)
                if not t or not os.path.exists(t):
                    err(f, "hreflang %s -> missing %s" % (code, u))
            clusters[file_to_url(f)] = tuple(sorted(alts))
        # links (ignore inline scripts' strings: only real attributes outside <script>)
        body = re.sub(r"<script(?![^>]*ld\+json).*?</script>", "", h, flags=re.S)
        for attr, u in re.findall(r'\s(href|src)="([^"]+)"', body):
            u = html.unescape(u)
            if re.match(r"^(https?:|mailto:|tel:|data:|//|javascript:)", u):
                if u.startswith(SITE + "/") or u == SITE:
                    t = url_to_file(u)
                    if t and not os.path.exists(t):
                        err(f, "absolute link to missing %s" % u)
                continue
            path, _, frag = u.partition("#")
            if path == "":
                tgt = f
            elif path.startswith("/"):
                tgt = os.path.join(ROOT, unquote(path).lstrip("/"))
                if path.endswith("/") or os.path.isdir(tgt):
                    tgt = os.path.join(tgt, "index.html")
            else:
                tgt = os.path.normpath(os.path.join(os.path.dirname(f), unquote(path)))
                if path.endswith("/") or os.path.isdir(tgt):
                    tgt = os.path.join(tgt, "index.html")
            if not os.path.exists(tgt):
                err(f, "broken link %s" % u)
            elif frag and tgt.endswith(".html") and frag not in ids_of(tgt):
                err(f, "missing anchor #%s in %s" % (frag, os.path.relpath(tgt, ROOT)))
    for url, cl in clusters.items():
        for code, u in cl:
            if code == "x-default":
                continue
            other = clusters.get(u)
            if other is not None and other != cl:
                err(url_to_file(url), "hreflang cluster differs from %s" % u)
                break
    for sm in glob.glob(os.path.join(ROOT, "sitemap*.xml")):
        try:
            t = ET.parse(sm)
        except ET.ParseError as e:
            err(sm, "XML does not parse: %s" % e)
            continue
        for loc in t.getroot().iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            tf = url_to_file(loc.text.strip())
            if not tf or not os.path.exists(tf):
                err(sm, "loc missing on disk: %s" % loc.text)
    for w in warnings:
        print("WARNING", w)
    for e in errors:
        print("ERROR", e)
    print("%d pages checked, %d errors, %d warnings" % (len(pages), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
