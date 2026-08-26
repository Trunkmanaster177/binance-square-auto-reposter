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

    # Remove duplicate IDs
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
# FETCH BINANCE SQUARE
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

    print(
        "Final URL:",
        response.url
    )

    response.raise_for_status()

    try:

        data = response.json()

    except Exception as e:

        print(
            "JSON parsing failed:",
            e
        )

        print(
            response.text[:5000]
        )

        return []

    if data.get("code") != "000000":

        print(
            "Binance API error:",
            data.get("message")
        )

        return []

    data_section = data.get(
        "data",
        {}
    )

    vos = data_section.get(
        "vos",
        []
    )

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

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_posts = {}

    for post in posts:

        post_id = str(
            post.get(
                "id",
                ""
            )
        ).strip()

        if post_id:

            unique_posts[post_id] = post

    posts = list(
        unique_posts.values()
    )

    print(
        "Actual post objects found:",
        len(posts)
    )

    # --------------------------------------------------------
    # DEBUG AUTHOR INFORMATION
    # --------------------------------------------------------

    print()
    print(
        "========== AUTHOR DEBUG =========="
    )

    for post in posts:

        print()
        print(
            "POST ID:",
            repr(post.get("id"))
        )

        print(
            "authorName:",
            repr(post.get("authorName"))
        )

        print(
            "authorId:",
            repr(post.get("authorId"))
        )

        print(
            "userId:",
            repr(post.get("userId"))
        )

        print(
            "username:",
            repr(post.get("username"))
        )

        print(
            "handle:",
            repr(post.get("handle"))
        )

        print(
            "nickname:",
            repr(post.get("nickname"))
        )

        print(
            "creatorName:",
            repr(post.get("creatorName"))
        )

        print(
            "creatorId:",
            repr(post.get("creatorId"))
        )

        print(
            "webLink:",
            repr(post.get("webLink"))
        )

    print()
    print(
        "========== END AUTHOR DEBUG =========="
    )
    print()

    return posts


# ============================================================
# FIND REAL POST OBJECTS
# ============================================================

def find_post_objects(
    obj,
    path="root"
):

    results = []

    if isinstance(
        obj,
        dict
    ):

        keys = set(
            obj.keys()
        )

        post_markers = {
            "id",
            "authorName",
            "content",
            "webLink",
            "cardType"
        }

        matches = len(
            keys.intersection(
                post_markers
            )
        )

        # Require ID + another post field
        if (
            "id" in keys
            and matches >= 2
        ):

            results.append(
                obj
            )

            print(
                "Post object found at:",
                path
            )

            return results

        # Continue searching nested data

        for key, value in obj.items():

            results.extend(
                find_post_objects(
                    value,
                    f"{path}.{key}"
                )
            )

    elif isinstance(
        obj,
        list
    ):

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

    target = (
        SOURCE_AUTHOR
        .lower()
        .strip()
        .lstrip("@")
    )

    possible_names = [

        post.get(
            "authorName"
        ),

        post.get(
            "authorHandle"
        ),

        post.get(
            "username"
        ),

        post.get(
            "handle"
        ),

        post.get(
            "nickname"
        ),

        post.get(
            "creatorName"
        )

    ]

    for value in possible_names:

        if not value:
            continue

        value = (
            str(value)
            .strip()
            .lower()
            .lstrip("@")
        )

        if value == target:

            return True

    return False


# ============================================================
# EXTRACT POST
# ============================================================

def extract_post(post):

    return {

        "id": str(
            post.get(
                "id",
                ""
            )
        ).strip(),

        "authorName": str(
            post.get(
                "authorName",
                ""
            )
        ).strip(),

        "title": str(
            post.get(
                "title"
            ) or ""
        ).strip(),

        "content": str(
            post.get(
                "content"
            ) or ""
        ).strip(),

        "webLink": str(
            post.get(
                "webLink"
            ) or ""
        ).strip(),

        "images": (
            post.get(
                "images"
            )
            or []
        ),

        "hashtags": (
            post.get(
                "hashtagList"
            )
            or []
        )

    }


