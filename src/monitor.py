import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from binance_square import (
    download_image,
    upload_one_image,
    publish_text,
    publish_images,
)


# ============================================================
# CONFIG
# ============================================================

SOURCE_AUTHOR = os.getenv(
    "SOURCE_AUTHOR",
    "TF_bnb"
)

BASE_URL = "https://www.binance.com"

PROFILE_URL = (
    f"{BASE_URL}/en/square/profile/{SOURCE_AUTHOR}"
)

STATE_FILE = Path("src/state.json")

MEDIA_DIR = Path("tmp_media")

MAX_POSTS = 50
MAX_IMAGES_PER_POST = 4

SCRAPE_RETRIES = 4

SCROLL_COUNT = 12
SCROLL_PIXELS = 2500

SCROLL_WAIT = 2

PAGE_WAIT = 7


# ============================================================
# IMAGE URL PATTERNS
# ============================================================

# Square user-uploaded images normally appear under this path.
PGC_IMAGE_PATTERN = re.compile(
    r'https?://(?:public|bin)\.bnbstatic\.com/image/pgc/'
    r'[A-Za-z0-9_./:%?=&-]+'
)

# Also support protocol-relative URLs.
PGC_IMAGE_PATTERN_PROTOCOL_RELATIVE = re.compile(
    r'//(?:public|bin)\.bnbstatic\.com/image/pgc/'
    r'[A-Za-z0-9_./:%?=&-]+'
)


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

        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            raise ValueError("Invalid state format")

        data.setdefault(
            "initialized",
            False
        )

        data.setdefault(
            "processed_ids",
            []
        )

        return data

    except Exception as e:

        print(
            "WARNING: Could not read state.json:",
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

    processed = state.get(
        "processed_ids",
        []
    )

    # Remove duplicates while preserving order.
    processed = list(
        dict.fromkeys(
            str(x)
            for x in processed
        )
    )

    # Keep the last 500 IDs.
    processed = processed[-500:]

    state["processed_ids"] = processed

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(url):

    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return urljoin(
            BASE_URL,
            url
        )

    return url


def is_valid_post_image(url):

    if not url:
        return False

    url = normalize_url(url)

    if not url:
        return False

    lower = url.lower()

    # We specifically want Square PGC uploads.
    if "/image/pgc/" not in lower:
        return False

    # Ignore obvious UI/asset files.
    blocked_terms = [
        "cookie",
        "logo",
        "brand",
        "static/content/square/images",
        "static/content/",
        "admin_mgs_image_upload",
    ]

    for term in blocked_terms:

        if term in lower:
            return False

    # Basic image extension check.
    # Binance sometimes omits extensions, so don't require one.
    valid_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    )

    if (
        not any(
            lower.split("?")[0].endswith(ext)
            for ext in valid_extensions
        )
    ):
        # PGC URLs are still accepted because Binance
        # can serve extensionless/image-transformed URLs.
        pass

    return True


# ============================================================
# IMAGE EXTRACTION
# ============================================================

def extract_pgc_images_from_html(html):

    if not html:
        return []

    found = []

    # Normal absolute URLs.
    for match in PGC_IMAGE_PATTERN.findall(html):

        url = normalize_url(match)

        if (
            url
            and is_valid_post_image(url)
            and url not in found
        ):

            found.append(url)

    # Protocol-relative URLs.
    for match in (
        PGC_IMAGE_PATTERN_PROTOCOL_RELATIVE.findall(
            html
        )
    ):

        url = normalize_url(match)

        if (
            url
            and is_valid_post_image(url)
            and url not in found
        ):

            found.append(url)

    return found


def extract_images_from_container(container):

    images = []

    try:

        html = container.evaluate(
            "(el) => el.outerHTML"
        )

        images.extend(
            extract_pgc_images_from_html(
                html
            )
        )

    except Exception as e:

        print(
            "Container HTML extraction failed:",
            repr(e)
        )

    # --------------------------------------------------------
    # Also inspect image elements.
    # --------------------------------------------------------

    try:

        imgs = container.locator("img")

        count = imgs.count()

        for i in range(count):

            try:

                img = imgs.nth(i)

                attributes = [
                    "src",
                    "data-src",
                    "data-original",
                    "data-lazy-src"
                ]

                for attribute in attributes:

                    value = img.get_attribute(
                        attribute
                    )

                    if not value:
                        continue

                    url = normalize_url(
                        value
                    )

                    if (
                        url
                        and is_valid_post_image(url)
                        and url not in images
                    ):

                        images.append(url)

            except Exception:
                continue

    except Exception:
        pass

    return images[:MAX_IMAGES_PER_POST]


