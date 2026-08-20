"""
Kostenloser Google Maps Scraper via Playwright inkl. URL-Bereinigung.
"""
import logging
import re
import urllib.parse
from typing import List, Dict
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def _clean_url(url: str) -> str:
    """Filtert Google-Ad-Redirects und unvollständige URLs heraus."""
    if not url:
        return None
    
    # Google-Interne & Ad-Redirect-Links verwerfen
    if "aclk?" in url or "google.com/aclk" in url or "googleadservices" in url:
        return None
        
    if url.startswith("https:///") or url.startswith("http:///"):
        return None
        
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
        
    return url

def fetch_places(niche: str, location: str, max_results: int = 20) -> List[Dict]:
    query = f"{niche} {location}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/maps/search/{encoded_query}"
    
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        page = context.new_page()
        
        try:
            page.goto(url, timeout=15000)
            
            # Cookie-Banner
            try:
                page.click("button[aria-label*='Alle akzeptieren'], button:has-text('Alle akzeptieren')", timeout=3000)
            except Exception:
                pass

            page.wait_for_selector("div[role='feed'], div[role='main']", timeout=10000)
            
            # Leichtes Scrollen für mehr Ergebnisse
            for _ in range(2):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(800)

            cards = page.query_selector_all("div[role='article']")
            
            for card in cards[:max_results]:
                try:
                    title_el = card.query_selector("div.fontHeadlineSmall")
                    company_name = title_el.inner_text().strip() if title_el else None
                    
                    if not company_name:
                        continue
                        
                    link_el = card.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""
                    place_id = href.split("?")[0].split("/")[-1] if href else company_name
                    
                    # Vollständigen Text der Karte für zuverlässiges RegEx-Matching holen
                    card_text = card.inner_text()
                    card_html = card.inner_html()

                    # 1. Website-URL suchen & säubern
                    raw_website = None
                    web_el = card.query_selector("a[data-value='Website'], a[aria-label*='Website'], a[aria-label*='website']")
                    if web_el:
                        raw_website = web_el.get_attribute("href")
                    
                    if not raw_website:
                        all_links = card.query_selector_all("a")
                        for l in all_links:
                            h = l.get_attribute("href") or ""
                            if h.startswith("http") and "google." not in h and "ggpht." not in h:
                                raw_website = h
                                break

                    website_url = _clean_url(raw_website)

                    # 2. RATING robust via RegEx im Kartentext suchen (sucht z.B. "4,8" oder "5,0")
                    rating = None
                    rating_match = re.search(r'(\d+[\.,]\d+)\s*(?:Sterne|stars)?', card_text, re.IGNORECASE)
                    if rating_match:
                        try:
                            r_val = rating_match.group(1).replace(',', '.')
                            rating = float(r_val)
                        except ValueError:
                            pass

                    # 3. REVIEW-COUNT robust über Klammern (z.B. "(14)" oder "(1.234)") suchen
                    review_count = 0
                    review_match = re.search(r'\((\d{1,3}(?:\.\d{3})*|\d+)\)', card_text)
                    if review_match:
                        clean_rev = review_match.group(1).replace('.', '')
                        if clean_rev.isdigit():
                            review_count = int(clean_rev)

                    # 4. TELEFONNUMMER im Kartentext oder über data-item-id finden
                    phone = None
                    phone_el = card.query_selector('button[data-item-id^="phone:tel:"]')
                    if phone_el:
                        pid = phone_el.get_attribute("data-item-id") or ""
                        if "phone:tel:" in pid:
                            phone = pid.split("phone:tel:")[-1]
                    
                    if not phone:
                        phone_match = re.search(r'(?:[\+\(]?\d{2,4}\)?[\s\-\/]?)?\d{3,5}[\s\-\/]?\d{3,8}', card_text)
                        if phone_match:
                            phone = phone_match.group(0).strip()

                    results.append({
                        "place_id": place_id,
                        "company_name": company_name,
                        "niche": niche,
                        "location": location,
                        "address": f"{location}, Deutschland",
                        "website_url": website_url,
                        "phone": phone,
                        "rating": rating,
                        "review_count": review_count,
                    })
                except Exception as e:
                    logger.warning(f"Fehler beim Parsen einer Maps-Karte: {e}")

        except Exception as exc:
            logger.error(f"Fehler beim Abrufen von Google Maps für '{query}': {exc}")
        finally:
            browser.close()
        
    logger.info("Google Maps Scraper '%s': %d Treffer gefunden", query, len(results))
    return results