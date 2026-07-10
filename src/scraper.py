import asyncio
import random
import re
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from src.config import (
    BROWSER_HEADLESS,
    DELIVERY_PINCODES,
    MAX_SPONSORED_RESULTS,
    MYNTRA_BASE_URL,
    PAGE_LOAD_WAIT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from src.models import ProductResult, DeliveryEstimate
from src.parser import (
    parse_product_json,
    parse_product_page,
    parse_search_json_sponsored,
    parse_sponsored_results,
)
from src.utils import (
    build_category_search_url,
    build_product_api_url,
    build_product_search_url,
    build_product_url,
    build_search_api_url,
)


class MyntraScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=BROWSER_HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            },
        )

    async def close(self):
        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()

    async def fetch_json(self, url: str):
        try:
            response = await self.context.request.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Referer": "https://www.myntra.com/",
                },
            )

            if not response.ok:
                return None

            text = await response.text()

            if not text.strip().startswith("{"):
                return None

            return await response.json()

        except Exception:
            return None

    async def fetch_page_html(self, url: str) -> str:
        page = await self.context.new_page()

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=REQUEST_TIMEOUT,
            )

            await page.wait_for_timeout(PAGE_LOAD_WAIT)

            html = await page.content()
            return html

        finally:
            await page.close()

    async def resolve_product_url(self, product_id: str) -> str:
        search_url = build_product_search_url(product_id)
        page = await self.context.new_page()

        try:
            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=REQUEST_TIMEOUT,
            )

            await page.wait_for_timeout(PAGE_LOAD_WAIT)

            product_link_locator = page.locator(f'a[href*="{product_id}"]').first

            if await product_link_locator.count() > 0:
                href = await product_link_locator.get_attribute("href")

                if href:
                    if href.startswith("http"):
                        return href

                    return f"{MYNTRA_BASE_URL}{href}"

            return build_product_url(product_id)

        finally:
            await page.close()

    def extract_delivery_days(self, text: str | None) -> str | None:
        if not text:
            return None

        text = str(text)

        day_match = re.search(r"(\d+)\s*(day|days)", text, re.IGNORECASE)

        if day_match:
            return day_match.group(1)

        return None

    def extract_delivery_message(self, text: str | None) -> str | None:
        if not text:
            return None

        text = re.sub(r"\s+", " ", str(text)).strip()

        patterns = [
            r"(Delivery by [A-Za-z]+,?\s*\d{1,2})",
            r"(Get it by [A-Za-z]+,?\s*\d{1,2})",
            r"(Usually delivered in \d+\s*days?)",
            r"(Expected delivery in \d+\s*days?)",
            r"(Delivery in \d+\s*days?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return match.group(1)

        if "delivery" in text.lower():
            delivery_index = text.lower().find("delivery")
            return text[delivery_index: delivery_index + 180]

        return None

    async def try_enter_pincode(self, page, pincode: str) -> bool:
        pincode_selectors = [
            "input[placeholder*='pincode' i]",
            "input[placeholder*='pin code' i]",
            "input[placeholder*='PIN' i]",
            "input.pincode-code",
            ".pincode-code",
            "input[type='tel']",
            "input[type='text']",
        ]

        input_box = None

        for selector in pincode_selectors:
            locator = page.locator(selector)

            if await locator.count() > 0:
                input_box = locator.first
                break

        if not input_box:
            return False

        await input_box.click()
        await input_box.fill("")
        await input_box.type(pincode, delay=80)

        button_selectors = [
            "button:has-text('CHECK')",
            "button:has-text('Check')",
            ".pincode-check",
            "input[value='CHECK']",
            "text=CHECK",
        ]

        clicked = False

        for selector in button_selectors:
            button = page.locator(selector)

            if await button.count() > 0:
                await button.first.click()
                clicked = True
                break

        if not clicked:
            await input_box.press("Enter")

        await page.wait_for_timeout(3500)

        return True

    async def scrape_delivery_estimates(
        self,
        product_url: str,
        pincodes: dict[str, str] = DELIVERY_PINCODES,
    ) -> list[DeliveryEstimate]:
        delivery_results = []

        for city, pincode in pincodes.items():
            page = await self.context.new_page()

            try:
                await page.goto(
                    product_url,
                    wait_until="domcontentloaded",
                    timeout=REQUEST_TIMEOUT,
                )

                await page.wait_for_timeout(PAGE_LOAD_WAIT)

                entered = await self.try_enter_pincode(page, pincode)

                if not entered:
                    delivery_results.append(
                        DeliveryEstimate(
                            city=city,
                            pincode=pincode,
                            estimated_delivery_days=None,
                            message=None,
                            status="unavailable",
                            error="Pincode input was not found on the product page.",
                        )
                    )
                    continue

                body_text = await page.locator("body").inner_text(timeout=8000)

                message = self.extract_delivery_message(body_text)
                estimated_days = self.extract_delivery_days(message or body_text)

                if message or estimated_days:
                    delivery_results.append(
                        DeliveryEstimate(
                            city=city,
                            pincode=pincode,
                            estimated_delivery_days=estimated_days,
                            message=message,
                            status="success",
                            error=None,
                        )
                    )
                else:
                    delivery_results.append(
                        DeliveryEstimate(
                            city=city,
                            pincode=pincode,
                            estimated_delivery_days=None,
                            message=None,
                            status="unavailable",
                            error="Delivery message was not found after entering pincode.",
                        )
                    )

            except Exception as error:
                delivery_results.append(
                    DeliveryEstimate(
                        city=city,
                        pincode=pincode,
                        estimated_delivery_days=None,
                        message=None,
                        status="failed",
                        error=str(error),
                    )
                )

            finally:
                await page.close()

            await asyncio.sleep(random.uniform(1.0, 2.0))

        return delivery_results

    async def scrape_product(
        self,
        product_id: str,
        include_delivery: bool = False,
    ) -> ProductResult:
        result = ProductResult(product_id=product_id)

        try:
            product_data = None
            product_url = None

            product_api_url = build_product_api_url(product_id)
            product_json = await self.fetch_json(product_api_url)

            if product_json:
                product_data = parse_product_json(product_json)

            if not product_data or not product_data.get("title"):
                product_url = await self.resolve_product_url(product_id)
                product_html = await self.fetch_page_html(product_url)
                product_data = parse_product_page(product_html)

            result.title = product_data.get("title")
            result.description = product_data.get("description")
            result.images = product_data.get("images", [])
            result.rating = product_data.get("rating")
            result.total_ratings_count = product_data.get("total_ratings_count")
            result.category = product_data.get("category")

            if not result.title:
                result.description = None
                result.images = []
                result.rating = None
                result.total_ratings_count = None
                result.category = None
                result.sponsored_results = []
                result.delivery_estimates = []
                result.status = "failed"
                result.error = (
                    "Product data could not be extracted. Myntra may have returned "
                    "a blocked/non-product page or the product ID may be unavailable."
                )
                return result

            if result.category:
                sponsored_results = []

                search_api_url = build_search_api_url(result.category)
                search_json = await self.fetch_json(search_api_url)

                if search_json:
                    sponsored_results = parse_search_json_sponsored(search_json)

                if not sponsored_results:
                    try:
                        category_url = build_category_search_url(result.category)
                        category_html = await self.fetch_page_html(category_url)
                        sponsored_results = parse_sponsored_results(category_html)
                    except Exception:
                        sponsored_results = []

                result.sponsored_results = sponsored_results[:MAX_SPONSORED_RESULTS]

            else:
                result.sponsored_results = []
                result.status = "partial_success"
                result.error = "Product scraped, but category could not be extracted."
                return result

            if include_delivery:
                if not product_url:
                    product_url = await self.resolve_product_url(product_id)

                result.delivery_estimates = await self.scrape_delivery_estimates(
                    product_url=product_url,
                    pincodes=DELIVERY_PINCODES,
                )

            result.status = "success"
            result.error = None
            return result

        except PlaywrightTimeoutError:
            result.status = "failed"
            result.error = "Page load timed out"
            return result

        except PlaywrightError as error:
            result.status = "failed"
            result.error = f"Playwright error: {error}"
            return result

        except Exception as error:
            result.status = "failed"
            result.error = str(error)
            return result

    async def scrape_products(
        self,
        product_ids: list[str],
        include_delivery: bool = False,
    ) -> list[ProductResult]:
        results = []

        for index, product_id in enumerate(product_ids, start=1):
            print(f"Processing {index}/{len(product_ids)}: {product_id}")

            result = await self.scrape_product(
                product_id=product_id,
                include_delivery=include_delivery,
            )

            results.append(result)

            await asyncio.sleep(random.uniform(2.0, 4.0))

        return results