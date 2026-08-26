import os
import json
import sys
import requests
from pathlib import Path
from datetime import datetime, timezone


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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
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

    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    state["processed_ids"] = list(
        dict.fromkeys(
            state.get("processed_ids", [])
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
# FETCH FEED
# ============================================================

def get_latest_posts():

    params = {
        "pageIndex": 1,
        "pageSize": 20,
        "type": 2
    }

    print("Fetching Binance Square...")

    response = requests.get(
        FEED_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )

    print(
        "HTTP status:",
        response.status_code
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != "000000":

        print(
            "Binance API error:",
            data.get("message")
        )

        return []

    data_section = data.get("data", {})

    vos = data_section.get("vos", [])

    print(
        "Objects returned in data.vos:",
        len(vos)
    )

    posts = []

    for index, item in enumerate(vos):

        found = find_post_objects(
            item,
            f"data.vos[{index}]"
        )

        posts.extend(found)

    # Remove duplicate post IDs

    unique = {}

    for post in posts:

        post_id = str(
            post.get("id", "")
        ).strip()

        if post_id:
            unique[post_id] = post

    posts = list(unique.values())

    print(
        "Actual post objects found:",
        len(posts)
    )

    # Debug output

    for post in posts[:5]:

        print(
            "POST:",
            post.get("id"),
            "| AUTHOR:",
            post.get("authorName")
        )

    return posts


# ============================================================
# FIND REAL POST OBJECTS
# ============================================================

def find_post_objects(obj, path="root"):

    results = []

    if isinstance(obj, dict):

        keys = set(obj.keys())

        # A real Square post normally contains several
        # of these fields.

        post_markers = {
            "id",
            "authorName",
            "content",
            "webLink",
            "cardType"
        }

        matches = len(
            keys.intersection(post_markers)
        )

        # Require ID + at least one other post field.
        if (
            "id" in keys
            and matches >= 2
        ):

            results.append(obj)

            print(
                "Post object found at:",
                path
            )

            return results

        # Otherwise continue searching nested objects.

        for key, value in obj.items():

            results.extend(
                find_post_objects(
                    value,
                    f"{path}.{key}"
                )
            )

    elif isinstance(obj, list):

        for index, value in enumerate(obj):

            results.extend(
                find_post_objects(
                    value,
                    f"{path}[{index}]"
                )
            )

    return results


# ============================================================
# SOURCE FILTER
# ============================================================

def is_source_post(post):

    target = SOURCE_AUTHOR.lower().lstrip("@")

    possible_names = [
        post.get("authorName"),
        post.get("authorHandle"),
        post.get("username"),
        post.get("handle"),
        post.get("nickname")
    ]

    for value in possible_names:

        if value:

            value = str(
                value
            ).strip().lower().lstrip("@")

            if value == target:
                return True

    return False


# ============================================================
# EXTRACT POST
# ============================================================

def extract_post(post):

    return {
        "id": str(
            post.get("id", "")
        ).strip(),

        "authorName": str(
            post.get("authorName", "")
        ).strip(),

        "title": str(
            post.get("title") or ""
        ).strip(),

        "content": str(
            post.get("content") or ""
        ).strip(),

        "webLink": str(
            post.get("webLink") or ""
        ).strip(),

        "images": post.get(
            "images"
        ) or [],

        "hashtags": post.get(
            "hashtagList"
        ) or []
    }


# ============================================================
# BUILD REPOST
# ============================================================

def build_repost_text(post):

    content = post["content"]

    if not content:

        return None

    text = content

    text += (
        f"\n\nSource: @{SOURCE_AUTHOR}"
    )

    if post["webLink"]:

        text += (
            f"\nOriginal: {post['webLink']}"
        )

    # Safe maximum

    if len(text) > 8000:

        text = text[:7950]

        text += (
            f"\n\nSource: @{SOURCE_AUTHOR}"
        )

    return text


# ============================================================
# PUBLISH
# ============================================================

def publish_to_square(text):

    api_key = os.getenv(
        "BINANCE_SQUARE_OPENAPI_KEY"
    )

    if not api_key:

        print(
            "ERROR: BINANCE_SQUARE_OPENAPI_KEY "
            "secret is missing."
        )

        return False

    headers = {
        "X-Square-OpenAPI-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": HEADERS["User-Agent"]
    }

    payload = {
        "bodyTextOnly": text
    }

    print(
        "Publishing to Binance Square..."
    )

    response = requests.post(
        POST_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    print(
        "Publish HTTP status:",
        response.status_code
    )

    try:

        result = response.json()

    except Exception:

        print(
            response.text
        )

        return False

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    if not response.ok:
        return False

    code = result.get("code")

    return code in (
        None,
        "000000",
        200,
        "200"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)

    print(
        "Binance Square Auto Reposter"
    )

    print("=" * 60)

    print(
        "Source creator:",
        SOURCE_AUTHOR
    )

    state = load_state()

    posts = get_latest_posts()

    if not posts:

        print(
            "No posts found."
        )

        return

    source_posts = []

    for post in posts:

        if is_source_post(post):

            source_posts.append(
                extract_post(post)
            )

    print(
        f"Found {len(source_posts)} "
        f"post(s) from {SOURCE_AUTHOR}"
    )

    # ========================================================
    # FIRST RUN
    # ========================================================

    if not state.get("initialized"):

        print(
            "FIRST RUN: initializing state."
        )

        for post in source_posts:

            if post["id"]:

                state["processed_ids"].append(
                    post["id"]
                )

        state["initialized"] = True

        save_state(state)

        print(
            "Existing posts marked as processed."
        )

        print(
            "New posts will be reposted "
            "from the next run."
        )

        return

    # ========================================================
    # NEW POSTS
    # ========================================================

    processed = set(
        state.get(
            "processed_ids",
            []
        )
    )

    new_posts = [
        post
        for post in source_posts
        if post["id"]
        and post["id"] not in processed
    ]

    if not new_posts:

        print(
            "No new posts."
        )

        return

    print(
        f"NEW POSTS: {len(new_posts)}"
    )

    # Oldest first

    new_posts.reverse()

    for post in new_posts:

        print(
            "-" * 60
        )

        print(
            "Post:",
            post["id"]
        )

        print(
            "Author:",
            post["authorName"]
        )

        print(
            "Text:",
            post["content"][:300]
        )

        repost_text = build_repost_text(
            post
        )

        if not repost_text:

            print(
                "Skipping empty post."
            )

            processed.add(
                post["id"]
            )

            continue

        success = publish_to_square(
            repost_text
        )

        if success:

            print(
                "POSTED SUCCESSFULLY"
            )

            processed.add(
                post["id"]
            )

            state["processed_ids"] = list(
                processed
            )

            save_state(state)

        else:

            print(
                "POST FAILED"
            )

            # Don't mark it as processed.
            # It will retry next run.

            break

    state["processed_ids"] = list(
        processed
    )

    save_state(state)

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
