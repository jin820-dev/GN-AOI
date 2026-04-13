import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from app.services.csv_loader import CSV_HEADER, CsvLoadResult, CsvRecord, get_latest_record, load_csv_records

FULL_OPTIONS = ("yes", "no")
FUEL_TYPE_OPTIONS = ("regular", "high_octane", "diesel")


@dataclass(frozen=True)
class CreateFormState:
    values: dict[str, str]
    errors: dict[str, str]


@dataclass(frozen=True)
class CreateRecordResult:
    success: bool
    form_state: CreateFormState
    message: str | None
    error_message: str | None


def build_record_form_state(values: dict[str, str] | None = None, errors: dict[str, str] | None = None) -> CreateFormState:
    defaults = {
        "date": "",
        "time": "",
        "fuel_l": "",
        "price_yen": "",
        "trip_km": "",
        "odd_km": "",
        "full": "yes",
        "fuel_type": "regular",
        "note": "",
    }
    if values:
        defaults.update({key: str(value) for key, value in values.items() if key in defaults})

    return CreateFormState(values=defaults, errors=errors or {})


def build_form_options() -> dict[str, list[dict[str, str]]]:
    return {
        "full": [
            {"value": "yes", "label": "yes"},
            {"value": "no", "label": "no"},
        ],
        "fuel_type": [
            {"value": "regular", "label": "regular"},
            {"value": "high_octane", "label": "high_octane"},
            {"value": "diesel", "label": "diesel"},
        ],
    }


def _parse_decimal(raw_value: str, *, max_decimals: int, allow_zero: bool, label: str, required: bool = True) -> tuple[str | None, str | None]:
    value = raw_value.strip()
    if value == "":
        if required:
            return None, f"{label}を入力してください。"
        return "", None

    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None, f"{label}は数値で入力してください。"

    if decimal_value < 0:
        return None, f"{label}に負の値は使えません。"

    if not allow_zero and decimal_value == 0:
        return None, f"{label}は 0 より大きい値を入力してください。"

    quantizer = Decimal("1") if max_decimals == 0 else Decimal(f"1.{'0' * max_decimals}")
    normalized = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
    return format(normalized, f".{max_decimals}f"), None


def _validate_choice(value: str, choices: tuple[str, ...], label: str) -> str | None:
    normalized = value.strip()
    if normalized not in choices:
        return f"{label}の選択が不正です。"
    return None


def _quantize_one_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("1.0"), rounding=ROUND_HALF_UP), ".1f")


def _complete_distance_fields(normalized: dict[str, str], latest_record: CsvRecord | None) -> tuple[dict[str, str], dict[str, str], str]:
    errors: dict[str, str] = {}

    trip_input_exists = normalized["trip_km"] != ""
    odd_input_exists = normalized["odd_km"] != ""
    input_mode = "trip" if trip_input_exists else "odd"

    if trip_input_exists and not odd_input_exists and latest_record and latest_record.odd_km_value is not None:
        completed_odd = Decimal(str(latest_record.odd_km_value)) + Decimal(normalized["trip_km"])
        normalized["odd_km"] = _quantize_one_decimal(completed_odd)

    if odd_input_exists and not trip_input_exists and latest_record and latest_record.odd_km_value is not None:
        completed_trip = Decimal(normalized["odd_km"]) - Decimal(str(latest_record.odd_km_value))
        if completed_trip <= 0:
            errors["odd_km"] = "積算距離が前回記録以下です。入力値を確認してください。"
        else:
            normalized["trip_km"] = _quantize_one_decimal(completed_trip)

    return normalized, errors, input_mode


