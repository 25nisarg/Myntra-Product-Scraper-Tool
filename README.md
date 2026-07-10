# Myntra Product Scraper Tool

## Overview

This project is a FastAPI-based tool that reads a CSV file containing Myntra product IDs and returns product information in a structured JSON format.

For each product ID, the tool attempts to fetch the product title, description, one or two images, rating, total ratings count, category, and the first 3 sponsored/ad-marked products from the related category page.

The tool is designed to continue working even if some products are unavailable, blocked, or missing data.

## How to Run

### 1. Create a virtual environment

```bash
python -m venv venv
```

### 2. Activate the virtual environment

For Windows:

```bash
venv\Scripts\activate
```

For macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

```bash
playwright install chromium
```

### 5. Add the input CSV

Place the product CSV file inside the `input` folder and rename it as:

```text
products.csv
```

The CSV must contain this column:

```text
product_id
```

### 6. Run the application

```bash
python run.py
```

Open the application in the browser:

```text
http://127.0.0.1:8000
```

## API Usage

To scrape products from the default CSV:

```text
http://127.0.0.1:8000/scrape-default
```

To test only a few products:

```text
http://127.0.0.1:8000/scrape-default?max_products=10
```

To include the optional delivery check:

```text
http://127.0.0.1:8000/scrape-default?max_products=2&include_delivery=true
```

To download the output JSON:

```text
http://127.0.0.1:8000/download-output
```

## Approach

The tool first reads product IDs from the uploaded CSV file. It then processes each product one by one.

For each product, the scraper tries to fetch publicly available Myntra product data. If direct product data is not available, it falls back to loading the public product/search page using Playwright. The returned page content is then parsed to extract product details.

After extracting the product category, the tool searches the related category page and returns the first 3 sponsored/ad-marked products with their rating and price.

The output is saved as JSON because it is structured, machine-readable, and easy to use for further processing.

The scraper runs sequentially with small delays because marketplace websites may block aggressive automated requests.

## Assumptions

* The input CSV contains a `product_id` column.
* Product information is publicly accessible and does not require login.
* Some product IDs may be unavailable, removed, blocked, or may return non-product pages.
* Some fields may be missing for some products.
* Missing values are returned as `null` instead of guessing incorrect data.
* Sponsored/ad-marked products are extracted only when they are available in the public page or response.
* Delivery checking depends on Myntra’s live page behaviour and may return unavailable results.

## Scoped In

* CSV input support
* FastAPI backend
* Simple frontend for upload and viewing results
* Product title extraction
* Product description extraction
* One or two product image extraction
* Rating extraction
* Total ratings count extraction where available
* Category extraction
* First 3 sponsored/ad-marked category results
* JSON output generation
* Downloadable JSON output
* Error handling for failed or missing products
* Optional delivery check for selected city pincodes

## Scoped Out

* Login-based scraping
* Private API or account-based access
* Captcha solving
* Proxy rotation
* High-speed parallel scraping
* Database storage
* Cloud deployment

## Known Issues and Limitations

* Myntra may block or change automated page access.
* Some product IDs may return unavailable or non-product pages.
* Some product fields may not be exposed clearly, so the tool returns `null`.
* Delivery estimates may return `unavailable` if Myntra does not show delivery messages during automated checking.
* Sponsored result detection depends on the data available in Myntra’s current page or response structure.

## What I Would Improve With More Time

* Add stronger retry handling.
* Add better logging.
* Improve sponsored result detection if Myntra changes its page structure.
* Improve delivery estimate extraction.
* Add unit tests for CSV reading, parsing, and scraping.
* Add Docker support for easier setup.

## Sample Output

A sample run was completed using 10 product IDs.

```text
Total products: 10
Successful: 9
Failed: 1
Output format: JSON
```

Example product output:

```json
{
    "product_id": "31786093",
    "title": "SUPERVEK Unisex Solid Pure Cotton Bucket Hat with Embroidered Detail",
    "description": "Black solid bucket hat with thunder bolt embroidered detail",
    "images": [
        "https://assets.myntassets.com/example-image-1.jpg",
        "https://assets.myntassets.com/example-image-2.jpg"
    ],
    "rating": "4.1",
    "total_ratings_count": "18",
    "category": "Hat",
    "sponsored_results": [
        {
            "title": "ToniQ Self Design Sun Hat",
            "rating": "4.4",
            "price": "Rs. 1000",
            "product_url": "https://www.myntra.com/hat/toniq/example-product/buy"
        }
    ],
    "delivery_estimates": [],
    "status": "success",
    "error": null
}
```

Example failed product output:

```json
{
    "product_id": "35512522",
    "title": null,
    "description": null,
    "images": [],
    "rating": null,
    "total_ratings_count": null,
    "category": null,
    "sponsored_results": [],
    "delivery_estimates": [],
    "status": "failed",
    "error": "Product data could not be extracted. Myntra may have returned a blocked/non-product page or the product ID may be unavailable."
}
```

## Submission

The final submission includes:

```text
Product/
├── input/
│   └── products.csv
├── output/
│   └── sample_output.json
├── src/
├── templates/
├── static/
├── requirements.txt
├── README.md
├── run.py
└── .gitignore
```
