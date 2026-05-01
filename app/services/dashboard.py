from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

from app.services.csv_loader import CSV_HEADER, load_csv_records
from app.services.record_create_service import build_form_options, build_record_form_state, CreateFormState
from app.services.record_formatter import format_record_cards
from app.services.summary_service import build_summary
from app.services.vehicle_service import load_vehicle_catalog, resolve_vehicle_csv_path


@dataclass(frozen=True)
class HomeViewModel:
    app_name: str
    page_key: str
    page_title: str
    csv_header: list[str]
    vehicle_label: str
    owner_label: str
    vehicles: list[dict[str, str]]
    selected_vehicle_id: str | None
    summary_items: list[dict[str, str]]
    summary_groups: list[dict]
    summary_mobile_primary: list[dict[str, str]]
    summary_mobile_details: list[dict[str, str]]
    fuel_economy_chart: dict[str, list]
    fuel_price_chart: dict[str, list]
    monthly_summaries: list[dict[str, str]]
    monthly_summary_groups: list[dict]
    last_record: dict[str, str] | None
    record_cards: list[dict]
    notices: list[str]
    errors: list[str]
    has_records: bool
    form_values: dict[str, str]
    form_errors: dict[str, str]
    form_options: dict[str, list[dict[str, str]]]
    edit_state: dict[str, str] | None


SUMMARY_GROUP_DEFINITIONS = [
    {"key": "basic", "label": "基本", "metrics": ["総走行距離", "総給油量", "平均燃費"]},
    {"key": "economy", "label": "燃費", "metrics": ["直近燃費", "直近5回平均", "最高燃費", "最低燃費"]},
    {
        "key": "fuel-cost",
        "label": "給油・費用",
        "metrics": ["給油回数", "総給油金額", "平均給油金額", "平均燃料単価", "平均給油量"],
    },
    {"key": "vehicle", "label": "車両情報", "metrics": ["初期ODD", "現在ODD", "直近給油日"]},
]

SUMMARY_MOBILE_PRIMARY_LABELS = ["直近燃費", "平均燃費", "最高燃費"]
SUMMARY_MOBILE_DETAIL_LABELS = [
    "総走行距離",
    "総給油量",
    "直近5回平均",
    "最低燃費",
    "給油回数",
    "総給油金額",
    "平均給油金額",
    "平均燃料単価",
    "平均給油量",
    "初期ODD",
    "現在ODD",
    "直近給油日",
]


def _build_summary_groups(summary_items: list[dict[str, str]]) -> list[dict]:
    items_by_label = {item["label"]: item for item in summary_items}
    return [
        {
            "key": group["key"],
            "label": group["label"],
            "metrics": [
                items_by_label[label]
                for label in group["metrics"]
                if label in items_by_label
            ],
        }
        for group in SUMMARY_GROUP_DEFINITIONS
    ]


def _split_value_unit(value: str) -> dict[str, str]:
    if value == "-":
        return {"value_main": value, "value_unit": ""}

    main, separator, unit = value.partition(" ")
    if not separator:
        return {"value_main": value, "value_unit": ""}
    return {"value_main": main, "value_unit": unit}


def _pick_summary_items(summary_items: list[dict[str, str]], labels: list[str], *, split_value: bool = False) -> list[dict[str, str]]:
    items_by_label = {item["label"]: item for item in summary_items}
    picked_items = []
    for label in labels:
        item = items_by_label.get(label)
        if item is None:
            continue
        picked_item = dict(item)
        if split_value:
            picked_item.update(_split_value_unit(picked_item["value"]))
        picked_items.append(picked_item)
    return picked_items


def _build_fuel_economy_chart(records: list) -> dict[str, list]:
    points = []
    cumulative_distance = 0
    cumulative_fuel = 0

    for record in reversed(records):
        if record.economy_km_l is None or record.trip_km_value is None or record.fuel_l_value is None:
            continue

        cumulative_distance += record.trip_km_value
        cumulative_fuel += record.fuel_l_value
        if cumulative_fuel <= 0:
            continue

        points.append(
            {
                "label": record.date,
                "value": record.economy_km_l,
                "average_value": round(cumulative_distance / cumulative_fuel, 2),
            }
        )

    return {
        "labels": [point["label"] for point in points],
        "values": [point["value"] for point in points],
        "average_values": [point["average_value"] for point in points],
    }


def _build_fuel_price_chart(records: list) -> dict[str, list]:
    points = [
        {
            "label": record.date,
            "value": round(record.price_yen_value / record.fuel_l_value, 1),
        }
        for record in reversed(records)
        if record.price_yen_value is not None and record.fuel_l_value is not None and record.fuel_l_value > 0
    ]
    return {
        "labels": [point["label"] for point in points],
        "values": [point["value"] for point in points],
    }


