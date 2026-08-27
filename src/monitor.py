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


SOURCE_AUTHOR = os.getenv(
    "SOURCE_AUTHOR",
    "TF_bnb"
)

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

        print(
            "State file read error:",
            repr(e)
        )

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
            state.get(
                "processed_ids",
                []
            )
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
# IMAGE EXTRACTION
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

            href = link.get_attribute(
                "href"
            )

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

            # ------------------------------------------------
            # FIND REAL BINANCE FEED CARD
            # ------------------------------------------------

            container = link.locator(
                "xpath=ancestor::div[contains(@class, 'feed-buzz-card-base-view')][1]"
            )

            if container.count() == 0:

                # Fallback: walk upward through DOM
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

                imgs = container.locator(
                    "img"
                )

                img_count = imgs.count()

                if debug:

                    print()
                    print(
                        "=" * 60
                    )

                    print(
                        "IMAGE DEBUG"
                    )

                    print(
                        "Post ID:",
                        post_id
                    )

                    print(
                        "REAL CONTAINER:",
                        container.get_attribute(
                            "class"
                        )
                    )

                    print(
                        "IMG ELEMENTS FOUND:",
                        img_count
                    )

                for j in range(
                    min(img_count, 10)
                ):

                    img = imgs.nth(j)

                    candidates = []

                    # ----------------------------------------
                    # STANDARD IMAGE ATTRIBUTES
                    # ----------------------------------------

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

                    # ----------------------------------------
                    # SRCSET
                    # ----------------------------------------

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

                    # ----------------------------------------
                    # FILTER CANDIDATES
                    # ----------------------------------------

                    for url in candidates:

                        if not url:
                            continue

                        if url.startswith(
                            "data:"
                        ):
                            continue

                        # Ignore cookie UI
                        if (
                            "cookielaw.org"
                            in url
                        ):
                            continue

                        if url not in images:

                            images.append(
                                url
                            )

                # ------------------------------------------------
                # KEEP ACTUAL BINANCE PGC IMAGES
                # ------------------------------------------------

                pgc_images = [
                    url
                    for url in images
                    if (
                        "public.bnbstatic.com/image/pgc/"
                        in url
                    )
                ]

                if pgc_images:

                    images = pgc_images

                # ------------------------------------------------
                # FALLBACK FOR OTHER BINANCE IMAGE HOSTS
                # ------------------------------------------------

                else:

                    binance_images = [
                        url
                        for url in images
                        if (
                            "bnbstatic.com"
                            in url
                            or "binance.com"
                            in url
                        )
                    ]

                    images = binance_images

                if debug:

                    print(
                        "FINAL IMAGE URLS FOUND:"
                    )

                    for image in images[:4]:

                        print(
                            "IMAGE:",
                            image
                        )

                    print(
                        "=" * 60
                    )

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

            # ------------------------------------------------
            # SAVE POST
            # ------------------------------------------------

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


# ============================================================
# SCRAPE BINANCE SQUARE PROFILE
# ============================================================

