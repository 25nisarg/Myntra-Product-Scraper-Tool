import json
import re
from bs4 import BeautifulSoup

from src.config import MAX_IMAGES, MAX_SPONSORED_RESULTS
from src.models import SponsoredProduct
from src.utils import (
    clean_text,
    clean_description,
    clean_rating,
    clean_sponsored_rating,
    extract_number,
    image_dedupe_key,
    is_valid_product_image_url,
    normalize_image_url,
    normalize_myntra_url,
)


def strip_html(value):
    if value is None:
        return None

    text = BeautifulSoup(str(value), "lxml").get_text(" ", strip=True)
    return clean_text(text)


def extract_json_from_script(html: str) -> dict | None:
    patterns = [
        r"window\.__myx\s*=\s*(\{.*?\});",
        r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});",
        r"__PRELOADED_STATE__\s*=\s*(\{.*?\});",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    return None


def find_first_scalar(data, possible_keys: list[str]):
    possible_keys = [key.lower() for key in possible_keys]

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in possible_keys and value not in [None, "", []]:
                if isinstance(value, (str, int, float)):
                    return clean_text(str(value))

                if isinstance(value, dict):
                    for nested_key in ["value", "name", "text", "title", "count", "total"]:
                        if nested_key in value and value[nested_key]:
                            return strip_html(value[nested_key])

        for value in data.values():
            result = find_first_scalar(value, possible_keys)
            if result:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_first_scalar(item, possible_keys)
            if result:
                return result

    return None


