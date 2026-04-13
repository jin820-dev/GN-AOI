import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.csv_loader import CSV_HEADER, CsvRecord, load_csv_records


@dataclass(frozen=True)
class DeleteRecordResult:
    success: bool
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


def delete_record(csv_path: Path, record_index: int) -> DeleteRecordResult:
    load_result = load_csv_records(csv_path)
    if not load_result.header_valid:
        return DeleteRecordResult(
            success=False,
            message=None,
            error_message="削除対象 CSV のヘッダが不正なため削除できません。",
        )

    records = list(load_result.records)
    if record_index < 0 or record_index >= len(records):
        return DeleteRecordResult(
            success=False,
            message=None,
            error_message="削除対象の記録が見つかりませんでした。",
        )

    remaining_records = [record for index, record in enumerate(records) if index != record_index]

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=csv_path.parent) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writeheader()
            for record in remaining_records:
                writer.writerow(_record_to_row(record))

        temp_path.replace(csv_path)
    except OSError:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return DeleteRecordResult(
            success=False,
            message=None,
            error_message="CSV の再保存に失敗したため、削除を完了できませんでした。",
        )

    return DeleteRecordResult(
        success=True,
        message="記録を削除しました。",
        error_message=None,
    )
