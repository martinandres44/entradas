"""
FIFA World Cup 2026 - Monitor de Tickets
Chequea disponibilidad para:
  - Argentina vs. Argelia  (16 jun, Kansas City)
  - Argentina vs. Austria  (22 jun, Dallas)
"""

import os
import json
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# URLs oficiales a chequear (se agregan como contexto en el análisis)
FIFA_URLS = [
    "https://www.fifa.com/en/tickets",
    "https://www.marketplace.fifa.com",   # mercado de reventa oficial
]

MATCHES = [
    {
        "id": "argentina-algeria",
        "label": "🇦🇷 Argentina vs. 🇩🇿 Argelia",
        "date": "16 jun · Arrowhead Stadium, Kansas City · 9 PM ET",
        "search_terms": [
            "FIFA World Cup 2026 Argentina Algeria tickets available site:fifa.com",
            "Argentina Algeria Kansas City June 16 FIFA ticket last minute",
            "argentina argelia tickets mundial 2026 disponibles",
        ]
    },
    {
        "id": "argentina-austria",
        "label": "🇦🇷 Argentina vs. 🇦🇹 Austria",
        "date": "22 jun · AT&T Stadium, Dallas · 1 PM ET",
        "search_terms": [
            "FIFA World Cup 2026 Argentina Austria tickets available site:fifa.com",
            "Argentina Austria Dallas June 22 FIFA ticket last minute",
            "argentina austria tickets mundial 2026 disponibles",
        ]
    }
]

POSITIVE_SIGNALS = [
    "available", "disponible", "in stock", "add to cart",
    "comprar", "buy now", "ticket found", "resale", "marketplace",
    "last-minute", "on sale", "purchase"
]

NEGATIVE_SIGNALS = [
    "sold out", "no tickets", "not available", "unavailable",
    "agotado", "sin entradas", "no hay entradas"
]


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


def check_fifa_direct(match_id: str) -> dict:
    """Intenta hacer fetch directo a páginas de FIFA para detectar señales."""
    results = {}

    urls_to_check = [
        f"https://www.marketplace.fifa.com",
        "https://www.fifa.com/en/tickets",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FIFATicketMonitor/1.0)",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    }

    for url in urls_to_check:
        try:
            r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            body = r.text.lower()

            found_positive = [s for s in POSITIVE_SIGNALS if s in body]
            found_negative = [s for s in NEGATIVE_SIGNALS if s in body]

            results[url] = {
                "status_code": r.status_code,
                "positive": found_positive,
                "negative": found_negative,
                "accessible": r.status_code == 200
            }
        except Exception as e:
            results[url] = {"error": str(e)}

    return results


def analyze_signals(direct_results: dict) -> tuple[str, str]:
    """
    Retorna (status, resumen_texto)
    status: 'available' | 'sold_out' | 'unknown'
    """
    all_positive = []
    all_negative = []

    for url, data in direct_results.items():
        if "positive" in data:
            all_positive.extend(data["positive"])
        if "negative" in data:
            all_negative.extend(data["negative"])

    if all_positive and not all_negative:
        return "available", f"Señales positivas: {', '.join(set(all_positive))}"
    elif all_negative and not all_positive:
        return "sold_out", f"Señales negativas: {', '.join(set(all_negative))}"
    elif all_positive and all_negative:
        return "mixed", f"Mixto — positivas: {', '.join(set(all_positive))} | negativas: {', '.join(set(all_negative))}"
    else:
        return "unknown", "No se detectaron señales claras. Revisá manualmente: https://www.fifa.com/en/tickets"


def load_previous_state() -> dict:
    try:
        with open("ticket_state.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state: dict) -> None:
    with open("ticket_state.json", "w") as f:
        json.dump(state, f, indent=2)


def main():
    state = load_previous_state()
    timestamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")
    changed_matches = []

    for match in MATCHES:
        mid = match["id"]
        print(f"\n--- Chequeando: {match['label']} ---")

        direct = check_fifa_direct(mid)
        status, summary = analyze_signals(direct)

        prev_status = state.get(mid, {}).get("status")

        print(f"Status: {status}")
        print(f"Resumen: {summary}")

        if status != prev_status:
            changed_matches.append({
                "match": match,
                "status": status,
                "summary": summary,
                "prev": prev_status
            })

        state[mid] = {
            "status": status,
            "summary": summary,
            "last_checked": timestamp
        }

    save_state(state)

    # Notificar por Telegram si hubo cambios
    if changed_matches:
        for item in changed_matches:
            m = item["match"]
            s = item["status"]

            if s == "available":
                emoji = "🟢"
                alert = "¡ENTRADAS DISPONIBLES!"
            elif s == "sold_out":
                emoji = "🔴"
                alert = "Sin disponibilidad detectada"
            elif s == "mixed":
                emoji = "🟡"
                alert = "Señales mixtas — revisá manualmente"
            else:
                emoji = "⚪"
                alert = "Estado desconocido — revisá manualmente"

            msg = (
                f"{emoji} <b>FIFA Monitor · {alert}</b>\n\n"
                f"<b>{m['label']}</b>\n"
                f"{m['date']}\n\n"
                f"{item['summary']}\n\n"
                f"🔗 <a href='https://www.fifa.com/en/tickets'>Comprá en FIFA.com/tickets</a>\n"
                f"🔗 <a href='https://www.marketplace.fifa.com'>Mercado de Reventa FIFA</a>\n\n"
                f"<i>Chequeado: {timestamp}</i>"
            )
            send_telegram(msg)
            print(f"Telegram enviado para {m['id']}")
    else:
        print("\nSin cambios en los estados. No se envió notificación.")
        # Mandá un ping silencioso cada 6 horas para saber que el bot está vivo
        checks_done = sum(1 for v in state.values() if "last_checked" in v)
        hour = datetime.utcnow().hour
        if hour % 6 == 0 and datetime.utcnow().minute < 15:
            msg = (
                f"⏱ <b>FIFA Monitor · Activo</b>\n"
                f"Sin cambios en la disponibilidad.\n"
                f"Última verificación: {timestamp}\n\n"
                f"Argentina vs. Argelia: {state.get('argentina-algeria', {}).get('status', '?')}\n"
                f"Argentina vs. Austria: {state.get('argentina-austria', {}).get('status', '?')}"
            )
            send_telegram(msg)


if __name__ == "__main__":
    main()
