"""
Robuster kostenloser SERP-Checker via Playwright.
"""

import logging
import re
import urllib.parse
from typing import Dict, List

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# --------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------

def _normalize(text: str) -> str:
    if not text:
        return ""

    text = text.lower()

    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss"
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _company_tokens(company_name: str) -> List[str]:

    stopwords = {
        "gmbh",
        "ug",
        "mbh",
        "ag",
        "kg",
        "co",
        "und",
        "&",
        "ohg",
        "e.k.",
        "ek",
        "gbr",
        "holding",
        "deutschland"
    }

    tokens = []

    for token in _normalize(company_name).split():

        if len(token) < 3:
            continue

        if token in stopwords:
            continue

        tokens.append(token)

    return tokens


def _match_company(company_name: str, result_text: str) -> bool:

    company_norm = _normalize(company_name)
    result_norm = _normalize(result_text)

    if company_norm in result_norm:
        return True

    tokens = _company_tokens(company_name)

    if not tokens:
        return False

    matches = sum(token in result_norm for token in tokens)

    return matches >= max(1, len(tokens) // 2)


# --------------------------------------------------------
# SERP
# --------------------------------------------------------

def _check_via_playwright(company_name: str, keyword: str) -> Dict:

    encoded = urllib.parse.quote(keyword)

    url = f"https://www.google.de/search?q={encoded}&hl=de"

    organic_rank = None
    runs_ads = False

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            locale="de-DE",
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 2000}
        )

        page = context.new_page()

        try:

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Cookie Banner
            cookie_buttons = [
                "button:has-text('Alle akzeptieren')",
                "button:has-text('Ich stimme zu')",
                "button:has-text('Accept all')",
                "#L2AGLb"
            ]

            for selector in cookie_buttons:
                try:
                    page.locator(selector).click(timeout=1500)
                    break
                except Exception:
                    pass

            page.wait_for_timeout(2000)

            # Ergebnisse laden lassen
            page.wait_for_selector("body", timeout=10000)

            # --------------------------------------------------
            # Ads erkennen
            # --------------------------------------------------

            page_text = page.locator("body").inner_text().lower()

            if _normalize(company_name) in _normalize(page_text):

                ad_indicators = [
                    "gesponsert",
                    "sponsored",
                    "anzeige"
                ]

                if any(ind in page_text for ind in ad_indicators):
                    runs_ads = True

            # --------------------------------------------------
            # Organische Treffer
            # --------------------------------------------------

            selectors = [
                "div.g",
                "div.tF2Cxc",
                "div.MjjYud"
            ]

            seen = set()
            results = []

            for selector in selectors:
                try:
                    for item in page.locator(selector).all():

                        handle = item.element_handle()

                        if handle is None:
                            continue

                        if id(handle) in seen:
                            continue

                        seen.add(id(handle))

                        results.append(item)

                except Exception:
                    pass

            rank = 0

            for result in results:

                try:

                    text = result.inner_text(timeout=1000)

                    if len(text.strip()) < 20:
                        continue

                    rank += 1

                    if _match_company(company_name, text):
                        organic_rank = rank
                        break

                except Exception:
                    continue

            browser.close()

            return {
                "organic_rank": organic_rank,
                "runs_ads": runs_ads,
                "serp_source": "playwright_free"
            }

        except Exception as exc:

            browser.close()

            logger.exception("SERP Fehler: %s", exc)

            return {
                "organic_rank": None,
                "runs_ads": None,
                "serp_source": "error"
            }


def check_serp(company_name: str, keyword: str, location: str = "") -> Dict:
    """
    Öffentliche API.
    """

    return _check_via_playwright(company_name, keyword)