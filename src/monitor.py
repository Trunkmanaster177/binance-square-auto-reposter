import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from binance_square import (
    download_image,
    upload_one_image,
    publish_text,
    publish_images,
)


SOURCE_AUTHOR = os.getenv("SOURCE_AUTHOR", "TF_bnb")

PROFILE_URL = (
    "https://www.binance.com/en/square/profile/"
    + SOURCE_AUTHOR
)

STATE_FILE = Path("src/state.json")
MEDIA_DIR = Path("tmp_media")


def load_state():
    if not STATE_FILE.exists():
        return {
            "initialized": False,
            "processed_ids": []
        }

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {
            "initialized": False,
            "processed_ids": []
        }


def save_state(state):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    state["processed_ids"] = list(
        dict.fromkeys(
            state.get("processed_ids", [])
        )
    )[-500:]

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def extract_visible_posts(page, debug=False):
    posts = {}

    links = page.locator(
        'a[href*="/square/post/"]'
    )

    count = links.count()

    for i in range(count):

        try:
            link = links.nth(i)

            href = link.get_attribute("href")

            if not href:
                continue

            post_id = (
                href.rstrip("/")
                .split("/")[-1]
            )

            if not post_id.isdigit():
                continue

            if post_id in posts:
                continue

            # Find nearest article first.
            container = link.locator(
                "xpath=ancestor::article[1]"
            )

            if container.count() == 0:
                container = link.locator(
                    "xpath=ancestor::div[1]"
                )

            try:
                text = container.inner_text(
                    timeout=2000
                )
            except Exception:
                text = link.inner_text(
                    timeout=2000
                )

            images = []

            # ------------------------------------------------
            # DEBUG IMAGE INSPECTION
            # ------------------------------------------------

            try:
                imgs = container.locator("img")
                img_count = imgs.count()

                if debug and i == 0:
                    print()
                    print("=" * 70)
                    print("IMAGE DEBUG")
                    print("=" * 70)
                    print("Post ID:", post_id)
                    print("IMG ELEMENTS FOUND:", img_count)

                for j in range(min(img_count, 10)):

                    img = imgs.nth(j)

                    attributes = {}

                    for attr in [
                        "src",
                        "srcset",
                        "data-src",
                        "data-original",
                        "data-lazy-src",
                        "data-url",
                        "data-image",
                        "alt"
                    ]:
                        try:
                            value = img.get_attribute(attr)

                            if value:
                                attributes[attr] = value
                        except Exception:
                            pass

                    if debug and i == 0:
                        print()
                        print(f"IMG #{j + 1}")
                        print("ATTRIBUTES:")
                        print(json.dumps(
                            attributes,
                            indent=2,
                            ensure_ascii=False
                        ))

                    # Try normal src.
                    src = attributes.get("src")

                    if src and not src.startswith("data:"):
                        if src not in images:
                            images.append(src)

                    # Try lazy-loading attributes.
                    for attr in [
                        "data-src",
                        "data-original",
                        "data-lazy-src",
                        "data-url",
                        "data-image"
                    ]:
                        value = attributes.get(attr)

                        if value and not value.startswith("data:"):
                            if value not in images:
                                images.append(value)

                    # Try srcset.
                    srcset = attributes.get("srcset")

                    if srcset:
                        candidates = []

                        for item in srcset.split(","):
                            item = item.strip()

                            if not item:
                                continue

                            url = item.split(" ")[0]

                            if (
                                url
                                and not url.startswith("data:")
                            ):
                                candidates.append(url)

                        # Pick the last/largest candidate.
                        if candidates:
                            selected = candidates[-1]

                            if selected not in images:
                                images.append(selected)

            except Exception as e:

                if debug and i == 0:
                    print(
                        "IMAGE EXTRACTION ERROR:",
                        repr(e)
                    )

            # ------------------------------------------------
            # CHECK CSS BACKGROUND IMAGES
            # ------------------------------------------------

            try:

                elements = container.locator(
                    "[style*='background-image']"
                )

                element_count = elements.count()

                if debug and i == 0:
                    print()
                    print(
                        "BACKGROUND IMAGE ELEMENTS:",
                        element_count
                    )

                for j in range(
                    min(element_count, 10)
                ):

                    element = elements.nth(j)

                    style = element.get_attribute(
                        "style"
                    )

                    if debug and i == 0:
                        print(
                            "BACKGROUND STYLE:",
                            style
                        )

                    if style and "url(" in style:

                        start = style.find(
                            "url("
                        ) + 4

                        end = style.find(
                            ")",
                            start
                        )

                        if end > start:

                            url = style[
                                start:end
                            ].strip(
                                "\"'"
                            )

                            if (
                                url
                                and not url.startswith(
                                    "data:"
                                )
                                and url not in images
                            ):
                                images.append(url)

            except Exception as e:

                if debug and i == 0:
                    print(
                        "BACKGROUND IMAGE ERROR:",
                        repr(e)
                    )

            if debug and i == 0:
                print()
                print(
                    "FINAL IMAGE URLS FOUND:"
                )

                for image in images:
                    print(image)

                print("=" * 70)
                print()

            if href.startswith("/"):
                href = (
                    "https://www.binance.com"
                    + href
                )

            posts[post_id] = {
                "id": post_id,
                "webLink": href,
                "content": text.strip(),
                "images": images[:4]
            }

        except Exception as e:

            print(
                "Post extraction error:",
                repr(e)
            )

            continue

    return posts


