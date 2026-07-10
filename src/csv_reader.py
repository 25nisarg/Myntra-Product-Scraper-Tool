import pandas as pd
from pathlib import Path


def read_product_ids(csv_file_path: str | Path) -> list[str]:
    """
    Reads product IDs from a CSV file.

    Expected CSV column:
    product_id
    """

    csv_file_path = Path(csv_file_path)

    if not csv_file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

    df = pd.read_csv(csv_file_path)

    if "product_id" not in df.columns:
        raise ValueError("CSV must contain a 'product_id' column")

    product_ids = (
        df["product_id"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    product_ids = [pid for pid in product_ids if pid]

    if not product_ids:
        raise ValueError("No valid product IDs found in CSV")

    return product_ids