def scrape_profile():

    print("=" * 60)

    print(
        "BINANCE SQUARE TF_BNB SCRAPER"
    )

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

        # ------------------------------------------------
        # FIRST EXTRACTION WITH DEBUG
        # ------------------------------------------------

        initial = extract_visible_posts(
            page,
            debug=True
        )

        posts.update(
            initial
        )

        print(
            "Initial extraction:",
            len(posts),
            "posts"
        )

        # ------------------------------------------------
        # SCROLL
        # ------------------------------------------------

        for scroll in range(12):

            visible = extract_visible_posts(
                page
            )

            before = len(posts)

            posts.update(
                visible
            )

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

            # ------------------------------------------------
            # EXTRA WAIT IF NOTHING NEW
            # ------------------------------------------------

            if len(posts) == before:

                time.sleep(3)

                visible = extract_visible_posts(
                    page
                )

                posts.update(
                    visible
                )

        browser.close()

    result = list(
        posts.values()
    )

    print()

    print(
        "TOTAL POSTS FOUND:",
        len(result)
    )

    # ------------------------------------------------
    # SHOW FIRST 10 POSTS
    # ------------------------------------------------

    for post in result[:10]:

        print()

        print(
            "POST:",
            post["id"]
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

        if post.get("images"):

            for image in post["images"]:

                print(
                    "IMAGE:",
                    image
                )

    return result


# ============================================================
# PROCESS ONE POST
# ============================================================

def process_post(post):

    text = post.get(
        "content",
        ""
    ).strip()

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

    # ========================================================
    # TEXT ONLY
    # ========================================================

    if not image_urls:

        print(
            "No images found."
        )

        print(
            "Publishing text-only post..."
        )

        result = publish_text(
            text
        )

        return bool(result)

    # ========================================================
    # IMAGE POST
    # ========================================================

    print(
        f"Found {len(image_urls)} image(s)."
    )

    MEDIA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    local_files = []

    # ------------------------------------------------
    # DOWNLOAD IMAGES
    # ------------------------------------------------

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

            local_files.append(
                path
            )

            print(
                "Downloaded:",
                path
            )

        except Exception as e:

            print(
                "Image download failed:",
                repr(e)
            )

    # ------------------------------------------------
    # DON'T PUBLISH TEXT-ONLY IF IMAGE DOWNLOAD FAILED
    # ------------------------------------------------

    if not local_files:

        print(
            "All image downloads failed."
        )

        print(
            "Post will NOT be published."
        )

        return False

    # ------------------------------------------------
    # UPLOAD IMAGES TO BINANCE
    # ------------------------------------------------

    processed_urls = []

    for path in local_files:

        try:

            uploaded_url = (
                upload_one_image(
                    path
                )
            )

            if uploaded_url:

                processed_urls.append(
                    uploaded_url
                )

                print(
                    "Uploaded image URL:",
                    uploaded_url
                )

        except Exception as e:

            print(
                "Binance image upload failed:",
                repr(e)
            )

    # ------------------------------------------------
    # NO SUCCESSFUL UPLOADS
    # ------------------------------------------------

    if not processed_urls:

        print(
            "No images successfully uploaded."
        )

        print(
            "Post will NOT be marked processed."
        )

        return False

    # ------------------------------------------------
    # PUBLISH IMAGE POST
    # ------------------------------------------------

    print(
        "Publishing image post..."
    )

    result = publish_images(
        text,
        processed_urls
    )

    print(
        "Publish result:",
        result
    )

    # ------------------------------------------------
    # IMPORTANT:
    # Don't blindly assume HTTP 200 means success.
    # Check common Binance response codes.
    # ------------------------------------------------

    if not isinstance(
        result,
        dict
    ):

        return False

    code = result.get(
        "code"
    )

    if code in (
        "000000",
        0,
        None
    ):

        return True

    print(
        "Binance publish returned failure code:",
        code
    )

    return False


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

    # ========================================================
    # FIRST RUN
    # ========================================================

    if not state.get(
        "initialized",
        False
    ):

        print()

        print(
            "FIRST RUN:"
        )

        print(
            "Marking existing posts as processed."
        )

        for post in posts:

            processed.add(
                post["id"]
            )

        state[
            "processed_ids"
        ] = list(
            processed
        )

        state[
            "initialized"
        ] = True

        save_state(
            state
        )

        print(
            "Initialization complete."
        )

        print(
            "Existing posts will NOT be reposted."
        )

        return

    # ========================================================
    # FIND NEW POSTS
    # ========================================================

    new_posts = [

        post

        for post in posts

        if post["id"]
        not in processed
    ]

    print()

    print(
        "NEW POSTS:",
        len(new_posts)
    )

    if not new_posts:

        return

    # ========================================================
    # OLDEST FIRST
    # ========================================================

    new_posts.reverse()

    # ========================================================
    # PROCESS NEW POSTS
    # ========================================================

    for post in new_posts:

        print()

        print(
            "=" * 50
        )

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

            success = pro
