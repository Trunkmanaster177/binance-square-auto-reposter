import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


SOURCE_AUTHOR = os.getenv(
    "SOURCE_AUTHOR",
    "TF_bnb"
)

PROFILE_URL = (
    "https://www.binance.com/en/square/profile/"
    + SOURCE_AUTHOR
)


def inspect_posts(page):

    print()
    print("=" * 80)
    print("BINANCE DOM IMAGE INVESTIGATION")
    print("=" * 80)

    links = page.locator(
        'a[href*="/square/post/"]'
    )

    count = links.count()

    print(
        "POST LINKS FOUND:",
        count
    )

    if count == 0:
        print("No post links found.")
        return

    # Inspect first few posts instead of only one.
    for i in range(min(count, 3)):

        try:

            link = links.nth(i)

            href = link.get_attribute(
                "href"
            )

            print()
            print("-" * 80)
            print(
                f"POST LINK #{i + 1}:",
                href
            )
            print("-" * 80)

            # ------------------------------------------------
            # WALK UP THE DOM
            # ------------------------------------------------

            current = link

            for level in range(1, 8):

                try:

                    current = current.locator(
                        "xpath=.."
                    )

                    tag = current.evaluate(
                        "(el) => el.tagName"
                    )

                    class_name = current.get_attribute(
                        "class"
                    )

                    html = current.evaluate(
                        "(el) => el.outerHTML"
                    )

                    print()
                    print(
                        f"DOM LEVEL {level}: "
                        f"<{tag}>"
                    )

                    print(
                        "CLASS:",
                        class_name
                    )

                    print(
                        "HTML LENGTH:",
                        len(html or "")
                    )

                    # ------------------------------------------------
                    # IMAGE-RELATED ELEMENTS
                    # ------------------------------------------------

                    try:

                        image_count = current.locator(
                            "img"
                        ).count()

                        picture_count = current.locator(
                            "picture"
                        ).count()

                        source_count = current.locator(
                            "source"
                        ).count()

                        video_count = current.locator(
                            "video"
                        ).count()

                        print(
                            "IMG:",
                            image_count,
                            "| PICTURE:",
                            picture_count,
                            "| SOURCE:",
                            source_count,
                            "| VIDEO:",
                            video_count
                        )

                    except Exception:
                        pass

                    # Stop when we reach a reasonably large container.
                    if len(html or "") > 50000:

                        print(
                            "Large container reached."
                        )

                        # Save HTML to artifact file.
                        Path(
                            "debug_post.html"
                        ).write_text(
                            html,
                            encoding="utf-8"
                        )

                        print(
                            "Saved:",
                            "debug_post.html"
                        )

                        break

                except Exception as e:

                    print(
                        "DOM inspection error:",
                        repr(e)
                    )

                    break

            # ------------------------------------------------
            # SEARCH THE ENTIRE PAGE FOR IMAGE-LIKE URLs
            # ------------------------------------------------

            print()
            print(
                "SEARCHING PAGE HTML FOR IMAGE URLS..."
            )

            page_html = page.content()

            # Print URLs containing common image extensions.
            import re

            matches = re.findall(
                r'https?://[^"\']+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\']*)?',
                page_html,
                flags=re.IGNORECASE
            )

            unique_matches = []

            for match in matches:

                if match not in unique_matches:
                    unique_matches.append(match)

            print(
                "IMAGE-LIKE URLS FOUND:",
                len(unique_matches)
            )

            for url in unique_matches[:20]:

                print(
                    "IMAGE:",
                    url[:500]
                )

            # ------------------------------------------------
            # SEARCH FOR BINANCE CDN URLS
            # ------------------------------------------------

            print()
            print(
                "SEARCHING FOR BINANCE CDN REFERENCES..."
            )

            cdn_matches = re.findall(
                r'https?://[^"\']*binance[^"\']*',
                page_html,
                flags=re.IGNORECASE
            )

            unique_cdn = []

            for url in cdn_matches:

                if url not in unique_cdn:
                    unique_cdn.append(url)

            print(
                "BINANCE URL REFERENCES:",
                len(unique_cdn)
            )

            for url in unique_cdn[:30]:

                print(
                    "BINANCE:",
                    url[:500]
                )

        except Exception as e:

            print(
                "POST INSPECTION ERROR:",
                repr(e)
            )


def main():

    print("=" * 60)
    print("BINANCE SQUARE DOM DEBUGGER")
    print("=" * 60)

    print(
        "Profile:",
        SOURCE_AUTHOR
    )

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

        time.sleep(8)

        print(
            "Page:",
            page.title()
        )

        inspect_posts(page)

        # ------------------------------------------------
        # SAVE FULL PAGE HTML
        # ------------------------------------------------

        try:

            html = page.content()

            Path(
                "debug_page.html"
            ).write_text(
                html,
                encoding="utf-8"
            )

            print()
            print(
                "Full page HTML saved:"
            )

            print(
                "debug_page.html"
            )

            print(
                "HTML size:",
                len(html)
            )

        except Exception as e:

            print(
                "Could not save page HTML:",
                repr(e)
            )

        browser.close()

    print()
    print("=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
