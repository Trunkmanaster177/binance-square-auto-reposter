import os
import json
import sys
import requests
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

SOURCE_AUTHOR = os.getenv("SOURCE_AUTHOR", "TF_bnb")

FEED_URL = (
    "https://www.binance.com/"
    "bapi/composite/v3/friendly/pgc/content/article/list"
)

POST_URL = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi/content/add"
)

STATE_FILE = Path("src/state.json")

PAGE_SIZE = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.binance.com/en/square",
}


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
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "initialized": False,
            "processed_ids": []
        }


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Keep only the newest 500 IDs
    state["processed_ids"] = state.get("processed_ids", [])[-500:]

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# FETCH BINANCE SQUARE
# ============================================================

def get_latest_posts():

    params = {
        "pageIndex": 1,
        "pageSize": PAGE_SIZE,
        "type": 2
    }

    print("Fetching Binance Square...")

    response = requests.get(
        FEED_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    # Binance/community endpoint formats can change.
    # Try common response structures.

    posts = []

    if isinstance(data, dict):

        data_section = data.get("data")

        if isinstance(data_section, list):
            posts = data_section

        elif isinstance(data_section, dict):

            for key in (
                "list",
                "articles",
                "items",
                "data"
            ):
                value = data_section.get(key)

                if isinstance(value, list):
                    posts = value
                    break

    if not posts:
        print("No posts found in response.")

    return posts


# ============================================================
# FILTER SOURCE CREATOR
# ============================================================

def is_source_post(post):

    author_name = str(
        post.get("authorName", "")
    ).strip()

    # Exact match first
    if author_name.lower() == SOURCE_AUTHOR.lower():
        return True

    # Some responses may expose handle separately
    for key in (
        "authorHandle",
        "username",
        "handle",
        "nickname"
    ):
        value = str(
            post.get(key, "")
        ).strip()

        if value.lower().lstrip("@") == SOURCE_AUTHOR.lower().lstrip("@"):
            return True

    return False


# ============================================================
# EXTRACT POST
# ============================================================

def extract_post(post):

    post_id = str(
        post.get("id", "")
    ).strip()

    content = (
        post.get("content")
        or post.get("body")
        or post.get("bodyText")
        or ""
    )

    title = (
        post.get("title")
        or ""
    )

    web_link = (
        post.get("webLink")
        or post.get("url")
        or ""
    )

    images = post.get("images") or []

    return {
        "id": post_id,
        "title": str(title).strip(),
        "content": str(content).strip(),
        "webLink": str(web_link).strip(),
        "images": images
    }


# ============================================================
# BUILD CONTENT
# ============================================================

def build_repost_text(post):

    content = post["content"]

    if not content:
        return None

    # Don't create an empty post.
    # Add attribution so it isn't presented as your original work.

    source_line = (
        f"\n\nSource: @{SOURCE_AUTHOR}"
    )

    if post["webLink"]:
        source_line += (
            f"\nOriginal: {post['webLink']}"
        )

    final_text = content + source_line

    # Binance Square has content-length restrictions.
    # Keep a reasonable safety limit.

    if len(final_text) > 8000:
        final_text = final_text[:7950] + "..." + source_line

    return final_text


# ============================================================
# PUBLISH TO YOUR SQUARE
# ============================================================

def publish_to_square(text):

    api_key = os.getenv(
        "BINANCE_SQUARE_OPENAPI_KEY"
    )

    if not api_key:
        print(
            "ERROR: BINANCE_SQUARE_OPENAPI_KEY "
            "GitHub Secret is missing."
        )

        return False

    headers = {
        "X-Square-OpenAPI-Key": api_key,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill",
        "User-Agent": HEADERS["User-Agent"]
    }

    payload = {
        "bodyTextOnly": text
    }

    print("Publishing to your Binance Square...")

    response = requests.post(
        POST_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    print(
        "Binance publish HTTP status:",
        response.status_code
    )

    try:
        result = response.json()
    except Exception:
        result = response.text

    print("Publish response:")
    print(json.dumps(
        result,
        indent=2,
        ensure_ascii=False
    ) if isinstance(result, dict) else result)

    if response.ok:

        if isinstance(result, dict):

            code = result.get("code")

            # Binance commonly uses 200 for success.
            if code not in (None, 200, "200"):
                print(
                    "Binance returned an API error:",
                    code
                )
                return False

        return True

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("Binance Square Auto Reposter")
    print("=" * 60)

    print(
        "Source creator:",
        SOURCE_AUTHOR
    )

    state = load_state()

    posts = get_latest_posts()

    if not posts:
        print("No feed posts returned.")
        return

    source_posts = [
        p for p in posts
        if is_source_post(p)
    ]

    print(
        f"Found {len(source_posts)} post(s) "
        f"from {SOURCE_AUTHOR}"
    )

    # --------------------------------------------------------
    # FIRST RUN SAFETY
    # --------------------------------------------------------

    if not state.get("initialized"):

        print()
        print(
            "FIRST RUN: initializing state."
        )

        for post in source_posts:

            extracted = extract_post(post)

            if extracted["id"]:
                state["processed_ids"].append(
                    extracted["id"]
                )

        state["initialized"] = True

        save_state(state)

        print(
            "Existing posts were marked as processed."
        )

        print(
            "The bot will start reposting NEW posts "
            "from the next scheduled run."
        )

        return

    # --------------------------------------------------------
    # FIND NEW POSTS
    # --------------------------------------------------------

    processed_ids = set(
        state.get("processed_ids", [])
    )

    new_posts = []

    for post in source_posts:

        extracted = extract_post(post)

        if not extracted["id"]:
            continue

        if extracted["id"] not in processed_ids:
            new_posts.append(extracted)

    if not new_posts:

        print("No new posts.")

        return

    print(
        f"NEW POSTS FOUND: {len(new_posts)}"
    )

    # Oldest first so multiple posts are reposted
    # in chronological order.

    new_posts.reverse()

    for post in new_posts:

        print()
        print("-" * 60)

        print(
            "Post ID:",
            post["id"]
        )

        print(
            "Content:",
            post["content"][:500]
        )

        repost_text = build_repost_text(post)

        if not repost_text:

            print(
                "Skipping because post has no text."
            )

            processed_ids.add(post["id"])

            continue

        success = publish_to_square(
            repost_text
        )

        if success:

            print(
                "SUCCESS:",
                post["id"]
            )

            processed_ids.add(
                post["id"]
            )

            state["processed_ids"] = list(
                processed_ids
            )

            save_state(state)

        else:

            print(
                "FAILED:",
                post["id"]
            )

            # IMPORTANT:
            # Don't mark failed posts as processed.
            # The next GitHub Action run will retry them.

            break

    state["processed_ids"] = list(
        processed_ids
    )

    save_state(state)

    print()
    print(
        "Finished:",
        datetime.now(
            timezone.utc
        ).isoformat()
    )


if __name__ == "__main__":

    try:
        main()

    except Exception as e:

        print(
            "FATAL ERROR:",
            repr(e)
        )

        sys.exit(1)
