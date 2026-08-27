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


def presign_image(path):
    filename = path.name

    # Current Square OpenAPI media flow.
    endpoint = (
        BASE
        + "/bapi/composite/v2/public/pgc/openApi/image/presignedUrl"
    )

    response = requests.post(
        endpoint,
        headers=HEADERS,
        json={
            "imageName": filename
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") not in (
        "000000",
        0,
        None
    ):
        raise RuntimeError(
            f"Binance presign failed: {data}"
        )

    payload = data.get("data") or {}

    presigned_url = payload.get(
        "presignedUrl"
    )

    file_ticket = payload.get(
        "fileTicket"
    )

    if not presigned_url:
        raise RuntimeError(
            f"No presignedUrl returned: {data}"
        )

    return presigned_url, file_ticket


def upload_image(path, presigned_url):
    content_type = (
        mimetypes.guess_type(
            path.name
        )[0]
        or "image/jpeg"
    )

    with open(path, "rb") as f:

        response = requests.put(
            presigned_url,
            data=f,
            headers={
                "Content-Type": content_type
            },
            timeout=120
        )

    response.raise_for_status()


def wait_for_image(file_ticket):
    endpoint = (
        BASE
        + "/bapi/composite/v2/public/pgc/openApi/image/imageStatus"
    )

    for attempt in range(10):

        response = requests.post(
            endpoint,
            headers=HEADERS,
            json={
                "fileTicket": file_ticket
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        payload = data.get(
            "data"
        ) or {}

        status = payload.get(
            "status"
        )

        print(
            f"Image processing: "
            f"{attempt + 1}/10 status={status}"
        )

        if status == 1:

            image_url = (
                payload.get("imageUrl")
                or payload.get("url")
            )

            if not image_url:
                raise RuntimeError(
                    f"Image processed but URL missing: {data}"
                )

            return image_url

        time.sleep(3)

    raise RuntimeError(
        "Image processing timed out."
    )


def upload_one_image(path):

    print(
        f"Uploading image: {path.name}"
    )

    presigned_url, file_ticket = (
        presign_image(path)
    )

    upload_image(
        path,
        presigned_url
    )

    return wait_for_image(
        file_ticket
    )


def publish_text(text):

    check_key()

    endpoint = (
        BASE
        + "/bapi/composite/v1/public/pgc/openApi/content/add"
    )

    payload = {
        "contentType": 1,
        "bodyTextOnly": text,
        "isPublish": True
    }

    response = requests.post(
        endpoint,
        headers=HEADERS,
        json=payload,
        timeout=60
    )

    print(
        "Publish HTTP:",
        response.status_code
    )

    data = response.json()

    print(
        "Publish response:",
        data
    )

    return data


def publish_images(text, image_urls):

    check_key()

    if not image_urls:
        return publish_text(text)

    if len(image_urls) > 4:
        image_urls = image_urls[:4]

    endpoint = (
        BASE
        + "/bapi/composite/v1/public/pgc/openApi/content/add"
    )

    payload = {
        "contentType": 1,
        "bodyTextOnly": text,
        "imageList": image_urls,
        "isPublish": True
    }

    response = requests.post(
        endpoint,
        headers=HEADERS,
        json=payload,
        timeout=60
    )

    print(
        "Publish HTTP:",
        response.status_code
    )

    data = response.json()

    print(
        "Publish response:",
        data
    )

    return data
