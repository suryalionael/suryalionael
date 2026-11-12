#!/usr/bin/env python3
"""Commit Metro: builds the profile README cards from live GitHub data.

Usage:  python3 scripts/generate.py        (needs GITHUB_TOKEN, or a logged-in `gh`)
Writes: assets/*.svg (dark + light) and the block between the metro markers in README.md
Standard library only.
"""
import base64
import datetime as dt
import json
import os
import pathlib
import subprocess
import urllib.request
from xml.sax.saxutils import escape

# ----------------------------------------------------------------- settings
USER = os.environ.get("METRO_USER", "suryalionael")
ROLE = "Data Science & Analytics student."   # first half of the tagline
FEATURED = []        # repo names to feature; empty = your pinned repos
MAX_STATIONS = 4     # keep it even, the cards sit two per row
SKIP = {USER}        # repos left off the map

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICONS = json.loads((pathlib.Path(__file__).parent / "icons.json").read_text())

SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','Helvetica Neue',sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"

THEMES = {
    "dark": dict(page="#0d1117", card="#0d1117", border="#30363d", text="#f0f6fc",
                 soft="#c9d1d9", muted="#9198a1", track="#30363d", empty="#161b22",
                 kicker="#3fb950", train="#f0f6fc"),
    "light": dict(page="#ffffff", card="#ffffff", border="#d1d9e0", text="#1f2328",
                  soft="#3d444d", muted="#59636e", track="#e6eaef", empty="#ebedf0",
                  kicker="#1a7f37", train="#ffffff"),
}

STAR = ("M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 "
        "2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79"
        "l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z")
FORK = ("M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 "
        "0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 "
        "0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 "
        "0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 "
        "0 1.5 0Z")

QUERY = """
query($login:String!){ user(login:$login){
  name login bio company location avatarUrl(size:160)
  followers{totalCount}
  pinnedItems(first:6,types:REPOSITORY){nodes{... on Repository{name}}}
  repositories(first:100,ownerAffiliations:OWNER,privacy:PUBLIC,
               orderBy:{field:PUSHED_AT,direction:DESC}){
    totalCount
    nodes{name description url isFork isArchived stargazerCount forkCount
          primaryLanguage{name color}
          languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}
  contributionsCollection{contributionCalendar{totalContributions
    weeks{contributionDays{date contributionCount}}}}
}}"""


# --------------------------------------------------------------------- data
def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not t:
        t = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    if not t:
        raise SystemExit("Set GITHUB_TOKEN or log in with `gh auth login`.")
    return t


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", body, {
        "Authorization": f"bearer {token()}", "User-Agent": "commit-metro"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        raise SystemExit(data["errors"])
    user = data["data"]["user"]
    img = urllib.request.urlopen(user["avatarUrl"], timeout=30)
    mime = img.headers.get_content_type()
    user["avatar"] = f"data:{mime};base64,{base64.b64encode(img.read()).decode()}"
    return user


# ------------------------------------------------------------------ helpers
def cut(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip("-_ ") + "…"


def wrap(text, width, lines):
    out, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width and cur:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = cut(out[-1] + " …", width) if len(out[-1]) + 2 <= width else out[-1][: width - 1] + "…"
    return out


def ink(color):
    """Readable text colour on top of `color`."""
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#1f2328" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#ffffff"


def icon(lang, x, y, size, fill):
    d = ICONS.get(lang)
    if not d:
        return f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 3}" fill="{fill}"/>'
    return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24">'
            f'<path d="{d}" fill="{fill}"/></svg>')


