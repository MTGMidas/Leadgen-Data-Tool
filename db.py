"""
Datenbank-Layer. Nutzt psycopg2 direkt (bewusst kein ORM), da die
eigentliche Business-Logik in der SQL-View liegt und wir hier nur
sauberes Upserting brauchen.
"""
import logging
from contextlib import contextmanager
from typing import Dict, Iterable, List

import psycopg2
import psycopg2.extras

from . import config

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO raw_leads (
    place_id, company_name, niche, location, address, website_url, phone,
    rating, review_count, target_keyword, organic_rank, runs_ads, serp_source,
    has_gtm, has_gtag, has_fbq, has_google_ads_tag, website_reachable, scraped_at
) VALUES (
    %(place_id)s, %(company_name)s, %(niche)s, %(location)s, %(address)s,
    %(website_url)s, %(phone)s, %(rating)s, %(review_count)s,
    %(target_keyword)s, %(organic_rank)s, %(runs_ads)s, %(serp_source)s,
    %(has_gtm)s, %(has_gtag)s, %(has_fbq)s, %(has_google_ads_tag)s,
    %(website_reachable)s, now()
)
ON CONFLICT (place_id) DO UPDATE SET
    company_name        = EXCLUDED.company_name,
    address              = EXCLUDED.address,
    website_url          = EXCLUDED.website_url,
    phone                = EXCLUDED.phone,
    rating               = EXCLUDED.rating,
    review_count         = EXCLUDED.review_count,
    target_keyword       = EXCLUDED.target_keyword,
    organic_rank         = EXCLUDED.organic_rank,
    runs_ads             = EXCLUDED.runs_ads,
    serp_source          = EXCLUDED.serp_source,
    has_gtm              = EXCLUDED.has_gtm,
    has_gtag             = EXCLUDED.has_gtag,
    has_fbq              = EXCLUDED.has_fbq,
    has_google_ads_tag   = EXCLUDED.has_google_ads_tag,
    website_reachable    = EXCLUDED.website_reachable,
    scraped_at           = now(),
    updated_at           = now();
"""


@contextmanager
def get_connection():
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_leads(leads: Iterable[Dict]) -> int:
    """Schreibt/aktualisiert eine Liste angereicherter Leads. Gibt Anzahl zurück."""
    leads = list(leads)
    if not leads:
        return 0

    # Fehlende Keys defensiv mit None auffüllen (falls Scraping/SERP fehlschlug)
    required_keys = [
        "place_id", "company_name", "niche", "location", "address",
        "website_url", "phone", "rating", "review_count", "target_keyword",
        "organic_rank", "runs_ads", "serp_source", "has_gtm", "has_gtag",
        "has_fbq", "has_google_ads_tag", "website_reachable",
    ]
    for lead in leads:
        for key in required_keys:
            lead.setdefault(key, None)

    with get_connection() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, UPSERT_SQL, leads)

    logger.info("%d Leads in raw_leads upserted.", len(leads))
    return len(leads)


def fetch_top_leads(limit: int = 100) -> List[Dict]:
    """Liest die priorisierte Lead-Liste aus der Scoring-View."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM vw_lead_scoring ORDER BY final_score DESC NULLS LAST LIMIT %s;",
                (limit,),
            )
            return cur.fetchall()
