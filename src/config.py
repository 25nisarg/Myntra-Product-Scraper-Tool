from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

DEFAULT_INPUT_FILE = INPUT_DIR / "products.csv"
DEFAULT_OUTPUT_FILE = OUTPUT_DIR / "result.json"

MYNTRA_BASE_URL = "https://www.myntra.com"

REQUEST_TIMEOUT = 30000
PAGE_LOAD_WAIT = 3000

MAX_IMAGES = 2
MAX_SPONSORED_RESULTS = 3

BROWSER_HEADLESS = False

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DELIVERY_PINCODES = {
    "Bengaluru": "560001",
    "Mumbai": "400001",
    "Delhi": "110001",
    "Ahmedabad": "380001",
    "Kolkata": "700001",
}