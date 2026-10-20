import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import streamlit.components.v1 as components
from yfinance import Search

# --- KONFIGURATION & TRADINGVIEW-FARBEN ---
RISIKO_SCHWELLE = 0.02
GEWICHTE = {"Technik": 0.45, "Sentiment": 0.25, "Risiko": 0.30}

BG_COLOR = "#131722"      
TEXT_COLOR = "#d1d4dc"    

st.set_page_config(page_title="Global Terminal", page_icon="🌍", layout="wide")

# Custom CSS für den Dark Mode
st.markdown(f"""
    <style>
    .stApp {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; }}
    .stSidebar {{ background-color: #1e222d; border-right: 1px solid #2a2e39; }}
    h1, h2, h3 {{ color: {TEXT_COLOR} !important; font-family: 'Roboto', sans-serif; }}
    .stTextInput>div>div>input {{ background-color: #1e222d; color: {TEXT_COLOR}; border: 1px solid #2a2e39; }}
    .stSelectbox>div>div>div {{ background-color: #1e222d; color: {TEXT_COLOR}; }}
    header {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)

# --- SUCHE ---
@st.cache_data(ttl=3600)
def suche_weltweit(query_text: str):
    if not query_text or len(query_text) < 2: 
        return pd.DataFrame()
    try:
        search = Search(query_text, max_results=10)
        quotes = search.quotes
        if not quotes: 
            return pd.DataFrame()
        results = [{"Ticker": q.get("symbol"), "Name": q.get("shortname", q.get("longname", "Unbekannt"))} for q in quotes if q.get("quoteType") == "EQUITY"]
        return pd.DataFrame(results)
    except Exception: 
        return pd.DataFrame()

# --- DATEN & AGENTEN ---
@st.cache_data(ttl=300)
def lade_und_analysiere(ticker_symbol: str):
    try:
        daten = yf.Ticker(ticker_symbol).history(period="1y")
        if daten.empty: return {"fehler": "Keine Daten."}
        
        daten.ta.rsi(length=14, append=True)
        daten.ta.macd(append=True)
        daten.ta.bbands(length=20, append=True)

        renditen = daten["Close"].pct_change().dropna()
        volatilitaet = float(renditen.std())
        kurs_heute = daten["Close"].iloc[-1]
        kurs_vor5 = daten["Close"].iloc[-6] if len(daten) >= 6 else daten["Close"].iloc[0]
        momentum = float((kurs_heute - kurs_vor5) / kurs_vor5 * 100)

        d = {
            "ticker": ticker_symbol, "kurs": float(kurs_heute),
            "rsi": float(daten["RSI_14"].iloc[-1]), "macd": float(daten["MACD_12_26_9"].iloc[-1]),
            "macd_signal": float(daten["MACDs_12_26_9"].iloc[-1]), "bb_lower": float(daten["BBL_20_2.0"].iloc[-1]),
            "bb_upper": float(daten["BBU_20_2.0"].iloc[-1]), "volatilitaet": volatilitaet, "momentum": momentum
        }
        
        # Agenten Logik
        s_tech = 0.0
        if d["rsi"] < 30: s_tech += 0.4
        elif d["rsi"] > 70: s_tech -= 0.4
        if d["macd"] > d["macd_signal"]: s_tech += 0.3
        else: s_tech -= 0.3
        if d["kurs"] <= d["bb_lower"]: s_tech += 0.3
        elif d["kurs"] >= d["bb_upper"]: s_tech -= 0.3
        s_tech = float(np.clip(s_tech, -1.0, 1.0))

        s_sent = 1.0 if momentum > 3 else (0.5 if momentum > 1 else (0.0 if momentum > -1 else (-0.5 if momentum > -3 else -1.0)))
        s_risk = -1.0 if volatilitaet > RISIKO_SCHWELLE * 1.5 else (-0.5 if volatilitaet > RISIKO_SCHWELLE else 0.0)

        score = (GEWICHTE["Technik"] * s_tech + GEWICHTE["Sentiment"] * s_sent + GEWICHTE["Risiko"] * s_risk)
        std = np.std([s_tech, s_sent, s_risk])
        konfidenz = 0.5 + (0.95 - 0.5) * max(0.0, 1 - (std / 0.816))

        richtung = "BULLISCH" if score > 0.1 else ("BÄRISCH" if score < -0.1 else "NEUTRAL")
        
        return {"daten": d, "richtung": richtung, "wkt": round(konfidenz * 100, 1), "score": round(score, 3)}
    except Exception as e:
        return {"fehler": str(e)}

# --- SIDEBAR UI ---
with st.sidebar:
    st.markdown(f"<h2 style='color:{TEXT_COLOR}'>🌍 Watchlist</h2>", unsafe_allow_html=True)
    suchbegriff = st.text_input("Suchen (z.B. AAPL, SAP, Alibaba)", "")
    
    if suchbegriff:
        ergebnisse = suche_weltweit(suchbegriff)
        if not ergebnisse.empty:
            auswahl = st.selectbox("Ergebnisse:", ergebnisse["Ticker"].tolist(), format_func=lambda x: f"{ergebnisse[ergebnisse['Ticker']==x]['Name'].values[0]} ({x})")
            ausgewaehlter_ticker = auswahl
        else:
            st.info("Nichts gefunden.")
            ausgewaehlter_ticker = None
    else:
        standard = {"AAPL": "Apple (US)", "MSFT": "Microsoft (US)", "SAP.DE": "SAP (DE)", "BABA": "Alibaba (CN)", "TSLA": "Tesla (US)"}
        auswahl = st.selectbox("Beliebte Aktien:", list(standard.keys()), format_func=lambda x: standard[x])
        ausgewaehlter_ticker = auswahl

# --- HAUPTBEREICH ---
if ausgewaehlter_ticker:
    result = lade_und_analysiere(ausgewaehlter_ticker)
    
    if "fehler" in result:
        st.error(result["fehler"])
    else:
        d = result["daten"]
        farbe = "#089981" if result["richtung"] == "BULLISCH" else ("#f23645" if result["richtung"] == "BÄRISCH" else "#d1d4dc")
        
        # Kopfzeile
        st.markdown(f"""
            <div style="display: flex; align-items: baseline; gap: 20px; font-family: 'Roboto', sans-serif; margin-bottom: 20px;">
                <h1 style="margin: 0; color: {TEXT_COLOR};">{ausgewaehlter_ticker}</h1>
                <h2 style="margin: 0; color: {farbe};">Signal: {result['richtung']} ({result['wkt']}%)</h2>
            </div>
        """, unsafe_allow_html=True)

        # Das echte TradingView Widget einbetten
        # Wir nutzen den offiziellen TradingView Embed Code
        tradingview_html = f"""
        <div class="tradingview-widget-container" style="height:100%; width:100%">
          <div id="tradingview_chart" style="height:calc(100% - 32px); width:100%"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "{ausgewaehlter_ticker}",
            "interval": "D",
            "timezone": "Europe/Berlin",
            "theme": "dark",
            "style": "1",
            "locale": "de_DE",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "withdateranges": true,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "studies": [
              "RSI@tv-basicstudies",
              "MASimple@tv-basicstudies"
            ],
            "container_id": "tradingview_chart"
          }});
          </script>
        </div>
        """
        
        # Das Widget mit einer festen Höhe in Streamlit anzeigen
        components.html(tradingview_html, height=700)
        
        # Kleine Info-Zeile unten
        st.caption(f"🤖 KI-Analyse: Score {result['score']} | RSI {d['rsi']:.1f} | Volatilität {d['volatilitaet']:.2%} | (Zeichnen & Indikatoren direkt im Chart oben möglich)")