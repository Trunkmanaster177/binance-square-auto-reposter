import os
import time
import mimetypes
from pathlib import Path

import requests


API_KEY = os.environ.get("BINANCE_SQUARE_OPENAPI_KEY")

BASE = "https://www.binance.com"

HEADERS = {
    "X-Square-OpenAPI-Key": API_KEY or "",
    "Content-Type": "application/json",
    "clienttype": "binanceSkill",
}


def check_key():
    if not API_KEY:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY GitHub Secret is missing."
        )


def download_image(url, directory, index):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "image/jpeg"
    )

    extension = mimetypes.guess_extension(
        content_type.split(";")[0]
    ) or ".jpg"

    path = directory / f"image_{index}{extension}"

    path.write_bytes(response.content)

    return path
