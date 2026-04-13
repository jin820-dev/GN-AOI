import csv
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.services.csv_loader import CSV_HEADER, CsvRecord
from app.services.record_create_service import finalize_record_input


@dataclass(frozen=True)
class ImportRecordsResult:
    success: bool
    imported_count: int
    message: str | None
    error_message: str | None
    error_details: list[str]


def _build_latest_record(row_number: int, row: dict[str, str]) -> CsvRecord:
    fuel_l_value = float(row["fuel_l"]) if row["fuel_l"] else None
    price_yen_value = float(row["price_yen"]) if row["price_yen"] else None
    trip_km_value = float(row["trip_km"]) if row["trip_km"] else None
    odd_km_value = float(row["odd_km"]) if row["odd_km"] else None
    economy_km_l = None
    if trip_km_value and fuel_l_value and fuel_l_value > 0:
        economy_km_l = trip_km_value / fuel_l_value

    return CsvRecord(
        row_id=f"import-{row_number}",
        row_number=row_number,
        date=row["date"],
        time=row["time"],
        fuel_l=row["fuel_l"],
        price_yen=row["price_yen"],
        trip_km=row["trip_km"],
        odd_km=row["odd_km"],
        full=row["full"],
        distance_mode=row["distance_mode"],
        fuel_type=row["fuel_type"],
        note=row["note"],
        fuel_l_value=fuel_l_value,
        price_yen_value=price_yen_value,
        trip_km_value=trip_km_value,
        odd_km_value=odd_km_value,
        economy_km_l=economy_km_l,
    )


def _is_blank_row(row: dict[str, str]) -> bool:
    return all((row.get(column, "") or "").strip() == "" for column in CSV_HEADER)


def import_records(csv_path: Path, source_bytes: bytes) -> ImportRecordsResult:
    if not source_bytes:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="CSV ファイルを選択してください。",
            error_details=[],
        )

    try:
        text = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="UTF-8 の CSV ファイルを指定してください。",
            error_details=[],
        )

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
    except csv.Error:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="CSV を読み込めませんでした。",
            error_details=[],
        )

    fieldnames = reader.fieldnames or []
    if fieldnames != CSV_HEADER:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="CSV ヘッダが不正です。GN-AOI 互換の固定ヘッダを指定してください。",
            error_details=[],
        )

    normalized_rows: list[dict[str, str]] = []
    error_details: list[str] = []
    latest_record: CsvRecord | None = None

    for row_number, row in enumerate(reader, start=2):
        normalized_row = {column: (row.get(column, "") or "").strip() for column in CSV_HEADER}
        if _is_blank_row(normalized_row):
            continue

        finalized, errors = finalize_record_input(normalized_row, latest_record)
        if errors:
            joined_errors = " / ".join(f"{label}: {message}" for label, message in errors.items())
            error_details.append(f"{row_number} 行目: {joined_errors}")
            continue

        normalized_rows.append(finalized)
        latest_record = _build_latest_record(row_number, finalized)

    if error_details:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="不正なデータが含まれているため、インポートを中止しました。",
            error_details=error_details,
        )

    if not normalized_rows:
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="有効なデータ行がありません。",
            error_details=[],
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=csv_path.parent) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writeheader()
            for row in normalized_rows:
                writer.writerow(row)
        temp_path.replace(csv_path)
    except OSError:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return ImportRecordsResult(
            success=False,
            imported_count=0,
            message=None,
            error_message="CSV の保存に失敗しました。",
            error_details=[],
        )

    return ImportRecordsResult(
        success=True,
        imported_count=len(normalized_rows),
        message=f"{len(normalized_rows)} 件の記録をインポートしました。",
        error_message=None,
        error_details=[],
    )
