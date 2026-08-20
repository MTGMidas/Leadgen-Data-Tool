-- ============================================================================
-- Lead-Gen Scoring Pipeline · PostgreSQL Schema
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw_leads (
    id                  SERIAL PRIMARY KEY,
    place_id            TEXT UNIQUE NOT NULL,
    company_name        TEXT NOT NULL,
    niche               TEXT NOT NULL,
    location            TEXT NOT NULL,
    address             TEXT,
    website_url         TEXT,
    phone               TEXT,
    rating              NUMERIC(3,2),
    review_count        INTEGER DEFAULT 0,

    -- SERP-Daten
    target_keyword      TEXT,
    organic_rank        INTEGER,
    runs_ads             BOOLEAN,
    serp_source          TEXT,

    -- Tech-Stack-Daten
    has_gtm              BOOLEAN DEFAULT FALSE,
    has_gtag             BOOLEAN DEFAULT FALSE,
    has_fbq               BOOLEAN DEFAULT FALSE,
    has_google_ads_tag   BOOLEAN DEFAULT FALSE,
    has_tracking          BOOLEAN GENERATED ALWAYS AS (
                              has_gtm OR has_gtag OR has_fbq OR has_google_ads_tag
                          ) STORED,
    website_reachable     BOOLEAN,

    scraped_at            TIMESTAMPTZ,
    created_at             TIMESTAMPTZ DEFAULT now(),
    updated_at             TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_leads_niche_location
    ON raw_leads (niche, location);

-- Gewichte-Tabelle
CREATE TABLE IF NOT EXISTS scoring_weights (
    id            SERIAL PRIMARY KEY,
    alpha         NUMERIC(3,2) NOT NULL DEFAULT 0.20,
    beta          NUMERIC(3,2) NOT NULL DEFAULT 0.40,
    gamma         NUMERIC(3,2) NOT NULL DEFAULT 0.40,
    k_need        NUMERIC(4,3) NOT NULL DEFAULT 0.100,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_weights_sum CHECK (alpha + beta + gamma = 1.0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_scoring_weights_active
    ON scoring_weights (is_active) WHERE is_active;

INSERT INTO scoring_weights (alpha, beta, gamma, k_need, is_active)
SELECT 0.20, 0.40, 0.40, 0.100, TRUE
WHERE NOT EXISTS (SELECT 1 FROM scoring_weights WHERE is_active);

-- Scoring-ViewCREATE OR REPLACE VIEW vw_lead_scoring AS
WITH active_weights AS (
    SELECT alpha, beta, gamma, k_need
    FROM scoring_weights
    WHERE is_active
    LIMIT 1
),
base AS (
    SELECT
        rl.*,
        (LN(rl.review_count + 1) /
         NULLIF(LN(MAX(rl.review_count) OVER () + 1), 0)) AS b_index,

        (1 - EXP(-1 * aw.k_need *
              GREATEST(0, COALESCE(rl.organic_rank, 999) - 10)
        )) AS n_index,

        CASE
            WHEN rl.runs_ads = TRUE  AND rl.has_tracking = FALSE THEN 1.0
            WHEN rl.runs_ads = FALSE AND rl.has_tracking = FALSE THEN 0.8
            WHEN rl.runs_ads = FALSE AND rl.has_tracking = TRUE  THEN 0.4
            ELSE 0.1
        END AS p_index,

        aw.alpha, aw.beta, aw.gamma
    FROM raw_leads rl
    CROSS JOIN active_weights aw
    -- Filter entfernt: Jetzt werden alle gescrapten Unternehmen bewertet!
)
SELECT
    id,
    place_id,
    company_name,
    niche,
    location,
    address,
    website_url,
    phone,
    rating,
    review_count,
    organic_rank,
    runs_ads,
    has_tracking,
    has_gtm,
    has_gtag,
    has_fbq,
    has_google_ads_tag,
    ROUND(GREATEST(b_index, 0.001)::numeric, 4) AS b_index,
    ROUND(n_index::numeric, 4) AS n_index,
    ROUND(p_index::numeric, 4) AS p_index,
    ROUND(
        ((POWER(GREATEST(b_index, 0.001), alpha) *
          POWER(GREATEST(n_index, 0.001), beta)  *
          POWER(GREATEST(p_index, 0.001), gamma)) * 100)::numeric, 
        2
    ) AS final_score,
    CASE
        WHEN runs_ads = TRUE AND has_tracking = FALSE
            THEN 'Schaltet Ads OHNE Tracking – verbrennt nachweislich Budget'
        WHEN runs_ads = FALSE AND has_tracking = FALSE AND COALESCE(organic_rank, 999) > 10
            THEN 'Keine Ads, kein Tracking, schlechtes SEO – kompletter Blindflug'
        WHEN runs_ads = FALSE AND has_tracking = TRUE
            THEN 'Tracking vorhanden, aber keine Ads – Conversion-Daten liegen brach'
        ELSE 'Bereits vergleichsweise gut aufgestellt'
    END AS pitch_hint
FROM base
ORDER BY final_score DESC NULLS LAST;