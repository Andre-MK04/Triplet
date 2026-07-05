"""Alert email rendering.

Inline-styled HTML that mirrors the app's dark boarding-pass cards, plus a plain-text
alternative. Every price is presented as observed, never guaranteed.
"""

from html import escape

from app.config import settings
from app.db.models import SavedSearchDB
from app.models import TripOption
from app.tools.schemas import SearchTripsOutput

INK = "#0b1117"
PANEL = "#162029"
LINE = "#2a3844"
MINT = "#7ddfc3"
MIST = "#93a6b4"
CLOUD = "#e8f0f4"
GOLD = "#ffd08a"


def best_trip(output: SearchTripsOutput) -> TripOption | None:
    return min(output.trips, key=lambda trip: trip.totalPrice) if output.trips else None


def build_alert_subject(row: SavedSearchDB, output: SearchTripsOutput, city_names: dict[str, str]) -> str:
    top = best_trip(output)
    if not top:
        return f"{settings.app_name}: no matching trips right now"
    origin_city = city_names.get(top.outboundFlight.origin, top.outboundFlight.origin)
    destination_city = city_names.get(top.outboundFlight.destination, top.outboundFlight.destination)
    price = round(top.totalPrice)
    if (top.dealScore or top.score) >= 85:
        return f"{destination_city} for €{price}? This looks unusually cheap."
    return f"{settings.app_name} found a €{price} trip from {origin_city}"


def trip_route_headline(trip: TripOption, city_names: dict[str, str]) -> str:
    out_origin = city_names.get(trip.outboundFlight.origin, trip.outboundFlight.origin)
    out_destination = city_names.get(trip.outboundFlight.destination, trip.outboundFlight.destination)
    if trip.tripType == "open_jaw":
        ret_origin = city_names.get(trip.returnFlight.origin, trip.returnFlight.origin)
        return f"{out_origin} → {out_destination} / {ret_origin} → home"
    return f"{out_origin} → {out_destination}"


def trip_dates_line(trip: TripOption) -> str:
    start = trip.outboundFlight.departureDateTime.strftime("%-d %b")
    end = trip.returnFlight.departureDateTime.strftime("%-d %b")
    nights = f"{trip.nights} night" + ("" if trip.nights == 1 else "s")
    return f"{start} – {end} · {nights}"


def link_label(trip: TripOption) -> str:
    return trip.bookingLabel or "Check price"


def build_alert_html(
    row: SavedSearchDB,
    output: SearchTripsOutput,
    city_names: dict[str, str],
    manage_note: str,
) -> str:
    cards = "".join(
        render_trip_card_html(trip, city_names)
        for trip in output.trips[: settings.alerts_max_results_per_email]
    )
    name = escape(row.name or "your saved search")
    dashboard_url = f"{settings.alerts_public_base_url}/dashboard"
    account_line = (
        f'<a href="{escape(dashboard_url)}" style="color:{MINT};">Manage this watch on your dashboard</a>'
        if row.user_id
        else escape(manage_note)
    )
    return f"""\
<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:24px 12px;background-color:{INK};font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;">
    <p style="margin:0 0 4px;font-size:18px;font-weight:700;color:{CLOUD};">✈ {escape(settings.app_name)}</p>
    <p style="margin:0 0 20px;font-size:13px;color:{MIST};">New trip ideas for <strong style="color:{CLOUD};">{name}</strong></p>
    {cards}
    <p style="margin:20px 0 6px;font-size:12px;color:{MIST};">
      Prices were observed when we checked and can change at any time — always confirm the final
      price with the airline or provider. {escape(settings.app_name)} does not sell or book flights.
    </p>
    <p style="margin:0;font-size:12px;color:{MIST};">{account_line}</p>
    <p style="margin:12px 0 0;font-size:11px;color:{MIST};">
      You are receiving this because you saved a {escape(settings.app_name)} alert for this search.
    </p>
  </div>
</body>
</html>
"""


