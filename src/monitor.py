import os
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

SOURCE_AUTHOR = os.getenv("SOURCE_AUTHOR", "TF_bnb")

PROFILE_URL = (
    "https://www.binance.com/en/square/profile/"
    + SOURCE_AUTHOR
)

STATE_FILE = Path("src/state.json")


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

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

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
            state.get(
                "processed_ids",
                []
            )
        )
    )[-500:]

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# SCRAPE PROFILE WITH BROWSER
# ============================================================

def scrape_profile():

    print("=" * 60)
    print("BINANCE SQUARE BROWSER SCRAPER")
    print("=" * 60)

    print(
        "Profile:",
        SOURCE_AUTHOR
    )

    print(
        "URL:",
        PROFILE_URL
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
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
                "Chrome/139.0.0.0 Safari/537.36"
            )
        )

        print()
        print("Opening Binance profile...")

        try:

            page.goto(
                PROFILE_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

        except Exception as e:

            print(
                "Navigation warning:",
                repr(e)
            )

        print(
            "Waiting for Binance Square..."
        )

        time.sleep(8)

        print(
            "Current URL:",
            page.url
        )

        title = page.title()

        print(
            "Page title:",
            repr(title)
        )

        # ----------------------------------------------------
        # CHECK AWS WAF
        # ----------------------------------------------------

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        lower_body = body_text.lower()

        waf_words = [
            "verify that you're not a robot",
            "aws waf",
            "challenge",
            "javascript is disabled"
        ]

        if any(
            word in lower_body
            for word in waf_words
        ):

            print()
            print(
                "AWS WAF / BOT CHALLENGE DETECTED."
            )

            print(
                "GitHub Actions cannot access "
                "the profile through this browser."
            )

            print()
            print(
                "First 3000 characters:"
            )

            print(
                body_text[:3000]
            )

            browser.close()

            return []

        # ----------------------------------------------------
        # SCROLL PROFILE
        # ----------------------------------------------------

        print()
        print(
            "Scrolling profile..."
        )

        for i in range(6):

            page.mouse.wheel(
                0,
                2500
            )

            time.sleep(2)

            print(
                "Scroll",
                i + 1,
                "/ 6"
            )

        # ----------------------------------------------------
        # FIND POST LINKS
        # ----------------------------------------------------

        print()
        print(
            "Searching for Square posts..."
        )

        post_links = page.locator(
            'a[href*="/square/post/"]'
        )

        count = post_links.count()

        print(
            "Post links found:",
            count
        )

        posts = {}

        for i in range(count):

            try:

                link = post_links.nth(i)

                href = link.get_attribute(
                    "href"
                )

                if not href:
                    continue

                # --------------------------------------------
                # EXTRACT POST ID
                # --------------------------------------------

                parts = href.rstrip(
                    "/"
                ).split("/")

                post_id = parts[-1]

                if not post_id.isdigit():
                    continue

                if post_id in posts:
                    continue

                # --------------------------------------------
                # FIND POST CONTAINER
                # --------------------------------------------

                article = link.locator(
                    "xpath=ancestor::article[1]"
                )

                if article.count() == 0:

                    article = link.locator(
                        "xpath=ancestor::*[self::div][1]"
                    )

                try:

                    text = article.inner_text(
                        timeout=3000
                    )

                except Exception:

                    text = link.inner_text(
                        timeout=3000
                    )

                # --------------------------------------------
                # IMAGES
                # --------------------------------------------

                images = []

                try:

                    imgs = article.locator(
                        "img"
                    )

                    img_count = imgs.count()

                    for j in range(
                        min(
                            img_count,
                            4
                        )
                    ):

                        src = imgs.nth(
                            j
                        ).get_attribute(
                            "src"
                        )

                        if src:
                            images.append(
                                src
                            )

                except Exception:
                    pass

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

        browser.close()

        result = list(
            posts.values()
        )

        print()
        print(
            "Unique posts extracted:",
            len(result)
        )

        # ----------------------------------------------------
        # DEBUG
        # ----------------------------------------------------

        for post in result[:10]:

            print()
            print(
                "POST ID:",
                post["id"]
            )

            print(
                "LINK:",
                post["webLink"]
            )

            print(
                "CONTENT:",
                post["content"][:500]
            )

            print(
                "IMAGES:",
                len(
                    post["images"]
                )
            )

        return result


# ============================================================
# MAIN
# ============================================================

def main():

    posts = scrape_profile()

    if not posts:

        print()
        print(
            "NO POSTS EXTRACTED."
        )

        return

    state = load_state()

    processed = set(
        state.get(
            "processed_ids",
            []
        )
    )

    print()
    print(
        "Already processed:",
        len(processed)
    )

    new_posts = [
        post
        for post in posts
        if post["id"]
        not in processed
    ]

    print(
        "New posts:",
        len(new_posts)
    )

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not state.get(
        "initialized"
    ):

        print()
        print(
            "FIRST RUN."
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
            "Existing TF_bnb posts "
            "marked as processed."
        )

        print(
            "Future new posts will be "
            "detected automatically."
        )

        return

    # --------------------------------------------------------
    # SHOW NEW POSTS
    # --------------------------------------------------------

    if not new_posts:

        print()
        print(
            "No new TF_bnb posts."
        )

        return

    print()
    print(
        "========== NEW POSTS =========="
    )

    for post in new_posts:

        print()
        print(
            "POST ID:",
            post["id"]
        )

        print(
            "LINK:",
            post["webLink"]
        )

        print(
            "CONTENT:"
        )

        print(
            post["content"][:2000]
        )

        print(
            "IMAGES:",
            len(
                post["images"]
            )
        )

    print()
    print(
        "================================"
    )

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------
    #
    # We intentionally DO NOT mark new posts as processed yet.
    #
    # First we confirm that the browser scraper works.
    # Then we'll connect the Binance Square OpenAPI publisher.
    #

    print()
    print(
        "Browser scraper test complete."
    )

    print(
        "New posts were NOT marked processed."
    )

    print(
        "This allows us to test safely."
    )

    print()
    print(
        "Finished:",
        datetime.now(
            timezone.utc
        ).isoformat()
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print()
        print(
            "FATAL ERROR:",
            repr(e)
        )

        sys.exit(1)
