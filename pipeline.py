"""
Hauptskript der Lead-Gen-Pipeline.

Ablauf je Nische/Standort aus config.SEARCH_MATRIX:
  1. fetch_places()            -> Basisdaten (Google Places)
  2. enrich_lead_data()        -> parallelisiert: Tech-Scraping + SERP-Check
  3. db.upsert_leads()         -> Persistierung in PostgreSQL
Das eigentliche Scoring passiert NICHT hier, sondern in vw_lead_scoring (SQL).

Aufruf (z.B. als wöchentlicher Cronjob):
    python -m leadgen.pipeline
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from tqdm import tqdm

from . import config, db
from .google_places import fetch_places
from .serp_checker import check_serp
from .tech_scraper import scrape_for_tracking_tags

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def enrich_lead_data(lead: Dict, target_keyword: str) -> Dict:
    """Reichert einen einzelnen Lead um Tech-Stack- und SERP-Daten an."""
    tech_info = scrape_for_tracking_tags(lead.get("website_url"))
    lead.update(tech_info)

    serp_info = check_serp(
        company_name=lead["company_name"],
        keyword=target_keyword,
        location=lead["location"],
    )
    lead["target_keyword"] = target_keyword
    lead.update(serp_info)
    return lead


def run_pipeline_for_segment(niche: str, location: str) -> List[Dict]:
    """Führt die volle Pipeline für eine Nische/Standort-Kombination aus."""
    logger.info("Starte Segment: %s / %s", niche, location)
    raw_leads = fetch_places(niche, location)

    if not raw_leads:
        logger.warning("Keine Places-Treffer für %s / %s", niche, location)
        return []

    target_keyword = f"{niche} {location}"
    enriched: List[Dict] = []

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {
            executor.submit(enrich_lead_data, lead, target_keyword): lead
            for lead in raw_leads
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"{niche}/{location}"):
            try:
                enriched.append(future.result())
            except Exception as exc:
                lead = futures[future]
                logger.error("Enrichment fehlgeschlagen für %s: %s", lead.get("company_name"), exc)

    return enriched


def run_pipeline() -> int:
    """Läuft die komplette Suchmatrix durch und persistiert alle Leads."""
    total_upserted = 0
    for segment in config.SEARCH_MATRIX:
        enriched_leads = run_pipeline_for_segment(segment["niche"], segment["location"])
        total_upserted += db.upsert_leads(enriched_leads)

    logger.info("Pipeline abgeschlossen. %d Leads insgesamt upserted.", total_upserted)
    return total_upserted


if __name__ == "__main__":
    run_pipeline()
