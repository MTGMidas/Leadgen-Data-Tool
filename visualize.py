"""
Erstellt ein interaktives HTML-Dashboard mit Plotly-Diagrammen
sowie einem integrierten Kundenakten-Browser (Togglebar) mit flexibler Schlüsselerkennung.
"""
import json
from decimal import Decimal
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from . import db

def _find_field(lead_dict, keywords, default="-"):
    """Sucht in einem Dictionary flexibel nach einem Key, der eines der Keywords enthält."""
    if not isinstance(lead_dict, dict):
        return default
    for k, v in lead_dict.items():
        k_lower = str(k).lower()
        if any(kw in k_lower for kw in keywords):
            if v is not None and str(v).strip() != "":
                return v
    return default

def build_dashboard(out_html: str = "leads_dashboard.html"):
    leads = db.fetch_top_leads(limit=500)
    if not leads:
        print("Keine Leads für die Visualisierung gefunden.")
        return

    print(f"Gefundene Leads in DB: {len(leads)}")
    
    # Debug-Ausgabe: Zeigt dir im Terminal exakt, was die Datenbank liefert
    if leads:
        print("\n--- ERSTER LEAD (ROHDATEN AUS DB) ---")
        for k, v in leads[0].items():
            print(f"  Spalte '{k}': {v} (Typ: {type(v)})")
        print("--------------------------------------\n")

    # Daten flexibel aufbereiten
    processed_leads = []
    for lead in leads:
        item = {}
        item["name"] = _find_field(lead, ["name", "title", "company", "firma"], "Unbekannt")
        item["segment"] = _find_field(lead, ["segment", "category", "branche", "type"], "-")
        item["city"] = _find_field(lead, ["city", "location", "ort", "stadt"], "-")
        item["address"] = _find_field(lead, ["address", "street", "anschrift", "strasse"], "-")
        item["phone"] = _find_field(lead, ["phone", "tel", "telefon", "mobil"], "-")
        item["website"] = _find_field(lead, ["website", "url", "web"], "-")
        
        # Metriken & Scores (Erweiterte Keywords)
        item["final_score"] = float(_find_field(lead, ["final_score", "score", "total", "gesamt_score", "gesamtscore"], 0.0) or 0.0)
        item["n_index"] = float(_find_field(lead, ["n_index", "need", "n_idx", "potenzial", "bedarf"], 0.0) or 0.0)
        item["b_index"] = float(_find_field(lead, ["b_index", "business", "b_idx", "groesse", "aktivitaet"], 0.0) or 0.0)
        item["rating"] = _find_field(lead, ["rating", "stars", "sterne"], None)
        
        # Reviews Count (Erweiterte Keywords inkl. user_ratings_total)
        raw_reviews = _find_field(lead, ["reviews_count", "user_ratings_total", "user_ratings", "reviews", "review_count", "review_cnt", "bewertungen", "anzahl_bewertungen"], 0)
        try:
            item["reviews_count"] = int(float(raw_reviews)) if raw_reviews is not None else 0
        except (ValueError, TypeError):
            item["reviews_count"] = 0
        
        # Website Status / Reachable robust normalisieren
        raw_reachable = _find_field(lead, ["reachable", "status", "active", "online", "is_reachable"], False)
        if isinstance(raw_reachable, str):
            item["website_reachable"] = raw_reachable.lower() in ["true", "1", "yes", "active", "online", "ok", "reachable", "success"]
        else:
            item["website_reachable"] = bool(raw_reachable) if raw_reachable is not None else False
        
        # Tech-Stack Tags robust normalisieren
        for tag_key, tag_keywords in [
            ("has_gtm", ["gtm", "googletagmanager"]),
            ("has_gtag", ["gtag"]),
            ("has_fbq", ["fbq", "facebook", "pixel"]),
            ("has_google_ads_tag", ["ads", "google_ads", "googleads"])
        ]:
            val = _find_field(lead, tag_keywords, False)
            if isinstance(val, str):
                item[tag_key] = val.lower() in ["true", "1", "yes", "active", "online", "ok", "reachable", "success"]
            else:
                item[tag_key] = bool(val) if val is not None else False
        
        processed_leads.append(item)

    df = pd.DataFrame(processed_leads)

    # Datentypen für Pandas/Plotly absichern
    df["final_score"] = pd.to_numeric(df["final_score"], errors="coerce").fillna(0)
    df["n_index"] = pd.to_numeric(df["n_index"], errors="coerce").fillna(0)
    df["b_index"] = pd.to_numeric(df["b_index"], errors="coerce").fillna(0)
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df["reviews_count"] = pd.to_numeric(df["reviews_count"], errors="coerce").fillna(0)

    # --- Plotly Subplots erstellen (2x2 Grid) ---
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Top Leads nach Final Score",
            "Bewertungen vs. Rating",
            "N-Index (Potenzial) vs. B-Index (Größe)",
            "Segment-Verteilung"
        )
    )

    # Plot 1: Top Leads Bar Chart
    df_sorted = df.sort_values("final_score", ascending=True).tail(15)
    fig.add_trace(
        go.Bar(
            x=df_sorted["final_score"],
            y=df_sorted["name"],
            orientation="h",
            marker=dict(color=df_sorted["final_score"], colorscale="Viridis"),
            text=df_sorted["final_score"].round(1),
            textposition="auto",
        ),
        row=1, col=1
    )

    # Plot 2: Reviews vs Rating
    fig.add_trace(
        go.Scatter(
            x=df["rating"],
            y=df["reviews_count"],
            mode="markers",
            marker=dict(
                size=12,
                color=df["final_score"],
                colorscale="Plasma",
                showscale=True,
                colorbar=dict(title="Score", x=0.46, len=0.45, y=0.8)
            ),
            text=df["name"].astype(str) + " (" + df["segment"].astype(str) + ")",
            hovertemplate="<b>%{text}</b><br>Rating: %{x} ⭐<br>Bewertungen: %{y}<br><extra></extra>"
        ),
        row=1, col=2
    )

    # Plot 3: N-Index vs B-Index Scatter
    fig.add_trace(
        go.Scatter(
            x=df["b_index"],
            y=df["n_index"],
            mode="markers",
            marker=dict(
                size=df["final_score"].clip(lower=5) / 3 + 5,
                color=df["final_score"],
                colorscale="Viridis",
            ),
            text=df["name"].astype(str) + " (" + df["segment"].astype(str) + ")",
            hovertemplate="<b>%{text}</b><br>B-Index (Größe): %{x:.1f}<br>N-Index (Potenzial): %{y:.1f}<br><extra></extra>"
        ),
        row=2, col=1
    )

    # Plot 4: Segment Distribution
    if "segment" in df.columns:
        seg_counts = df["segment"].value_counts()
        fig.add_trace(
            go.Bar(
                x=seg_counts.index,
                y=seg_counts.values,
                marker=dict(color="#3366cc")
            ),
            row=2, col=2
        )

    fig.update_layout(
        height=900,
        title_text="<b>Lead Generation & Tech Stack Dashboard</b>",
        showlegend=False,
        template="plotly_white"
    )

    fig.update_xaxes(title_text="Score", row=1, col=1)
    fig.update_yaxes(title_text="Kunde", row=1, col=1)
    fig.update_xaxes(title_text="Google Rating", row=1, col=2)
    fig.update_yaxes(title_text="Anzahl Bewertungen", row=1, col=2)
    fig.update_xaxes(title_text="B-Index (Größe)", row=2, col=1)
    fig.update_yaxes(title_text="N-Index (Potenzial)", row=2, col=1)
    fig.update_xaxes(title_text="Segment", row=2, col=2)
    fig.update_yaxes(title_text="Anzahl Leads", row=2, col=2)

    plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    # Serialisieren für das Frontend (inkl. Decimal-Konvertierung)
    cleaned_leads = []
    for item in processed_leads:
        clean_item = {}
        for k, v in item.items():
            if pd.isna(v) or v is None:
                clean_item[k] = "-"
            elif isinstance(v, Decimal):
                clean_item[k] = float(v) if '.' in str(v) else int(v)
            else:
                clean_item[k] = v
        cleaned_leads.append(clean_item)

    # HTML-Ausgabe
    html_content = f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>Lead Dashboard & Kundenakten</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f6f9;
                margin: 0;
                padding: 20px;
                color: #333;
            }}
            .container {{
                max-width: 1300px;
                margin: 0 auto;
                background: #fff;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            }}
            .explanation-box {{
                background: #eef2f7;
                border-left: 5px solid #007bff;
                padding: 20px;
                margin: 30px 0;
                border-radius: 4px;
            }}
            .browser-section {{
                margin-top: 40px;
                border-top: 2px solid #eaeaea;
                padding-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 style="text-align: center; color: #222; margin-bottom: 30px;">Lead Generation Dashboard</h1>
            
            {plotly_html}

            <div class="explanation-box">
                <h3>💡 Erklärung zum Score Index (Final Score)</h3>
                <p>Der finale Score setzt sich aus zwei Hauptindizes zusammen, die priorisieren, welche Unternehmen das größte Potenzial für eine Zusammenarbeit bieten:</p>
                <ul>
                    <li><strong>N-Index (Needs / Digitalisierungsbedarf):</strong> Bewertet das Fehlen wichtiger Marketing- und Tracking-Skripte (z. B. Google Tag Manager, Google Ads, Meta Pixel). Je weniger dieser Tools aktiv sind, desto höher ist der Beratungsbedarf.</li>
                    <li><strong>B-Index (Business Size / Aktivität):</strong> Misst die Größe, Sichtbarkeit und Aktivität des Unternehmens anhand von Google-Bewertungen, Rating und Standortpräsenz.</li>
                    <li><strong>Final Score:</strong> Die gewichtete Kombination aus Bedarf und Unternehmensgröße, um die lukrativsten Leads sofort zu identifizieren.</li>
                </ul>
            </div>

            <div class="browser-section">
                <h2 style="color: #333; margin-bottom: 10px;">📂 Interaktive Kundenakten</h2>
                <p style="color: #666; margin-bottom: 20px;">Wähle einen Kunden aus der Togglebar aus, um die detaillierten Kontaktdaten, gemessenen Metriken und Tracking-Signale einzusehen:</p>
                
                <div style="margin-bottom: 25px;">
                    <label for="customerSelect" style="font-weight: bold; margin-right: 10px; color: #444;">Kunde auswählen:</label>
                    <select id="customerSelect" onchange="renderCustomerDetail(this.value)" style="padding: 10px; font-size: 16px; border-radius: 4px; border: 1px solid #ccc; width: 420px; max-width: 100%;">
                    </select>
                </div>

                <div id="customerDetailCard" style="background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
                </div>
            </div>
        </div>

        <script>
            const leadsData = {json.dumps(cleaned_leads, ensure_ascii=False)};

            function initCustomerBrowser() {{
                const select = document.getElementById('customerSelect');
                if (!select || !leadsData.length) return;
                
                select.innerHTML = '';
                leadsData.forEach((lead, index) => {{
                    const opt = document.createElement('option');
                    opt.value = index;
                    const scoreVal = lead.final_score !== undefined && !isNaN(lead.final_score) ? Number(lead.final_score).toFixed(1) : '0';
                    opt.textContent = `${{lead.name}} (${{lead.segment}} - ${{lead.city}}) [Score: ${{scoreVal}}]`;
                    select.appendChild(opt);
                }});
                renderCustomerDetail(0);
            }}

            function renderCustomerDetail(index) {{
                const lead = leadsData[index];
                if (!lead) return;

                const container = document.getElementById('customerDetailCard');
                
                const formatTag = (val) => (val === true) ? '<span style="color: #28a745; font-weight: bold;">✔ Vorhanden</span>' : '<span style="color: #999;">✘ Nicht gefunden</span>';
                const formatReach = (val) => (val === true) ? '<span style="color: #28a745; font-weight: bold;">Erreichbar</span>' : '<span style="color: #dc3545; font-weight: bold;">Nicht erreichbar</span>';

                const webUrl = lead.website;
                const webHtml = webUrl && webUrl !== '-' ? `<a href="${{webUrl.startsWith('http') ? webUrl : 'https://' + webUrl}}" target="_blank" style="color: #007bff;">${{webUrl}}</a>` : '-';

                const ratingStr = (lead.rating !== null && lead.rating !== '-' && lead.rating !== undefined) ? lead.rating + ' ⭐ (' + lead.reviews_count + ' Bewertungen)' : '-';

                container.innerHTML = `
                    <h3 style="margin-top: 0; color: #007bff; border-bottom: 1px solid #eee; padding-bottom: 10px; font-size: 1.3em;">${{lead.name}}</h3>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
                        <!-- 1. KONTAKTDATEN -->
                        <div style="background: #f8f9fa; padding: 18px; border-radius: 6px; border-left: 4px solid #007bff;">
                            <h4 style="margin-top: 0; color: #333; margin-bottom: 12px; border-bottom: 1px solid #e5e5e5; padding-bottom: 6px;">📞 Kontaktdaten</h4>
                            <p style="margin: 8px 0;"><strong>Name:</strong> ${{lead.name}}</p>
                            <p style="margin: 8px 0;"><strong>Adresse:</strong> ${{lead.address}}</p>
                            <p style="margin: 8px 0;"><strong>Telefon:</strong> ${{lead.phone}}</p>
                            <p style="margin: 8px 0;"><strong>Website:</strong> ${{webHtml}}</p>
                            <p style="margin: 8px 0;"><strong>Branche / Segment:</strong> ${{lead.segment}}</p>
                            <p style="margin: 8px 0;"><strong>Stadt:</strong> ${{lead.city}}</p>
                        </div>

                        <!-- 2. GEMESSENE ZAHLEN & METRIKEN -->
                        <div style="background: #f8f9fa; padding: 18px; border-radius: 6px; border-left: 4px solid #28a745;">
                            <h4 style="margin-top: 0; color: #333; margin-bottom: 12px; border-bottom: 1px solid #e5e5e5; padding-bottom: 6px;">📊 Gemessene Metriken & Scores</h4>
                            <p style="margin: 8px 0;"><strong>Finaler Score:</strong> <span style="font-size: 1.15em; font-weight: bold; color: #28a745;">${{lead.final_score !== undefined && !isNaN(lead.final_score) ? Number(lead.final_score).toFixed(2) : '-'}}</span></p>
                            <p style="margin: 8px 0;"><strong>N-Index (Potenzial/Bedarf):</strong> ${{lead.n_index !== undefined && !isNaN(lead.n_index) ? Number(lead.n_index).toFixed(2) : '-'}}</p>
                            <p style="margin: 8px 0;"><strong>B-Index (Größe/Aktivität):</strong> ${{lead.b_index !== undefined && !isNaN(lead.b_index) ? Number(lead.b_index).toFixed(2) : '-'}}</p>
                            <p style="margin: 8px 0;"><strong>Google Rating:</strong> ${{ratingStr}}</p>
                            <p style="margin: 8px 0;"><strong>Website Status:</strong> ${{formatReach(lead.website_reachable)}}</p>
                        </div>
                    </div>

                    <!-- 3. TECHNISCHE TRACKING-SIGNALE -->
                    <div style="margin-top: 20px; background: #fff; padding: 18px; border: 1px solid #eaeaea; border-radius: 6px;">
                        <h4 style="margin-top: 0; color: #333; margin-bottom: 12px; border-bottom: 1px solid #f0f0f0; padding-bottom: 6px;">🔍 Technische Tracking-Signale (Marketing-Stack)</h4>
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; text-align: center;">
                            <div style="background: #fdfdfd; padding: 12px; border: 1px solid #eee; border-radius: 4px;">
                                <div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Google Tag Manager</div>
                                <div>${{formatTag(lead.has_gtm)}}</div>
                            </div>
                            <div style="background: #fdfdfd; padding: 12px; border: 1px solid #eee; border-radius: 4px;">
                                <div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Google Gtag</div>
                                <div>${{formatTag(lead.has_gtag)}}</div>
                            </div>
                            <div style="background: #fdfdfd; padding: 12px; border: 1px solid #eee; border-radius: 4px;">
                                <div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Meta Pixel (FBQ)</div>
                                <div>${{formatTag(lead.has_fbq)}}</div>
                            </div>
                            <div style="background: #fdfdfd; padding: 12px; border: 1px solid #eee; border-radius: 4px;">
                                <div style="font-size: 0.85em; color: #666; margin-bottom: 4px;">Google Ads Tag</div>
                                <div>${{formatTag(lead.has_google_ads_tag)}}</div>
                            </div>
                        </div>
                    </div>
                `;
            }}

            window.addEventListener('DOMContentLoaded', initCustomerBrowser);
        </script>
    </body>
    </html>
    """

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Dashboard erfolgreich erstellt: {out_html}")

if __name__ == "__main__":
    build_dashboard()