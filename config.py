"""
Zentrale Konfiguration der Lead-Gen-Pipeline.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys (Nicht mehr benötigt) -------------------------------------
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "")

# --- SERP Backend Wahl ----------------------------------------------------
SERP_BACKEND = os.getenv("SERP_BACKEND", "playwright_free")

# --- Datenbank (Neon.tech Cloud DB als direkter Standard, hier von uns entfernt aus Datenschutzgründen) ----------------
   DATABASE_URL = os.getenv("DATABASE_URL")
   if not DATABASE_URL:
       raise RuntimeError("DATABASE_URL fehlt – .env.example nach .env kopieren und ausfüllen.")
)

# --- Scraping-Verhalten ------------------------------------------------------
REQUEST_TIMEOUT_SECONDS = 15
MAX_WORKERS = 3                 # Konservativ für sanftes Scraping
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SCRAPE_DELAY_SECONDS = 2.0       

# --- Nischen × Standorte: Hier definierst du deine Suchmatrix --------------
SEARCH_MATRIX = [
    {"niche": "Dachdecker", "location": "Flensburg"},
    {"niche": "Zimmermann", "location": "Hamburg"},
    {"niche": "Zahnarzt", "location": "Flensburg"},
    {"niche": "Elektriker", "location": "Kiel"},
    {"niche": "Physiotherapie", "location": "Schleswig"},
]

SERP_TOP_N = 30