import re
from urllib.parse import quote_plus


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    value = re.sub(r"\s+", " ", str(value))
    value = value.strip()

    if not value:
        return None

    return value


def build_product_api_url(product_id: str) -> str:
    return f"https://www.myntra.com/gateway/v2/product/{product_id}"


def build_search_api_url(query: str, rows: int = 30) -> str:
    search_term = quote_plus(query)
    return (
        f"https://www.myntra.com/gateway/v2/search/{search_term}"
        f"?rawQuery={search_term}&rows={rows}&o=0&plaEnabled=true"
    )


def build_product_search_url(product_id: str) -> str:
    search_term = quote_plus(product_id)
    return f"https://www.myntra.com/{search_term}?rawQuery={search_term}"


def build_product_url(product_id: str) -> str:
    return f"https://www.myntra.com/{product_id}"


def build_category_search_url(category: str) -> str:
    search_term = quote_plus(category)
    return f"https://www.myntra.com/{search_term}?rawQuery={search_term}"


def safe_get_text(soup, selector: str) -> str | None:
    element = soup.select_one(selector)

    if not element:
        return None

    return clean_text(element.get_text())


def safe_get_attribute(soup, selector: str, attribute: str) -> str | None:
    element = soup.select_one(selector)

    if not element:
        return None

    return element.get(attribute)


def extract_number(value: str | None) -> str | None:
    if not value:
        return None

    match = re.search(r"[\d,.]+[kK]?", str(value))

    if not match:
        return None

    return match.group(0)


def is_valid_product_image_url(url: str | None) -> bool:
    if not url:
        return False

    url = str(url).lower()

    blocked_domains = [
        "facebook.com",
        "google",
        "doubleclick",
        "analytics",
        "pixel",
        "snapchat",
        "ads",
    ]

    if any(domain in url for domain in blocked_domains):
        return False

    if not url.startswith("http"):
        return False

    valid_markers = [
        "assets.myntassets.com",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    ]

    return any(marker in url for marker in valid_markers)


def normalize_myntra_url(url: str | None) -> str | None:
    """
    Normalizes Myntra product/category URLs.
    """

    if not url:
        return None

    url = str(url).strip()

    if url.startswith("http"):
        return url

    if not url.startswith("/"):
        url = "/" + url

    return f"https://www.myntra.com{url}"


def normalize_image_url(url: str | None) -> str | None:
    """
    Normalizes Myntra image URLs and converts image variants into one standard format.
    """

    if not url:
        return None

    url = str(url).strip()

    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)

    url = url.replace(
        "h_($height),q_($qualityPercentage),w_($width)",
        "h_720,q_90,w_540"
    )

    if "assets.myntassets.com" in url and "/assets/images/" in url:
        image_path = url.split("/assets/images/", 1)[1]
        url = f"https://assets.myntassets.com/h_720,q_90,w_540/v1/assets/images/{image_path}"

    return url


def image_dedupe_key(url: str | None) -> str | None:
    """
    Creates a duplicate-checking key for Myntra images.
    This prevents same image appearing as both:
    /h_720,q_90,w_540/v1/assets/images/...
    and
    /assets/images/...
    """

    if not url:
        return None

    url = normalize_image_url(url)

    if not url:
        return None

    if "/assets/images/" in url:
        return url.split("/assets/images/", 1)[1]

    return url


def clean_sponsored_rating(value: str | None) -> str | None:
    """
    Cleans sponsored rating value.
    Example:
    '4.4|777' becomes '4.4'
    """

    if not value:
        return None

    value = clean_text(value)

    if not value:
        return None

    match = re.search(r"\d+(\.\d+)?", value)

    if match:
        return match.group(0)

    return value


def clean_description(value: str | None) -> str | None:
    """
    Removes invalid placeholder descriptions.
    """

    value = clean_text(value)

    if not value:
        return None

    invalid_values = {
        "listview",
        "gridview",
        "pdp",
        "none",
        "null",
        "na",
        "n/a",
    }

    if value.lower() in invalid_values:
        return None

    return value


def clean_rating(value: str | None) -> str | None:
    """
    Formats product rating to a cleaner value.
    Example:
    4.064935064935065 becomes 4.1
    """

    if value is None:
        return None

    try:
        number = float(value)

        if number == 0:
            return "0"

        return str(round(number, 1))

    except ValueError:
        return clean_text(value)