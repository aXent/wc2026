#!/usr/bin/env python3
"""
generate.py — bouwt de WK 2026 cheat sheet (index.html) uit live data.

Werking:
  1. Haalt groepsstanden + wedstrijden op bij football-data.org (gratis tier, key nodig).
  2. Zet dat om naar de drie dynamische stukken van de pagina:
        - de 12 groepskaartjes (HTML)
        - het JS-object met de groepsstanden voor de popovers
        - het JS-object met alle wedstrijden (uitslagen + programma) voor de accordion
  3. Vult die in een template.html met placeholders en schrijft index.html weg.

De statische schil (kop, format-strook, knock-outbracket met BE/NL-indicatoren,
alle CSS en de interactieve JS) staat in template.html en verandert niet — de
groepsindeling ligt immers vast sinds de loting.

Gebruik:
    export FD_TOKEN=xxxxxxxx          # je football-data.org API-key
    python generate.py               # schrijft index.html

Afhankelijkheden: alleen de Python-standaardbibliotheek (urllib, zoneinfo).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------------------- 
# Config
# -----------------------------------------------------------------------------
API_BASE   = "https://api.football-data.org/v4"
COMP_CODE  = "WC"                       # World Cup; verifieer in je football-data.org-account
TOKEN      = os.environ.get("FD_TOKEN", "")
TZ         = ZoneInfo("Europe/Brussels")   # Belgische tijd (CEST)
TEMPLATE   = "template.html"
OUTPUT     = "index.html"

WEEKDAYS   = ["ma", "di", "wo", "do", "vr", "za", "zo"]   # ma=0 .. zo=6

# Welke teamcode hoort bij welk land (Nederlandse naam + vlag-emoji).
# Sleutel = de 3-letter code (tla) die football-data.org teruggeeft.
# Mocht een team niet gevonden worden, dan logt het script een waarschuwing
# zodat je de juiste sleutel kunt toevoegen.
TEAMS = {
    "MEX": ("Mexico", "🇲🇽"),        "RSA": ("Zuid-Afrika", "🇿🇦"),
    "KOR": ("Zuid-Korea", "🇰🇷"),    "CZE": ("Tsjechië", "🇨🇿"),
    "CAN": ("Canada", "🇨🇦"),        "SUI": ("Zwitserland", "🇨🇭"),
    "BIH": ("Bosnië-Herz.", "🇧🇦"),  "QAT": ("Qatar", "🇶🇦"),
    "BRA": ("Brazilië", "🇧🇷"),      "MAR": ("Marokko", "🇲🇦"),
    "SCO": ("Schotland", "🏴󠁧󠁢󠁳󠁣󠁴󠁿"),  "HAI": ("Haïti", "🇭🇹"),
    "USA": ("Ver. Staten", "🇺🇸"),   "AUS": ("Australië", "🇦🇺"),
    "PAR": ("Paraguay", "🇵🇾"),      "TUR": ("Turkije", "🇹🇷"),
    "GER": ("Duitsland", "🇩🇪"),     "ECU": ("Ecuador", "🇪🇨"),
    "CIV": ("Ivoorkust", "🇨🇮"),     "CUW": ("Curaçao", "🇨🇼"),
    "NED": ("Nederland", "🇳🇱"),     "JPN": ("Japan", "🇯🇵"),
    "SWE": ("Zweden", "🇸🇪"),        "TUN": ("Tunesië", "🇹🇳"),
    "BEL": ("België", "🇧🇪"),        "EGY": ("Egypte", "🇪🇬"),
    "IRN": ("Iran", "🇮🇷"),          "NZL": ("Nieuw-Zeeland", "🇳🇿"),
    "ESP": ("Spanje", "🇪🇸"),        "URU": ("Uruguay", "🇺🇾"),
    "CPV": ("Kaapverdië", "🇨🇻"),    "KSA": ("Saoedi-Arabië", "🇸🇦"),
    "FRA": ("Frankrijk", "🇫🇷"),     "SEN": ("Senegal", "🇸🇳"),
    "NOR": ("Noorwegen", "🇳🇴"),     "IRQ": ("Irak", "🇮🇶"),
    "ARG": ("Argentinië", "🇦🇷"),    "AUT": ("Oostenrijk", "🇦🇹"),
    "ALG": ("Algerije", "🇩🇿"),      "JOR": ("Jordanië", "🇯🇴"),
    "POR": ("Portugal", "🇵🇹"),      "COL": ("Colombia", "🇨🇴"),
    "UZB": ("Oezbekistan", "🇺🇿"),   "COD": ("DR Congo", "🇨🇩"),
    "ENG": ("Engeland", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),  "CRO": ("Kroatië", "🇭🇷"),
    "GHA": ("Ghana", "🇬🇭"),         "PAN": ("Panama", "🇵🇦"),
}
NL_MONTHS = None  # niet nodig; we gebruiken dd/m

# -----------------------------------------------------------------------------
# Data ophalen
# -----------------------------------------------------------------------------
def api(path):
    """Eenvoudige GET naar football-data.org met de auth-header."""
    req = urllib.request.Request(f"{API_BASE}{path}",
                                 headers={"X-Auth-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"API-fout {e.code} op {path}: {e.read().decode(errors='ignore')}")

def team_meta(t):
    """Map een team-object van de API naar (naam, vlag, code)."""
    code = (t.get("tla") or "").upper()
    if code in TEAMS:
        nl, flag = TEAMS[code]
        return nl, flag, code
    # fallback: probeer op naam, anders waarschuwen
    print(f"WAARSCHUWING: onbekend team {t.get('name')} (tla={code}) — voeg toe aan TEAMS",
          file=sys.stderr)
    return t.get("name", "?"), "🏳️", code

def gd_str(n):
    """Doelsaldo met echt minteken, '+'-prefix bij positief."""
    if n > 0:  return f"+{n}"
    if n < 0:  return f"−{abs(n)}"      # U+2212, past bij de styling
    return "0"

def when_label(utc_iso):
    """ISO-UTC -> ('do 25/6', '03:00') in Belgische tijd."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(TZ)
    return f"{WEEKDAYS[dt.weekday()]} {dt.day}/{dt.month}", dt.strftime("%H:%M")

