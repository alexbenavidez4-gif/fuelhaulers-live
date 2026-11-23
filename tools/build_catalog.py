#!/usr/bin/env python3
"""Builds the fuelhaulers.live knowledge catalog.

Reads:
  data/catalog.json  - site facts, FAQs, and guides (edit this file)
  index.html         - the TERMINALS list the live app uses (single list of racks)
Writes:
  terminals/  racks/  guides/  about/   - static pages for Google and AI tools
  terminals.json  llms.txt  sitemap.xml  assets/catalog.css

Run from the repo root:  python3 tools/build_catalog.py
Uses only the Python standard library.
"""
import html, json, os, re, shutil, datetime
from urllib.parse import quote, quote_plus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://fuelhaulers.live"
UTAH = {"Salt Lake City", "Cedar City / St. George", "Cisco / Grand Junction"}
TODAY = datetime.date.today().isoformat()
e = html.escape


def slug(s):
    s = s.lower().replace("&", " and ").replace("/", " ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def load():
    cat = json.load(open(os.path.join(ROOT, "data/catalog.json"), encoding="utf-8"))
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    a = src.index("const TERMINALS"); b = src.index("];", a)
    rows = re.findall(r'\{"id": "([^"]+)", "name": "([^"]+)", "addr": "([^"]+)", "region": "([^"]+)"\}', src[a:b])
    regions = []
    terms = []
    seen = set()
    for tid, name, addr, region in rows:
        street, _, city = addr.rpartition(",")
        city = city.strip() or region
        state = "UT" if region in UTAH else "TX"
        base = slug(f"{name} {city}")
        s, n = base, 2
        while s in seen:
            s = f"{base}-{n}"; n += 1
        seen.add(s)
        terms.append(dict(id=tid, name=name, addr=addr, street=street.strip(), city=city, state=state,
                          region=region, slug=s, tcn=tid if tid.startswith("T-") else None))
        if region not in regions:
            regions.append(region)
    return cat, terms, regions


CSS = """:root{--navy:#0F2436;--navy2:#16324a;--cream:#F5F0E6;--ink:#1d2430;--muted:#5d6675;--orange:#E4572E;--orange2:#F28C28;--line:#e4dccb}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font:17px/1.6 Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:#B5401C}
.top{background:var(--navy);color:#fff}
.top .in{max-width:980px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 18px}
.brand{color:#fff;text-decoration:none;font-weight:800;font-size:20px;letter-spacing:.2px;display:flex;align-items:center;gap:8px}
.brand img{width:30px;height:30px;border-radius:7px}
.top nav{display:flex;flex-wrap:wrap;gap:4px 14px}
.top nav a{color:#F5F0E6;text-decoration:none;font-size:15px;font-weight:600;padding:4px 0}
.top nav a:hover{color:var(--orange2)}
main{max-width:980px;margin:0 auto;padding:18px 16px 40px}
.crumbs{font-size:14px;color:var(--muted);margin:0 0 6px}
.crumbs a{color:var(--muted)}
h1{font-size:clamp(26px,5vw,38px);line-height:1.2;margin:4px 0 10px;color:var(--navy)}
h2{font-size:23px;margin:28px 0 8px;color:var(--navy)}
h3{font-size:18px;margin:18px 0 4px}
.lead{font-size:18px;color:#2c3442;margin:0 0 16px}
.cta{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 8px}
.btn{display:inline-block;padding:12px 18px;border-radius:10px;font-weight:700;text-decoration:none;background:var(--orange);color:#fff}
.btn.alt{background:var(--navy);color:#fff}
.btn:hover{filter:brightness(1.08)}
.facts{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:14px 0}
.facts dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:0}
.facts dt{font-weight:700;color:var(--muted)}.facts dd{margin:0}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:10px 0 6px;font-size:16px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#efe8d8;color:var(--navy)}
tr:last-child td{border-bottom:0}
.tablewrap{overflow-x:auto}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin:10px 0}
.card{display:block;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;text-decoration:none;color:var(--ink)}
.card b{color:var(--navy);display:block}
.card span{color:var(--muted);font-size:15px}
.card:hover{border-color:var(--orange2)}
.faq h3{margin-top:14px}.faq p{margin:2px 0 8px;color:#2c3442}
.note{font-size:14px;color:var(--muted)}
.src{font-size:14px}.src li{margin:2px 0}
footer{background:var(--navy);color:#cfd6df;font-size:14px}
footer .in{max-width:980px;margin:0 auto;padding:20px 16px 30px}
footer a{color:#F5F0E6}
@media (max-width:560px){.facts dl{grid-template-columns:1fr}.facts dt{margin-top:6px}th,td{padding:8px}}
"""


def page(path, title, desc, body, ld, crumbs):
    canon = SITE + path
    crumb_html = " › ".join((f'<a href="{u}">{e(n)}</a>' if u else e(n)) for n, u in crumbs)
    ld = list(ld) + [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + u} if u else {"item": canon})}
        for i, (n, u) in enumerate(crumbs)]}]
    lds = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canon}">
