from __future__ import annotations
import json
import math
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

def make_json_safe(value: Any) -> Any:
    """Recursively convert Python, NumPy, and pandas values into JSON values."""
    if value is None:
        return None

    if value is pd.NA:
        return None

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        numeric_value = float(value)
        return numeric_value if math.isfinite(numeric_value) else None

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    if isinstance(value, pd.Series):
        return make_json_safe(value.to_dict())

    if isinstance(value, pd.DataFrame):
        return make_json_safe(value.to_dict(orient="records"))

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value

def write_json(
    destination: Path | str,
    payload: Any,
    indent: int = 2,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    safe_payload = make_json_safe(payload)

    temporary_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json.tmp",
            prefix=f"{path.stem}_",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name

            json.dump(
                safe_payload,
                temporary_file,
                ensure_ascii=False,
                indent=indent,
                allow_nan=False,
            )

            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)

    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

    return path