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
        teams = [{"flag": TEAMS[c][1], "nl": TEAMS[c][0], "code": c,
                  "pts": tbl[c]["pts"], "gd": tbl[c]["gf"] - tbl[c]["ga"]} for c in order]
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
# Renderen (identiek format aan de placeholders in template.html)
# ----------------------------------------------------------------------------
def render_group_cards(groups):
    out = []
    for g in sorted(groups):
        gr = groups[g]
        has_be = any(t["code"] == "BEL" for t in gr["teams"])
        rows = "".join(
            f'<li class="q{i}{" be" if t["code"]=="BEL" else ""}">'
            f'<span class="pos">{i}</span><span class="fl">{t["flag"]}</span>'
            f'<span class="nm">{t["nl"]}</span><span class="pts">{t["pts"]}</span>'
            f'<span class="gd">{gd_str(t["gd"])}</span></li>'
            for i, t in enumerate(gr["teams"], 1))
        out.append(
            f'<div class="grp{" has-be" if has_be else ""}"><div class="gh">'
            f'<span class="glet">{g}</span><span class="gname">Groep {g}</span>'
            f'<span class="played">{gr["played"]}/3</span></div><ol>{rows}</ol></div>')
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
    html = open(TEMPLATE, encoding="utf-8").read()
    html = html.replace("{{DATE}}",     date_label())
    html = html.replace("{{GROUPS}}",   render_group_cards(groups))
    html = html.replace("{{POP_DATA}}", render_pop_data(groups))
    html = html.replace("{{FX_DATA}}",  render_fx_data(groups))
    open(OUTPUT, "w", encoding="utf-8").write(html)
    tot = sum(len(g["matches"]) for g in groups.values())
    print(f"{OUTPUT} geschreven — {len(groups)} groepen, {tot} groepsduels.")

if __name__ == "__main__":
    main()
