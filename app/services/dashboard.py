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
    record_cards: list[dict]
    notices: list[str]
    errors: list[str]
    has_records: bool
    form_values: dict[str, str]
    form_errors: dict[str, str]
    form_options: dict[str, list[dict[str, str]]]


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
        summary_items=[
            {"label": metric.label, "value": metric.value}
            for metric in build_summary(
                records,
                initial_odd_km=catalog.selected_vehicle.initial_odd_km if catalog.selected_vehicle else 0,
            )
        ],
        record_cards=format_record_cards(records),
        notices=notices,
        errors=errors,
        has_records=bool(records),
        form_values=resolved_form_state.values,
        form_errors=resolved_form_state.errors,
        form_options=build_form_options(),
    )
    return asdict(model)