def _validate_record_input(form_input: dict[str, str]) -> tuple[dict[str, str] | None, dict[str, str]]:
    errors: dict[str, str] = {}
    normalized = {column: form_input.get(column, "").strip() for column in CSV_HEADER}

    for field_name, label in (("date", "日付"), ("time", "時刻")):
        if normalized[field_name] == "":
            errors[field_name] = f"{label}を入力してください。"

    fuel_l, fuel_l_error = _parse_decimal(normalized["fuel_l"], max_decimals=2, allow_zero=False, label="給油量")
    if fuel_l_error:
        errors["fuel_l"] = fuel_l_error
    else:
        normalized["fuel_l"] = fuel_l

    price_yen, price_error = _parse_decimal(normalized["price_yen"], max_decimals=0, allow_zero=False, label="価格")
    if price_error:
        errors["price_yen"] = price_error
    else:
        normalized["price_yen"] = price_yen

    trip_km, trip_error = _parse_decimal(
        normalized["trip_km"],
        max_decimals=1,
        allow_zero=False,
        label="区間距離",
        required=False,
    )
    if trip_error:
        errors["trip_km"] = trip_error
    else:
        normalized["trip_km"] = trip_km

    odd_km, odd_error = _parse_decimal(
        normalized["odd_km"],
        max_decimals=1,
        allow_zero=True,
        label="積算距離",
        required=False,
    )
    if odd_error:
        errors["odd_km"] = odd_error
    else:
        normalized["odd_km"] = odd_km

    if normalized["trip_km"] == "" and normalized["odd_km"] == "":
        distance_error = "区間距離または積算距離のどちらかを入力してください。"
        errors["trip_km"] = distance_error
        errors["odd_km"] = distance_error

    if "fuel_l" not in errors and normalized["fuel_l"] and Decimal(normalized["fuel_l"]) > Decimal("200"):
        errors["fuel_l"] = "給油量が大きすぎます。入力値を確認してください。"

    if "trip_km" not in errors and normalized["trip_km"] and Decimal(normalized["trip_km"]) > Decimal("3000"):
        errors["trip_km"] = "区間距離が大きすぎます。入力値を確認してください。"

    if "odd_km" not in errors and normalized["odd_km"] and Decimal(normalized["odd_km"]) > Decimal("9999999.9"):
        errors["odd_km"] = "積算距離が大きすぎます。入力値を確認してください。"

    full_error = _validate_choice(normalized["full"], FULL_OPTIONS, "満タン")
    if full_error:
        errors["full"] = full_error

    fuel_type_error = _validate_choice(normalized["fuel_type"], FUEL_TYPE_OPTIONS, "油種")
    if fuel_type_error:
        errors["fuel_type"] = fuel_type_error

    normalized["note"] = normalized["note"].strip()

    if errors:
        return None, errors

    return normalized, {}


def _finalize_record_data(form_input: dict[str, str], latest_record: CsvRecord | None) -> tuple[dict[str, str] | None, dict[str, str]]:
    normalized, errors = _validate_record_input(form_input)
    if errors:
        return None, errors

    completed, completion_errors, input_mode = _complete_distance_fields(normalized, latest_record)
    if completion_errors:
        return None, completion_errors

    if completed["trip_km"] and Decimal(completed["trip_km"]) > Decimal("3000"):
        return None, {"trip_km": "区間距離が大きすぎます。入力値を確認してください。"}

    if completed["odd_km"] and Decimal(completed["odd_km"]) > Decimal("9999999.9"):
        return None, {"odd_km": "積算距離が大きすぎます。入力値を確認してください。"}

    completed["distance_mode"] = input_mode
    return completed, {}


def finalize_record_input(form_input: dict[str, str], latest_record: CsvRecord | None) -> tuple[dict[str, str] | None, dict[str, str]]:
    return _finalize_record_data(form_input, latest_record)


def _append_csv_row(csv_path: Path, row: dict[str, str]) -> str | None:
    csv_result: CsvLoadResult = load_csv_records(csv_path)
    if not csv_result.header_valid:
        return "追記先 CSV のヘッダが不正なため保存できません。"

    try:
        with csv_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
            writer.writerow({column: row.get(column, "") for column in CSV_HEADER})
    except OSError:
        return "CSV への書き込みに失敗しました。"

    return None


def create_record(csv_path: Path, form_input: dict[str, str]) -> CreateRecordResult:
    latest_record = get_latest_record(csv_path)
    normalized, errors = finalize_record_input(form_input, latest_record)
    if errors:
        return CreateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input, errors=errors),
            message=None,
            error_message="入力内容を確認してください。",
        )

    write_error = _append_csv_row(csv_path, normalized)
    if write_error:
        return CreateRecordResult(
            success=False,
            form_state=build_record_form_state(values=form_input),
            message=None,
            error_message=write_error,
        )

    return CreateRecordResult(
        success=True,
        form_state=build_record_form_state(),
        message="記録を追加しました。",
        error_message=None,
    )
