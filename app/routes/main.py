import csv
import io
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_file, url_for

from app.services.data_reset_service import reset_all_data
from app.services.csv_loader import load_csv_records
from app.services.dashboard import build_home_view_model, build_monthly_summary_csv_rows
from app.services.record_create_service import create_record
from app.services.record_delete_service import delete_record
from app.services.record_import_service import import_records
from app.services.record_update_service import update_record
from app.services.vehicle_service import create_vehicle, delete_vehicle, load_vehicle_catalog, resolve_vehicle_csv_path

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home():
    data_dir = Path(current_app.config["DATA_DIR"])
    view_model = build_home_view_model(
        app_name=current_app.config["APP_NAME"],
        data_dir=data_dir,
        selected_vehicle_id=request.args.get("vehicle"),
        page_key="home",
        page_title="ホーム",
    )
    return render_template("home.html", **view_model)


@main_bp.get("/records")
def records():
    data_dir = Path(current_app.config["DATA_DIR"])
    view_model = build_home_view_model(
        app_name=current_app.config["APP_NAME"],
        data_dir=data_dir,
        selected_vehicle_id=request.args.get("vehicle"),
        page_key="records",
        page_title="記録",
    )
    return render_template("records.html", **view_model)


@main_bp.get("/settings")
def settings():
    data_dir = Path(current_app.config["DATA_DIR"])
    view_model = build_home_view_model(
        app_name=current_app.config["APP_NAME"],
        data_dir=data_dir,
        selected_vehicle_id=request.args.get("vehicle"),
        page_key="settings",
        page_title="設定",
    )
    return render_template("settings.html", **view_model)


@main_bp.post("/records")
def create_record_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")

    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)
    if catalog.selected_vehicle is None:
        view_model = build_home_view_model(
            app_name=current_app.config["APP_NAME"],
            data_dir=data_dir,
            selected_vehicle_id=selected_vehicle_id,
            page_key="records",
            page_title="記録",
        )
        view_model["errors"].append("追加対象の車両を特定できませんでした。")
        return render_template("records.html", **view_model), 400

    form_input = {key: request.form.get(key, "") for key in current_app.config["CSV_HEADER"]}
    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    result = create_record(csv_path=csv_path, form_input=form_input)

    if result.success:
        flash(result.message or "記録を追加しました。", "success")
        return redirect(url_for("main.records", vehicle=catalog.selected_vehicle.id))

    view_model = build_home_view_model(
        app_name=current_app.config["APP_NAME"],
        data_dir=data_dir,
        selected_vehicle_id=catalog.selected_vehicle.id,
        form_state=result.form_state,
        page_key="records",
        page_title="記録",
    )
    if result.error_message:
        view_model["errors"].append(result.error_message)
    return render_template("records.html", **view_model), 400


@main_bp.post("/records/delete")
def delete_record_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")

    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)
    if catalog.selected_vehicle is None:
        flash("削除対象の車両を特定できませんでした。", "error")
        return redirect(url_for("main.records", vehicle=selected_vehicle_id) if selected_vehicle_id else url_for("main.records"))

    record_index_raw = request.form.get("record_index", "").strip()
    try:
        record_index = int(record_index_raw)
    except ValueError:
        flash("削除対象の記録インデックスが不正です。", "error")
        return redirect(url_for("main.records", vehicle=catalog.selected_vehicle.id))

    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    result = delete_record(csv_path=csv_path, record_index=record_index)

    if result.success:
        flash(result.message or "記録を削除しました。", "success")
    else:
        flash(result.error_message or "記録を削除できませんでした。", "error")

    return redirect(url_for("main.records", vehicle=catalog.selected_vehicle.id))


@main_bp.post("/records/update")
def update_record_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")

    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)
    if catalog.selected_vehicle is None:
        flash("編集対象の車両を特定できませんでした。", "error")
        return redirect(url_for("main.records", vehicle=selected_vehicle_id) if selected_vehicle_id else url_for("main.records"))

    record_index_raw = request.form.get("record_index", "").strip()
    try:
        record_index = int(record_index_raw)
    except ValueError:
        flash("編集対象の記録インデックスが不正です。", "error")
        return redirect(url_for("main.records", vehicle=catalog.selected_vehicle.id))

    form_input = {key: request.form.get(key, "") for key in current_app.config["CSV_HEADER"]}
    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    result = update_record(
        csv_path=csv_path,
        record_index=record_index,
        row_id=request.form.get("row_id", "").strip(),
        form_input=form_input,
    )

    if result.success:
        flash(result.message or "記録を更新しました。", "success")
        return redirect(url_for("main.records", vehicle=catalog.selected_vehicle.id))

    view_model = build_home_view_model(
        app_name=current_app.config["APP_NAME"],
        data_dir=data_dir,
        selected_vehicle_id=catalog.selected_vehicle.id,
        form_state=result.form_state,
        edit_state={
            "record_index": record_index_raw,
            "row_id": request.form.get("row_id", "").strip(),
        },
        page_key="records",
        page_title="記録",
    )
    if result.error_message:
        view_model["errors"].append(result.error_message)
    return render_template("records.html", **view_model), 400