<meta name="theme-color" content="#0F2436">
<meta property="og:type" content="website">
<meta property="og:site_name" content="fuelhaulers.live">
<meta property="og:url" content="{canon}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{SITE}/og-image.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/catalog.css">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-FN67N6TDTN"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-FN67N6TDTN');</script>
{lds}
</head>
<body>
<header class="top"><div class="in">
<a class="brand" href="/"><img src="/icon-192.png" alt="" width="30" height="30">fuelhaulers.live</a>
<nav aria-label="Site"><a href="/">Live racks</a><a href="/terminals/">Terminals</a><a href="/recap">HOS Recap</a><a href="/guides/">Guides</a><a href="/about/">About</a></nav>
</div></header>
<main>
<p class="crumbs">{crumb_html}</p>
{body}
</main>
<footer><div class="in">
<a href="/">Live rack wait times</a> · <a href="/terminals/">Fuel terminals</a> · <a href="/recap">HOS Recap calculator</a> · <a href="/guides/">Guides</a> · <a href="/about/">About</a> · <a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a><br>
© {TODAY[:4]} fuelhaulers.live · Built by fuel haulers, for fuel haulers. Never post while driving.
</div></footer>
</body>
</html>
"""


def write(rel, text):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def faq_block(faqs, heading="Common questions"):
    if not faqs:
        return "", None
    h = f'<section class="faq"><h2>{e(heading)}</h2>' + "".join(
        f"<h3>{e(f['q'])}</h3><p>{e(f['a'])}</p>" for f in faqs) + "</section>"
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs]}
    return h, ld


def place_ld(t):
    d = {"@context": "https://schema.org", "@type": "Place", "name": f"{t['name']} ({t['city']}, {t['state']})",
         "description": f"Fuel terminal and truck loading rack in {t['city']}, {t['state']}.",
         "url": f"{SITE}/racks/{t['slug']}/",
         "address": {"@type": "PostalAddress", "streetAddress": t["street"], "addressLocality": t["city"],
                     "addressRegion": t["state"], "addressCountry": "US"}}
    if t["tcn"]:
        d["identifier"] = {"@type": "PropertyValue", "propertyID": "IRS Terminal Control Number (TCN)", "value": t["tcn"]}
    return d


def build():
    cat, terms, regions = load()
    site = cat["site"]
    by = {r: [t for t in terms if t["region"] == r] for r in regions}
    rslug = {r: slug(r) for r in regions}
    for d in ("terminals", "racks", "guides", "about"):
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    urls = []

    # ---- CSS
    write("assets/catalog.css", CSS)

    # ---- /terminals/
    cards = "".join(f'<a class="card" href="/terminals/{rslug[r]}/"><b>{e(r)}, {"UT" if r in UTAH else "TX"}</b><span>{len(by[r])} fuel terminal{"s" if len(by[r]) != 1 else ""}</span></a>' for r in regions)
    body = f"""<h1>Fuel Terminals in Texas and Utah</h1>
