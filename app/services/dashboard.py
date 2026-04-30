from dataclasses import dataclass, asdict
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
    record_cards: list[dict]
    notices: list[str]
    errors: list[str]
    has_records: bool
    form_values: dict[str, str]
    form_errors: dict[str, str]
    form_options: dict[str, list[dict[str, str]]]


SUMMARY_GROUP_DEFINITIONS = [
    {"key": "basic", "label": "基本", "metrics": ["総走行距離", "総給油量", "平均燃費"]},
    {"key": "economy", "label": "燃費", "metrics": ["直近燃費", "最高燃費", "最低燃費"]},
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


def build_home_view_model(
    app_name: str,
    data_dir: Path,
    selected_vehicle_id: str | None,
    form_state: CreateFormState | None = None,
    page_key: str = "home",
    page_title: str = "ホーム",
) -> dict:
    # The selected vehicle is derived from the request query, not server memory.
    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)

    notices = list(catalog.notices)
    errors = list(catalog.errors)
    records = []
    resolved_form_state = form_state or build_record_form_state()

    if catalog.selected_vehicle is not None:
        csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
        csv_result = load_csv_records(csv_path)
        notices.extend(csv_result.notices)
        errors.extend(csv_result.errors)
        records = list(reversed(csv_result.records))

    summary_items = [
        {"label": metric.label, "value": metric.value}
        for metric in build_summary(
            records,
            initial_odd_km=catalog.selected_vehicle.initial_odd_km if catalog.selected_vehicle else 0,
        )
    ]

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
        record_cards=format_record_cards(records),
        notices=notices,
        errors=errors,
        has_records=bool(records),
        form_values=resolved_form_state.values,
        form_errors=resolved_form_state.errors,
        form_options=build_form_options(),
    )
    return asdict(model)
