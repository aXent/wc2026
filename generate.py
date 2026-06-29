#!/usr/bin/env python3
"""
generate.py — bouwt de WK 2026 cheat sheet (index.html) uit TheSportsDB-data.

Aanpak:
  1. Eén API-call: eventsseason.php?id=4429 (alle WK-wedstrijden + scores + tijden).
  2. De groepsindeling ligt vast sinds de loting, dus die staat hardcoded (GROUPS).
     We koppelen elke wedstrijd aan een groep als BEIDE teams in dezelfde groep zitten,
     en nemen per groep de eerste 6 zulke duels (= de groepsfase; knockout valt af).
  3. De standen rekenen we zelf uit die duels (3/1/0 punten, doelsaldo) — de tabel-
     endpoint van TheSportsDB werkt op de gratis tier namelijk alleen voor
     'featured' competities.
  4. We renderen de drie dynamische blokken en vullen template.html -> index.html.

Gebruik:
    export TSDB_KEY=...          # premium key; gratis key 123 is te beperkt
    python generate.py

Afhankelijkheden: alleen de Python-standaardbibliotheek.
TheSportsDB gratis tier geeft maar 15 seizoensevents terug; voor het volledige
WK-schema is een premium key nodig.
"""

import json, os, sys, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
KEY      = os.environ.get("TSDB_KEY") or "123"      # '123' = gratis testkey
LEAGUE   = "4429"                                    # FIFA World Cup
SEASONS  = ["2026", "2026-2027"]                     # meeste events wint
BASE     = f"https://www.thesportsdb.com/api/v1/json/{KEY}"
TZ       = ZoneInfo("Europe/Brussels")              # Belgische tijd (CEST)
TEMPLATE = "template.html"
OUTPUT   = "index.html"
CACHE    = "data.json"                               # tijdlijn-cache (doelpunten/kaarten)
THIRDS   = "thirds_table.json"                       # officiële toewijzing beste nrs. 3 (Annex C, 495 combinaties)
WEEKDAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
MONTHS   = ["januari","februari","maart","april","mei","juni",
            "juli","augustus","september","oktober","november","december"]

