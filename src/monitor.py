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


# ============================================================
# STATE
# ============================================================

def load_state():

    if not STATE_FILE.exists():
        return {
            "initialized": False,
            "processed_ids": []
        }

    try:
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:
        print("State read error:", repr(e))

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


# ============================================================
# EXTRACT POSTS
# ============================================================

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

            # Find Binance's actual feed card.
            container = link.locator(
                "xpath=ancestor::div[contains(@class, 'feed-buzz-card-base-view')][1]"
            )

            if container.count() == 0:

                container = link

                for _ in range(10):

                    try:

                        parent = container.locator(
                            "xpath=.."
                        )

                        parent_class = (
                            parent.get_attribute(
                                "class"
                            )
                            or ""
                        )

                        if (
                            "feed-buzz-card-base-view"
                            in parent_class
                        ):

                            container = parent
                            break

                        container = parent

                    except Exception:
                        break

            # ------------------------------------------------
            # TEXT
            # ------------------------------------------------

            try:

                text = container.inner_text(
                    timeout=3000
                )

            except Exception:

                try:

                    text = link.inner_text(
                        timeout=3000
                    )

                except Exception:

                    text = ""

            # ------------------------------------------------
            # IMAGES
            # ------------------------------------------------

            images = []

            try:

                imgs = container.locator("img")

                img_count = imgs.count()

                if debug:

                    print()
                    print("=" * 60)
                    print("IMAGE DEBUG")
                    print("Post ID:", post_id)
                    print("IMG ELEMENTS FOUND:", img_count)

                for j in range(
                    min(img_count, 10)
                ):

                    img = imgs.nth(j)

                    candidates = []

                    # Normal image attributes.
                    for attr in [
                        "src",
                        "data-src",
                        "data-original",
                        "data-lazy-src",
                        "data-url",
                        "data-image"
                    ]:

                        try:

                            value = img.get_attribute(
                                attr
                            )

                            if value:
                                candidates.append(
                                    value
                                )

                        except Exception:
                            pass

                    # srcset.
                    try:

                        srcset = img.get_attribute(
                            "srcset"
                        )

                        if srcset:

                            for item in srcset.split(","):

                                item = item.strip()

                                if not item:
                                    continue

                                url = item.split(
                                    " "
                                )[0]

                                if url:
                                    candidates.append(
                                        url
                                    )

                    except Exception:
                        pass

                    for url in candidates:

                        if not url:
                            continue

                        if url.startswith("data:"):
                            continue

                        if "cookielaw.org" in url:
                            continue

                        if url not in images:
                            images.append(url)

                # Prefer actual Square PGC images.
                pgc_images = [
                    url
                    for url in images
                    if "public.bnbstatic.com/image/pgc/"
                    in url
                ]

                if pgc_images:

                    images = pgc_images

                else:

                    # Fallback for Binance CDN.
                    images = [
                        url
                        for url in images
                        if (
                            "bnbstatic.com" in url
                            or "binance.com" in url
                        )
                    ]

                images = images[:4]

                if debug:

                    print("FINAL IMAGE URLS:")

                    for image in images:
                        print("IMAGE:", image)

                    print("=" * 60)

            except Exception as e:

                if debug:
                    print(
                        "Image extraction error:",
                        repr(e)
                    )

            # ------------------------------------------------
            # NORMALIZE LINK
            # ------------------------------------------------

            if href.startswith("/"):
                href = (
                    "https://www.binance.com"
                    + href
                )

            posts[post_id] = {
                "id": post_id,
                "webLink": href,
                "content": text.strip(),
                "images": images
            }

        except Exception as e:

            print(
                "Post extraction error:",
                repr(e)
            )

    return posts


# ============================================================
# SCRAPE PROFILE
# ============================================================

def scrape_profile():

    print("=" * 60)
    print("BINANCE SQUARE TF_BNB SCRAPER")
    print("=" * 60)

    print("Profile:", SOURCE_AUTHOR)

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

        print("Opening profile...")

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

        # First extraction with debug.
        initial = extract_visible_posts(
            page,
            debug=True
        )

        posts.update(initial)

        print(
            "Initial extraction:",
            len(posts),
            "posts"
        )

        # Scroll and collect.
        for scroll in range(12):

            visible = extract_visible_posts(
                page
            )

            before = len(posts)

            posts.update(visible)

            print(
                f"Scroll {scroll + 1}/12 | "
                f"visible={len(visible)} | "
                f"total={len(posts)}"
            )

            page.mouse.wheel(
                0,
                2500
            )

            time.sleep(2)

            if len(posts) == before:

                time.sleep(3)

                visible = extract_visible_posts(
                    page
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
            len(post.get("images", []))
        )

        for image in post.get("images", []):
            print(
                "IMAGE:",
                image
            )

    return result


# ============================================================
# PROCESS ONE POST
# ============================================================

def process_post(post):

    post_id = post["id"]

    text = post.get(
        "content",
        ""
    ).strip()

    if not text:

        print(
            "Skipping empty post:",
            post_id
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
            "No images found."
        )

        print(
            "Publishing text-only post..."
        )

        result = publish_text(text)

        print(
            "Text publish response:",
            result
        )

        if isinstance(result, dict):

            code = result.get("code")

            return code in (
                "000000",
                0,
                None
            )

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

    # Download.
    for index, url in enumerate(
        image_urls[:4],
        start=1
    ):

        try:

            print(
                f"Downloading image {index}:",
                url
            )

            path = download_image(
                url,
                MEDIA_DIR,
                index
            )

            local_files.append(path)

            print(
                "Downloaded:",
                path
            )

        except Exception as e:

            print(
                "Image download failed:",
                repr(e)
            )

    if not local_files:

        print(
            "All image downloads failed."
        )

        print(
            "NOT publishing text-only."
        )

        return False

    # Upload to Binance.
    processed_urls = []

    for path in local_files:

        try:

            print(
                "Uploading:",
                path
            )

            uploaded_url = upload_one_image(
                path
            )

            if uploaded_url:

                processed_urls.append(
                    uploaded_url
                )

                print(
                    "Uploaded URL:",
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

    # Publish.
    print(
        "Publishing image post..."
    )

    result = publish_images(
        text,
        processed_urls
    )

    print(
        "Publish response:",
        result
    )

    if isinstance(result, dict):

        code = result.get("code")

        if code in (
            "000000",
            0,
            None
        ):
            return True

        print(
            "Publish failed with code:",
            code
        )

        return False

    return bool(result)


# ============================================================
# MAIN
# ============================================================

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
            "FIRST RUN"
        )

        print(
            "Marking existing posts as processed."
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
    # FIND NEW POSTS
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

    if not new_posts:

        return

    # Oldest first.
    new_posts.reverse()

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

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
            len(
                post.get(
                    "images",
                    []
                )
            )
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
                    "FAILED:",
                    post["id"]
                )

                print(
                    "NOT marked as processed."
                )

        except Exception as e:

            print(
                "POST FAILED:",
                repr(e)
            )

            print(
                "Will retry on next run."
            )

    save_state(state)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
