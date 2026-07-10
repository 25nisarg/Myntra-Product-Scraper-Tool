import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import (
    DEFAULT_INPUT_FILE,
    DEFAULT_OUTPUT_FILE,
    INPUT_DIR,
    OUTPUT_DIR,
)
from src.csv_reader import read_product_ids
from src.json_writer import write_json
from src.models import ScrapeResponse
from src.scraper import MyntraScraper


app = FastAPI(
    title="Myntra Product Scraper Tool",
    description="FastAPI tool to scrape Myntra product details from product IDs.",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
        },
    )


@app.get("/health")
async def health_check():
    return {
        "status": "running",
        "message": "Myntra FastAPI scraper is running successfully",
    }


@app.post("/scrape")
async def scrape_from_uploaded_csv(
    file: UploadFile = File(...),
    max_products: Optional[int] = Query(
        default=None,
        description="Optional limit for testing. Example: 5",
    ),
    include_delivery: bool = Query(
        default=False,
        description="Optional bonus delivery check for selected city pincodes.",
    ),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported",
        )

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    uploaded_file_path = INPUT_DIR / "uploaded_products.csv"

    try:
        content = await file.read()

        with open(uploaded_file_path, "wb") as uploaded_file:
            uploaded_file.write(content)

        product_ids = read_product_ids(uploaded_file_path)

        if max_products:
            product_ids = product_ids[:max_products]

        scraper = MyntraScraper()

        try:
            await scraper.start()
            results = await scraper.scrape_products(
                product_ids,
                include_delivery=include_delivery,
            )

        finally:
            await scraper.close()

        successful = len([item for item in results if item.status == "success"])
        failed = len([item for item in results if item.status == "failed"])

        response = ScrapeResponse(
            total_products=len(product_ids),
            successful=successful,
            failed=failed,
            output_file=str(DEFAULT_OUTPUT_FILE),
            results=results,
        )

        response_data = response.model_dump(mode="json")

        write_json(response_data, DEFAULT_OUTPUT_FILE)

        return JSONResponse(content=response_data)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@app.get("/scrape-default")
async def scrape_default_csv(
    max_products: Optional[int] = Query(
        default=None,
        description="Optional limit for testing. Example: 5",
    ),
    include_delivery: bool = Query(
        default=False,
        description="Optional bonus delivery check for selected city pincodes.",
    ),
):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_INPUT_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Default CSV not found. Place products.csv inside the input folder.",
        )

    try:
        product_ids = read_product_ids(DEFAULT_INPUT_FILE)

        if max_products:
            product_ids = product_ids[:max_products]

        scraper = MyntraScraper()

        try:
            await scraper.start()
            results = await scraper.scrape_products(
                product_ids,
                include_delivery=include_delivery,
            )

        finally:
            await scraper.close()

        successful = len([item for item in results if item.status == "success"])
        failed = len([item for item in results if item.status == "failed"])

        response = ScrapeResponse(
            total_products=len(product_ids),
            successful=successful,
            failed=failed,
            output_file=str(DEFAULT_OUTPUT_FILE),
            results=results,
        )

        response_data = response.model_dump(mode="json")

        write_json(response_data, DEFAULT_OUTPUT_FILE)

        return JSONResponse(content=response_data)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@app.get("/download-output")
async def download_output():
    if not DEFAULT_OUTPUT_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="Output file not found. Run scraping first.",
        )

    return FileResponse(
        path=DEFAULT_OUTPUT_FILE,
        filename="result.json",
        media_type="application/json",
    )