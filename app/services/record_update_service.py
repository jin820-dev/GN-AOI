import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.csv_loader import CSV_HEADER, CsvRecord, load_csv_records
from app.services.record_create_service import CreateFormState, build_record_form_state, finalize_record_input


@dataclass(frozen=True)
class UpdateRecordResult:
    success: bool
    form_state: CreateFormState
    message: str | None
    error_message: str | None


def _record_to_row(record: CsvRecord) -> dict[str, str]:
    return {
        "date": record.date,
        "time": record.time,
        "fuel_l": record.fuel_l,
        "price_yen": record.price_yen,
        "trip_km": record.trip_km,
        "odd_km": record.odd_km,
        "full": record.full,
        "distance_mode": record.distance_mode,
        "fuel_type": record.fuel_type,
        "note": record.note,
    }


def _write_records(csv_path: Path, records: list[dict[str, str]]) -> str | None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=csv_path.parent) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writeheader()
            for row in records:
                writer.writerow({column: row.get(column, "") for column in CSV_HEADER})

        temp_path.replace(csv_path)
    except OSError:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return "CSV の再保存に失敗したため、編集を完了できませんでした。"

    return None


def update_record(csv_path: Path, record_index: int, row_id: str, form_input: dict[str, str]) -> UpdateRecordResult:
    load_result = load_csv_records(csv_path)
    if not load_result.header_valid:
        return UpdateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input),
            message=None,
            error_message="編集対象 CSV のヘッダが不正なため保存できません。",
        )

    records = list(load_result.records)
    if record_index < 0 or record_index >= len(records):
        return UpdateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input),
            message=None,
            error_message="編集対象の記録が見つかりませんでした。",
        )

    target_record = records[record_index]
    if row_id and row_id != target_record.row_id:
        return UpdateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input),
            message=None,
            error_message="編集対象の記録が更新されています。画面を再読み込みしてから再度編集してください。",
        )

    previous_record = records[record_index - 1] if record_index > 0 else None
    normalized, errors = finalize_record_input(form_input, previous_record)
    if errors:
        return UpdateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input, errors=errors),
            message=None,
            error_message="入力内容を確認してください。",
        )

    rows = [
        normalized if index == record_index else _record_to_row(record)
        for index, record in enumerate(records)
    ]
    write_error = _write_records(csv_path, rows)
    if write_error:
        return UpdateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input),
            message=None,
            error_message=write_error,
        )

    return UpdateRecordResult(
        success=True,
        form_state=build_record_form_state(),
        message="記録を更新しました。",
        error_message=None,
    )
