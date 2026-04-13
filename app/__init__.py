from pathlib import Path

from flask import Flask

from app.routes.main import main_bp


def create_app(instance_path: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    instance_dir = Path(app.instance_path)
    records_dir = instance_dir / "records"
    vehicles_path = instance_dir / "vehicles.json"

    records_dir.mkdir(parents=True, exist_ok=True)
    if not vehicles_path.exists():
        vehicles_path.write_text("[]\n", encoding="utf-8")

    app.config.from_mapping(
        APP_NAME="GN-AOI",
        DATA_DIR=str(instance_dir),
        CSV_HEADER=[
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
        ],
        SECRET_KEY="gnaoi-dev-secret",
    )

    app.register_blueprint(main_bp)

    return app
