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