# -----------------------------------------------------------------------------
# Data verwerken tot een handige structuur
# -----------------------------------------------------------------------------
def build_groups():
    standings = api(f"/competitions/{COMP_CODE}/standings")
    matches   = api(f"/competitions/{COMP_CODE}/matches?stage=GROUP_STAGE")

    groups = {}   # "A" -> {"played":n, "teams":[...], "matches":[...]}

    # 1) standen
    for s in standings.get("standings", []):
        if s.get("type") != "TOTAL" or not s.get("group"):
            continue
        letter = s["group"].split("_")[-1]          # "GROUP_A" -> "A"
        teams, played = [], 0
        for row in s["table"]:
            nl, flag, code = team_meta(row["team"])
            played = max(played, row["playedGames"])
            teams.append({
                "nl": nl, "flag": flag, "code": code,
                "pts": row["points"], "gd": row["goalDifference"],
            })
        groups[letter] = {"played": played, "teams": teams, "matches": []}

    # 2) wedstrijden (chronologisch per groep)
    for m in sorted(matches.get("matches", []), key=lambda x: x["utcDate"]):
        if not m.get("group"):
            continue
        letter = m["group"].split("_")[-1]
        if letter not in groups:
            continue
        hnl, hfl, hc = team_meta(m["homeTeam"])
        anl, afl, ac = team_meta(m["awayTeam"])
        d, t = when_label(m["utcDate"])
        ft = m.get("score", {}).get("fullTime", {})
        played = m.get("status") == "FINISHED" and ft.get("home") is not None
        groups[letter]["matches"].append({
            "d": d, "t": t,
            "score": f'{ft["home"]}–{ft["away"]}' if played else None,
            "h": [hfl, hnl], "a": [afl, anl],
            "be": "BEL" in (hc, ac), "nl": "NED" in (hc, ac),
        })
    return groups

