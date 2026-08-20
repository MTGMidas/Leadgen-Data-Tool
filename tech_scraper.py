"""
Scraped die öffentlich sichtbare Startseite eines Unternehmens via Playwright
auf Marketing-/Tracking-Skripte (GTM, gtag, FB Pixel, Google Ads).
Umgeht JavaScript-Ladezeiten, Cookie-Banner und SSL-Zertifikatsfehler.
"""
import logging
import re
from typing import Dict, Optional
from playwright.sync_api import sync_playwright

from . import config

logger = logging.getLogger(__name__)

# Signatur-Patterns je Tracking-Technologie
PATTERNS = {
    "has_gtm": re.compile(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]+"),
    "has_gtag": re.compile(r"googletagmanager\.com/gtag/js|gtag\("),
    "has_fbq": re.compile(r"connect\.facebook\.net/.+/fbevents\.js|fbq\("),
    "has_google_ads_tag": re.compile(r"AW-\d{9,}"),
}

_EMPTY_RESULT = {
    "has_gtm": False,
    "has_gtag": False,
    "has_fbq": False,
    "has_google_ads_tag": False,
    "website_reachable": False,
}


def scrape_for_tracking_tags(website_url: Optional[str]) -> Dict:
    """
    Öffnet die Website mit Playwright (Headless Chrome), wartet kurz auf das Rendering,
    liest das vollständige HTML sowie alle eingebundenen Skripte aus und matcht die Patterns.
    """
    if not website_url:
        return dict(_EMPTY_RESULT)

    if not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url

    try:
        with sync_playwright() as p:
            # Starte Headless Browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=getattr(config, "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                ignore_https_errors=True  # Verhindert Abbrüche bei ungültigen/abgelaufenen SSL-Zertifikaten lokaler Firmen
            )
            page = context.new_page()
            
            # Timeout aus Config übernehmen (Standard: z.B. 10 Sekunden)
            timeout_ms = getattr(config, "REQUEST_TIMEOUT_SECONDS", 10) * 1000
            page.set_default_timeout(timeout_ms)

            try:
                # Website aufrufen und warten, bis das DOM bereit ist
                response = page.goto(website_url, wait_until="domcontentloaded", timeout=timeout_ms)
                
                if not response or response.status >= 400:
                    browser.close()
                    return dict(_EMPTY_RESULT)
                
                # Kurze Wartezeit (2 Sek.), damit dynamische Skripte/Consent-Manager nachladen können
                page.wait_for_timeout(2000)
                
                # Gesamtes gerendertes HTML abgreifen
                html = page.content()
                
                # Alle Skript-Quellen und Skript-Inhalte direkt via JS aus dem DOM extrahieren
                script_blobs = page.evaluate("""
                    () => Array.from(document.querySelectorAll('script'))
                              .map(s => (s.src || '') + ' ' + (s.innerText || ''))
                              .join('\\n')
                """)
                
                # Such-Heuhaufen zusammenbauen
                haystack = script_blobs + "\n" + html
                
                # Muster abgleichen
                result = {key: bool(pattern.search(haystack)) for key, pattern in PATTERNS.items()}
                result["website_reachable"] = True
                
                browser.close()
                return result

            except Exception as exc:
                logger.warning("Playwright-Fehler beim Laden von %s: %s", website_url, exc)
                browser.close()
                return dict(_EMPTY_RESULT)

    except Exception as exc:
        logger.warning("Konnte Playwright-Instanz nicht starten: %s", exc)
        return dict(_EMPTY_RESULT)