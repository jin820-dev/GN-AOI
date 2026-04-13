from dataclasses import dataclass

from app.services.csv_loader import CsvRecord


@dataclass(frozen=True)
class SummaryMetric:
    label: str
    value: str


def _format_distance(value: float | None) -> str:
    return "-- km" if value is None else f"{value:.1f} km"


def _format_fuel(value: float | None) -> str:
    return "-- L" if value is None else f"{value:.2f} L"


def _format_economy(value: float | None) -> str:
    return "-- km/L" if value is None else f"{value:.2f} km/L"


def build_summary(records: list[CsvRecord], initial_odd_km: float = 0) -> list[SummaryMetric]:
    trip_distance = sum(record.trip_km_value for record in records if record.trip_km_value is not None)
    total_distance = initial_odd_km + trip_distance
    total_fuel = sum(record.fuel_l_value for record in records if record.fuel_l_value is not None)
    economy_values = [record.economy_km_l for record in records if record.economy_km_l is not None]

    average_economy = None
    if trip_distance > 0 and total_fuel > 0:
        average_economy = trip_distance / total_fuel

    latest_economy = next(
        (record.economy_km_l for record in records if record.economy_km_l is not None),
        None,
    )

    return [
        SummaryMetric(label="総走行距離", value=_format_distance(total_distance if total_distance > 0 else None)),
        SummaryMetric(label="総給油量", value=_format_fuel(total_fuel if total_fuel > 0 else None)),
        SummaryMetric(label="平均燃費", value=_format_economy(average_economy)),
        SummaryMetric(label="最高燃費", value=_format_economy(max(economy_values) if economy_values else None)),
        SummaryMetric(label="最低燃費", value=_format_economy(min(economy_values) if economy_values else None)),
        SummaryMetric(label="直近燃費", value=_format_economy(latest_economy)),
    ]
