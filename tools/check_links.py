#!/usr/bin/env python3
"""Site health check for fuelhaulers.live (standard library only).

Visits every page in sitemap.xml plus every page they link to, and reports:
  * broken links (pages, images, files) on this site
  * broken links to other websites
  * sitemap pages that don't load, redirect, are blocked from Google (noindex),
    or point their canonical tag at a different address
  * pages on this site that are linked to but missing from the sitemap

Writes link-report.md and exits 1 when something needs fixing.
Usage: python3 tools/check_links.py [https://fuelhaulers.live]
"""
import re, sys, time, urllib.request, urllib.error, concurrent.futures as cf
from html.parser import HTMLParser
from urllib.parse import urljoin, urldefrag, urlparse

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://fuelhaulers.live").rstrip("/")
HOST = urlparse(BASE).netloc
UA = "Mozilla/5.0 (compatible; FuelHaulersLinkCheck/1.0; +https://fuelhaulers.live/)"
# Some sites hang up on anything that looks like a robot, so try a plain browser-style request too.
UA_PLAIN = "Mozilla/5.0"
# Sites that block robots or always answer oddly; a failure there is not a real broken link.
SKIP_EXTERNAL = ("fonts.googleapis.com", "fonts.gstatic.com", "facebook.com", "www.facebook.com",
                 "tiktok.com", "www.tiktok.com", "instagram.com", "www.instagram.com",
                 "x.com", "twitter.com", "linkedin.com", "www.linkedin.com")
# Links inside the app's JavaScript templates, not real addresses.
TEMPLATE = re.compile(r"\$\{|\{\{")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.robots, self.canonical = [], "", None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and (a.get("name") or "").lower() == "robots":
            self.robots = (a.get("content") or "").lower()
        if tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        for attr in ("href", "src"):
            v = a.get(attr)
            if v and tag in ("a", "link", "img", "script", "source", "iframe"):
                if tag == "link" and (a.get("rel") or "").lower() in ("preconnect", "dns-prefetch"):
                    continue
                self.links.append(v.strip())


def fetch(url, method="GET", ua=None):
    """Return (status, final_url, body_text). status 0 = could not connect."""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": ua or UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=25) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read(3_000_000).decode("utf-8", "replace") if method == "GET" and ("html" in ctype or "xml" in ctype) else ""
                return r.status, r.geturl(), body
        except urllib.error.HTTPError as e:
            if e.code in (405, 403) and method == "HEAD":
                return fetch(url, "GET", ua)
            if e.code >= 500 and attempt < 2:   # GitHub sometimes hiccups; try again
                time.sleep(3); continue
            return e.code, url, ""
        except Exception:
            if attempt < 2:
                time.sleep(3); continue
            if ua is None:                       # last try: plain browser-style request
                return fetch(url, method, UA_PLAIN)
            return 0, url, ""


def norm(u):
    u = urldefrag(u)[0]
    p = urlparse(u)
    return p._replace(query="").geturl() if p.netloc == HOST else u


def main():
    status, _, sm = fetch(BASE + "/sitemap.xml")
    if status != 200:
        print("Could not load sitemap.xml:", status); sys.exit(1)
    sitemap = [norm(u) for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm)]
    sitemap_set = set(sitemap)
    if not sitemap:
        print("sitemap.xml has no pages in it"); sys.exit(1)

    pages, seen, queue = {}, set(sitemap), list(sitemap)
    linked_from = {}            # url -> first page that linked it
    problems = {"internal": [], "external": [], "sitemap": [], "missing": []}
    blocked = []                # other sites that refuse robots (403/429) - can't verify, not counted

    # 1. crawl every page on this site (sitemap pages + any other site pages they link to)
    while queue:
        batch, queue = queue, []
        with cf.ThreadPoolExecutor(8) as ex:
            results = dict(zip(batch, ex.map(fetch, batch)))
        for url, (st, final, body) in results.items():
            pages[url] = st
            in_map = url in sitemap_set
            if st != 200:
                (problems["sitemap"] if in_map else problems["internal"]).append(
                    (url, f"answers {st or 'no connection'}", linked_from.get(url, "sitemap.xml")))
                continue
            if in_map and norm(final).rstrip("/") != url.rstrip("/"):
                problems["sitemap"].append((url, f"redirects to {final}", "sitemap.xml"))
            if not body:
                continue
            p = Links(); p.feed(body)
            if in_map and "noindex" in p.robots:
                problems["sitemap"].append((url, "has a noindex tag (Google is told not to list it)", "sitemap.xml"))
            if in_map and p.canonical and norm(urljoin(url, p.canonical)).rstrip("/") != url.rstrip("/"):
                problems["sitemap"].append((url, f"canonical tag points to {p.canonical}", "sitemap.xml"))
            for raw in p.links:
                if TEMPLATE.search(raw) or raw.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:")):
                    continue
                full = norm(urljoin(url, raw))
                if not full.startswith("http") or full in seen:
                    continue
                seen.add(full); linked_from[full] = url
                if urlparse(full).netloc == HOST:
                    path = urlparse(full).path
                    is_page = path.endswith("/") or path.endswith(".html") or "." not in path.rsplit("/", 1)[-1]
                    if is_page:
                        queue.append(full)
                        if full not in sitemap_set and not path.endswith(("privacy.html", "terms.html")):
                            problems["missing"].append((full, "linked on the site but not in sitemap.xml", url))
                    else:
                        queue.append(full)

    # 2. check links that go to other websites
    external = [u for u in seen if urlparse(u).netloc not in (HOST, "") and urlparse(u).netloc not in SKIP_EXTERNAL]
    with cf.ThreadPoolExecutor(8) as ex:
        for url, (st, _, _) in zip(external, ex.map(lambda u: fetch(u, "HEAD"), external)):
            if st in (401, 403, 429):
                blocked.append((url, f"answers {st} (site blocks robots - check by hand)", linked_from.get(url, "?")))
            elif st == 0 or st >= 400:
                problems["external"].append((url, f"answers {st or 'no connection'}", linked_from.get(url, "?")))

    # 3. write the report
    total = sum(len(v) for v in problems.values())
    lines = ["# fuelhaulers.live link check", "",
             f"Checked {len(pages)} addresses on the site ({len(sitemap)} in the sitemap) "
             f"and {len(external)} links to other websites.", ""]
    titles = {"sitemap": "Sitemap pages with a problem (these hurt Google indexing)",
              "internal": "Broken links on this site",
              "external": "Broken links to other websites",
              "missing": "Pages missing from the sitemap"}
    if total == 0:
        lines.append("✅ No broken links. Every sitemap page loads and is open to Google.")
    for k, title in titles.items():
        if problems[k]:
            lines += [f"## {title} ({len(problems[k])})", "", "| Address | Problem | Found on |", "|---|---|---|"]
            lines += [f"| {u} | {why} | {src} |" for u, why, src in sorted(problems[k])]
            lines.append("")
    if blocked:
        lines += [f"## Could not check - these sites block robots ({len(blocked)})", "",
                  "Not counted as broken. Open them in a browser now and then to be sure.", "",
                  "| Address | Note | Found on |", "|---|---|---|"]
        lines += [f"| {u} | {why} | {src} |" for u, why, src in sorted(blocked)]
        lines.append("")
    report = "\n".join(lines)
    open("link-report.md", "w").write(report + "\n")
    print(report)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
