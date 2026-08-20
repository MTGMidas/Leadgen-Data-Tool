"""
Exportiert die priorisierte Lead-Liste (vw_lead_scoring) als CSV.

Aufruf:
    python -m leadgen.export_csv --limit 200 --out leads_export.csv
"""
import argparse
import csv
import logging
from datetime import date

from . import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIELDNAMES = [
    "company_name", "niche", "location", "phone", "website_url", "address",
    "rating", "review_count", "organic_rank", "runs_ads", "has_tracking",
    "has_gtm", "has_gtag", "has_fbq", "has_google_ads_tag",
    "b_index", "n_index", "p_index", "final_score", "pitch_hint",
]


def export(limit: int, out_path: str) -> None:
    leads = db.fetch_top_leads(limit=limit)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead)

    logger.info("%d Leads nach '%s' exportiert.", len(leads), out_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exportiert priorisierte Leads als CSV.")
    parser.add_argument("--limit", type=int, default=200, help="Max. Anzahl Leads")
    parser.add_argument(
        "--out",
        type=str,
        default=f"leads_export_{date.today().isoformat()}.csv",
        help="Ausgabedatei",
    )
    args = parser.parse_args()
    export(args.limit, args.out)
