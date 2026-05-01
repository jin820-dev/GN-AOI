from dataclasses import dataclass

from app.services.csv_loader import CsvRecord


@dataclass(frozen=True)
class SummaryMetric:
    label: str
    value: str


def _format_distance(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} km"


def _format_fuel(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f} L"


def _format_economy(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f} km/L"


def _format_count(value: int | None) -> str:
    return "-" if value is None else f"{value} 回"


def _format_currency(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f} 円"


def _format_unit_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f} 円/L"


def _format_date(value: str | None) -> str:
    return value if value else "-"


def build_summary(records: list[CsvRecord], initial_odd_km: float = 0) -> list[SummaryMetric]:
    trip_distance = sum(record.trip_km_value for record in records if record.trip_km_value is not None)
    fallback_total_distance = initial_odd_km + trip_distance
    total_fuel = sum(record.fuel_l_value for record in records if record.fuel_l_value is not None)
    fuel_values = [record.fuel_l_value for record in records if record.fuel_l_value is not None]
    price_values = [record.price_yen_value for record in records if record.price_yen_value is not None]
    economy_values = [record.economy_km_l for record in records if record.economy_km_l is not None]
    latest_odd_km = next(
        (record.odd_km_value for record in records if record.odd_km_value is not None),
        None,
    )
    latest_date = next((record.date for record in records if record.date), None)
    total_distance = latest_odd_km if latest_odd_km is not None else fallback_total_distance

    average_economy = None
    if trip_distance > 0 and total_fuel > 0:
        average_economy = trip_distance / total_fuel

    recent_5_economy_values = economy_values[:5]
    recent_5_average_economy = (
        round(sum(recent_5_economy_values) / len(recent_5_economy_values), 2)
        if recent_5_economy_values
        else None
    )

    total_price = sum(price_values)
    average_price = total_price / len(price_values) if price_values else None
    average_unit_price = total_price / total_fuel if total_price > 0 and total_fuel > 0 else None
    average_fuel = total_fuel / len(fuel_values) if fuel_values else None
    current_odd_km = latest_odd_km if latest_odd_km is not None else fallback_total_distance

    latest_economy = next(
        (record.economy_km_l for record in records if record.economy_km_l is not None),
        None,
    )

    return [
        SummaryMetric(label="総走行距離", value=_format_distance(total_distance if total_distance > 0 else None)),
        SummaryMetric(label="総給油量", value=_format_fuel(total_fuel if total_fuel > 0 else None)),
        SummaryMetric(label="平均燃費", value=_format_economy(average_economy)),
        SummaryMetric(label="直近5回平均", value=_format_economy(recent_5_average_economy)),
        SummaryMetric(label="最高燃費", value=_format_economy(max(economy_values) if economy_values else None)),
        SummaryMetric(label="最低燃費", value=_format_economy(min(economy_values) if economy_values else None)),
        SummaryMetric(label="直近燃費", value=_format_economy(latest_economy)),
        SummaryMetric(label="給油回数", value=_format_count(len(records))),
        SummaryMetric(label="総給油金額", value=_format_currency(total_price if price_values else None)),
        SummaryMetric(label="平均給油金額", value=_format_currency(average_price)),
        SummaryMetric(label="平均燃料単価", value=_format_unit_price(average_unit_price)),
        SummaryMetric(label="平均給油量", value=_format_fuel(average_fuel)),
        SummaryMetric(label="直近給油日", value=_format_date(latest_date)),
        SummaryMetric(label="初期ODD", value=_format_distance(initial_odd_km)),
        SummaryMetric(label="現在ODD", value=_format_distance(current_odd_km)),
    ]
