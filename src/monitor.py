import requests
import re

URL = "https://www.binance.com/en/square/profile/TF_bnb"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

print("=" * 60)
print("BINANCE TF_BNB PROFILE TEST")
print("=" * 60)

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

print("HTTP STATUS:", response.status_code)
print("FINAL URL:", response.url)
print("CONTENT TYPE:", response.headers.get("content-type"))
print("HTML LENGTH:", len(response.text))

print()
print("========== SEARCHING HTML ==========")

terms = [
    "TF_bnb",
    "359",
    "square",
    "post",
    "__NEXT_DATA__",
    "__INITIAL_STATE__",
    "14.4K",
]

for term in terms:

    count = response.text.lower().count(
        term.lower()
    )

    print(
        f"{term}: {count} occurrence(s)"
    )

print()
print("========== HTML SAMPLE ==========")

print(
    response.text[:15000]
)

print()
print("========== END ==========")
