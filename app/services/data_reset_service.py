import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResetDataResult:
    success: bool
    removed_record_files: int
    message: str | None
    error_message: str | None


def reset_all_data(data_dir: Path) -> ResetDataResult:
    records_dir = data_dir / "records"
    config_path = data_dir / "vehicles.json"
    removed_record_files = 0

    try:
        records_dir.mkdir(parents=True, exist_ok=True)
        for csv_path in records_dir.glob("*.csv"):
            csv_path.unlink()
            removed_record_files += 1

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps([], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return ResetDataResult(
            success=False,
            removed_record_files=0,
            message=None,
            error_message="初期化に失敗しました。",
        )

    return ResetDataResult(
        success=True,
        removed_record_files=removed_record_files,
        message="全データを初期化しました。",
        error_message=None,
    )
