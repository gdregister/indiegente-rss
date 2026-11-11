#!/usr/bin/env python3
"""Gera um feed RSS (podcast) para o programa Indiegente (Antena 3 / RTP Play).

A RTP não publica RSS para este programa, por isso este script:
  1. lê a página do programa no RTP Play e encontra os episódios mais recentes;
  2. abre a página de cada episódio novo para obter o link direto do MP3;
  3. guarda o histórico em episodes.json (a página só mostra ~12 episódios);
  4. escreve feed.xml, pronto a adicionar ao YouTube Music, Apple Podcasts, etc.

Só usa a biblioteca padrão do Python 3.9+.
"""
import html
import json
import re
import sys
import urllib.request
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

PROGRAM_ID = "257"
PROGRAM_URL = f"https://www.rtp.pt/play/p{PROGRAM_ID}/indiegente"
BASE = "https://www.rtp.pt"
TITLE = "Indiegente"
AUTHOR = "Nuno Calado · Antena 3 (RTP)"
DESCRIPTION = (
    "Nuno Calado apresenta o som mais alternativo e atual da rádio. "
    "Na Antena 3, de segunda a quinta-feira, entre as 23h e as 24h, "
    "e edição Gold à sexta-feira, entre as 21h e as 23h. "
    "(Feed não oficial gerado a partir do RTP Play.)"
)
MAX_EPISODES = 300
HERE = Path(__file__).resolve().parent
DB = HERE / "episodes.json"
OUT = HERE / "docs" / "feed.xml"
LISBON = ZoneInfo("Europe/Lisbon")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def get(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if method == "HEAD":
            return r.headers
        return r.read().decode("utf-8", "replace")


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_date(text):
    """'10 nov. 2026' -> datetime em Lisboa (hora de emissão aproximada)."""
    m = re.search(r"(\d{1,2})\s+([a-zç]{3})\w*\.?\s+(\d{4})", text.lower())
    if not m:
        return None
    d = datetime(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    hour = 21 if d.weekday() == 4 else 23  # sexta: edição Gold às 21h
    return d.replace(hour=hour, tzinfo=LISBON)


def parse_program_page(page):
    """Devolve [{id, url, date, description, duration_min}] da página do programa."""
    eps = []
    pattern = re.compile(
        r'<a href="(/play/p%s/e(\d+)/[^"]*)"[^>]*class="[^"]*vod-audio[^"]*"[^>]*>(.*?)</a>'
        % PROGRAM_ID, re.S)
    for m in pattern.finditer(page):
        block = m.group(3)
        date = re.search(r'class="podcast-date">([^<]+)<', block)
        desc = re.search(r'class="podcast-description">(.*?)</p>', block, re.S)
        dur = re.search(r'podcast-metadata[^>]*>\s*(\d+)\s*min', block)
        eps.append({
            "id": m.group(2),
            "url": BASE + m.group(1),
            "date_text": clean(date.group(1)) if date else "",
            "description": clean(desc.group(1)) if desc else "",
            "duration_min": int(dur.group(1)) if dur else None,
        })
    return eps


def parse_episode_page(page):
    mp3 = re.search(r'var f = "(https://[^"]+\.mp3)"', page)
    dur = re.search(r'itemprop="duration" content="PT(\d+)H(\d+)M(\d+)S"', page)
    date = re.search(r'class="episode-date">([^<]+)<', page)
    desc = re.search(r'class="vod-description">(.*?)</p>', page, re.S)
    img = re.search(r'<meta property="og:image" content="([^"?]+)', page)
    return {
        "mp3": mp3.group(1) if mp3 else None,
        "duration_s": (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + int(dur.group(3))) if dur else None,
        "date_text": clean(date.group(1)) if date else None,
        "description": clean(desc.group(1)) if desc else None,
        "image": img.group(1) if img else None,
    }


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def build_feed(episodes, image):
    items = []
    for e in episodes:
        dt = datetime.fromisoformat(e["pubdate"])
        title = f"{TITLE} – {dt.strftime('%d/%m/%Y')}"
        if e.get("description"):
            short = e["description"].rstrip(". ")
            if not short.lower().startswith("inclui entre outros"):
                title += f" · {short[:80]}"
        desc = e.get("description") or TITLE
        dur = f"\n      <itunes:duration>{hms(e['duration_s'])}</itunes:duration>" if e.get("duration_s") else ""
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <description>{escape(desc)}</description>
      <itunes:summary>{escape(desc)}</itunes:summary>
      <link>{escape(e['url'])}</link>
      <guid isPermaLink="false">rtp-play-e{e['id']}</guid>
      <pubDate>{format_datetime(dt)}</pubDate>
      <enclosure url="{escape(e['mp3'])}" length="{e.get('length') or 0}" type="audio/mpeg"/>{dur}
      <itunes:episodeType>full</itunes:episodeType>
    </item>""")
    now = format_datetime(datetime.now(LISBON))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(TITLE)}</title>
    <link>{PROGRAM_URL}</link>
    <description>{escape(DESCRIPTION)}</description>
    <language>pt-PT</language>
    <lastBuildDate>{now}</lastBuildDate>
    <itunes:author>{escape(AUTHOR)}</itunes:author>
    <itunes:summary>{escape(DESCRIPTION)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Music"/>
    <itunes:image href="{escape(image)}"/>
    <image><url>{escape(image)}</url><title>{escape(TITLE)}</title><link>{PROGRAM_URL}</link></image>
{chr(10).join(items)}
  </channel>
</rss>
"""


def main():
    db = json.loads(DB.read_text()) if DB.exists() else {"image": None, "episodes": []}
    known = {e["id"]: e for e in db["episodes"]}

    listing = parse_program_page(get(PROGRAM_URL))
    if not listing:
        sys.exit("Nenhum episódio encontrado na página do programa — o layout do RTP Play pode ter mudado.")

    added = 0
    for item in listing:
        if item["id"] in known:
            continue
        try:
            info = parse_episode_page(get(item["url"]))
        except Exception as exc:  # um episódio falhado não deve parar o resto
            print(f"aviso: e{item['id']}: {exc}", file=sys.stderr)
            continue
        if not info["mp3"]:
            print(f"aviso: e{item['id']}: sem MP3", file=sys.stderr)
            continue
        dt = parse_date(info["date_text"] or item["date_text"])
        if not dt:
            print(f"aviso: e{item['id']}: data ilegível", file=sys.stderr)
            continue
        length = 0
        try:
            length = int(get(info["mp3"], "HEAD").get("Content-Length") or 0)
        except Exception:
            pass
        known[item["id"]] = {
            "id": item["id"],
            "url": item["url"],
            "pubdate": dt.isoformat(),
            "description": info["description"] or item["description"],
            "duration_s": info["duration_s"] or ((item["duration_min"] or 0) * 60) or None,
            "mp3": info["mp3"],
            "length": length,
        }
        if info["image"]:
            db["image"] = info["image"]
        added += 1

    # Ordena do mais recente para o mais antigo (desempata pelo id do episódio).
    episodes = sorted(known.values(), key=lambda e: (e["pubdate"], int(e["id"])), reverse=True)[:MAX_EPISODES]
    db["episodes"] = episodes
    image = (db.get("image") or "https://cdn-images.rtp.pt/EPG/radio/imagens/1073_13610_55092.png") + "?w=1400"

    DB.write_text(json.dumps(db, ensure_ascii=False, indent=1))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build_feed(episodes, image))
    print(f"{added} episódio(s) novo(s); {len(episodes)} no feed.")


if __name__ == "__main__":
    main()
