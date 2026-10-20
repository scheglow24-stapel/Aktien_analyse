import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from yfinance import Search

# --- KONFIGURATION & TRADINGVIEW-FARBEN ---
BG_COLOR = "#131722"      
GRID_COLOR = "#2a2e39"    
TEXT_COLOR = "#d1d4dc"    
UP_COLOR = "#089981"      
DOWN_COLOR = "#f23645"    
SMA20_COLOR = "#f5c142"   
SMA50_COLOR = "#2962ff"   
SMA200_COLOR = "#e91e63"  

st.set_page_config(page_title="TV Clone", page_icon="📈", layout="wide")

st.markdown(f"""
    <style>
    .stApp {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; }}
    .stSidebar {{ background-color: #1e222d; border-right: 1px solid {GRID_COLOR}; }}
    h1, h2, h3 {{ color: {TEXT_COLOR} !important; font-family: 'Roboto', sans-serif; }}
    .stButton>button {{ background-color: #2962ff; color: white; border-radius: 4px; }}
    .stTextInput>div>div>input {{ background-color: #1e222d; color: {TEXT_COLOR}; border: 1px solid {GRID_COLOR}; }}
    .stSelectbox>div>div>div {{ background-color: #1e222d; color: {TEXT_COLOR}; }}
    header {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>
""", unsafe_allow_html=True)

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

@st.cache_data(ttl=300)
def lade_daten(ticker_symbol: str):
    try:
        daten = yf.Ticker(ticker_symbol).history(period="1y")
        if daten.empty: 
            return {"fehler": "Keine Daten."}
        
        daten.ta.rsi(length=14, append=True)
        daten["SMA_20"] = daten["Close"].rolling(window=20).mean()
        daten["SMA_50"] = daten["Close"].rolling(window=50).mean()
        daten["SMA_200"] = daten["Close"].rolling(window=200).mean()
        
        return {"historie": daten, "ticker": ticker_symbol}
    except Exception as e:
        return {"fehler": str(e)}

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
        standard = {"AAPL": "Apple (US)", "MSFT": "Microsoft (US)", "NVDA": "NVIDIA (US)", "SAP.DE": "SAP (DE)", "BABA": "Alibaba (CN)"}
        auswahl = st.selectbox("Beliebte Aktien:", list(standard.keys()), format_func=lambda x: standard[x])
        ausgewaehlter_ticker = auswahl

if ausgewaehlter_ticker:
    data = lade_daten(ausgewaehlter_ticker)
    
    if "fehler" in data:
        st.error(data["fehler"])
    else:
        df = data["historie"]
        
        aktueller_kurs = df["Close"].iloc[-1]
        vorheriger_kurs = df["Close"].iloc[-2]
        kurs_aenderung = aktueller_kurs - vorheriger_kurs
        prozent_aenderung = (kurs_aenderung / vorheriger_kurs) * 100
        
        farbe = UP_COLOR if kurs_aenderung >= 0 else DOWN_COLOR
        pfeil = "▲" if kurs_aenderung >= 0 else "▼"
        
        waehrung = "€" if ".DE" in ausgewaehlter_ticker else ("¥" if (".SS" in ausgewaehlter_ticker or ".SZ" in ausgewaehlter_ticker) else "$")

        st.markdown(f"""
            <div style="display: flex; align-items: baseline; gap: 15px; font-family: 'Roboto', sans-serif;">
                <h2 style="margin: 0; color: {TEXT_COLOR};">{ausgewaehlter_ticker}</h2>
                <h1 style="margin: 0; color: {farbe}; font-size: 2.5rem;">{waehrung}{aktueller_kurs:,.2f}</h1>
                <h3 style="margin: 0; color: {farbe};">{pfeil} {kurs_aenderung:,.2f} ({prozent_aenderung:.2f}%)</h3>
            </div>
        """, unsafe_allow_html=True)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, 
                            row_heights=[0.65, 0.15, 0.20])

        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Preis",
            increasing_line_color=UP_COLOR, decreasing_line_color=DOWN_COLOR
        ), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20", line=dict(color=SMA20_COLOR, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50", line=dict(color=SMA50_COLOR, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA_200"], name="SMA 200", line=dict(color=SMA200_COLOR, width=1.5)), row=1, col=1)

        colors = [UP_COLOR if close >= open else DOWN_COLOR for close, open in zip(df['Close'], df['Open'])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors, name="Volumen"), row=2, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI", line=dict(color='#b2b5be', width=1.5)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color=DOWN_COLOR, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color=UP_COLOR, row=3, col=1)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=BG_COLOR,
            xaxis_rangeslider_visible=False,
            height=800,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=TEXT_COLOR)),
            hovermode="x unified"
        )

        fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1, zeroline=False)
        fig.update_yaxes(title_text="", side="right", row=1, col=1)
        fig.update_yaxes(title_text="", side="right", row=2, col=1)
        fig.update_yaxes(title_text="RSI", side="right", row=3, col=1)

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})