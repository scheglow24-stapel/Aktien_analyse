import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

# --- KONFIGURATION ---
RISIKO_SCHWELLE = 0.02
GEWICHTE = {"Technik": 0.45, "Sentiment": 0.25, "Risiko": 0.30}

st.set_page_config(page_title="Aktien-Analyse", page_icon="📈", layout="centered")
st.title("📈 Aktien-Analyse")
st.caption("Technik · Sentiment · Risiko – gewichtet und kalibriert")

@st.cache_data(ttl=300)
def lade_und_bereche_indikatoren(ticker_symbol: str) -> dict:
    try:
        daten = yf.Ticker(ticker_symbol).history(period="6mo")
        if daten.empty:
            return {"fehler": f"Keine Daten für {ticker_symbol}."}
        
        daten.ta.rsi(length=14, append=True)
        daten.ta.macd(append=True)
        daten.ta.bbands(length=20, append=True)

        renditen = daten["Close"].pct_change().dropna()
        volatilitaet = float(renditen.std())
        kurs_heute = daten["Close"].iloc[-1]
        kurs_vor5 = daten["Close"].iloc[-6] if len(daten) >= 6 else daten["Close"].iloc[0]
        momentum = float((kurs_heute - kurs_vor5) / kurs_vor5 * 100)

        return {
            "ticker": ticker_symbol,
            "kurs": float(daten["Close"].iloc[-1]),
            "rsi": float(daten["RSI_14"].iloc[-1]),
            "macd": float(daten["MACD_12_26_9"].iloc[-1]),
            "macd_signal": float(daten["MACDs_12_26_9"].iloc[-1]),
            "bb_lower": float(daten["BBL_20_2.0"].iloc[-1]),
            "bb_upper": float(daten["BBU_20_2.0"].iloc[-1]),
            "volatilitaet": volatilitaet,
            "momentum": momentum,
            "historie": daten # Wichtig: Wir geben die ganzen Daten für das Chart mit zurück
        }
    except Exception as e:
        return {"fehler": f"Fehler bei {ticker_symbol}: {e}"}

def technischer_agent(d: dict) -> float:
    score = 0.0
    if d["rsi"] < 30: score += 0.4
    elif d["rsi"] > 70: score -= 0.4
    if d["macd"] > d["macd_signal"]: score += 0.3
    else: score -= 0.3
    if d["kurs"] <= d["bb_lower"]: score += 0.3
    elif d["kurs"] >= d["bb_upper"]: score -= 0.3
    return float(np.clip(score, -1.0, 1.0))

def sentiment_agent(d: dict) -> float:
    m = d["momentum"]
    if m > 3: return 1.0
    if m > 1: return 0.5
    if m > -1: return 0.0
    if m > -3: return -0.5
    return -1.0

def risiko_agent(d: dict) -> float:
    v = d["volatilitaet"]
    if v > RISIKO_SCHWELLE * 1.5: return -1.0
    if v > RISIKO_SCHWELLE: return -0.5
    return 0.0

def berechne_gewichtet_score(d: dict) -> dict:
    s_tech, s_sent, s_risk = technischer_agent(d), sentiment_agent(d), risiko_agent(d)
    score = (GEWICHTE["Technik"] * s_tech + GEWICHTE["Sentiment"] * s_sent + GEWICHTE["Risiko"] * s_risk)
    
    std = np.std([s_tech, s_sent, s_risk])
    uebereinstimmung = max(0.0, 1 - (std / 0.816))
    konfidenz = 0.5 + (0.95 - 0.5) * uebereinstimmung

    if score > 0.1: richtung, wkt = "BULLISCH", konfidenz
    elif score < -0.1: richtung, wkt = "BÄRISCH", konfidenz
    else: richtung, wkt = "NEUTRAL", 0.5

    return {
        "Ticker": d["ticker"], "Richtung": richtung,
        "Wahrscheinlichkeit (%)": round(wkt * 100, 1),
        "Score": round(score, 3),
        "Technik": round(s_tech, 2), "Sentiment": round(s_sent, 2), "Risiko": round(s_risk, 2),
        "Historie": d["historie"] # Historie für die Charts durchreichen
    }

# --- UI ---
ticker_eingabe = st.text_input("Ticker (kommagetrennt)", "AAPL, MSFT, NVDA")
ticker_liste = [t.strip().upper() for t in ticker_eingabe.split(",") if t.strip()]

if st.button("Analysieren", type="primary"):
    if not ticker_liste:
        st.warning("Bitte mindestens einen Ticker eingeben.")
    else:
        with st.spinner("Analysiere..."):
            ergebnisse = []
            for t in ticker_liste:
                d = lade_und_bereche_indikatoren(t)
                if "fehler" in d:
                    st.error(d["fehler"])
                    continue
                ergebnisse.append(berechne_gewichtet_score(d))
            
            if ergebnisse:
                # Tabelle (ohne die Historie-Spalte anzuzeigen)
                df = pd.DataFrame([{k:v for k,v in e.items() if k != "Historie"} for e in ergebnisse])
                df = df.sort_values("Wahrscheinlichkeit (%)", ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.divider()
                st.subheader("📊 Technische Charts")

                # Charts für jeden Ticker generieren
                for e in ergebnisse:
                    with st.expander(f"{e['Ticker']} – Chart anzeigen ({e['Richtung']} | {e['Wahrscheinlichkeit (%)']}%)"):
                        daten = e["Historie"]
                        
                        # Gleitende Durchschnitte berechnen (SMA 20 und 50)
                        daten["SMA_20"] = daten["Close"].rolling(window=20).mean()
                        daten["SMA_50"] = daten["Close"].rolling(window=50).mean()
                        
                        # Streamlit Candlestick Chart
                        st.candle_chart(
                            daten,
                            x="Date",
                            open="Open",
                            high="High",
                            low="Low",
                            close="Close",
                            volume="Volume",
                            title=f"{e['Ticker']} Kerzenchart",
                            use_container_width=True
                        )
                        
                        # Zusatzinfo: Aktuelle RSI- und MACD-Werte
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Aktueller Kurs", f"${e['Historie']['Close'].iloc[-1]:.2f}")
                        col2.metric("RSI (14)", f"{e['Technik']:.2f}")
                        col3.metric("Sentiment (5T)", f"{e['Sentiment']:.2f}")
