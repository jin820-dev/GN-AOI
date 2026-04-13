import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from app.services.csv_loader import CSV_HEADER


@dataclass(frozen=True)
class VehicleMeta:
    id: str
    label: str
    csv_file: str
    owner: str | None
    enabled: bool
    initial_odd_km: float


@dataclass(frozen=True)
class VehicleCatalog:
    vehicles: list[VehicleMeta]
    selected_vehicle: VehicleMeta | None
    notices: list[str]
    errors: list[str]


@dataclass(frozen=True)
class CreateVehicleResult:
    success: bool
    vehicle_id: str | None
    message: str | None
    error_message: str | None


@dataclass(frozen=True)
class DeleteVehicleResult:
    success: bool
    next_vehicle_id: str | None
    message: str | None
    error_message: str | None


def _normalize_vehicle(item: object) -> VehicleMeta | None:
    if not isinstance(item, dict):
        return None

    vehicle_id = str(item.get("id", "")).strip()
    label = str(item.get("label", "")).strip()
    csv_file = str(item.get("csv_file", "")).strip()
    enabled = bool(item.get("enabled", False))

    if not vehicle_id or not label or not csv_file:
        return None

    owner = item.get("owner")
    owner_value = None if owner in (None, "") else str(owner)
    initial_odd_km = item.get("initial_odd_km", 0)
    try:
        initial_odd_km_value = float(str(initial_odd_km).strip() or "0")
    except ValueError:
        initial_odd_km_value = 0.0

    return VehicleMeta(
        id=vehicle_id,
        label=label,
        csv_file=csv_file,
        owner=owner_value,
        enabled=enabled,
        initial_odd_km=initial_odd_km_value,
    )


def load_vehicle_catalog(data_dir: Path, selected_vehicle_id: str | None) -> VehicleCatalog:
    # Step 2.5 keeps vehicle state reconstructable from disk and URL only.
    config_path = data_dir / "vehicles.json"
    notices: list[str] = []
    errors: list[str] = []

    if not config_path.exists():
        errors.append("vehicles.json が見つかりません。")
        return VehicleCatalog(vehicles=[], selected_vehicle=None, notices=notices, errors=errors)

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("vehicles.json を正しい JSON として読み込めませんでした。")
        return VehicleCatalog(vehicles=[], selected_vehicle=None, notices=notices, errors=errors)

    if not isinstance(payload, list):
        errors.append("vehicles.json は車両メタデータの配列である必要があります。")
        return VehicleCatalog(vehicles=[], selected_vehicle=None, notices=notices, errors=errors)

    vehicles = [vehicle for item in payload if (vehicle := _normalize_vehicle(item)) and vehicle.enabled]

    if not vehicles:
        notices.append("有効な車両がありません。")
        return VehicleCatalog(vehicles=[], selected_vehicle=None, notices=notices, errors=errors)

    selected_vehicle = None
    if selected_vehicle_id:
        selected_vehicle = next((vehicle for vehicle in vehicles if vehicle.id == selected_vehicle_id), None)
        if selected_vehicle is None:
            notices.append("指定された車両が見つからなかったため、先頭の有効車両を表示しています。")

    if selected_vehicle is None:
        selected_vehicle = vehicles[0]

    return VehicleCatalog(
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        notices=notices,
        errors=errors,
    )


def resolve_vehicle_csv_path(data_dir: Path, vehicle: VehicleMeta) -> Path:
    return data_dir / "records" / vehicle.csv_file


def _load_vehicle_payload(config_path: Path) -> tuple[list[dict] | None, str | None]:
    if not config_path.exists():
        return [], None

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "vehicles.json を正しい JSON として読み込めませんでした。"

    if not isinstance(payload, list):
        return None, "vehicles.json は車両メタデータの配列である必要があります。"

    normalized_payload: list[dict] = []
    for item in payload:
        if isinstance(item, dict):
            normalized_payload.append(dict(item))
    return normalized_payload, None


