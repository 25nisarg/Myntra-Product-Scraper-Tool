import json
from pathlib import Path
from typing import Any


def write_json(data: Any, output_file_path: str | Path) -> None:
    """
    Writes scraped result data into a JSON file.
    """

    output_file_path = Path(output_file_path)

    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4,
            default=lambda obj: obj.model_dump() if hasattr(obj, "model_dump") else str(obj),
        )