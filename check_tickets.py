"""
FIFA World Cup 2026 - Monitor de Precios y Disponibilidad
Usa la API pública de SeatGeek (gratuita, requiere client_id).

Obtené tu client_id gratis en: https://seatgeek.com/build
Guardalo en GitHub Secrets como SEATGEEK_CLIENT_ID

Partidos monitoreados:
  - Argentina vs. Argelia  (M19 - 16 jun, Kansas City)  event_id: 17196233
  - Argentina vs. Austria  (M43 - 22 jun, Dallas)        event_id: 17196270
"""

import os, json, requests
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
SEATGEEK_CLIENT_ID  = os.environ.get("SEATGEEK_CLIENT_ID", "")

# Umbrales de notificación
PRICE_DROP_ALERT  = 50   # Notificar si el precio mínimo baja $50 o más
PRICE_RISE_ALERT  = 100  # Notificar si sube $100 o más
COUNT_CHANGE_PCT  = 25   # Notificar si la cantidad cambia ±25%

MATCHES = [
    {
        "id": "argentina-algeria",
        "label": "🇦🇷 Argentina vs. 🇩🇿 Argelia",
        "date": "16 jun · Arrowhead Stadium, Kansas City · 9 PM ET",
        "seatgeek_id": 17196233,
        "buy_url": "https://seatgeek.com/fifa-world-cup-tickets/international-soccer/2026-06-16-8-pm/17196233",
    },
    {
        "id": "argentina-austria",
        "label": "🇦🇷 Argentina vs. 🇦🇹 Austria",
        "date": "22 jun · AT&T Stadium, Dallas · 1 PM ET",
        "seatgeek_id": 17196270,
        "buy_url": "https://seatgeek.com/fifa-world-cup-tickets/international-soccer/2026-06-22-1-pm/17196270",
    },
]


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=10).raise_for_status()