# code -> (Nederlandse naam, vlag, [Engelse namen zoals TheSportsDB ze kan geven])
TEAMS = {
 "MEX":("Mexico","🇲🇽",["Mexico"]),                 "RSA":("Zuid-Afrika","🇿🇦",["South Africa"]),
 "KOR":("Zuid-Korea","🇰🇷",["South Korea","Korea Republic"]), "CZE":("Tsjechië","🇨🇿",["Czechia","Czech Republic"]),
 "CAN":("Canada","🇨🇦",["Canada"]),                 "SUI":("Zwitserland","🇨🇭",["Switzerland"]),
 "BIH":("Bosnië-Herz.","🇧🇦",["Bosnia and Herzegovina","Bosnia-Herzegovina"]), "QAT":("Qatar","🇶🇦",["Qatar"]),
 "BRA":("Brazilië","🇧🇷",["Brazil"]),               "MAR":("Marokko","🇲🇦",["Morocco"]),
 "SCO":("Schotland","🏴󠁧󠁢󠁳󠁣󠁴󠁿",["Scotland"]),         "HAI":("Haïti","🇭🇹",["Haiti"]),
 "USA":("Ver. Staten","🇺🇸",["United States","USA"]), "AUS":("Australië","🇦🇺",["Australia"]),
 "PAR":("Paraguay","🇵🇾",["Paraguay"]),             "TUR":("Turkije","🇹🇷",["Turkey","Türkiye","Turkiye"]),
 "GER":("Duitsland","🇩🇪",["Germany"]),             "ECU":("Ecuador","🇪🇨",["Ecuador"]),
 "CIV":("Ivoorkust","🇨🇮",["Ivory Coast","Cote d'Ivoire","Côte d'Ivoire"]), "CUW":("Curaçao","🇨🇼",["Curacao","Curaçao"]),
 "NED":("Nederland","🇳🇱",["Netherlands","Holland"]),"JPN":("Japan","🇯🇵",["Japan"]),
 "SWE":("Zweden","🇸🇪",["Sweden"]),                 "TUN":("Tunesië","🇹🇳",["Tunisia"]),
 "BEL":("België","🇧🇪",["Belgium"]),                "EGY":("Egypte","🇪🇬",["Egypt"]),
 "IRN":("Iran","🇮🇷",["Iran","Iran IR"]),           "NZL":("Nieuw-Zeeland","🇳🇿",["New Zealand"]),
 "ESP":("Spanje","🇪🇸",["Spain"]),                  "URU":("Uruguay","🇺🇾",["Uruguay"]),
 "CPV":("Kaapverdië","🇨🇻",["Cape Verde","Cabo Verde"]), "KSA":("Saoedi-Arabië","🇸🇦",["Saudi Arabia"]),
 "FRA":("Frankrijk","🇫🇷",["France"]),              "SEN":("Senegal","🇸🇳",["Senegal"]),
 "NOR":("Noorwegen","🇳🇴",["Norway"]),              "IRQ":("Irak","🇮🇶",["Iraq"]),
 "ARG":("Argentinië","🇦🇷",["Argentina"]),          "AUT":("Oostenrijk","🇦🇹",["Austria"]),
 "ALG":("Algerije","🇩🇿",["Algeria"]),              "JOR":("Jordanië","🇯🇴",["Jordan"]),
 "POR":("Portugal","🇵🇹",["Portugal"]),             "COL":("Colombia","🇨🇴",["Colombia"]),
 "UZB":("Oezbekistan","🇺🇿",["Uzbekistan"]),        "COD":("DR Congo","🇨🇩",["DR Congo","Congo DR","Democratic Republic of Congo"]),
 "ENG":("Engeland","🏴󠁧󠁢󠁥󠁮󠁧󠁿",["England"]),           "CRO":("Kroatië","🇭🇷",["Croatia"]),
 "GHA":("Ghana","🇬🇭",["Ghana"]),                   "PAN":("Panama","🇵🇦",["Panama"]),
}
# Loting (vast). Volgorde binnen een groep maakt niet uit; standen worden berekend.
GROUPS = {
 "A":["MEX","RSA","KOR","CZE"], "B":["CAN","SUI","BIH","QAT"], "C":["BRA","MAR","SCO","HAI"],
 "D":["USA","AUS","PAR","TUR"], "E":["GER","CIV","ECU","CUW"], "F":["NED","JPN","SWE","TUN"],
 "G":["BEL","EGY","IRN","NZL"], "H":["ESP","URU","CPV","KSA"], "I":["FRA","SEN","NOR","IRQ"],
 "J":["ARG","AUT","ALG","JOR"], "K":["POR","COL","UZB","COD"], "L":["ENG","CRO","GHA","PAN"],
}
EXPECTED_GROUP_MATCHES = sum(len(codes) * (len(codes) - 1) // 2 for codes in GROUPS.values())

# Snelle opzoektabel: genormaliseerde Engelse naam -> code
NAME2CODE = {}
for code, (_, _, aliases) in TEAMS.items():
    for a in aliases:
        NAME2CODE[a.strip().lower()] = code

def code_of(name):
    return NAME2CODE.get((name or "").strip().lower())

def group_of(code):
    for letter, codes in GROUPS.items():
        if code in codes:
            return letter
    return None

# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------
def fetch_events():
    """Probeer bekende seizoenslabels; gebruik de lijst met de meeste events."""
    best_season, best_events = None, []
    for season in SEASONS:
        url = f"{BASE}/eventsseason.php?id={LEAGUE}&s={season}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"API-fout {e.code} bij {url}")
        events = data.get("events") or []
        print(f"Seizoen '{season}': {len(events)} events opgehaald.")
        if len(events) > len(best_events):
            best_season, best_events = season, events
    if best_events:
        print(f"Seizoen '{best_season}' geselecteerd ({len(best_events)} events).")
        return best_season, best_events
    sys.exit("Geen events gevonden — controleer LEAGUE-id en SEASONS.")

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def gd_str(n):
    return f"+{n}" if n > 0 else (f"−{abs(n)}" if n < 0 else "0")   # − = U+2212

def when_label(ev):
    """('do 25/6', '03:00') in Belgische tijd uit strTimestamp (UTC)."""
    ts = ev.get("strTimestamp")
    if ts:
        dt = datetime.fromisoformat(ts.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    else:  # fallback: dateEvent + strTime
        t = (ev.get("strTime") or "00:00:00")[:8]
        dt = datetime.fromisoformat(f'{ev["dateEvent"]}T{t}').replace(tzinfo=ZoneInfo("UTC"))
    dt = dt.astimezone(TZ)
    return f"{WEEKDAYS[dt.weekday()]} {dt.day}/{dt.month}", dt.strftime("%H:%M"), dt

def played(ev):
    return ev.get("intHomeScore") not in (None, "") and ev.get("intAwayScore") not in (None, "")

# ----------------------------------------------------------------------------
# Data verwerken
# ----------------------------------------------------------------------------
def build_groups(events):
    # 1) per groep alle eigen duels verzamelen (beide teams in dezelfde groep)
    raw = {g: [] for g in GROUPS}
    for ev in events:
        hc, ac = code_of(ev.get("strHomeTeam")), code_of(ev.get("strAwayTeam"))
        if not hc or not ac:
            if hc != ac:  # alleen waarschuwen als het een WK-team lijkt
                miss = ev.get("strHomeTeam") if not hc else ev.get("strAwayTeam")
                if miss:
                    print(f"WAARSCHUWING: onbekend team '{miss}' — vul aan in TEAMS", file=sys.stderr)
            continue
        g = group_of(hc)
        if g and group_of(ac) == g:                       # zelfde groep = groepsduel
            d, t, dt = when_label(ev)
            raw[g].append({"dt": dt, "d": d, "t": t, "hc": hc, "ac": ac,
                           "hs": ev.get("intHomeScore"), "as": ev.get("intAwayScore"),
                           "fin": played(ev)})

    groups = {}
    for g, codes in GROUPS.items():
        ms = sorted(raw[g], key=lambda m: m["dt"])[:6]     # eerste 6 = groepsfase
        # 2) standen berekenen
        tbl = {c: {"pts": 0, "gf": 0, "ga": 0, "pl": 0} for c in codes}
        for m in ms:
            if not m["fin"]:
                continue
            hs, as_ = int(m["hs"]), int(m["as"])
            for c, gf, ga in ((m["hc"], hs, as_), (m["ac"], as_, hs)):
                tbl[c]["pl"] += 1; tbl[c]["gf"] += gf; tbl[c]["ga"] += ga
                tbl[c]["pts"] += 3 if gf > ga else (1 if gf == ga else 0)
        order = sorted(codes, key=lambda c: (tbl[c]["pts"],
                       tbl[c]["gf"] - tbl[c]["ga"], tbl[c]["gf"]), reverse=True)
        teams = [{"flag": TEAMS[c][1], "nl": TEAMS[c][0], "code": c, "pts": tbl[c]["pts"],
                  "gd": tbl[c]["gf"] - tbl[c]["ga"], "gf": tbl[c]["gf"]} for c in order]
        # 3) wedstrijdregels voor de accordion
        matches = [{
            "d": m["d"], "t": m["t"],
            "score": f'{int(m["hs"])}–{int(m["as"])}' if m["fin"] else None,
            "h": [TEAMS[m["hc"]][1], TEAMS[m["hc"]][0]],
            "a": [TEAMS[m["ac"]][1], TEAMS[m["ac"]][0]],
            "be": "BEL" in (m["hc"], m["ac"]), "nl": "NED" in (m["hc"], m["ac"]),
        } for m in ms]
        groups[g] = {"played": max((t["pl"] for t in tbl.values()), default=0),
                     "teams": teams, "matches": matches}
    return groups

def validate_group_schedule(groups, event_count, season):
    total = sum(len(gr["matches"]) for gr in groups.values())
    incomplete = {
        g: len(groups[g]["matches"])
        for g in sorted(groups)
        if len(groups[g]["matches"]) < 6
    }
    if not incomplete and total == EXPECTED_GROUP_MATCHES:
        return

    detail = ", ".join(f"{g}:{n}/6" for g, n in incomplete.items())
    hint = ("De gratis TheSportsDB key '123' geeft maar 15 seizoensevents terug; "
            "zet TSDB_KEY op een premium key in GitHub Secrets.")
    if KEY != "123":
        hint = "Controleer of TSDB_KEY een premium key is en toegang heeft tot de volledige season endpoint."
    sys.exit(
        f"Onvolledig WK-schema: {total}/{EXPECTED_GROUP_MATCHES} groepsduels "
        f"gevonden uit {event_count} events voor seizoen '{season}'. "
        f"Ontbrekend: {detail}. {hint}"
    )

# ----------------------------------------------------------------------------
# Tijdlijn-cache (doelpunten + kaarten per gespeeld duel)
# ----------------------------------------------------------------------------
# Een afgelopen wedstrijd verandert niet meer, dus halen we de tijdlijn één keer
# op (lookuptimeline.php) en bewaren we 'm in data.json. Dat bestand wordt mee
# gecommit, zodat de cache de (efemere) Actions-runner overleeft. Per run kost
# dit dus alleen API-calls voor pas afgelopen duels, niet voor alles.
def fetch_timeline(eid):
    """Doelpunten + kaarten voor één wedstrijd; None bij API-fout (→ later opnieuw)."""
    url = f"{BASE}/lookuptimeline.php?id={eid}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            rows = json.load(r).get("timeline") or []
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"WAARSCHUWING: tijdlijn {eid} faalde ({e}) — later opnieuw", file=sys.stderr)
        return None
    out = []
    for r in rows:
        typ = r.get("strTimeline")
        if typ not in ("Goal", "Card"):
            continue
        det = r.get("strTimelineDetail") or ""
        if typ == "Goal" and det == "Missed Penalty":
            continue            # TheSportsDB tagt dit als 'Goal', maar het is géén doelpunt
        out.append({"t": int(r.get("intTime") or 0),
                    "k": "G" if typ == "Goal" else "C",
                    "d": det,
                    "p": r.get("strPlayer") or "",
                    "a": r.get("strAssist") or "",
                    "h": r.get("strHome") == "Yes"})
    out.sort(key=lambda x: x["t"])
    return out

SCHEMA = 2          # verhoog dit om de tijdlijn-cache geforceerd opnieuw op te bouwen

def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            c = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        c = {}
    if c.get("schema") != SCHEMA:                       # ander schema → cache verwerpen
        c = {"schema": SCHEMA, "events": {}}
    c.setdefault("events", {})
    return c

def tl_complete(entry, score):
    """True als de opgeslagen tijdlijn minstens zoveel doelpunten bevat als de uitslag.
    TheSportsDB zet score+FT vaak vóór de tijdlijn klaar is; dan staat er een lege/
    onvolledige tijdlijn in de cache die anders nooit meer ververst zou worden."""
    try:
        total = sum(int(x) for x in score.split("-"))
    except ValueError:
        return True
    goals = sum(1 for r in (entry.get("tl") or []) if r.get("k") == "G")
    return goals >= total

def update_cache(events, cache):
    """Vul de cache aan voor gespeelde duels die nieuw/niet-definitief/gewijzigd/onvolledig zijn."""
    evmap = cache["events"]
    fetched = 0
    for ev in events:
        eid = ev.get("idEvent")
        if not eid or not played(ev):
            continue
        score  = f'{ev.get("intHomeScore")}-{ev.get("intAwayScore")}'
        status = ev.get("strStatus") or ""
        old = evmap.get(eid)
        if (old and old.get("status") == "FT" and old.get("score") == score
                and "tl" in old and tl_complete(old, score)):
            continue                                   # definitief, ongewijzigd én volledig → skip
        tl = fetch_timeline(eid)
        if tl is None:                                 # API-fout → niet cachen, volgende run
            continue
        evmap[eid] = {"status": status, "score": score, "tl": tl}
        fetched += 1
    if fetched:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Tijdlijn-cache: {fetched} duel(s) opgehaald, {len(evmap)} in cache.")
    return cache

def render_tl_data(events, cache):
    """{'vlag_vlag_d/m': [ {t,k,d,p,a,h}, ... ]} — zelfde sleutel als de client berekent."""
    evmap = cache["events"]
    out = {}
    for ev in events:
        entry = evmap.get(ev.get("idEvent"))
        if not entry or not entry.get("tl"):
            continue
        hc, ac = code_of(ev.get("strHomeTeam")), code_of(ev.get("strAwayTeam"))
        if not hc or not ac:
            continue
        _, _, dt = when_label(ev)
        key = f"{TEAMS[hc][1]}_{TEAMS[ac][1]}_{dt.day}/{dt.month}"
        out[key] = entry["tl"]
    return json.dumps(out, ensure_ascii=False)

# ----------------------------------------------------------------------------
# Statistieken (topscorers/assists/kaarten + 'WK in cijfers')
# ----------------------------------------------------------------------------
def compute_stats(events, cache):
    """Aggregeer leaderboards + kerncijfers uit scores (events) en tijdlijnen (cache)."""
    evmap = cache["events"]
    players = {}
    def P(name, flag):
        return players.setdefault(name, {"name": name, "flag": flag,
                                         "goals": 0, "pen": 0, "ast": 0, "y": 0, "r": 0})
    pen = reds = yellows = total = mp = clean = 0
    big = most = fastest = None
    hat = []
    for ev in events:
        hc, ac = code_of(ev.get("strHomeTeam")), code_of(ev.get("strAwayTeam"))
        if not hc or not ac:
            continue
        if played(ev):                                  # cijfers uit de uitslag
            hs, as_ = int(ev["intHomeScore"]), int(ev["intAwayScore"])
            total += hs + as_; mp += 1
            clean += (as_ == 0) + (hs == 0)
            diff, summ = abs(hs - as_), hs + as_
            if big is None or (diff, summ) > (big["diff"], big["sum"]):
                big = {"diff": diff, "sum": summ, "hc": hc, "ac": ac, "score": f"{hs}–{as_}"}
            if most is None or summ > most["sum"]:
                most = {"sum": summ, "hc": hc, "ac": ac, "score": f"{hs}–{as_}"}
        entry = evmap.get(ev.get("idEvent"))             # leaderboards uit de tijdlijn
        if not entry:
            continue
        mg = {}
        for r in entry.get("tl") or []:
            if r["k"] == "G" and r["d"] == "Missed Penalty":
                continue
            flag = TEAMS[hc if r["h"] else ac][1]
            if r["k"] == "G":
                if r["d"] != "Own Goal":
                    pd = P(r["p"], flag); pd["goals"] += 1
                    if r["d"] == "Penalty":
                        pd["pen"] += 1; pen += 1
                    mg[r["p"]] = mg.get(r["p"], 0) + 1
                    if mg[r["p"]] == 3:
                        hat.append((r["p"], flag))
                    if fastest is None or r["t"] < fastest["t"]:
                        fastest = {"t": r["t"], "name": r["p"], "home": TEAMS[hc][0], "away": TEAMS[ac][0]}
                    if r["a"]:
                        P(r["a"], flag)["ast"] += 1
            else:                                        # kaart
                pd = P(r["p"], flag)
                if r["d"] == "Red Card":
                    pd["r"] += 1; reds += 1
                else:
                    pd["y"] += 1; yellows += 1
    al = list(players.values())
    scorers = sorted((p for p in al if p["goals"]), key=lambda p: (-p["goals"], -p["ast"], p["name"]))[:8]
    assists = sorted((p for p in al if p["ast"]),   key=lambda p: (-p["ast"], -p["goals"], p["name"]))[:8]
    cards   = sorted((p for p in al if p["r"] or p["y"]), key=lambda p: (-p["r"], -p["y"], p["name"]))[:8]
    return {"total": total, "matches": mp, "clean": clean, "pen": pen, "reds": reds,
            "yellows": yellows, "hat": hat, "fastest": fastest, "big": big, "most": most,
            "scorers": scorers, "assists": assists, "cards": cards}

def render_stats(events, cache):
    s = compute_stats(events, cache)
    if not s["matches"]:
        return ""                                        # nog niets gespeeld
    f2n = {TEAMS[c][1]: TEAMS[c][0] for c in TEAMS}
    be, nl = TEAMS["BEL"][1], TEAMS["NED"][1]
    def acc(flag):
        return " be" if flag == be else (" nl" if flag == nl else "")
    avg = f'{s["total"] / s["matches"]:.2f}'.replace(".", ",")
    def tile(lab, num, det, cls=""):
        return (f'<div class="stat {cls}"><span class="lab">{lab}</span>'
                f'<span class="num">{num}</span><span class="det">{det}</span></div>')
    big, most, fast = s["big"], s["most"], s["fastest"]
    win = (f'<div class="stat"><span class="lab">🔥 Grootste zege</span>'
           f'<span class="winline"><span class="fl">{TEAMS[big["hc"]][1]}</span>'
           f'<span class="sc">{big["score"]}</span><span class="fl">{TEAMS[big["ac"]][1]}</span></span>'
           f'<span class="det">{TEAMS[big["hc"]][0]} – {TEAMS[big["ac"]][0]}</span></div>')
    hatnames = " · ".join(f'{flag} {name.split()[-1]}' for name, flag in s["hat"]) or "nog geen"
    grid = (
        f'<div class="stat hero"><span class="lab">⚽ Totaal doelpunten</span>'
        f'<span class="num">{s["total"]}</span>'
        f'<span class="det">in {s["matches"]} wedstrijden · <b>gemiddeld {avg} per match</b></span></div>'
        + win
        + tile("📈 Meeste goals / match", most["sum"], f'{TEAMS[most["hc"]][0]} {most["score"]} {TEAMS[most["ac"]][0]}')
        + tile("🧤 Clean sheets", s["clean"], 'keer "de nul" gehouden')
        + tile("🎯 Penalty’s benut", s["pen"], "rake strafschoppen")
        + tile("🟥 Rode kaarten", s["reds"], f'+ {s["yellows"]} gele kaarten')
        + tile("🎩 Hat-tricks", len(s["hat"]), hatnames)
        + tile("⏱️ Snelste goal", (str(fast["t"]) + "'") if fast else "—",
               f'{fast["name"]} · {fast["home"]}–{fast["away"]}' if fast else "—")
    )
    def row(p, i, val, show_pen=False):
        rcls = f" r{i}" if i <= 3 else ""
        pn = f' · {p["pen"]} pen.' if show_pen and p["pen"] else ""
        return (f'<li class="lbrow{rcls}{acc(p["flag"])}"><span class="rank">{i}</span>'
                f'<span class="fl">{p["flag"]}</span><span class="who">'
                f'<span class="nm">{p["name"]}</span><span class="tm">{f2n.get(p["flag"], "")}{pn}</span>'
                f'</span>{val}</li>')
    def board(icon, title, sub, lst, valfn, show_pen=False):
        rows = "".join(row(p, i, valfn(p), show_pen) for i, p in enumerate(lst, 1))
        return (f'<div class="board"><div class="bh"><span class="bicon">{icon}</span>'
                f'<h3>{title}</h3><span class="bsub">{sub}</span></div><ol>{rows}</ol></div>')
    boards = (
        board("👟", "Gouden Schoen", "Goals", s["scorers"], lambda p: f'<span class="val">{p["goals"]}</span>', show_pen=True)
        + board("🅰️", "Assists", "Beslissend", s["assists"], lambda p: f'<span class="val">{p["ast"]}</span>')
        + board("🟨", "Kaarten", "Discipline", s["cards"], lambda p: f'<span class="cards">{"🟥" * p["r"]}{"🟨" * p["y"]}</span>')
    )
    return (f'<div class="statgrid">{grid}</div>'
            f'<div class="subhead">Topscorers &amp; kaarten</div>'
            f'<div class="boards">{boards}</div>')

# ----------------------------------------------------------------------------
# Knock-out: vakjes invullen vanuit de groepsstand
# ----------------------------------------------------------------------------
def load_thirds_table():
    try:
        with open(THIRDS, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Knock-outschema: welke twee vakjes voeden elk duel (#73..#104). Bron = template KO.
KO_FIXTURES = {
 73:("2A","2B"), 74:("1E","3"),  75:("1F","2C"), 76:("1C","2F"),
 77:("1I","3"),  78:("2E","2I"), 79:("1A","3"),  80:("1L","3"),
 81:("1D","3"),  82:("1G","3"),  83:("2K","2L"), 84:("1H","2J"),
 85:("1B","3"),  86:("1J","2H"), 87:("1K","3"),  88:("2D","2G"),
 89:("W74","W77"), 90:("W73","W75"), 91:("W76","W78"), 92:("W79","W80"),
 93:("W83","W84"), 94:("W81","W82"), 95:("W86","W88"), 96:("W85","W87"),
 97:("W89","W90"), 98:("W93","W94"), 99:("W91","W92"), 100:("W95","W96"),
 101:("W97","W98"), 102:("W99","W100"), 103:("V101","V102"), 104:("W101","W102"),
}
KO_ROUNDS = [list(range(73, 89)), [89,90,91,92,93,94,95,96], [97,98,99,100], [101,102], [103,104]]

def fetch_knockout(events):
    """Knock-outduels verzamelen uit de seizoensfeed én eventsround, en alleen de
    echte knock-outs houden: beide teams bekend én uit VERSCHILLENDE groepen
    (groepsduels zitten altijd binnen één groep). Zo maakt het niet uit of de feed
    de knock-outs al bevat, en vermijden we ronde-nummercollisies (bv. 'ronde 2' =
    zowel groepsspeeldag 2 als de finale)."""
    seen = {e.get("idEvent"): e for e in events}
    for r in (32, 16, 8, 4, 2):
        url = f"{BASE}/eventsround.php?id={LEAGUE}&r={r}&s=2026"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                for e in (json.load(resp).get("events") or []):
                    seen[e.get("idEvent")] = e
        except (urllib.error.URLError, json.JSONDecodeError):
            continue
    ko = []
    for e in seen.values():
        hc, ac = code_of(e.get("strHomeTeam")), code_of(e.get("strAwayTeam"))
        if hc and ac and group_of(hc) != group_of(ac):       # cross-group = knock-outduel
            ko.append(e)
    return ko

def render_bracket_data(groups, ko_events):
    """1X/2X (zodra groep af), beste-3e's (Annex C, zodra groepsfase af) en knock-out
    winnaars W## / verliezers V## doorzetten zodra een duel gespeeld is."""
    qual = {}
    for g, gr in groups.items():
        if gr["played"] >= 2 and len(gr["teams"]) >= 2:        # vanaf 2 speeldagen tonen
            t = gr["teams"]
            fin = gr["played"] >= 3                             # 3/3 = bevestigd; anders voorlopig (grijs)
            qual["1" + g] = [t[0]["flag"], t[0]["nl"], fin]
            qual["2" + g] = [t[1]["flag"], t[1]["nl"], fin]
    third, third_map = {}, {}
    if len(groups) == 12 and all(gr["played"] >= 3 for gr in groups.values()):
        t3 = {g: groups[g]["teams"][2] for g in groups}        # nr. 3 van elke groep
        ranked = sorted(groups, key=lambda g: (t3[g]["pts"], t3[g]["gd"], t3[g]["gf"]), reverse=True)
        third_map = load_thirds_table().get("".join(sorted(ranked[:8])), {})  # winnaargroep -> brongroep 3e
        for w, tg in third_map.items():
            third[w] = [t3[tg]["flag"], t3[tg]["nl"], tg]

    # knock-outduels indexeren op het (ongeordende) paar teamcodes
    ko, by_set = [], {}
    for e in ko_events:
        hc, ac = code_of(e.get("strHomeTeam")), code_of(e.get("strAwayTeam"))
        if not hc or not ac:
            continue
        rec = {"id": e.get("idEvent"), "codes": {hc, ac}, "by": {},
               "ft": e.get("strStatus") == "FT" and played(e)}
        if played(e):
            rec["by"] = {hc: int(e["intHomeScore"]), ac: int(e["intAwayScore"])}
        ko.append(rec)
        by_set[frozenset((hc, ac))] = rec

    winners, losers, scores = {}, {}, {}
    def fteam(code, sib):                                       # vakjescode -> teamcode (of None)
        if len(code) == 2 and code[0] in "12" and code[1] in GROUPS:
            g, pos = code[1], int(code[0])
            if g in groups and groups[g]["played"] >= 3 and len(groups[g]["teams"]) >= pos:
                return groups[g]["teams"][pos - 1]["code"]
            return None
        if code == "3":
            if sib and sib[0] == "1" and sib[1:] in third_map:
                return groups[third_map[sib[1:]]]["teams"][2]["code"]
            return None
        if code[0] == "W" and code[1:].isdigit():
            return winners.get(int(code[1:]))
        if code[0] == "V" and code[1:].isdigit():
            return losers.get(int(code[1:]))
        return None
    def infer(th, ta, exclude):                                # gelijkspel -> wie speelt later nog = winnaar
        for r in ko:
            if r["id"] == exclude:
                continue
            if th in r["codes"] and ta not in r["codes"]:
                return th
            if ta in r["codes"] and th not in r["codes"]:
                return ta
        return None
    for _ in range(len(KO_ROUNDS) + 1):                        # propageren door alle rondes
        changed = False
        for rnd in KO_ROUNDS:
            for n in rnd:
                if n in winners:
                    continue
                h, a = KO_FIXTURES[n]
                th, ta = fteam(h, a), fteam(a, h)
                if not th or not ta:
                    continue
                rec = by_set.get(frozenset((th, ta)))
                if not rec or not rec["ft"]:
                    continue
                sh, sa = rec["by"][th], rec["by"][ta]
                scores[n] = (th, ta, sh, sa)
                w = (th if sh > sa else ta) if sh != sa else infer(th, ta, rec["id"])
                if not w:
                    continue
                winners[n] = w
                losers[n] = ta if w == th else th
                changed = True
        if not changed:
            break

    wins = {}
    for n, c in winners.items():
        wins["W" + str(n)] = [TEAMS[c][1], TEAMS[c][0]]
    for n, c in losers.items():
        wins["V" + str(n)] = [TEAMS[c][1], TEAMS[c][0]]
    koscore = {str(n): f"{sh}–{sa}" for n, (th, ta, sh, sa) in scores.items()}
    return (json.dumps(qual, ensure_ascii=False), json.dumps(third, ensure_ascii=False),
            json.dumps(wins, ensure_ascii=False), json.dumps(koscore, ensure_ascii=False))

# ----------------------------------------------------------------------------
# Renderen (identiek format aan de placeholders in template.html)
# ----------------------------------------------------------------------------
def render_group_cards(groups):
    out = []
    for g in sorted(groups):
        gr = groups[g]
        has_be = any(t["code"] == "BEL" for t in gr["teams"])
        has_nl = any(t["code"] == "NED" for t in gr["teams"])
        rows = "".join(
            f'<li class="q{i}{" be" if t["code"]=="BEL" else (" nl" if t["code"]=="NED" else "")}">'
            f'<span class="pos">{i}</span><span class="fl">{t["flag"]}</span>'
            f'<span class="nm">{t["nl"]}</span><span class="pts">{t["pts"]}</span>'
            f'<span class="gd">{gd_str(t["gd"])}</span></li>'
            for i, t in enumerate(gr["teams"], 1))
        final = gr["played"] >= 3
        cls = "grp" + (" final" if final else "") + (" has-be" if has_be else (" has-nl" if has_nl else ""))
        badge = "Eindstand" if final else f'{gr["played"]}/3'
        out.append(
            f'<div class="{cls}"><div class="gh">'
            f'<span class="glet">{g}</span><span class="gname">Groep {g}</span>'
            f'<span class="played">{badge}</span></div><ol>{rows}</ol></div>')
    return "\n".join(out)

def render_pop_data(groups):
    parts = []
    for g in sorted(groups):
        gr = groups[g]
        t = ",".join(f'["{x["flag"]}","{x["nl"]}",{x["pts"]},"{gd_str(x["gd"])}"]'
                     for x in gr["teams"])
        parts.append(f'{g}:{{p:{gr["played"]},t:[{t}]}}')
    return "{" + ",".join(parts) + "}"

def render_fx_data(groups):
    parts = []
    for g in sorted(groups):
        ms = []
        for m in groups[g]["matches"]:
            f = [f'd:"{m["d"]}"']
            f.append(f's:"{m["score"]}"' if m["score"] else f't:"{m["t"]}"')
            if m["be"]: f.append("be:true")
            if m["nl"]: f.append("nl:true")
            f.append(f'h:["{m["h"][0]}","{m["h"][1]}"]')
            f.append(f'a:["{m["a"][0]}","{m["a"][1]}"]')
            ms.append("{" + ",".join(f) + "}")
        parts.append(f'{g}:[{",".join(ms)}]')
    return "{" + ",".join(parts) + "}"

def date_label():
    n = datetime.now(TZ)
    return f"Stand t/m {n.day} {MONTHS[n.month-1]}"

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    if not os.path.exists(TEMPLATE):
        sys.exit(f"{TEMPLATE} ontbreekt (de pagina met placeholders "
                 f"{{{{GROUPS}}}}, {{{{POP_DATA}}}}, {{{{FX_DATA}}}}, {{{{DATE}}}}).")
    season, events = fetch_events()
    groups = build_groups(events)
    validate_group_schedule(groups, len(events), season)
    cache = update_cache(events, load_cache())
    html = open(TEMPLATE, encoding="utf-8").read()
    html = html.replace("{{DATE}}",     date_label())
    html = html.replace("{{GROUPS}}",   render_group_cards(groups))
    html = html.replace("{{POP_DATA}}", render_pop_data(groups))
    html = html.replace("{{FX_DATA}}",  render_fx_data(groups))
    html = html.replace("{{TL_DATA}}",  render_tl_data(events, cache))
    html = html.replace("{{STATS}}",    render_stats(events, cache))
    ko_events = fetch_knockout(events)
    qual_json, third_json, wins_json, koscore_json = render_bracket_data(groups, ko_events)
    html = html.replace("{{QUAL_DATA}}",    qual_json)
    html = html.replace("{{THIRD_DATA}}",   third_json)
    html = html.replace("{{WINNERS_DATA}}", wins_json)
    html = html.replace("{{KO_SCORES}}",    koscore_json)
    open(OUTPUT, "w", encoding="utf-8").write(html)
    tot = sum(len(g["matches"]) for g in groups.values())
    print(f"{OUTPUT} geschreven — {len(groups)} groepen, {tot} groepsduels.")

if __name__ == "__main__":
    main()