# -----------------------------------------------------------------------------
# Renderen
# -----------------------------------------------------------------------------
def render_group_cards(groups):
    out = []
    for letter in sorted(groups):
        g = groups[letter]
        has_be = any(t["code"] == "BEL" for t in g["teams"])
        rows = []
        for i, t in enumerate(g["teams"], start=1):
            cls = f"q{i}" + (" be" if t["code"] == "BEL" else "")
            rows.append(
                f'<li class="{cls}"><span class="pos">{i}</span>'
                f'<span class="fl">{t["flag"]}</span>'
                f'<span class="nm">{t["nl"]}</span>'
                f'<span class="pts">{t["pts"]}</span>'
                f'<span class="gd">{gd_str(t["gd"])}</span></li>'
            )
        out.append(
            f'<div class="grp{" has-be" if has_be else ""}">'
            f'<div class="gh"><span class="glet">{letter}</span>'
            f'<span class="gname">Groep {letter}</span>'
            f'<span class="played">{g["played"]}/3</span></div>'
            f'<ol>{"".join(rows)}</ol></div>'
        )
    return "\n".join(out)

def render_pop_data(groups):
    """JS-object voor de popovers: A:{p:..,t:[[flag,naam,ptn,gd],...]}, ..."""
    parts = []
    for letter in sorted(groups):
        g = groups[letter]
        teams = ",".join(
            f'["{t["flag"]}","{t["nl"]}",{t["pts"]},"{gd_str(t["gd"])}"]'
            for t in g["teams"]
        )
        parts.append(f'{letter}:{{p:{g["played"]},t:[{teams}]}}')
    return "{" + ",".join(parts) + "}"

def render_fx_data(groups):
    """JS-object voor de accordion: A:[{d,t|score,h,a,be,nl}, ...], ..."""
    parts = []
    for letter in sorted(groups):
        ms = []
        for m in groups[letter]["matches"]:
            fields = [f'd:"{m["d"]}"']
            if m["score"]:
                fields.append(f's:"{m["score"]}"')
            else:
                fields.append(f't:"{m["t"]}"')
            if m["be"]: fields.append("be:true")
            if m["nl"]: fields.append("nl:true")
            fields.append(f'h:["{m["h"][0]}","{m["h"][1]}"]')
            fields.append(f'a:["{m["a"][0]}","{m["a"][1]}"]')
            ms.append("{" + ",".join(fields) + "}")
        parts.append(f'{letter}:[{",".join(ms)}]')
    return "{" + ",".join(parts) + "}"

def date_label():
    now = datetime.now(TZ)
    return f"Stand t/m {now.day} {['januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december'][now.month-1]}"

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    if not TOKEN:
        sys.exit("Zet eerst FD_TOKEN (je football-data.org API-key) als environment-variabele.")
    if not os.path.exists(TEMPLATE):
        sys.exit(f"{TEMPLATE} niet gevonden. Maak die van de huidige index.html "
                 f"door de dynamische stukken te vervangen door de placeholders "
                 f"{{{{GROUPS}}}}, {{{{POP_DATA}}}}, {{{{FX_DATA}}}}, {{{{DATE}}}}.")

    groups = build_groups()
    if len(groups) != 12:
        print(f"LET OP: {len(groups)} groepen gevonden i.p.v. 12 — check de competitiecode.",
              file=sys.stderr)

    html = open(TEMPLATE, encoding="utf-8").read()
    html = html.replace("{{DATE}}",     date_label())
    html = html.replace("{{GROUPS}}",   render_group_cards(groups))
    html = html.replace("{{POP_DATA}}", render_pop_data(groups))
    html = html.replace("{{FX_DATA}}",  render_fx_data(groups))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{OUTPUT} geschreven ({len(groups)} groepen, "
          f"{sum(len(g['matches']) for g in groups.values())} wedstrijden).")

if __name__ == "__main__":
    main()