def get_seatgeek_event(event_id: int) -> dict | None:
    """
    Llama a la API de SeatGeek y retorna el evento con stats de listings.
    Endpoint: GET https://api.seatgeek.com/2/events/{id}
    Retorna: lowest_price, average_price, listing_count, por categoría si hay info
    """
    params = {}
    if SEATGEEK_CLIENT_ID:
        params["client_id"] = SEATGEEK_CLIENT_ID

    try:
        r = requests.get(
            f"https://api.seatgeek.com/2/events/{event_id}",
            params=params,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  SeatGeek API status: {r.status_code}")
            return None
    except Exception as e:
        print(f"  Error SeatGeek API: {e}")
        return None


def parse_event_data(event: dict) -> dict:
    """Extrae precio mínimo, promedio y cantidad de listings del response."""
    stats = event.get("stats", {})
    return {
        "min_price":     stats.get("lowest_price"),
        "avg_price":     stats.get("average_price"),
        "listing_count": stats.get("listing_count"),
        "score":         event.get("score"),  # popularidad 0-1
        "title":         event.get("title", ""),
    }


def load_state() -> dict:
    try:
        with open("ticket_state.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state: dict) -> None:
    with open("ticket_state.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def check_changes(data: dict, prev: dict) -> list[str]:
    """Retorna lista de razones para notificar (vacía = no notificar)."""
    reasons = []

    new_price = data.get("min_price")
    old_price = prev.get("min_price")
    new_count = data.get("listing_count")
    old_count = prev.get("listing_count")

    if new_price is not None and old_price is None:
        reasons.append("primera detección de precio")

    if new_price and old_price:
        diff = old_price - new_price
        if diff >= PRICE_DROP_ALERT:
            reasons.append(f"precio bajó ${diff:.0f} 📉")
        elif (new_price - old_price) >= PRICE_RISE_ALERT:
            reasons.append(f"precio subió ${new_price - old_price:.0f} 📈")

    if new_count and old_count and old_count > 0:
        change_pct = (new_count - old_count) / old_count * 100
        if change_pct <= -COUNT_CHANGE_PCT:
            reasons.append(f"entradas cayeron {abs(change_pct):.0f}% ⚠️")
        elif change_pct >= COUNT_CHANGE_PCT:
            reasons.append(f"entradas subieron {change_pct:.0f}%")

    return reasons


def fmt_price(val) -> str:
    return f"${val:,.0f}" if val is not None else "—"


def build_message(match: dict, data: dict, prev: dict, reasons: list, ts: str) -> str:
    new_p = data.get("min_price")
    old_p = prev.get("min_price")
    new_c = data.get("listing_count")
    old_c = prev.get("listing_count")

    # Precio con delta
    if new_p and old_p:
        delta = new_p - old_p
        sign = "+" if delta > 0 else ""
        price_line = f"💲 <b>Precio mínimo:</b> {fmt_price(new_p)}  ({sign}{delta:.0f} vs anterior {fmt_price(old_p)})"
    else:
        price_line = f"💲 <b>Precio mínimo:</b> {fmt_price(new_p)}"

    # Cantidad con delta
    if new_c and old_c:
        delta_c = new_c - old_c
        sign = "+" if delta_c > 0 else ""
        count_line = f"🎟 <b>Listings disponibles:</b> {new_c:,}  ({sign}{delta_c:,} vs anterior {old_c:,})"
    else:
        count_line = f"🎟 <b>Listings disponibles:</b> {new_c:,}" if new_c else "🎟 <b>Listings:</b> —"

    avg_line = f"📊 <b>Precio promedio:</b> {fmt_price(data.get('avg_price'))}"
    razones  = "  |  ".join(reasons)

    return (
        f"⚽ <b>FIFA Ticket Monitor</b>\n"
        f"{match['label']}\n"
        f"{match['date']}\n\n"
        f"{price_line}\n"
        f"{avg_line}\n"
        f"{count_line}\n\n"
        f"⚡ <b>Alerta:</b> {razones}\n\n"
        f"🔗 <a href='https://www.fifa.com/en/tickets'>FIFA oficial</a>  |  "
        f"<a href='{match['buy_url']}'>Ver en SeatGeek</a>\n\n"
        f"<i>Fuente: SeatGeek API · {ts}</i>"
    )


def main():
    state = load_state()
    ts = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    notified = False

    if not SEATGEEK_CLIENT_ID:
        print("⚠️  SEATGEEK_CLIENT_ID no configurado. Intentando sin autenticación...")

    for match in MATCHES:
        mid = match["id"]
        print(f"\n=== {match['label']} ===")

        event = get_seatgeek_event(match["seatgeek_id"])
        if not event:
            print("  No se pudo obtener datos de SeatGeek")
            continue

        data = parse_event_data(event)
        prev = state.get(mid, {})

        print(f"  Min: {fmt_price(data['min_price'])}  |  Avg: {fmt_price(data['avg_price'])}  |  Listings: {data['listing_count']}")

        reasons = check_changes(data, prev)

        if reasons:
            msg = build_message(match, data, prev, reasons, ts)
            send_telegram(msg)
            print(f"  → Telegram: {', '.join(reasons)}")
            notified = True

        history = prev.get("history", [])
        history.append({
            "ts":            ts,
            "min_price":     data["min_price"],
            "avg_price":     data["avg_price"],
            "listing_count": data["listing_count"],
        })
        history = history[-48:]  # últimas 48 entradas (~12hs de historial)

        state[mid] = {
            "min_price":     data["min_price"],
            "avg_price":     data["avg_price"],
            "listing_count": data["listing_count"],
            "last_checked":  ts,
            "history":       history,
        }

    save_state(state)

    # Ping de vida cada 6 horas
    hour = datetime.now(timezone.utc).hour
    minute = datetime.now(timezone.utc).minute
    if not notified and hour % 6 == 0 and minute < 16:
        lines = []
        for match in MATCHES:
            s = state.get(match["id"], {})
            p = fmt_price(s.get("min_price"))
            c = f"{s['listing_count']:,}" if s.get("listing_count") else "—"
            lines.append(f"{match['label']}\n  💲 desde {p}  ·  🎟 {c} listings")

        send_telegram(
            f"⏱ <b>FIFA Monitor · Resumen cada 6h</b>\n\n"
            + "\n\n".join(lines)
            + f"\n\n🔗 <a href='https://www.fifa.com/en/tickets'>FIFA oficial</a>\n"
            + f"<i>{ts}</i>"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