def _build_monthly_summaries(records: list) -> list[dict[str, str]]:
    monthly: dict[str, dict] = {}

    for record in records:
        if len(record.date) < 7:
            continue

        month = record.date[:7]
        bucket = monthly.setdefault(
            month,
            {
                "total_fuel_l": 0,
                "total_price_yen": 0,
                "total_trip_km": 0,
                "fuel_count": 0,
                "economy_values": [],
            },
        )

        bucket["fuel_count"] += 1
        if record.fuel_l_value is not None:
            bucket["total_fuel_l"] += record.fuel_l_value
        if record.price_yen_value is not None:
            bucket["total_price_yen"] += record.price_yen_value
        if record.trip_km_value is not None:
            bucket["total_trip_km"] += record.trip_km_value
        if record.economy_km_l is not None:
            bucket["economy_values"].append(record.economy_km_l)

    summaries = []
    for month in sorted(monthly.keys(), reverse=True):
        bucket = monthly[month]
        economy_values = bucket["economy_values"]
        average_economy = sum(economy_values) / len(economy_values) if economy_values else None
        summaries.append(
            {
                "month": month,
                "year": month[:4],
                "total_fuel_l": f"{round(bucket['total_fuel_l'], 2):.2f} L",
                "total_price_yen": f"{round(bucket['total_price_yen']):.0f} 円",
                "fuel_count": f"{bucket['fuel_count']} 回",
                "total_trip_km": f"{round(bucket['total_trip_km'], 1):.1f} km",
                "average_economy_km_l": "-" if average_economy is None else f"{round(average_economy, 2):.2f} km/L",
            }
        )

    return summaries


def _build_monthly_summary_groups(monthly_summaries: list[dict[str, str]]) -> list[dict]:
    groups: list[dict] = []
    for summary in monthly_summaries:
        if not groups or groups[-1]["year"] != summary["year"]:
            groups.append({"year": summary["year"], "months": []})
        groups[-1]["months"].append(summary)
    return groups


def _build_last_record(records: list) -> dict[str, str] | None:
    if not records:
        return None

    record = records[0]
    return {
        "odd_km": record.odd_km,
        "price_yen": record.price_yen,
        "fuel_type": record.fuel_type,
        "distance_mode": record.distance_mode,
    }


def _build_initial_form_state(last_record: dict[str, str] | None) -> CreateFormState:
    values = {"date": date.today().isoformat()}
    if last_record:
        values.update(
            {
                "fuel_type": last_record["fuel_type"],
                "distance_mode": last_record["distance_mode"],
            }
        )
    return build_record_form_state(values=values)


def _is_economy_anomaly(economy_km_l: float | None, average_economy: float | None) -> bool:
    if economy_km_l is None or average_economy is None or average_economy <= 0:
        return False
    return abs(economy_km_l - average_economy) / average_economy >= 0.20


def _format_record_cards(records: list) -> list[dict]:
    total_distance = sum(record.trip_km_value for record in records if record.trip_km_value is not None)
    total_fuel = sum(record.fuel_l_value for record in records if record.fuel_l_value is not None)
    average_economy = total_distance / total_fuel if total_distance > 0 and total_fuel > 0 else None
    cards = format_record_cards(records)

    for card, record in zip(cards, records):
        card["is_economy_anomaly"] = _is_economy_anomaly(record.economy_km_l, average_economy)

    return cards


def build_home_view_model(
    app_name: str,
    data_dir: Path,
    selected_vehicle_id: str | None,
    form_state: CreateFormState | None = None,
    edit_state: dict[str, str] | None = None,
    page_key: str = "home",
    page_title: str = "ホーム",
) -> dict:
    # The selected vehicle is derived from the request query, not server memory.
    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)

    notices = list(catalog.notices)
    errors = list(catalog.errors)
    records = []

    if catalog.selected_vehicle is not None:
        csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
        csv_result = load_csv_records(csv_path)
        notices.extend(csv_result.notices)
        errors.extend(csv_result.errors)
        records = list(reversed(csv_result.records))

    last_record = _build_last_record(records)
    resolved_form_state = form_state or _build_initial_form_state(last_record)

    summary_items = [
        {"label": metric.label, "value": metric.value}
        for metric in build_summary(
            records,
            initial_odd_km=catalog.selected_vehicle.initial_odd_km if catalog.selected_vehicle else 0,
        )
    ]
    monthly_summaries = _build_monthly_summaries(records)

    model = HomeViewModel(
        app_name=app_name,
        page_key=page_key,
        page_title=page_title,
        csv_header=CSV_HEADER,
        vehicle_label=catalog.selected_vehicle.label if catalog.selected_vehicle else "利用不可",
        owner_label="今後対応予定",
        vehicles=[
            {"id": vehicle.id, "label": vehicle.label}
            for vehicle in catalog.vehicles
        ],
        selected_vehicle_id=catalog.selected_vehicle.id if catalog.selected_vehicle else None,
        summary_items=summary_items,
        summary_groups=_build_summary_groups(summary_items),
        summary_mobile_primary=_pick_summary_items(summary_items, SUMMARY_MOBILE_PRIMARY_LABELS, split_value=True),
        summary_mobile_details=_pick_summary_items(summary_items, SUMMARY_MOBILE_DETAIL_LABELS),
        fuel_economy_chart=_build_fuel_economy_chart(records),
        fuel_price_chart=_build_fuel_price_chart(records),
        monthly_summaries=monthly_summaries,
        monthly_summary_groups=_build_monthly_summary_groups(monthly_summaries),
        last_record=last_record,
        record_cards=_format_record_cards(records),
        notices=notices,
        errors=errors,
        has_records=bool(records),
        form_values=resolved_form_state.values,
        form_errors=resolved_form_state.errors,
        form_options=build_form_options(),
        edit_state=edit_state,
    )
    return asdict(model)
