"""
FIFA World Cup 2026 - Monitor de Precios y Disponibilidad
Fuentes: SeatGeek API + TickPick (scraping HTML) + Gametime (scraping HTML)

Secrets requeridos en GitHub:
  - TELEGRAM_BOT_TOKEN
  - TELEGRAM_CHAT_ID
  - SEATGEEK_CLIENT_ID   (gratis en seatgeek.com/build)
"""

import os, json, re, requests
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
SEATGEEK_CLIENT_ID = os.environ.get("SEATGEEK_CLIENT_ID", "")

PRICE_DROP_ALERT = 50    # avisar si baja $50 o más en cualquier fuente
PRICE_RISE_ALERT = 100   # avisar si sube $100 o más

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# ──────────────────────────────────────────────
# CONFIGURACIÓN DE PARTIDOS
# ──────────────────────────────────────────────
MATCHES = [
    {
        "id":    "argentina-algeria",
        "label": "🇦🇷 Argentina vs. 🇩🇿 Argelia",
        "date":  "16 jun · Arrowhead Stadium, Kansas City · 9 PM ET",
        "seatgeek_id": 17196233,
        "tickpick_url": "https://www.tickpick.com/buy-fifa-world-cup-26-group-j-argentina-vs-algeria-match-19-tickets-arrowhead-stadium-6-16-26-8pm/6259640/",
        "gametime_url": "https://gametime.co/soccer/fifa-world-cup-argentina-vs-algeria-match-19-group-j-tickets/6-16-2026-kansas-city-mo-arrowhead-stadium/events/66ac27f8880867d8fb9ee65f",
        "seatgeek_url": "https://seatgeek.com/fifa-world-cup-tickets/international-soccer/2026-06-16-8-pm/17196233",
    },
    {
        "id":    "argentina-austria",
        "label": "🇦🇷 Argentina vs. 🇦🇹 Austria",
        "date":  "22 jun · AT&T Stadium, Dallas · 1 PM ET",
        "seatgeek_id": 17385144,
        "tickpick_url": "https://www.tickpick.com/buy-world-cup-26-group-j-argentina-vs-austria-match-43-tickets-att-stadium-6-22-26-12pm/6259682/",
        "gametime_url": "https://gametime.co/soccer/fifa-world-cup-argentina-vs-austria-match-43-group-j-tickets/6-22-2026-arlington-tx-att-stadium/events/66ac27f8880867d8fb9ee683",
        "seatgeek_url": "https://seatgeek.com/fifa-world-cup-tickets/international-soccer/2026-06-22-12-pm/17385144",
    },
]


# ──────────────────────────────────────────────
# SCRAPERS
# ──────────────────────────────────────────────

def scrape_tickpick(url: str) -> dict:
    """
    1. Intenta API interna: api.tickpick.com/1.0/listings/internal/event/{id}
    2. Fallback: scraping HTML (precio en texto + conteo en JSON embebido)
    """
    # Extraer event_id de la URL
    m = re.search(r"/(\d{6,8})/?$", url)
    event_id = m.group(1) if m else None

    # Intento 1: API interna
    if event_id:
        try:
            api_url = f"https://api.tickpick.com/1.0/listings/internal/event/{event_id}?mid={event_id}"
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                listings = data if isinstance(data, list) else data.get("listings", [])
                if listings:
                    prices = []
                    for l in listings:
                        p = l.get("c") or l.get("price") or l.get("listingPrice") or l.get("p")
                        if p:
                            try:
                                prices.append(int(float(p)))
                            except Exception:
                                pass
                    prices = [p for p in prices if 100 < p < 20000]
                    return {
                        "source":        "TickPick",
                        "min_price":     min(prices) if prices else None,
                        "listing_count": len(listings),
                        "ok":            True,
                    }
        except Exception:
            pass

    # Intento 2: Scraping HTML
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        body = r.text
        # Precio en texto estatico
        mp = re.search(r"start at \$([0-9,]+)", body, re.IGNORECASE)
        price = int(mp.group(1).replace(",", "")) if mp else None
        # Conteo en JSON embebido (TickPick incluye datos en window.__PRELOADED_STATE__)
        mc = re.search(r'"totalListings"\s*:\s*(\d+)', body)
        if not mc:
            mc = re.search(r'"listingCount"\s*:\s*(\d+)', body)
        count = int(mc.group(1)) if mc else None
        return {"source": "TickPick", "min_price": price, "listing_count": count, "ok": True}
    except Exception as e:
        return {"source": "TickPick", "ok": False, "error": str(e)[:80]}