# ============================================================
# POST CONTAINER
# ============================================================

def find_post_container(link):

    # Binance Square's structure can change, so use
    # several levels rather than relying on one class name.

    selectors = [
        "xpath=ancestor::article[1]",
        "xpath=ancestor::div[contains(@class,'feed-card')][1]",
        "xpath=ancestor::div[contains(@class,'FeedBuzzBaseViewRoot')][1]",
        "xpath=ancestor::div[contains(@class,'feed-buzz-card-base-view')][1]",
        "xpath=ancestor::div[contains(@class,'card-content-box')][1]",
    ]

    for selector in selectors:

        try:

            locator = link.locator(
                selector
            )

            if locator.count() > 0:

                container = locator.first

                try:

                    html_length = len(
                        container.evaluate(
                            "(el) => el.outerHTML"
                        )
                    )

                except Exception:

                    html_length = 0

                # Prefer a reasonably large container.
                if html_length >= 1000:
                    return container

        except Exception:
            continue

    # Last fallback.
    try:

        return link.locator(
            "xpath=ancestor::div[1]"
        )

    except Exception:

        return link


# ============================================================
# EXTRACT POSTS
# ============================================================

def extract_visible_posts(page, debug=False):

    posts = {}

    try:

        links = page.locator(
            'a[href*="/square/post/"]'
        )

        count = links.count()

    except Exception as e:

        print(
            "Could not locate post links:",
            repr(e)
        )

        return posts

    for i in range(count):

        try:

            link = links.nth(i)

            href = link.get_attribute(
                "href"
            )

            if not href:
                continue

            href = normalize_url(
                href
            )

            if not href:
                continue

            match = re.search(
                r"/square/post/(\d+)",
                href
            )

            if not match:
                continue

            post_id = match.group(1)

            if post_id in posts:
                continue

            container = find_post_container(
                link
            )

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

            text = text.strip()

            # ------------------------------------------------
            # IMAGES
            # ------------------------------------------------

            images = extract_images_from_container(
                container
            )

            # ------------------------------------------------
            # DEBUG
            # ------------------------------------------------

            if debug and i == 0:

                print()
                print(
                    "=" * 70
                )

                print(
                    "IMAGE DEBUG"
                )

                print(
                    "=" * 70
                )

                print(
                    "Post ID:",
                    post_id
                )

                print(
                    "IMG ELEMENTS:",
                    end=" "
                )

                try:

                    print(
                        container.locator(
                            "img"
                        ).count()
                    )

                except Exception:

                    print("?")

                print(
                    "PGC IMAGE URLS:",
                    len(images)
                )

                for image in images:

                    print(
                        "IMAGE:",
                        image
                    )

                print(
                    "=" * 70
                )
                print()

            posts[post_id] = {
                "id": post_id,
                "webLink": href,
                "content": text,
                "images": images
            }

        except Exception as e:

            # One malformed card should never stop
            # the entire scraper.
            continue

    return posts


# ============================================================
# PAGE VALIDATION
# ============================================================

def page_is_valid(page):

    try:

        title = page.title()

    except Exception:

        title = ""

    try:

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

    except Exception:

        body_text = ""

    combined = (
        (title or "")
        + "\n"
        + (body_text or "")
    ).lower()

    # Binance CDN/WAF error page.
    error_phrases = [
        "error: the request could not be satisfied",
        "request could not be satisfied",
        "request blocked",
        "access denied",
        "403 forbidden"
    ]

    for phrase in error_phrases:

        if phrase in combined:

            print(
                "BINANCE PAGE ERROR DETECTED:",
                phrase
            )

            return False

    # A valid profile page should contain Square/post links.
    try:

        post_count = page.locator(
            'a[href*="/square/post/"]'
        ).count()

    except Exception:

        post_count = 0

    if post_count > 0:
        return True

    # The page may still be loading.
    # Check the URL/title before declaring failure.
    try:

        current_url = page.url

    except Exception:

        current_url = ""

    if (
        "/square/profile/" in current_url
        and "binance.com" in current_url
    ):

        # Give dynamic content a chance.
        time.sleep(3)

        try:

            post_count = page.locator(
                'a[href*="/square/post/"]'
            ).count()

        except Exception:

            post_count = 0

        if post_count > 0:
            return True

    return False