<p class="lead">{len(terms)} fuel racks and truck loading terminals across {len(regions)} areas of Texas and Utah, with addresses, IRS terminal control numbers, and live wait times from drivers.</p>
<div class="cta"><a class="btn" href="/">See live rack wait times</a><a class="btn alt" href="/recap">HOS Recap calculator</a></div>
<h2>Choose an area</h2><div class="cards">{cards}</div>"""
    ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Fuel Terminals in Texas and Utah", "url": SITE + "/terminals/"}]
    write("terminals/index.html", page("/terminals/", "Fuel Terminals in Texas and Utah: Racks, Addresses, Wait Times | FuelHaulers",
          f"All {len(terms)} fuel racks and terminals we cover in Texas and Utah, by city, with addresses, terminal numbers, and live wait times from drivers.",
          body, ld, [("Home", "/"), ("Fuel terminals", None)]))
    urls.append(("/terminals/", "weekly", "0.8"))

    # ---- city pages
    for r in regions:
        ts = by[r]; st = "UT" if r in UTAH else "TX"; n = len(ts)
        rows = "".join(f'<tr><td><a href="/racks/{t["slug"]}/">{e(t["name"])}</a></td><td>{e(t["addr"])}</td><td>{e(t["tcn"] or "")}</td></tr>' for t in ts)
        others = "".join(f'<a class="card" href="/terminals/{rslug[o]}/"><b>{e(o)}</b><span>{len(by[o])} terminals</span></a>' for o in regions if o != r)
        faqs = [{"q": f"How many fuel terminals are in the {r} area?", "a": f"fuelhaulers.live covers {n} fuel rack{'s' if n != 1 else ''} and terminal{'s' if n != 1 else ''} in the {r}, {st} area: " + ", ".join(t["name"] for t in ts) + "."},
                {"q": f"How can I check fuel rack wait times in {r}?", "a": f"Open fuelhaulers.live and pick {r}. Drivers at the rack post how busy each terminal is right now, lanes down, product outages, and the wait time. Each terminal also shows its usual busy hours."}]
        fh, fld = faq_block(faqs)
        body = f"""<h1>Fuel Terminals in {e(r)}, {st}</h1>
<p class="lead">{n} fuel rack{'s' if n != 1 else ''} and truck loading terminal{'s' if n != 1 else ''} in the {e(r)} area, with addresses and IRS terminal control numbers (TCN). Check live wait times from drivers before you roll.</p>
<div class="cta"><a class="btn" href="/?city={quote(r)}">Live wait times in {e(r)}</a><a class="btn alt" href="/recap">HOS Recap calculator</a></div>
<h2>{e(r)} fuel racks and terminals</h2>
<div class="tablewrap"><table><thead><tr><th>Terminal</th><th>Address</th><th>TCN</th></tr></thead><tbody>{rows}</tbody></table></div>
{fh}
<h2>Other areas</h2><div class="cards">{others}</div>"""
        ld = [{"@context": "https://schema.org", "@type": "ItemList", "name": f"Fuel terminals in {r}, {st}",
               "numberOfItems": n, "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{SITE}/racks/{t['slug']}/", "name": t["name"]} for i, t in enumerate(ts)]}, fld]
        write(f"terminals/{rslug[r]}/index.html", page(f"/terminals/{rslug[r]}/",
              f"Fuel Terminals in {r}, {st}: {n} Racks and Wait Times | FuelHaulers"[:90],
              f"{n} fuel racks and terminals in the {r}, {st} area with addresses, terminal numbers, and live wait times posted by fuel haulers.",
              body, ld, [("Home", "/"), ("Fuel terminals", "/terminals/"), (r, None)]))
        urls.append((f"/terminals/{rslug[r]}/", "weekly", "0.7"))

    # ---- rack pages
    for t in terms:
        r = t["region"]; nearby = [o for o in by[r] if o is not t]
        near = "".join(f'<a class="card" href="/racks/{o["slug"]}/"><b>{e(o["name"])}</b><span>{e(o["addr"])}</span></a>' for o in nearby)
        maps = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(f"{t['name']}, {t['addr']}, {t['state']}")
        tcn = f"<dt>Terminal number (TCN)</dt><dd>{e(t['tcn'])}</dd>" if t["tcn"] else ""
        body = f"""<h1>{e(t['name'])}: {e(t['city'])}, {t['state']}</h1>
