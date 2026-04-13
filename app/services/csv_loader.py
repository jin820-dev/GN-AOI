import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

CSV_HEADER = [
    "date",
    "time",
    "fuel_l",
    "price_yen",
    "trip_km",
    "odd_km",
    "full",
    "distance_mode",
    "fuel_type",
    "note",
]


@dataclass(frozen=True)
class CsvRecord:
    row_id: str
    row_number: int
    date: str
    time: str
    fuel_l: str
    price_yen: str
    trip_km: str
    odd_km: str
    full: str
    distance_mode: str
    fuel_type: str
    note: str
    fuel_l_value: float | None
    price_yen_value: float | None
    trip_km_value: float | None
    odd_km_value: float | None
    economy_km_l: float | None


@dataclass(frozen=True)
class CsvLoadResult:
    records: list[CsvRecord]
    notices: list[str]
    errors: list[str]
    header_valid: bool


def _to_float(value: str) -> float | None:
    cleaned = value.strip()
    if cleaned == "":
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_row_id(csv_path: Path, row_number: int, row: dict[str, str]) -> str:
    joined = "|".join(row.get(column, "") for column in CSV_HEADER)
    digest = hashlib.sha1(f"{csv_path.name}:{row_number}:{joined}".encode("utf-8")).hexdigest()
    return digest[:12]


def _normalize_row(csv_path: Path, row_number: int, row: dict[str, str]) -> CsvRecord:
    fuel_l_value = _to_float(row.get("fuel_l", ""))
    price_yen_value = _to_float(row.get("price_yen", ""))
    trip_km_value = _to_float(row.get("trip_km", ""))
    odd_km_value = _to_float(row.get("odd_km", ""))

    economy_km_l = None
    if trip_km_value and fuel_l_value and fuel_l_value > 0:
        economy_km_l = trip_km_value / fuel_l_value

    return CsvRecord(
        row_id=_build_row_id(csv_path, row_number, row),
        row_number=row_number,
        date=row.get("date", "").strip(),
        time=row.get("time", "").strip(),
        fuel_l=row.get("fuel_l", "").strip(),
        price_yen=row.get("price_yen", "").strip(),
        trip_km=row.get("trip_km", "").strip(),
        odd_km=row.get("odd_km", "").strip(),
        full=row.get("full", "").strip(),
        distance_mode=row.get("distance_mode", "").strip(),
        fuel_type=row.get("fuel_type", "").strip(),
        note=row.get("note", "").strip(),
        fuel_l_value=fuel_l_value,
        price_yen_value=price_yen_value,
        trip_km_value=trip_km_value,
        odd_km_value=odd_km_value,
        economy_km_l=economy_km_l,
    )


def load_csv_records(csv_path: Path) -> CsvLoadResult:
    # Records are reloaded from CSV for each request so Flask restarts do not lose state.
    notices: list[str] = []
    errors: list[str] = []

    if not csv_path.exists():
        errors.append(f"CSV ファイルが見つかりません: {csv_path.name}")
        return CsvLoadResult(records=[], notices=notices, errors=errors, header_valid=False)

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []

            if fieldnames != CSV_HEADER:
                errors.append("CSV ヘッダが不正です。GN-AOI 互換の固定ヘッダを期待しています。")
                return CsvLoadResult(
                    records=[],
                    notices=notices,
                    errors=errors,
                    header_valid=False,
                )

            records: list[CsvRecord] = []
            skipped_rows = 0

            for row_number, row in enumerate(reader, start=2):
                try:
                    records.append(_normalize_row(csv_path, row_number, row))
                except Exception:
                    skipped_rows += 1

    except OSError:
        errors.append(f"CSV ファイルを開けませんでした: {csv_path.name}")
        return CsvLoadResult(records=[], notices=notices, errors=errors, header_valid=False)

    if skipped_rows:
        notices.append(f"正規化できない行が {skipped_rows} 件あったためスキップしました。")

    if not records:
        notices.append("選択中の車両には表示できる記録がありません。")

    return CsvLoadResult(records=records, notices=notices, errors=errors, header_valid=True)


def get_latest_record(csv_path: Path) -> CsvRecord | None:
    # GN-AOI treats the CSV tail as the latest record for append-time completion.
    result = load_csv_records(csv_path)
    if not result.header_valid or not result.records:
        return None
    return result.records[-1]
