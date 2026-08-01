Prof. Aleks Farseev — Personal Website
======================================
A self-contained, multilingual (English / 中文 / 日本語 / 한국어 / हिन्दी / Русский),
SEO- and GEO-ready single-page website. Generated 2026-07-16.

CONTENTS
--------
index.html            The website. All photos are embedded (base64) — no image folder needed.
og-image.png          Social-share preview image (1200 x 630).
favicon.svg           Primary favicon (scalable). Also embedded inside index.html.
favicon-32.png        Fallback favicon (32 x 32).
apple-touch-icon.png  iOS home-screen icon (180 x 180).
icon-512.png          Large app / PWA icon (512 x 512).
robots.txt            Crawler rules — search engines AND AI crawlers opted in.
llms.txt              AI / LLM summary file (Generative Engine Optimization).
sitemap.xml           XML sitemap.

DEPLOY — 3 STEPS
----------------
1) REPLACE THE DOMAIN.
   This package uses a placeholder domain: aleksfarseev.com
   Find-and-replace it with your real domain in these four files:
     - index.html   (canonical, og:url, og:image, twitter:image, JSON-LD, sitemap link)
     - robots.txt
     - sitemap.xml
     - llms.txt
   og:image and twitter:image MUST be the full absolute URL, e.g.
   https://YOURDOMAIN.com/og-image.png

2) UPLOAD EVERYTHING TO YOUR WEB ROOT.
   All files must sit at the top level so they resolve at
   yourdomain.com/robots.txt, /llms.txt, /sitemap.xml, /og-image.png, etc.
     - Netlify / Vercel / Cloudflare Pages: drag this folder in, or connect a repo.
     - GitHub Pages: commit these files to the repo root (or the /docs folder).
     - cPanel / shared hosting: upload the files into public_html/.

3) AFTER GOING LIVE.
   - Verify the site in Google Search Console and Bing Webmaster Tools; submit sitemap.xml.
   - Test structured data:  https://search.google.com/test/rich-results
   - Check the social card:  LinkedIn Post Inspector  and  X (Twitter) Card Validator.

NOTES
-----
- index.html is fully self-contained (photos embedded), so it renders even when opened
  directly from disk. The favicon PNGs, og-image.png and the three text files are still
  required at the web root for full SEO / GEO and link-preview support.
- All six languages switch client-side and share a single URL.
- To update the copyright year or any content, edit index.html directly.
- Confirm the exact Google Scholar h-index on the live profile (currently shown as 23);
  it is a one-value edit in index.html and llms.txt if it needs changing.

============================================================
UPDATE (2026-08) — favicon, Faith journey, live Scholar
============================================================
1) GOOGLE SEARCH FAVICON FIX
   The old icon was a 32px PNG + a data-URI SVG — below Google's 48px
   minimum, so search results rendered a tiny/blurry mark. Replaced with
   a redesigned AF monogram that fills the tile, provided at multiples of
   48px (favicon-48/96/192/512.png), a real favicon.ico and favicon.svg,
   plus site.webmanifest. index.html now references crawlable, root-
   absolute icons (/favicon.ico, /favicon.svg, /favicon-96.png,
   /favicon-192.png). After deploy, request re-indexing in Google Search
   Console; the larger favicon can take a crawl cycle or two to appear.

2) FAITH JOURNEY (now ~1/3 of the page)
   The Faith section is expanded into a full 11-chapter journey (#faith),
   a "people who said yes" grid (Henry Kaestner, Aidan Chan, Yuh Tyng
   Hsiao) and a "Come build with us" join card with the faithdriven.sg QR
   and the Sept 18, 2026 watch party. Styled entirely in the SOMIN teal
   system (per the SOMIN brand guideline). Portraits are embedded (base64),
   processed to a teal-tinted duotone — no image folder required.

3) LIVE GOOGLE SCHOLAR (browser-only, no backend)
   The publications section now fetches the public Google Scholar profile
   (user ZJW7F18AAAAJ) live from the visitor's browser via public CORS
   proxies, parses it client-side, and renders SOMIN-styled cards plus
   live citation / h-index / i10-index metrics (the h-index also updates
   the "Impact at a glance" stat). If every proxy is unreachable it falls
   back to the curated list below (which is also what search crawlers and
   no-JS visitors see). To point it at a different profile, change USER_ID
   in the Scholar <script> near the end of index.html. Public proxies can
   rate-limit; the curated fallback guarantees the section is never empty.
