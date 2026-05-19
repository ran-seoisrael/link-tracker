import re
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Googlebot/2.1; "
        "+http://www.google.com/bot.html)"
    )
}
TIMEOUT = 15


def _normalize(url: str) -> str:
    """Decode percent-encoding and strip trailing slash for comparison.
    Handles Hebrew URLs where %D7%94 and %d7%94 represent the same character."""
    return unquote(url.strip().rstrip("/"))


def check_link(page_url: str, expected_link_url: str, expected_anchor: str) -> dict:
    result = {
        "status_200": None,
        "crawlable": None,
        "indexable": None,
        "canonical_self": None,
        "anchor_found": None,
        "url_match": None,
        "errors": [],
    }

    # ── 1. Fetch page ────────────────────────────────────────────────────
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except requests.exceptions.RequestException as exc:
        result["errors"].append(f"שגיאת חיבור לעמוד: {exc}")
        return result

    result["status_200"] = resp.status_code == 200
    if not result["status_200"]:
        result["errors"].append(f"קוד HTTP: {resp.status_code} (צפוי 200)")
        return result

    # ── 2. Parse HTML ────────────────────────────────────────────────────
    soup = BeautifulSoup(resp.text, "lxml")

    # ── 3. meta robots — follow (סריקה) ──────────────────────────────────
    meta_robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if meta_robots:
        content = meta_robots.get("content", "").lower()
        result["crawlable"] = "nofollow" not in content
        if not result["crawlable"]:
            result["errors"].append("העמוד מסומן nofollow (meta robots)")
    else:
        result["crawlable"] = True  # no tag = default index,follow

    # ── 4. meta robots — index (אינדוקס) ─────────────────────────────────
    if meta_robots:
        content = meta_robots.get("content", "").lower()
        result["indexable"] = "noindex" not in content
        if not result["indexable"]:
            result["errors"].append("העמוד מסומן noindex (meta robots)")
    else:
        result["indexable"] = True

    # ── 5. Canonical ─────────────────────────────────────────────────────
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag:
        canonical_href = canonical_tag.get("href", "").strip()
        # Decode percent-encoding on both sides so %D7%94 == %d7%94
        result["canonical_self"] = _normalize(canonical_href) == _normalize(page_url)
        if not result["canonical_self"]:
            result["errors"].append(f"קנוניקל מצביע על: {canonical_href}")
    else:
        result["canonical_self"] = False
        result["errors"].append("אין תגית canonical בעמוד")

    # ── 6. Find link by anchor text inside <body> ─────────────────────────
    body = soup.find("body")
    if not body:
        result["anchor_found"] = False
        result["url_match"] = False
        result["errors"].append("לא נמצא <body> בעמוד")
        return result

    found_link = None
    for a in body.find_all("a", href=True):
        if a.get_text(strip=True) == expected_anchor:
            found_link = a
            break

    if found_link is None:
        result["anchor_found"] = False
        result["url_match"] = False
        result["errors"].append(f'אנקור טקסט "{expected_anchor}" לא נמצא ב-body')
        return result

    result["anchor_found"] = True

    href_abs = urljoin(page_url, found_link["href"])
    result["url_match"] = _normalize(href_abs) == _normalize(expected_link_url)
    if not result["url_match"]:
        result["errors"].append(
            f"כתובת הקישור בעמוד: {href_abs} (צפוי: {expected_link_url})"
        )

    return result