def scrape_gametime(url: str) -> dict:
    """
    1. Intenta API interna: gametime.co/api/v2/events/{id}/listings
    2. Fallback: scraping HTML buscando JSON embebido en la pagina
    """
    m = re.search(r"/events/([a-f0-9]{20,})", url)
    event_id = m.group(1) if m else None

    # Intento 1: API interna
    if event_id:
        try:
            api_url = f"https://gametime.co/api/v2/events/{event_id}/listings"
            api_headers = {**HEADERS, "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
            r = requests.get(api_url, headers=api_headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                listings = data.get("listings", data if isinstance(data, list) else [])
                if listings:
                    prices = []
                    for l in listings:
                        p = l.get("price") or l.get("list_price") or l.get("display_price") or l.get("amount")
                        if p:
                            try:
                                prices.append(int(float(str(p).replace("$", "").replace(",", ""))))
                            except Exception:
                                pass
                    prices = [p for p in prices if 100 < p < 20000]
                    return {
                        "source":        "Gametime",
                        "min_price":     min(prices) if prices else None,
                        "listing_count": len(listings),
                        "ok":            True,
                    }
        except Exception:
            pass

    # Intento 2: scraping HTML
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        body = r.text
        # Precios en JSON embebido (Gametime usa Next.js con datos en __NEXT_DATA__)
        prices = re.findall(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', body)
        prices = [int(float(p)) for p in prices if 100 < int(float(p)) < 20000]
        # Conteo
        mc = re.search(r'"total(?:_listings|Listings|Count)"\s*:\s*(\d+)', body)
        count = int(mc.group(1)) if mc else None
        return {
            "source":        "Gametime",
            "min_price":     min(prices) if prices else None,
            "listing_count": count,
            "ok":            True,
        }
    except Exception as e:
        return {"source": "Gametime", "ok": False, "error": str(e)[:80]}


def fetch_seatgeek(event_id: int) -> dict:
    """Llama a la API oficial de SeatGeek."""
    try:
        params = {"client_id": SEATGEEK_CLIENT_ID} if SEATGEEK_CLIENT_ID else {}
        r = requests.get(
            f"https://api.seatgeek.com/2/events/{event_id}",
            params=params, timeout=15
        )
        if r.status_code != 200:
            return {"source": "SeatGeek", "ok": False, "error": f"HTTP {r.status_code}"}

        data  = r.json()
        stats = data.get("stats", {})

        return {
            "source":        "SeatGeek",
            "min_price":     stats.get("lowest_price"),
            "avg_price":     stats.get("average_price"),
            "listing_count": stats.get("listing_count"),
            "ok":            True,
        }
    except Exception as e:
        return {"source": "SeatGeek", "ok": False, "error": str(e)[:80]}


# ──────────────────────────────────────────────
# AGREGACIÓN
# ──────────────────────────────────────────────

def collect_match_data(match: dict) -> dict:
    results = [
        scrape_tickpick(match["tickpick_url"]),
        scrape_gametime(match["gametime_url"]),
    ]

    prices = [r["min_price"] for r in results if r.get("ok") and r.get("min_price")]
    counts = [r["listing_count"] for r in results if r.get("ok") and r.get("listing_count")]
    avgs   = [r["avg_price"] for r in results if r.get("ok") and r.get("avg_price")]

    return {
        "min_price":     min(prices) if prices else None,
        "avg_price":     round(sum(avgs) / len(avgs)) if avgs else None,
        "listing_count": max(counts) if counts else None,   # el mayor es el más completo
        "sources":       results,
    }


# ──────────────────────────────────────────────
# LÓGICA DE ALERTAS
# ──────────────────────────────────────────────

def detect_changes(data: dict, prev: dict) -> list[str]:
    reasons = []
    new_p, old_p = data.get("min_price"), prev.get("min_price")
    new_c, old_c = data.get("listing_count"), prev.get("listing_count")

    if new_p and not old_p:
        reasons.append("primera detección de precio")
    elif new_p and old_p:
        diff = old_p - new_p
        if diff >= PRICE_DROP_ALERT:
            reasons.append(f"precio bajó ${diff} 📉")
        elif (new_p - old_p) >= PRICE_RISE_ALERT:
            reasons.append(f"precio subió ${new_p - old_p} 📈")

    if new_c and old_c:
        pct = (new_c - old_c) / old_c * 100
        if pct <= -25:
            reasons.append(f"entradas cayeron {abs(pct):.0f}% ⚠️")
        elif pct >= 30:
            reasons.append(f"entradas subieron {pct:.0f}%")

    return reasons


# ──────────────────────────────────────────────
# MENSAJE TELEGRAM
# ──────────────────────────────────────────────

def fmt(v, prefix="$"):
    return f"{prefix}{int(v):,}" if v is not None else "—"

def build_message(match: dict, data: dict, prev: dict, reasons: list, ts: str) -> str:
    new_p, old_p = data.get("min_price"), prev.get("min_price")
    delta = f" ({'+' if new_p > old_p else ''}{new_p - old_p:+,} vs anterior {fmt(old_p)})" if new_p and old_p else ""

    source_lines = ""
    for s in data["sources"]:
        if not s.get("ok"):
            source_lines += f"  ⚠️ {s['source']}: error\n"
        else:
            p = fmt(s.get("min_price"))
            c = f"{s['listing_count']:,}" if s.get("listing_count") else "—"
            source_lines += f"  • {s['source']}: desde {p} · {c} listings\n"

    return (
        f"⚽ <b>FIFA Monitor · {match['label']}</b>\n"
        f"{match['date']}\n\n"
        f"💲 <b>Precio mínimo:</b> {fmt(new_p)}{delta}\n"
        f"📊 <b>Precio promedio:</b> {fmt(data.get('avg_price'))}\n"
        "🎟 <b>Listings:</b> " + (f"{data['listing_count']:,}" if data.get("listing_count") else "—") + "\n\n"
        f"<b>Por fuente:</b>\n{source_lines}\n"
        f"⚡ {' | '.join(reasons)}\n\n"
        f"🔗 <a href='https://www.fifa.com/en/tickets'>FIFA oficial</a>  "
        f"<a href='{match['seatgeek_url']}'>SeatGeek</a>  "
        f"<a href='{match['tickpick_url']}'>TickPick</a>  "
        f"<a href='{match['gametime_url']}'>Gametime</a>\n\n"
        f"<i>{ts}</i>"
    )


# ──────────────────────────────────────────────
# PERSISTENCIA
# ──────────────────────────────────────────────

def load_state() -> dict:
    try:
        with open("ticket_state.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_state(state: dict):
    with open("ticket_state.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(msg: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=10,
    ).raise_for_status()


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    state   = load_state()
    ts      = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    notified = False

    for match in MATCHES:
        mid  = match["id"]
        prev = state.get(mid, {})
        print(f"\n=== {match['label']} ===")

        data = collect_match_data(match)

        for s in data["sources"]:
            status = f"${s['min_price']}  listings:{s.get('listing_count')}" if s.get("ok") else f"ERROR: {s.get('error')}"
            print(f"  {s['source']}: {status}")

        reasons = detect_changes(data, prev)
        if reasons:
            send_telegram(build_message(match, data, prev, reasons, ts))
            print(f"  → Telegram: {', '.join(reasons)}")
            notified = True

        # Guardar historial (últimas 48 entradas ≈ 12 horas)
        history = prev.get("history", [])
        history.append({"ts": ts, "min_price": data["min_price"],
                         "avg_price": data["avg_price"], "listing_count": data["listing_count"]})

        # Guardar detalle por fuente para el dashboard
        sources_summary = {}
        for s in data.get("sources", []):
            sources_summary[s["source"]] = {
                "min_price":     s.get("min_price"),
                "listing_count": s.get("listing_count"),
                "ok":            s.get("ok", False),
                "error":         s.get("error"),
            }

        state[mid] = {
            "min_price":     data["min_price"],
            "avg_price":     data["avg_price"],
            "listing_count": data["listing_count"],
            "last_checked":  ts,
            "history":       history[-48:],
            "by_source":     sources_summary,
        }

    save_state(state)

    # Ping de vida cada 6 horas
    now = datetime.now(timezone.utc)
    if not notified and now.hour % 6 == 0 and now.minute < 16:
        lines = []
        for m in MATCHES:
            s = state.get(m["id"], {})
            lines.append(f"{m['label']}\n  💲 {fmt(s.get('min_price'))}  🎟 {s.get('listing_count') or '—'} listings")
        send_telegram(
            f"⏱ <b>FIFA Monitor · Resumen 6h</b>\n\n" + "\n\n".join(lines) +
            f"\n\n🔗 <a href='https://www.fifa.com/en/tickets'>FIFA oficial</a>\n<i>{ts}</i>"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