<p class="lead">Live rack wait times, address, and usual busy hours for the {e(t['name'])} fuel terminal in {e(t['city'])}, {t['state']}, posted by fuel haulers at the rack.</p>
<div class="facts"><dl>
<dt>Address</dt><dd>{e(t['addr'])}, {t['state']}</dd>{tcn}
<dt>Area</dt><dd><a href="/terminals/{rslug[r]}/">{e(r)}</a></dd>
<dt>Type</dt><dd>Fuel terminal / truck loading rack</dd>
</dl></div>
<div class="cta"><a class="btn" href="/?rack={quote(t['id'])}">See live wait time</a><a class="btn alt" href="{maps}" rel="noopener">Directions</a></div>
<h2>Is {e(t['name'])} busy right now?</h2>
<p>Drivers on fuelhaulers.live post how busy this rack is while they are in line: dead, moderate, busy, or packed, plus lanes down, product outages, and about how long the wait is. Tap <b>See live wait time</b> for the latest reports and a chart of this terminal's usual busy and quiet hours for each day of the week.</p>
<p>Waiting at the rack counts as on-duty time. Use the free <a href="/recap">HOS Recap calculator</a> to see how many hours you have left, and read <a href="/guides/texas-vs-federal-hours-of-service/">Texas vs. federal hours of service rules</a>.</p>
{('<h2>Other fuel terminals in ' + e(r) + '</h2><div class="cards">' + near + '</div>') if near else ''}
<p class="note">Terminal details come from public terminal listings. Wait times come from driver reports and can change quickly. Never post while driving.</p>"""
        write(f"racks/{t['slug']}/index.html", page(f"/racks/{t['slug']}/",
              f"{t['name']} {t['city']}, {t['state']}: Rack Wait Times and Address | FuelHaulers",
              f"Live rack wait times, address, and usual busy hours for {t['name']} at {t['addr']}, {t['state']}. Posted by fuel haulers at the rack.",
              body, [place_ld(t)], [("Home", "/"), ("Fuel terminals", "/terminals/"), (r, f"/terminals/{rslug[r]}/"), (t["name"], None)]))
        urls.append((f"/racks/{t['slug']}/", "weekly", "0.6"))

    # ---- guides
    gcards = "".join(f'<a class="card" href="/guides/{g["slug"]}/"><b>{e(g["title"])}</b><span>{e(g["description"])}</span></a>' for g in cat["guides"])
    write("guides/index.html", page("/guides/", "Hours of Service Guides for Fuel Haulers | FuelHaulers",
          "Plain-English guides for fuel haulers: Texas vs. federal hours of service, how the 70-hour recap works, and the 34-hour restart.",
          f'<h1>Guides for Fuel Haulers</h1><p class="lead">Plain-English answers on hours of service, recaps, and restarts, written for tanker drivers.</p><div class="cards">{gcards}</div><div class="cta"><a class="btn" href="/recap">Open the HOS Recap calculator</a></div>',
          [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Guides for Fuel Haulers", "url": SITE + "/guides/"}],
          [("Home", "/"), ("Guides", None)]))
    urls.append(("/guides/", "monthly", "0.7"))
    for g in cat["guides"]:
        secs = ""
        for s in g["sections"]:
            secs += f"<h2>{e(s['h'])}</h2>" + "".join(f"<p>{e(p)}</p>" for p in s.get("p", []))
            if s.get("table"):
                tb = s["table"]
                secs += '<div class="tablewrap"><table><thead><tr>' + "".join(f"<th>{e(h)}</th>" for h in tb["head"]) + "</tr></thead><tbody>" + "".join(
                    "<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in tb["rows"]) + "</tbody></table></div>"
            secs += "".join(f"<p>{e(p)}</p>" for p in s.get("p2", []))
        fh, fld = faq_block(g.get("faqs"))
        others = "".join(f'<li><a href="/guides/{o["slug"]}/">{e(o["title"])}</a></li>' for o in cat["guides"] if o is not g)
        src = "".join(f'<li><a href="{e(u)}" rel="noopener">{e(n)}</a></li>' for n, u in g.get("sources", []))
        body = f"""<h1>{e(g['title'])}</h1>