@main_bp.post("/settings/import")
def import_records_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")
    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)

    if catalog.selected_vehicle is None:
        flash("インポート先の車両を特定できませんでした。", "error")
        return redirect(url_for("main.settings"))

    upload = request.files.get("csv_file")
    source_bytes = upload.read() if upload else b""
    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    result = import_records(csv_path=csv_path, source_bytes=source_bytes)

    if result.success:
        flash(result.message or "記録をインポートしました。", "success")
    else:
        flash(result.error_message or "記録をインポートできませんでした。", "error")
        for detail in result.error_details[:5]:
            flash(detail, "error")
        if len(result.error_details) > 5:
            flash(f"ほか {len(result.error_details) - 5} 件のエラーがあります。", "error")

    return redirect(url_for("main.settings", vehicle=catalog.selected_vehicle.id))


@main_bp.get("/settings/export")
def export_records_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle")
    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)

    if catalog.selected_vehicle is None:
        flash("エクスポート対象の車両を特定できませんでした。", "error")
        return redirect(url_for("main.settings"))

    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    download_name = f"gnaoi-{catalog.selected_vehicle.id}.csv"

    if csv_path.exists():
        return send_file(
            csv_path,
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=download_name,
        )

    header = ",".join(current_app.config["CSV_HEADER"]) + "\n"
    return Response(
        header,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


@main_bp.get("/settings/export/monthly-summary")
def export_monthly_summary_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle")
    catalog = load_vehicle_catalog(data_dir=data_dir, selected_vehicle_id=selected_vehicle_id)

    if catalog.selected_vehicle is None:
        flash("エクスポート対象の車両を特定できませんでした。", "error")
        return redirect(url_for("main.home"))

    csv_path = resolve_vehicle_csv_path(data_dir=data_dir, vehicle=catalog.selected_vehicle)
    csv_result = load_csv_records(csv_path)
    records = list(reversed(csv_result.records)) if csv_result.header_valid else []
    rows = build_monthly_summary_csv_rows(records)

    output = io.StringIO()
    fieldnames = [
        "month",
        "total_price_yen",
        "total_fuel_l",
        "fuel_count",
        "total_trip_km",
        "average_economy_km_l",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    download_name = f"gnaoi_monthly_summary_{catalog.selected_vehicle.id}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


@main_bp.post("/settings/vehicles")
def create_vehicle_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    result = create_vehicle(
        data_dir=data_dir,
        label_input=request.form.get("label", ""),
        initial_odd_km_input=request.form.get("initial_odd_km", ""),
    )

    if result.success and result.vehicle_id:
        flash(result.message or "車両を追加しました。", "success")
        return redirect(url_for("main.home", vehicle=result.vehicle_id))

    flash(result.error_message or "車両を追加できませんでした。", "error")
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")
    return redirect(url_for("main.settings", vehicle=selected_vehicle_id) if selected_vehicle_id else url_for("main.settings"))


@main_bp.post("/settings/vehicles/delete")
def delete_vehicle_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")
    result = delete_vehicle(data_dir=data_dir, vehicle_id=request.form.get("vehicle_id", ""))

    if result.success:
        flash(result.message or "車両を削除しました。", "success")
        if result.next_vehicle_id:
            return redirect(url_for("main.home", vehicle=result.next_vehicle_id))
        return redirect(url_for("main.settings"))

    flash(result.error_message or "車両を削除できませんでした。", "error")
    fallback_vehicle_id = result.next_vehicle_id or selected_vehicle_id
    return redirect(url_for("main.settings", vehicle=fallback_vehicle_id) if fallback_vehicle_id else url_for("main.settings"))


@main_bp.post("/settings/reset")
def reset_data_entry():
    data_dir = Path(current_app.config["DATA_DIR"])
    result = reset_all_data(data_dir=data_dir)

    if result.success:
        flash(result.message or "初期化しました。", "success")
        return redirect(url_for("main.settings"))

    flash(result.error_message or "初期化できませんでした。", "error")
    selected_vehicle_id = request.args.get("vehicle") or request.form.get("vehicle")
    return redirect(url_for("main.settings", vehicle=selected_vehicle_id) if selected_vehicle_id else url_for("main.settings"))