def render_trip_card_html(trip: TripOption, city_names: dict[str, str]) -> str:
    headline = escape(trip_route_headline(trip, city_names))
    dates = escape(trip_dates_line(trip))
    price = f"€{round(trip.totalPrice)}"
    deal = trip.dealScore or trip.score
    fit_badge = (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;background-color:rgba(142,197,255,0.15);color:#8ec5ff;font-size:12px;font-weight:600;">{trip.fitScore} fit</span>'
        if trip.fitScore is not None
        else ""
    )
    transfer_line = ""
    if trip.groundTransfer:
        transfer_line = (
            f'<p style="margin:8px 0 0;font-size:12px;color:{GOLD};">🚆 '
            f"{escape(trip.groundTransfer.fromCity)} → {escape(trip.groundTransfer.toCity)}, approx. "
            f"{trip.groundTransfer.durationHours:g}h by {escape(trip.groundTransfer.mode)}</p>"
        )
    warnings_line = ""
    if trip.warnings:
        warnings_line = (
            f'<p style="margin:8px 0 0;font-size:12px;color:{GOLD};">⚠️ {escape("; ".join(trip.warnings[:2]))}</p>'
        )
    button = ""
    if trip.bookingUrl:
        button = (
            f'<a href="{escape(trip.bookingUrl)}" '
            f'style="display:inline-block;margin-top:12px;padding:9px 20px;border-radius:999px;'
            f'background-color:{MINT};color:{INK};font-size:13px;font-weight:700;text-decoration:none;">'
            f"{escape(link_label(trip))} ↗</a>"
        )
    return f"""\
    <div style="margin-bottom:14px;padding:18px;border-radius:16px;background-color:{PANEL};border:1px solid {LINE};">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td>
          <p style="margin:0;font-size:16px;font-weight:700;color:{CLOUD};">{headline}</p>
          <p style="margin:3px 0 0;font-size:12px;color:{MIST};">{dates}</p>
        </td>
        <td align="right" style="vertical-align:top;">
          <p style="margin:0;font-size:20px;font-weight:700;color:{MINT};">{price}</p>
        </td>
      </tr></table>
      <p style="margin:10px 0 0;">
        <span style="display:inline-block;padding:2px 10px;border-radius:999px;background-color:rgba(125,223,195,0.15);color:{MINT};font-size:12px;font-weight:600;">{deal} deal score</span>
        {fit_badge}
      </p>
      <p style="margin:10px 0 0;font-size:13px;line-height:1.5;color:{CLOUD};">{escape(trip.explanation)}</p>
      {transfer_line}
      {warnings_line}
      {button}
    </div>
"""


def build_alert_text(
    row: SavedSearchDB,
    output: SearchTripsOutput,
    city_names: dict[str, str],
    manage_note: str,
) -> str:
    lines = [
        f"{settings.app_name} alert: {row.name or 'Saved search'}",
        "Prices are observed, not guaranteed, and may change.",
        "",
    ]
    for trip in output.trips[: settings.alerts_max_results_per_email]:
        scores = f"deal {trip.dealScore or trip.score}"
        if trip.fitScore is not None:
            scores += f" · fit {trip.fitScore}"
        lines.append(
            f"- {trip_route_headline(trip, city_names)}: EUR {round(trip.totalPrice)} · "
            f"{trip_dates_line(trip)} · {scores}"
        )
        lines.append(f"  {trip.explanation}")
        if trip.bookingUrl:
            lines.append(f"  {link_label(trip)}: {trip.bookingUrl}")
        if trip.warnings:
            lines.append(f"  Warnings: {'; '.join(trip.warnings)}")
    lines.extend(
        [
            "",
            f"{settings.app_name} does not sell or book flights. Prices and availability can change "
            "after you open the provider site.",
            manage_note,
            f"You are receiving this because you saved a {settings.app_name} alert.",
        ]
    )
    return "\n".join(lines)