def scrape_profile():

    print("=" * 60)
    print("BINANCE SQUARE TF_BNB SCRAPER")
    print("=" * 60)

    print(
        "Profile:",
        SOURCE_AUTHOR
    )

    posts = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        page = browser.new_page(
            viewport={
                "width": 1280,
                "height": 900
            },
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 "
                "Safari/537.36"
            )
        )

        print(
            "Opening profile..."
        )

        page.goto(
            PROFILE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        time.sleep(7)

        print(
            "Page:",
            page.title()
        )

        # ----------------------------------------------------
        # FIRST EXTRACTION WITH DEBUG ENABLED
        # ----------------------------------------------------

        visible = extract_visible_posts(
            page,
            debug=True
        )

        posts.update(visible)

        print(
            f"Initial extraction: "
            f"{len(posts)} posts"
        )

        # ----------------------------------------------------
        # SCROLLING
        # ----------------------------------------------------

        for scroll in range(12):

            page.mouse.wheel(
                0,
                2500
            )

            time.sleep(2)

            visible = extract_visible_posts(
                page,
                debug=False
            )

            before = len(posts)

            posts.update(visible)

            print(
                f"Scroll {scroll + 1}/12 | "
                f"visible={len(visible)} | "
                f"total={len(posts)}"
            )

            if len(posts) == before:

                time.sleep(3)

                visible = extract_visible_posts(
                    page,
                    debug=False
                )

                posts.update(visible)

        browser.close()

    result = list(posts.values())

    print()
    print(
        "TOTAL POSTS FOUND:",
        len(result)
    )

    for post in result[:10]:

        print()
        print(
            "POST:",
            post["id"]
        )

        print(
            "IMAGES:",
            len(post["images"])
        )

        if post["images"]:
            for image in post["images"]:
                print(
                    "IMAGE URL:",
                    image
                )

    return result


def process_post(post):

    text = post["content"].strip()

    if not text:
        print(
            "Skipping empty post:",
            post["id"]
        )

        return False

    image_urls = post.get(
        "images",
        []
    )

    # --------------------------------------------------------
    # TEXT ONLY
    # --------------------------------------------------------

    if not image_urls:

        print(
            "Publishing text-only post..."
        )

        result = publish_text(text)

        return bool(result)

    # --------------------------------------------------------
    # IMAGE POST
    # --------------------------------------------------------

    print(
        f"Found {len(image_urls)} image(s)."
    )

    MEDIA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    local_files = []

    for index, url in enumerate(
        image_urls[:4],
        start=1
    ):

        try:

            path = download_image(
                url,
                MEDIA_DIR,
                index
            )

            local_files.append(path)

        except Exception as e:

            print(
                "Image download failed:",
                repr(e)
            )

    if not local_files:

        print(
            "All image downloads failed."
        )

        return False

    processed_urls = []

    for path in local_files:

        try:

            uploaded_url = upload_one_image(
                path
            )

            processed_urls.append(
                uploaded_url
            )

        except Exception as e:

            print(
                "Binance image upload failed:",
                repr(e)
            )

    if not processed_urls:

        print(
            "No images successfully uploaded."
        )

        return False

    result = publish_images(
        text,
        processed_urls
    )

    return bool(result)


def main():

    state = load_state()

    posts = scrape_profile()

    if not posts:

        print(
            "No posts found."
        )

        return

    processed = set(
        state.get(
            "processed_ids",
            []
        )
    )

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not state.get(
        "initialized",
        False
    ):

        print()
        print(
            "FIRST RUN:"
        )

        print(
            "Marking existing posts "
            "as processed."
        )

        for post in posts:

            processed.add(
                post["id"]
            )

        state["processed_ids"] = list(
            processed
        )

        state["initialized"] = True

        save_state(state)

        print(
            "Initialization complete."
        )

        return

    # --------------------------------------------------------
    # NEW POSTS
    # --------------------------------------------------------

    new_posts = [
        post
        for post in posts
        if post["id"] not in processed
    ]

    print()
    print(
        "NEW POSTS:",
        len(new_posts)
    )

    new_posts.reverse()

    for post in new_posts:

        print()
        print("=" * 50)

        print(
            "NEW POST:",
            post["id"]
        )

        print(
            "SOURCE:",
            post["webLink"]
        )

        print(
            "IMAGES:",
            len(post.get("images", []))
        )

        try:

            success = process_post(post)

            if success:

                processed.add(
                    post["id"]
                )

                state["processed_ids"] = list(
                    processed
                )

                save_state(state)

                print(
                    "SUCCESS:",
                    post["id"]
                )

            else:

                print(
                    "NOT MARKED PROCESSED."
                )

        except Exception as e:

            print(
                "POST FAILED:",
                repr(e)
            )

            print(
                "It will be retried "
                "on the next run."
            )

    save_state(state)


if __name__ == "__main__":
    main()