def find_rating_count(data):
    """
    Attempts to find total ratings count from exact and fuzzy keys.
    Returns None if the source does not clearly expose the field.
    """

    exact_keys = [
        "ratingCount",
        "ratingsCount",
        "totalRatings",
        "totalRatingsCount",
        "reviewCount",
        "reviewsCount",
        "totalReviews",
        "totalReviewCount",
    ]

    exact_result = find_first_scalar(data, exact_keys)

    if exact_result:
        return extract_number(exact_result) or exact_result

    def search(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                looks_like_count_key = (
                    ("rating" in key_lower or "review" in key_lower)
                    and (
                        "count" in key_lower
                        or "total" in key_lower
                        or "num" in key_lower
                    )
                )

                if looks_like_count_key and value not in [None, "", []]:
                    if isinstance(value, (str, int, float)):
                        return extract_number(str(value)) or clean_text(str(value))

                    if isinstance(value, dict):
                        for nested_key in ["count", "total", "value"]:
                            nested_value = value.get(nested_key)

                            if nested_value not in [None, "", []]:
                                return extract_number(str(nested_value)) or clean_text(str(nested_value))

                if isinstance(value, (dict, list)):
                    result = search(value)

                    if result:
                        return result

        elif isinstance(obj, list):
            for item in obj:
                result = search(item)

                if result:
                    return result

        return None

    return search(data)


def find_images(data) -> list[str]:
    images = []
    seen_keys = set()

    def search(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    normalized_url = normalize_image_url(value)
                    dedupe_key = image_dedupe_key(normalized_url)

                    if (
                        is_valid_product_image_url(normalized_url)
                        and dedupe_key
                        and dedupe_key not in seen_keys
                    ):
                        images.append(normalized_url)
                        seen_keys.add(dedupe_key)

                elif isinstance(value, (dict, list)):
                    search(value)

        elif isinstance(obj, list):
            for item in obj:
                search(item)

    search(data)

    return images[:MAX_IMAGES]


def parse_product_json(data: dict) -> dict:
    root = data.get("style") or data.get("data") or data

    brand = find_first_scalar(
        root,
        ["brand", "brandName", "brand_name"],
    )

    product_name = find_first_scalar(
        root,
        [
            "productDisplayName",
            "productName",
            "name",
            "title",
            "articleName",
        ],
    )

    if brand and product_name and brand.lower() not in product_name.lower():
        title = f"{brand} {product_name}"
    else:
        title = product_name or brand

    description = find_first_scalar(
        root,
        [
            "description",
            "productDetails",
            "styleNote",
            "style_note",
            "productDescription",
            "materials_care_desc",
        ],
    )

    rating = find_first_scalar(
        root,
        [
            "averageRating",
            "avgRating",
            "rating",
            "ratings",
            "styleRating",
        ],
    )

    total_ratings_count = find_rating_count(root)

    category = find_first_scalar(
        root,
        [
            "articleType",
            "category",
            "subCategory",
            "masterCategory",
            "productType",
            "displayCategory",
        ],
    )

    images = find_images(root)

    return {
        "title": clean_text(title),
        "description": clean_description(strip_html(description)),
        "images": images,
        "rating": clean_rating(rating),
        "total_ratings_count": clean_text(total_ratings_count),
        "category": clean_text(category),
    }


def parse_product_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    json_data = extract_json_from_script(html)

    if json_data:
        parsed_json = parse_product_json(json_data)

        if parsed_json.get("title"):
            return parsed_json

    title = None
    description = None
    images = []
    seen_image_keys = set()
    rating = None
    total_ratings_count = None
    category = None

    brand = soup.select_one("h1.pdp-title")
    name = soup.select_one("h1.pdp-name")

    brand_text = clean_text(brand.get_text()) if brand else None
    name_text = clean_text(name.get_text()) if name else None

    if brand_text and name_text:
        title = f"{brand_text} {name_text}"
    else:
        title = brand_text or name_text

    description_element = soup.select_one(".pdp-product-description-content")
    if description_element:
        description = clean_description(description_element.get_text())

    rating_element = soup.select_one(".index-overallRating")
    if rating_element:
        rating = clean_rating(rating_element.get_text())

    rating_count_element = soup.select_one(".index-ratingsCount")
    if rating_count_element:
        total_ratings_count = extract_number(rating_count_element.get_text())

    breadcrumbs = soup.select(".breadcrumbs-link")
    if breadcrumbs:
        category = clean_text(breadcrumbs[-1].get_text())

    image_elements = soup.select("img")

    for img in image_elements:
        src = img.get("src") or img.get("data-src")
        normalized_src = normalize_image_url(src)
        dedupe_key = image_dedupe_key(normalized_src)

        if (
            is_valid_product_image_url(normalized_src)
            and dedupe_key
            and dedupe_key not in seen_image_keys
        ):
            images.append(normalized_src)
            seen_image_keys.add(dedupe_key)

        if len(images) >= MAX_IMAGES:
            break

    return {
        "title": clean_text(title),
        "description": clean_description(description),
        "images": images[:MAX_IMAGES],
        "rating": clean_rating(rating),
        "total_ratings_count": clean_text(total_ratings_count),
        "category": clean_text(category),
    }


def find_product_list(data):
    products = []

    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = str(key).lower()

            if key_lower in ["products", "results", "items"] and isinstance(value, list):
                products.extend([item for item in value if isinstance(item, dict)])

            elif isinstance(value, (dict, list)):
                products.extend(find_product_list(value))

    elif isinstance(data, list):
        for item in data:
            products.extend(find_product_list(item))

    return products


def has_sponsored_marker(product: dict) -> bool:
    sponsored_keys = [
        "sponsored",
        "issponsored",
        "isad",
        "adid",
        "adtype",
        "pla",
        "ispla",
        "promoted",
    ]

    def search(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                if key_lower in sponsored_keys and value:
                    return True

                if isinstance(value, (dict, list)) and search(value):
                    return True

        elif isinstance(obj, list):
            for item in obj:
                if search(item):
                    return True

        return False

    return search(product)


def parse_search_json_sponsored(data: dict) -> list[SponsoredProduct]:
    product_items = find_product_list(data)
    sponsored_products = []

    for product in product_items:
        if not has_sponsored_marker(product):
            continue

        brand = find_first_scalar(product, ["brand", "brandName"])

        product_name = find_first_scalar(
            product,
            ["productDisplayName", "productName", "product", "name", "title"],
        )

        if brand and product_name and brand.lower() not in product_name.lower():
            title = f"{brand} {product_name}"
        else:
            title = product_name or brand

        rating = find_first_scalar(
            product,
            ["averageRating", "avgRating", "rating"],
        )

        price = find_first_scalar(
            product,
            ["discountedPrice", "sellingPrice", "price", "mrp"],
        )

        product_url = find_first_scalar(
            product,
            ["productUrl", "landingPageUrl", "url"],
        )

        product_url = normalize_myntra_url(product_url)
        rating = clean_sponsored_rating(rating)

        sponsored_products.append(
            SponsoredProduct(
                title=title,
                rating=rating,
                price=price,
                product_url=product_url,
            )
        )

        if len(sponsored_products) >= MAX_SPONSORED_RESULTS:
            break

    return sponsored_products


def parse_sponsored_results(html: str) -> list[SponsoredProduct]:
    soup = BeautifulSoup(html, "lxml")
    sponsored_products = []

    product_cards = soup.select("li.product-base")

    for card in product_cards:
        card_text = card.get_text(" ", strip=True).lower()

        is_sponsored = (
            "sponsored" in card_text
            or re.search(r"\bad\b", card_text) is not None
            or card.select_one('[class*="sponsored"]') is not None
            or card.select_one('[class*="ad"]') is not None
        )

        if not is_sponsored:
            continue

        brand = clean_text(
            card.select_one(".product-brand").get_text()
            if card.select_one(".product-brand")
            else None
        )

        product_name = clean_text(
            card.select_one(".product-product").get_text()
            if card.select_one(".product-product")
            else None
        )

        if brand and product_name:
            title = f"{brand} {product_name}"
        else:
            title = brand or product_name

        rating = clean_text(
            card.select_one(".product-ratingsContainer").get_text()
            if card.select_one(".product-ratingsContainer")
            else None
        )

        rating = clean_sponsored_rating(rating)

        price = clean_text(
            card.select_one(".product-discountedPrice").get_text()
            if card.select_one(".product-discountedPrice")
            else None
        )

        if not price:
            price = clean_text(
                card.select_one(".product-price").get_text()
                if card.select_one(".product-price")
                else None
            )

        link = card.select_one("a")
        product_url = None

        if link and link.get("href"):
            href = link.get("href")
            product_url = normalize_myntra_url(href)

        sponsored_products.append(
            SponsoredProduct(
                title=title,
                rating=rating,
                price=price,
                product_url=product_url,
            )
        )

        if len(sponsored_products) >= MAX_SPONSORED_RESULTS:
            break

    return sponsored_products