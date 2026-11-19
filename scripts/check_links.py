#!/usr/bin/env python3
"""Check every link and anchor in index.html and llms.txt.

Usage: python3 scripts/check_links.py [--offline]

- External links are fetched with curl (follows redirects, 15s timeout).
- X/Twitter (400/403/429) and LinkedIn (999) block bots, so those are reported as SKIP, not FAIL.
- In-page #anchors must match an element id.
- Exit code is 1 if anything FAILs, so this can run in CI.
"""
import re, subprocess, sys
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
offline = "--offline" in sys.argv

class P(HTMLParser):
    def __init__(s): super().__init__(); s.hrefs=[]; s.ids=set()
    def handle_starttag(s, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"): s.hrefs.append(d["href"])
        if d.get("id"): s.ids.add(d["id"])

p = P(); p.feed((ROOT/"index.html").read_text())
txt = (ROOT/"llms.txt").read_text()
urls = set(h for h in p.hrefs if h.startswith("http")) | set(re.findall(r"\]\((https?://[^)]+)\)", txt))
anchors = [h for h in p.hrefs if h.startswith("#") and len(h) > 1]
fails = 0

for a in sorted(set(anchors)):
    if a[1:] not in p.ids:
        print(f"FAIL anchor {a} has no matching id"); fails += 1

def check(u):
    r = subprocess.run(["curl","-s","-o","/dev/null","-L","--max-time","15","-A","Mozilla/5.0 link-check","-w","%{http_code}",u],capture_output=True,text=True)
    return u, r.stdout.strip()

if not offline:
    with ThreadPoolExecutor(8) as ex:
        for u, code in ex.map(check, sorted(urls)):
            botwall = (re.match(r"https?://(www\.)?(x|twitter)\.com/", u) and code in {"400","403","429"}) or (re.match(r"https?://(www\.)?linkedin\.com/", u) and code == "999")
            if code.startswith(("2","3")): print(f"ok   {code} {u}")
            elif botwall: print(f"SKIP {code} {u} (bot-blocked)")
            else: print(f"FAIL {code} {u}"); fails += 1

print(f"\n{len(urls)} external links, {len(set(anchors))} anchors, {fails} failed")
sys.exit(1 if fails else 0)