def _slugify_vehicle_id(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug or "vehicle"


def _build_unique_vehicle_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id

    suffix = 2
    while f"{base_id}-{suffix}" in existing_ids:
        suffix += 1
    return f"{base_id}-{suffix}"


def _parse_initial_odd_km(raw_value: str) -> tuple[float | None, str | None]:
    value = raw_value.strip()
    if value == "":
        return 0.0, None

    try:
        decimal_value = Decimal(value)
    except InvalidOperation:
        return None, "初期ODD距離は数値で入力してください。"

    if decimal_value < 0:
        return None, "初期ODD距離に負の値は使えません。"

    if decimal_value > Decimal("9999999.9"):
        return None, "初期ODD距離が大きすぎます。入力値を確認してください。"

    normalized = decimal_value.quantize(Decimal("1.0"), rounding=ROUND_HALF_UP)
    return float(normalized), None


def create_vehicle(data_dir: Path, label_input: str, initial_odd_km_input: str = "") -> CreateVehicleResult:
    label = label_input.strip()
    if not label:
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message="車両名を入力してください。",
        )

    initial_odd_km, initial_odd_km_error = _parse_initial_odd_km(initial_odd_km_input)
    if initial_odd_km_error:
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message=initial_odd_km_error,
        )

    config_path = data_dir / "vehicles.json"
    payload, payload_error = _load_vehicle_payload(config_path)
    if payload_error:
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message=payload_error,
        )

    payload = payload or []
    existing_labels = {
        str(item.get("label", "")).strip().casefold()
        for item in payload
        if isinstance(item, dict)
    }
    if label.casefold() in existing_labels:
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message="すでに存在します。",
        )

    existing_ids = {
        str(item.get("id", "")).strip()
        for item in payload
        if isinstance(item, dict)
    }
    vehicle_id = _build_unique_vehicle_id(_slugify_vehicle_id(label), existing_ids)
    csv_file = f"{vehicle_id}.csv"
    records_dir = data_dir / "records"
    csv_path = records_dir / csv_file

    vehicle_item = {
        "id": vehicle_id,
        "label": label,
        "csv_file": csv_file,
        "owner": None,
        "enabled": True,
        "initial_odd_km": initial_odd_km,
    }

    if csv_path.exists():
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message="同じ CSV 名の車両がすでに存在します。",
        )

    try:
        records_dir.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(",".join(CSV_HEADER) + "\n")

        payload.append(vehicle_item)
        config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        try:
            if csv_path.exists():
                csv_path.unlink()
        except OSError:
            pass
        return CreateVehicleResult(
            success=False,
            vehicle_id=None,
            message=None,
            error_message="車両の保存に失敗しました。",
        )

    return CreateVehicleResult(
        success=True,
        vehicle_id=vehicle_id,
        message="車両を追加しました。",
        error_message=None,
    )


def delete_vehicle(data_dir: Path, vehicle_id: str) -> DeleteVehicleResult:
    target_vehicle_id = vehicle_id.strip()
    if not target_vehicle_id:
        return DeleteVehicleResult(
            success=False,
            next_vehicle_id=None,
            message=None,
            error_message="削除対象の車両を特定できませんでした。",
        )

    config_path = data_dir / "vehicles.json"
    payload, payload_error = _load_vehicle_payload(config_path)
    if payload_error:
        return DeleteVehicleResult(
            success=False,
            next_vehicle_id=None,
            message=None,
            error_message=payload_error,
        )

    payload = payload or []
    target_index = next(
        (index for index, item in enumerate(payload) if str(item.get("id", "")).strip() == target_vehicle_id),
        None,
    )
    if target_index is None:
        return DeleteVehicleResult(
            success=False,
            next_vehicle_id=None,
            message=None,
            error_message="削除対象の車両が見つかりません。",
        )

    enabled_vehicles = [
        vehicle for item in payload
        if (vehicle := _normalize_vehicle(item)) and vehicle.enabled
    ]
    if len(enabled_vehicles) <= 1:
        return DeleteVehicleResult(
            success=False,
            next_vehicle_id=enabled_vehicles[0].id if enabled_vehicles else None,
            message=None,
            error_message="最後の1台は削除できません。",
        )

    target_item = payload[target_index]
    csv_file = str(target_item.get("csv_file", "")).strip()
    csv_path = data_dir / "records" / csv_file if csv_file else None
    next_payload = [item for index, item in enumerate(payload) if index != target_index]
    next_enabled_vehicles = [
        vehicle for item in next_payload
        if (vehicle := _normalize_vehicle(item)) and vehicle.enabled
    ]
    next_vehicle_id = next_enabled_vehicles[0].id if next_enabled_vehicles else None
    original_text = config_path.read_text(encoding="utf-8") if config_path.exists() else "[]\n"

    try:
        config_path.write_text(
            json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return DeleteVehicleResult(
            success=False,
            next_vehicle_id=next_vehicle_id,
            message=None,
            error_message="vehicles.json の更新に失敗しました。",
        )

    if csv_path and csv_path.exists():
        try:
            csv_path.unlink()
        except OSError:
            try:
                config_path.write_text(original_text, encoding="utf-8")
            except OSError:
                pass
            return DeleteVehicleResult(
                success=False,
                next_vehicle_id=target_vehicle_id,
                message=None,
                error_message="関連する CSV を削除できませんでした。",
            )

    return DeleteVehicleResult(
        success=True,
        next_vehicle_id=next_vehicle_id,
        message="車両を削除しました。",
        error_message=None,
    )