<p class="note">Updated {e(g['updated'])} · fuelhaulers.live</p>
<p class="lead">{e(g['intro'])}</p>
{secs}
<div class="cta"><a class="btn" href="/recap">Open the free HOS Recap calculator</a><a class="btn alt" href="/">Live rack wait times</a></div>
{fh}
<h2>More guides</h2><ul>{others}</ul>
<h2>Sources</h2><ul class="src">{src}</ul>
<p class="note">This guide is general information, not legal advice. Your carrier's policies and your ELD records come first.</p>"""
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": g["title"], "description": g["description"],
               "dateModified": g["updated"], "author": {"@type": "Organization", "name": "fuelhaulers.live", "url": SITE + "/"},
               "publisher": {"@type": "Organization", "name": "fuelhaulers.live", "logo": {"@type": "ImageObject", "url": SITE + "/icon-512.png"}},
               "mainEntityOfPage": f"{SITE}/guides/{g['slug']}/"}, fld]
        write(f"guides/{g['slug']}/index.html", page(f"/guides/{g['slug']}/", g["title"] + " | FuelHaulers", g["description"], body, ld,
              [("Home", "/"), ("Guides", "/guides/"), (g["title"], None)]))
        urls.append((f"/guides/{g['slug']}/", "monthly", "0.8"))

    # ---- about
    feats = "".join(f'<h3><a href="{e(f["link"])}">{e(f["name"])}</a></h3><p>{e(f["text"])}</p>' for f in site["features"])
    fh, fld = faq_block(cat["faqs"], "Questions about fuelhaulers.live")
    body = f"""<h1>About fuelhaulers.live</h1>
<p class="lead">{e(site['summary'])}</p>
<p>{e(site['built_by'])} It covers {len(terms)} fuel racks and terminals across {e(site['areas'])}. {e(site['cost'])}</p>
<div class="cta"><a class="btn" href="/">See live rack wait times</a><a class="btn alt" href="/?install">Install the app</a></div>
<h2>What you can do</h2>{feats}
{fh}
<h2>Contact</h2><p>Questions, a rack we're missing, or an idea? Email <a href="mailto:{e(site['email'])}">{e(site['email'])}</a>.</p>
<p class="note">{e(site['safety'])}</p>"""
    ld = [{"@context": "https://schema.org", "@type": "AboutPage", "name": "About fuelhaulers.live", "url": SITE + "/about/",
           "about": {"@type": "WebApplication", "name": "fuelhaulers.live", "url": SITE + "/", "applicationCategory": "TravelApplication",
                     "operatingSystem": "Any (web browser, Android, iPhone)", "description": site["summary"],
                     "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}}, fld]
    write("about/index.html", page("/about/", "About fuelhaulers.live: Free Rack Wait Times for Fuel Haulers",
          site["summary"][:155], body, ld, [("Home", "/"), ("About", None)]))
    urls.append(("/about/", "monthly", "0.6"))

    # ---- terminals.json (open data)
    write("terminals.json", json.dumps({
        "name": "fuelhaulers.live fuel terminal list", "url": SITE + "/terminals/", "updated": TODAY,
        "note": "Fuel racks and truck loading terminals covered by fuelhaulers.live. Texas and Utah terminal numbers (TCN) follow the IRS approved terminal list. Live wait times are at https://fuelhaulers.live/.",
        "count": len(terms),
        "terminals": [{"name": t["name"], "address": f"{t['addr']}, {t['state']}", "city": t["city"], "state": t["state"],
                       "area": t["region"], "tcn": t["tcn"], "page": f"{SITE}/racks/{t['slug']}/", "live": f"{SITE}/?rack={quote(t['id'])}"} for t in terms]
    }, indent=1, ensure_ascii=False) + "\n")

    # ---- llms.txt
    L = [f"# {site['name']}", "", f"> {site['summary']} {site['built_by']} Covers {len(terms)} fuel terminals in {site['areas']}. {site['cost']}", "",
         "## Main pages", f"- [Live rack wait times]({SITE}/): driver-posted fuel rack busyness, lanes down, product outages, wait times, usual busy hours",
         f"- [HOS Recap calculator]({SITE}/recap): free 70-hour / 8-day recap calculator; hours stay on the user's phone",
         f"- [Fuel terminals by area]({SITE}/terminals/): {len(terms)} racks with addresses and IRS terminal numbers",
         f"- [About]({SITE}/about/)", f"- [Terminal data (JSON)]({SITE}/terminals.json)", "", "## Guides"]
    L += [f"- [{g['title']}]({SITE}/guides/{g['slug']}/): {g['description']}" for g in cat["guides"]]
    L += ["", "## Areas"] + [f"- [{r}]({SITE}/terminals/{rslug[r]}/): {len(by[r])} terminal{'s' if len(by[r]) != 1 else ''}" for r in regions]
    L += ["", "## Facts"] + [f"- {f['q']} {f['a']}" for f in cat["faqs"]]
    write("llms.txt", "\n".join(L) + "\n")

    # ---- sitemap
    base = [("/", "daily", "1.0"), ("/recap", "monthly", "0.9")] + urls + [("/privacy.html", "yearly", "0.2"), ("/terms.html", "yearly", "0.2")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{SITE}{u}</loc><lastmod>{TODAY}</lastmod><changefreq>{c}</changefreq><priority>{p}</priority></url>" for u, c, p in base]
    sm.append("</urlset>")
    write("sitemap.xml", "\n".join(sm) + "\n")
    print(f"built: {len(regions)} area pages, {len(terms)} rack pages, {len(cat['guides'])} guides, about, llms.txt, terminals.json, sitemap ({len(base)} urls)")


if __name__ == "__main__":
    build()
