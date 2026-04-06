"""
FIFA World Cup 2026 - Monitor de Tickets
Monitorea disponibilidad para:
  - Argentina vs. Argelia  (M19 - 16 jun, Kansas City)
  - Argentina vs. Austria  (M43 - 22 jun, Dallas)
"""

import os
import json
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

MATCHES = [
    {
        "id": "argentina-algeria",
        "label": "🇦🇷 Argentina vs. 🇩🇿 Argelia",
        "date": "16 jun · Arrowhead Stadium, Kansas City · 9 PM ET",
        "urls": [
            {
                "url": "https://www.tickpick.com/buy-fifa-world-cup-26-group-j-argentina-vs-algeria-match-19-tickets-arrowhead-stadium-6-16-26-8pm/6259640/",
                "name": "TickPick",
                "keywords_available": ["$", "section", "row", "add to cart"],
                "keywords_sold": ["no tickets", "sold out"],
            },
            {
                "url": "https://seatgeek.com/fifa-world-cup-tickets/international-soccer/2026-06-16-8-pm/17196233",
                "name": "SeatGeek",
                "keywords_available": ["tickets from", "get tickets", "lowest price"],
                "keywords_sold": ["no tickets", "sold out"],
            },
            {
                "url": "https://gametime.co/soccer/fifa-world-cup-argentina-vs-algeria-match-19-group-j-tickets/6-16-2026-kansas-city-mo-arrowhead-stadium/events/66ac27f8880867d8fb9ee65f",
                "name": "Gametime",
                "keywords_available": ["$", "tickets", "buy"],
                "keywords_sold": ["no tickets", "sold out"],
            },
        ]
    },
    {
        "id": "argentina-austria",
        "label": "🇦🇷 Argentina vs. 🇦🇹 Austria",
        "date": "22 jun · AT&T Stadium, Dallas · 1 PM ET",
        "urls": [
            {
                "url": "https://www.vividseats.com/world-cup-soccer-tickets-att-stadium-6-22-2026--sports-soccer/production/5080516",
                "name": "VividSeats",
                "keywords_available": ["$", "tickets from", "buy tickets"],
                "keywords_sold": ["no tickets", "sold out"],
            },
            {
                "url": "https://www.tickpick.com/buy-world-cup-soccer-tickets-att-stadium-6-22-26/5064218/",
                "name": "TickPick",
                "keywords_available": ["$", "section", "row", "add to cart"],
                "keywords_sold": ["no tickets", "sold out"],
            },
        ]
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()
    print("Telegram enviado OK")


def check_url(url_config: dict) -> dict:
    try:
        r = requests.get(url_config["url"], headers=HEADERS, timeout=20, allow_redirects=True)
        body = r.text.lower()

        found_available = [k for k in url_config["keywords_available"] if k.lower() in body]
        found_sold      = [k for k in url_config["keywords_sold"] if k.lower() in body]

        if found_available and not found_sold:
            status = "available"
        elif found_sold:
            status = "sold_out"
        else:
            status = "unknown"

        return {
            "name": url_config["name"],
            "status": status,
            "found_available": found_available,
            "found_sold": found_sold,
            "http_code": r.status_code,
        }
    except Exception as e:
        return {
            "name": url_config["name"],
            "status": "error",
            "error": str(e)[:100],
        }


def check_match(match: dict) -> dict:
    results = [check_url(u) for u in match["urls"]]

    available_sources = [r for r in results if r["status"] == "available"]
    sold_sources      = [r for r in results if r["status"] == "sold_out"]

    if available_sources:
        overall = "available"
    elif sold_sources and not available_sources:
        overall = "sold_out"
    else:
        overall = "unknown"

    return {"overall": overall, "details": results}


def load_state() -> dict:
    try:
        with open("ticket_state.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state: dict) -> None:
    with open("ticket_state.json", "w") as f:
        json.dump(state, f, indent=2)


def build_message(match: dict, result: dict, timestamp: str) -> str:
    status = result["overall"]

    if status == "available":
        emoji, titulo = "🟢", "¡ENTRADAS DISPONIBLES!"
    elif status == "sold_out":
        emoji, titulo = "🔴", "Sin disponibilidad"
    else:
        emoji, titulo = "🟡", "Estado mixto — revisá"

    fuentes = ""
    for d in result["details"]:
        icon = {"available": "✅", "sold_out": "❌", "error": "⚠️"}.get(d["status"], "❓")
        fuentes += f"{icon} {d['name']}\n"

    return (
        f"{emoji} <b>FIFA Monitor · {titulo}</b>\n\n"
        f"<b>{match['label']}</b>\n"
        f"{match['date']}\n\n"
        f"<b>Fuentes chequeadas:</b>\n{fuentes}\n"
        f"🔗 <a href='https://www.fifa.com/en/tickets'>FIFA.com/tickets (oficial)</a>\n"
        f"🔗 <a href='https://tickets.fifa.com/en/marketplace'>Mercado Reventa FIFA</a>\n\n"
        f"<i>{timestamp}</i>"
    )


def main():
    state = load_state()
    timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    notified = False

    for match in MATCHES:
        mid = match["id"]
        print(f"\n=== {match['label']} ===")

        result = check_match(match)
        overall = result["overall"]
        prev = state.get(mid, {}).get("overall")

        for d in result["details"]:
            print(f"  {d['name']}: {d['status']}")

        # Notificar si cambió de estado, o siempre que haya disponibilidad
        should_notify = (overall != prev) or (overall == "available")

        if should_notify:
            msg = build_message(match, result, timestamp)
            send_telegram(msg)
            notified = True

        state[mid] = {"overall": overall, "last_checked": timestamp}

    save_state(state)

    # Ping de vida cada 6 horas
    if not notified:
        hour = datetime.utcnow().hour
        if hour % 6 == 0 and datetime.utcnow().minute < 16:
            resumen = ""
            for match in MATCHES:
                s = state.get(match["id"], {}).get("overall", "?")
                icon = "🟢" if s == "available" else "🔴" if s == "sold_out" else "🟡"
                resumen += f"{icon} {match['label']}\n"
            msg = (
                f"⏱ <b>FIFA Monitor · Activo</b>\n\n"
                f"{resumen}\n"
                f"<i>Último chequeo: {timestamp}</i>"
            )
            send_telegram(msg)

    print("\nDone.")


if __name__ == "__main__":
    main()