def text(x, y, s, size, fill, weight=400, font=SANS, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')


MOTION = "@media (prefers-reduced-motion: reduce){*{animation:none!important}.train{display:none}}"


def svg(w, h, body, label, css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
            f'<title>{escape(label)}</title><style>{css}{MOTION}</style>{body}</svg>')


def card(w, h, accent, title, body, label, P, css=""):
    frame = (
        f'<defs><clipPath id="c"><rect width="{w}" height="{h}" rx="12"/></clipPath></defs>'
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="12" fill="{P["card"]}" stroke="{P["border"]}"/>'
        f'<rect width="{w}" height="6" fill="{accent}" clip-path="url(#c)"/>'
        f'<circle cx="36" cy="38" r="9" fill="{accent}"/>'
        + text(36, 41.5, "M", 10, ink(accent), 800, anchor="middle")
        + text(54, 42.5, title, 13, P["text"], 700))
    return svg(w, h, frame + body, label, css)


# -------------------------------------------------------------------- cards
def metro(user, lines, P):
    hx, hy, x0, x1 = 440, 270, 150, 850
    slots = [(110, 230), (170, 150), (380, 390), (440, 310)]
    css = (".draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.4s ease-out forwards}"
           "@keyframes draw{to{stroke-dashoffset:0}}"
           ".pop{transform:scale(0);animation:pop .4s ease-out forwards}@keyframes pop{to{transform:scale(1)}}"
           ".hubp{opacity:0;animation:hubp 2.6s ease-out 2s infinite}"
           "@keyframes hubp{from{opacity:.8;transform:scale(1)}to{opacity:0;transform:scale(1.9)}}"
           "@media (prefers-reduced-motion: reduce){.draw{stroke-dashoffset:0}.pop{transform:none}}")
    paths, marks, trains = [], [], []
    for i, (line, (yl, yr)) in enumerate(zip(lines, slots)):
        col = line["color"]
        xk, xr = hx - abs(hy - yl), hx + abs(hy - yr)
        paths.append(
            f'<path id="l{i}" d="M{x0},{yl} L{xk},{yl} L{hx},{hy} L{xr},{yr} L{x1},{yr}" fill="none" '
            f'stroke="{col}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round" '
            f'class="draw" pathLength="1" style="animation-delay:{i * .25:.2f}s"/>')
        # where the stops go: left of the hub first, the rest on the right
        left, right = (x0 + 30, xk - 28), (xr + 45, x1 - 50)
        cap_l = max(0, int((left[1] - left[0]) // 62) + 1)
        cap_r = max(0, int((right[1] - right[0]) // 80) + 1)
        repos = line["repos"][: cap_l + cap_r]
        n_l = min(cap_l, (len(repos) + 1) // 2)
        spots = []
        for (a, b), group in ((left, repos[:n_l]), (right, repos[n_l:])):
            for k, repo in enumerate(group):
                x = (a + b) / 2 if len(group) == 1 else a + (b - a) * k / (len(group) - 1)
                spots.append((round(x), yl if (a, b) == left else yr, repo))
        for k, (x, y, repo) in enumerate(spots):
            delay = .8 + i * .2 + k * .08
            ty = y - 16 if k % 2 == 0 else y + 26
            marks.append(
                f'<circle cx="{x}" cy="{y}" r="8" fill="{P["page"]}" stroke="{col}" stroke-width="4" '
                f'class="pop" style="transform-origin:{x}px {y}px;animation-delay:{delay:.2f}s"/>'
                + text(x, ty, cut(repo["name"], 14), 12, P["text"], 600, anchor="middle",
                       extra=f'stroke="{P["page"]}" stroke-width="4" stroke-linejoin="round" paint-order="stroke"'))
        # line name pill
        name = line["name"].upper()
        pw = 34 + len(name) * 6.7 + 10
        px = x0 - 8 - pw
        marks.append(
            f'<rect x="{px:.1f}" y="{yl - 12}" width="{pw:.1f}" height="24" rx="12" fill="{col}"/>'
            + icon(line["name"], px + 8, yl - 7, 14, ink(col))
            + text(px + 28, yl + 4, name, 11, ink(col), 700, MONO))
        trains.append(
            f'<g class="train" opacity="0"><set attributeName="opacity" to="1" begin="{1.5 + i * .6:.1f}s" fill="freeze"/>'
            f'<rect x="-14" y="-7" width="28" height="14" rx="5" fill="{P["train"]}" '
            f'stroke="{col}" stroke-width="3"/><animateMotion dur="{9 + i * 2}s" begin="{1.5 + i * .6:.1f}s" '
            f'repeatCount="indefinite" rotate="auto"><mpath href="#l{i}" xlink:href="#l{i}"/></animateMotion></g>')
    handle = "@" + user["login"]
    hw = len(handle) * 8.4 + 26
    hub = (
        f'<circle cx="{hx}" cy="{hy}" r="32" fill="none" stroke="{P["kicker"]}" stroke-width="2" class="hubp" '
        f'style="transform-origin:{hx}px {hy}px"/>'
        f'<circle cx="{hx}" cy="{hy}" r="26" fill="{P["page"]}" stroke="{P["text"]}" stroke-width="5"/>'
        f'<defs><clipPath id="hub"><circle cx="{hx}" cy="{hy}" r="23.5"/></clipPath></defs>'
        f'<image href="{user["avatar"]}" x="{hx - 23.5}" y="{hy - 23.5}" width="47" height="47" '
        f'preserveAspectRatio="xMidYMid slice" clip-path="url(#hub)"/>'
        f'<rect x="{hx - hw / 2:.1f}" y="{hy + 34}" width="{hw:.1f}" height="20" rx="10" fill="{P["page"]}"/>'
        + text(hx, hy + 48, handle, 14, P["text"], 800, anchor="middle"))
    head = (text(0, 26, "COMMIT METRO", 12, P["kicker"], 400, MONO, extra='letter-spacing=".14em"')
            + text(0, 56, "Every line is a language, every stop a project", 26, P["text"], 700,
                   extra='letter-spacing="-.02em"'))
    label = f"{user['name']}'s repositories as a metro map, one line per language"
    return svg(880, 500, head + "".join(paths) + "".join(marks) + "".join(trains) + hub, label, css)


def interchange(user, latest, accent, P):
    w, h = 880, 196
    tagline = f"{ROLE} Working on {latest} right now." if latest else ROLE
    meta = [user.get("location"), user.get("company"),
            f"{user['followers']['totalCount']} followers",
            f"{user['repositories']['totalCount']} repositories"]
    body = (
        text(36, 96, user["name"], 28, P["text"], 800, extra='letter-spacing="-.02em"')
        + text(36, 126, tagline, 15, P["soft"])
        + text(36, 166, " · ".join(m for m in meta if m), 11.5, P["muted"], 400, MONO)
        + f'<defs><clipPath id="av"><circle cx="792" cy="101" r="47"/></clipPath></defs>'
        f'<circle cx="792" cy="101" r="52" fill="{P["text"]}" stroke="{accent}" stroke-width="5"/>'
        f'<image href="{user["avatar"]}" x="745" y="54" width="94" height="94" '
        f'preserveAspectRatio="xMidYMid slice" clip-path="url(#av)"/>')
    return card(w, h, accent, "Interchange", body, f"{user['name']}. {tagline}", P)


def station(n, repo, P):
    w, h = 434, 176
    lang = repo["primaryLanguage"] or {"name": "Other", "color": "#6e7781"}
    col = lang["color"] or "#6e7781"
    desc = wrap(repo["description"] or "No description yet.", 52, 2)
    body = (
        f'<circle cx="394" cy="38" r="17" fill="{col}"/>' + icon(lang["name"], 385, 29, 18, ink(col))
        + text(28, 82, cut(repo["name"], 36), 15.5, P["text"], 700, MONO)
        + "".join(text(28, 106 + 17 * i, line, 12.5, P["soft"]) for i, line in enumerate(desc))
        + f'<svg x="28" y="143" width="11" height="11" viewBox="0 0 16 16"><path d="{STAR}" fill="{P["muted"]}"/></svg>'
        + text(44, 153, repo["stargazerCount"], 11, P["muted"], 700, MONO)
        + f'<svg x="68" y="143" width="11" height="11" viewBox="0 0 16 16"><path d="{FORK}" fill="{P["muted"]}"/></svg>'
        + text(84, 153, repo["forkCount"], 11, P["muted"], 700, MONO)
        + f'<rect x="108" y="141" width="15" height="15" rx="4" fill="{col}"/>'
        + icon(lang["name"], 110.5, 143.5, 10, ink(col))
        + text(129, 153, lang["name"], 11, P["muted"], 700, MONO))
    label = f"{repo['name']}: {repo['description'] or 'repository'}"
    return card(w, h, col, f"Station {n:02d}", body, label, P)


def lines_card(langs, accent, P):
    w, row = 880, 30
    h = 74 + row * len(langs) + 14
    css = ".bar{transform-origin:0 0;animation:grow 1s ease-out both}@keyframes grow{from{transform:scaleX(0)}}"
    body = ""
    for i, (name, color, pct) in enumerate(langs):
        y = 74 + row * i
        body += (
            f'<rect x="28" y="{y}" width="18" height="18" rx="4" fill="{color}"/>'
            + icon(name, 31, y + 3, 12, ink(color))
            + text(56, y + 13.5, name, 13, P["text"], 700)
            + f'<rect x="230" y="{y + 4}" width="560" height="10" rx="5" fill="{P["track"]}"/>'
            f'<g transform="translate(230 {y + 4})"><rect class="bar" width="{max(10, 560 * pct / langs[0][2]):.1f}" '
            f'height="10" rx="5" fill="{color}" style="animation-delay:{i * .1:.1f}s"/></g>'
            + text(852, y + 13.5, f"{pct:.0f}%", 11.5, P["muted"], 700, MONO, "end"))
    label = "Languages: " + ", ".join(f"{n} {p:.0f}%" for n, _, p in langs)
    return card(w, h, accent, "Lines", body, label, P, css)


def timetable(days, total, accent, P):
    w, h, weeks = 880, 208, 26
    recent = days[-(weeks * 7 + dt.date.fromisoformat(days[-1]["date"]).isoweekday() % 7 + 1):]
    peak = max((d["contributionCount"] for d in recent), default=0) or 1
    cells = ""
    first = dt.date.fromisoformat(recent[0]["date"])
    offset = first.isoweekday() % 7           # Sunday on the top row
    for i, d in enumerate(recent):
        col, r = divmod(i + offset, 7)
        n = d["contributionCount"]
        level = 0 if n == 0 else min(4, 1 + int(3 * n / peak))
        fill = P["empty"] if level == 0 else accent
        op = "" if level == 0 else f' fill-opacity="{(.35, .55, .8, 1)[level - 1]}"'
        cells += (f'<rect x="{28 + col * 16}" y="{66 + r * 16}" width="13" height="13" rx="3" '
                  f'fill="{fill}"{op}><title>{d["date"]}: {n}</title></rect>')
    # streaks: today doesn't break a run until the day is over
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    current = 0
    for c in reversed(tail):
        if not c:
            break
        current += 1
    stats = [("CURRENT RUN", f"{current} day{'s' * (current != 1)}"),
             ("LONGEST SERVICE", f"{longest} day{'s' * (longest != 1)}"),
             ("TRIPS THIS YEAR", f"{total:,}")]
    body = cells
    for i, (k, v) in enumerate(stats):
        y = 78 + i * 46
        body += (text(520, y, k, 10.5, P["muted"], 400, MONO, extra='letter-spacing=".12em"')
                 + text(520, y + 23, v, 20, P["text"], 800))
    label = f"{total} contributions in the last year, longest streak {longest} days"
    return card(w, h, accent, f"Timetable · {weeks} weeks", body, label, P)


# ------------------------------------------------------------------- readme
START, END = "<!--metro:start-->", "<!--metro:end-->"


def pic(name, alt, width="100%"):
    return (f'<picture><source media="(prefers-color-scheme: light)" srcset="assets/{name}-light.svg">'
            f'<img src="assets/{name}-dark.svg" width="{width}" alt="{escape(alt, {chr(34): "&quot;"})}"></picture>')


def readme_block(user, stations):
    rows = []
    for i in range(0, len(stations), 2):
        rows.append("\n".join(
            f'<a href="{r["url"]}">{pic(f"station-{i + k + 1}", r["name"], "49.5%")}</a>'
            for k, r in enumerate(stations[i:i + 2])))
    return "\n\n".join([
        START,
        pic("metro", f"{user['name']}'s repositories as a metro map, one line per language"),
        "<sub>Every line is a language I write; every stop is one of my projects.</sub>",
        pic("interchange", user["name"]),
        "<p>\n" + "\n<br>\n".join(rows) + "\n</p>",
        pic("lines", "Languages by share of code"),
        pic("timetable", "Contribution timetable for the last 26 weeks"),
        END])


DEFAULT_README = """{block}

### Now boarding

- Data Science & Analytics student at Seneca Polytechnic, Toronto
- Building data pipelines, analytics marts and ML projects end to end
- Looking for a Summer 2027 co-op / internship

[GitHub](https://github.com/{login})

<sub>Commit Metro · redrawn every day by <a href="scripts/generate.py">a small script</a> in this repo</sub>
"""


def main():
    user = fetch()
    repos = [r for r in user["repositories"]["nodes"]
             if not r["isFork"] and not r["isArchived"] and r["name"] not in SKIP]

    # metro lines: the four languages with the most repos
    by_lang = {}
    for r in repos:
        if r["primaryLanguage"]:
            by_lang.setdefault(r["primaryLanguage"]["name"], []).append(r)
    top = sorted(by_lang.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:4]
    lines = [dict(name=k, color=v[0]["primaryLanguage"]["color"] or "#6e7781", repos=v) for k, v in top]

    # language share by bytes
    size, color = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            size[n] = size.get(n, 0) + e["size"]
            color[n] = e["node"]["color"] or "#6e7781"
    total = sum(size.values()) or 1
    langs = [(n, color[n], 100 * s / total) for n, s in sorted(size.items(), key=lambda kv: -kv[1])[:5]]
    accent = langs[0][1] if langs else "#3572A5"

    names = FEATURED or [n["name"] for n in user["pinnedItems"]["nodes"]]
    lookup = {r["name"]: r for r in repos}
    stations = [lookup[n] for n in names if n in lookup and (FEATURED or lookup[n]["description"])]
    stations = (stations or repos)[:MAX_STATIONS]

    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    latest = repos[0]["name"] if repos else ""

    ASSETS.mkdir(exist_ok=True)
    for old in ASSETS.glob("station-*.svg"):
        old.unlink()
    for mode, P in THEMES.items():
        out = {"metro": metro(user, lines, P),
               "interchange": interchange(user, latest, accent, P),
               "lines": lines_card(langs, accent, P),
               "timetable": timetable(days, cal["totalContributions"], accent, P)}
        for i, r in enumerate(stations, 1):
            out[f"station-{i}"] = station(i, r, P)
        for name, content in out.items():
            (ASSETS / f"{name}-{mode}.svg").write_text(content, encoding="utf-8")

    block = readme_block(user, stations)
    path = ROOT / "README.md"
    if path.exists() and START in path.read_text() and END in path.read_text():
        old = path.read_text()
        new = old[: old.index(START)] + block + old[old.index(END) + len(END):]
    else:
        new = DEFAULT_README.format(block=block, login=user["login"])
    path.write_text(new, encoding="utf-8")
    print(f"wrote {len(list(ASSETS.glob('*.svg')))} cards and README.md")


if __name__ == "__main__":
    main()
