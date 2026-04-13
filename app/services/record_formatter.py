from dataclasses import dataclass, asdict

from app.services.csv_loader import CsvRecord


@dataclass(frozen=True)
class RecordCard:
    row_id: str
    delete_index: int
    title: str
    subtitle: str
    economy_label: str
    meta_items: list[dict[str, str]]


def _format_currency(value: float | None, raw: str) -> str:
    if value is None:
        return raw or "--"
    return f"{value:.0f} 円"


def _format_float(value: float | None, suffix: str, digits: int = 1) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f} {suffix}"


def format_record_cards(records: list[CsvRecord]) -> list[dict]:
    cards: list[dict] = []

    for record in records:
        note_preview = record.note if record.note else "メモなし"
        if len(note_preview) > 52:
            note_preview = f"{note_preview[:49]}..."

        card = RecordCard(
            row_id=record.row_id,
            delete_index=record.row_number - 2,
            title=record.date or "日付不明",
            subtitle=record.time or "時刻未設定",
            economy_label=_format_float(record.economy_km_l, "km/L", digits=2),
            meta_items=[
                {"label": "給油量", "value": _format_float(record.fuel_l_value, "L", digits=2)},
                {"label": "価格", "value": _format_currency(record.price_yen_value, record.price_yen)},
                {"label": "区間距離", "value": _format_float(record.trip_km_value, "km", digits=1)},
                {"label": "積算距離", "value": _format_float(record.odd_km_value, "km", digits=1)},
                {"label": "満タン", "value": record.full or "--"},
                {"label": "油種", "value": record.fuel_type or "--"},
                {"label": "距離方式", "value": record.distance_mode or "--"},
                {"label": "メモ", "value": note_preview},
            ],
        )
        cards.append(asdict(card))

    return cards