# ============================================================
# BUILD REPOST TEXT
# ============================================================

def build_repost_text(post):

    content = post.get(
        "content",
        ""
    )

    if not content:

        return None

    text = content

    text += (
        f"\n\nSource: @{SOURCE_AUTHOR}"
    )

    if post.get("webLink"):

        text += (
            "\nOriginal: "
            + post["webLink"]
        )

    # Safety limit

    if len(text) > 8000:

        text = text[:7950]

        text += (
            f"\n\nSource: @{SOURCE_AUTHOR}"
        )

    return text


# ============================================================
# PUBLISH TO BINANCE SQUARE
# ============================================================

def publish_to_square(text):

    api_key = os.getenv(
        "BINANCE_SQUARE_OPENAPI_KEY"
    )

    if not api_key:

        print(
            "ERROR: "
            "BINANCE_SQUARE_OPENAPI_KEY "
            "secret is missing."
        )

        return False

    headers = {

        "X-Square-OpenAPI-Key":
            api_key,

        "Content-Type":
            "application/json",

        "User-Agent":
            HEADERS["User-Agent"]

    }

    payload = {

        "bodyTextOnly":
            text

    }

    print()
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
            "Non-JSON response:"
        )

        print(
            response.text[:5000]
        )

        return False

    print(
        "Publish response:"
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    if not response.ok:

        return False

    code = result.get(
        "code"
    )

    if code in (
        None,
        "000000",
        200,
        "200"
    ):

        return True

    return False


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 60
    )

    print(
        "Binance Square Auto Reposter"
    )

    print(
        "=" * 60
    )

    print(
        "Source creator:",
        SOURCE_AUTHOR
    )

    print()

    state = load_state()

    posts = get_latest_posts()

    if not posts:

        print(
            "No posts found."
        )

        return

    # --------------------------------------------------------
    # FILTER SOURCE
    # --------------------------------------------------------

    source_posts = []

    for post in posts:

        if is_source_post(
            post
        ):

            source_posts.append(
                extract_post(post)
            )

    print()
    print(
        f"Found {len(source_posts)} "
        f"post(s) from {SOURCE_AUTHOR}"
    )

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not state.get(
        "initialized"
    ):

        print()
        print(
            "FIRST RUN: initializing state."
        )

        for post in source_posts:

            if post["id"]:

                state[
                    "processed_ids"
                ].append(
                    post["id"]
                )

        state[
            "initialized"
        ] = True

        save_state(
            state
        )

        print(
            "Existing posts marked "
            "as processed."
        )

        print(
            "New posts will be reposted "
            "from the next run."
        )

        return

    # --------------------------------------------------------
    # FIND NEW POSTS
    # --------------------------------------------------------

    processed = set(
        state.get(
            "processed_ids",
            []
        )
    )

    new_posts = []

    for post in source_posts:

        if (
            post["id"]
            and post["id"]
            not in processed
        ):

            new_posts.append(
                post
            )

    if not new_posts:

        print()
        print(
            "No new posts."
        )

        return

    print()
    print(
        f"NEW POSTS FOUND: "
        f"{len(new_posts)}"
    )

    # Oldest first

    new_posts.reverse()

    for post in new_posts:

        print()
        print(
            "-" * 60
        )

        print(
            "Post ID:",
            post["id"]
        )

        print(
            "Author:",
            post["authorName"]
        )

        print(
            "Content:"
        )

        print(
            post["content"][:500]
        )

        repost_text = (
            build_repost_text(
                post
            )
        )

        if not repost_text:

            print(
                "Skipping empty post."
            )

            processed.add(
                post["id"]
            )

            continue

        success = (
            publish_to_square(
                repost_text
            )
        )

        if success:

            print()
            print(
                "POSTED SUCCESSFULLY"
            )

            processed.add(
                post["id"]
            )

            state[
                "processed_ids"
            ] = list(
                processed
            )

            save_state(
                state
            )

        else:

            print()
            print(
                "POST FAILED"
            )

            # Don't mark as processed.
            # It will retry next run.

            break

    state[
        "processed_ids"
    ] = list(
        processed
    )

    save_state(
        state
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