# ============================================================
# BROWSER SETUP
# ============================================================

def create_context(browser):

    context = browser.new_context(

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
        ),

        locale="en-US",

        timezone_id="Asia/Kolkata",

        extra_http_headers={
            "Accept-Language":
                "en-US,en;q=0.9"
        }
    )

    return context


# ============================================================
# SCRAPE PROFILE
# ============================================================

def scrape_profile():

    print("=" * 60)
    print("BINANCE SQUARE TF_BNB SCRAPER")
    print("=" * 60)

    print(
        "Profile:",
        SOURCE_AUTHOR
    )

    all_posts = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(

            headless=True,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        success = False

        try:

            for attempt in range(
                1,
                SCRAPE_RETRIES + 1
            ):

                print()
                print(
                    f"PROFILE ATTEMPT "
                    f"{attempt}/{SCRAPE_RETRIES}"
                )

                context = None

                try:

                    context = create_context(
                        browser
                    )

                    page = context.new_page()

                    print(
                        "Opening profile..."
                    )

                    page.goto(
                        PROFILE_URL,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    time.sleep(
                        PAGE_WAIT
                    )

                    try:

                        print(
                            "Page:",
                            page.title()
                        )

                    except Exception:

                        pass

                    # ------------------------------------------------
                    # Detect Binance error/WAF page.
                    # ------------------------------------------------

                    if not page_is_valid(
                        page
                    ):

                        print(
                            "Profile page is not usable."
                        )

                        if attempt < SCRAPE_RETRIES:

                            print(
                                "Retrying in "
                                f"{attempt * 3} seconds..."
                            )

                            time.sleep(
                                attempt * 3
                            )

                            context.close()

                            continue

                        raise RuntimeError(
                            "Binance profile could not "
                            "be loaded after retries."
                        )

                    # ------------------------------------------------
                    # Initial extraction.
                    # ------------------------------------------------

                    visible = extract_visible_posts(
                        page,
                        debug=True
                    )

                    all_posts.update(
                        visible
                    )

                    print(
                        "Initial extraction:",
                        len(all_posts),
                        "posts"
                    )

                    # ------------------------------------------------
                    # Scroll.
                    # ------------------------------------------------

                    for scroll in range(
                        SCROLL_COUNT
                    ):

                        visible = extract_visible_posts(
                            page
                        )

                        before = len(
                            all_posts
                        )

                        all_posts.update(
                            visible
                        )

                        print(
                            f"Scroll {scroll + 1}/"
                            f"{SCROLL_COUNT} | "
                            f"visible={len(visible)} | "
                            f"total={len(all_posts)}"
                        )

                        page.mouse.wheel(
                            0,
                            SCROLL_PIXELS
                        )

                        time.sleep(
                            SCROLL_WAIT
                        )

                        # Occasionally wait a little longer
                        # for lazy-loaded content.
                        if (
                            scroll + 1
                        ) % 4 == 0:

                            time.sleep(2)

                    success = True

                    context.close()

                    break

                except Exception as e:

                    print()
                    print(
                        "SCRAPE ATTEMPT FAILED:",
                        repr(e)
                    )

                    if context:

                        try:
                            context.close()
                        except Exception:
                            pass

                    if attempt < SCRAPE_RETRIES:

                        wait_time = (
                            attempt * 4
                        )

                        print(
                            f"Retrying in "
                            f"{wait_time} seconds..."
                        )

                        time.sleep(
                            wait_time
                        )

                    else:

                        print(
                            "All scrape attempts failed."
                        )

        finally:

            browser.close()

    if not success:

        raise RuntimeError(
            "Could not obtain a valid Binance Square "
            "profile page."
        )

    re
