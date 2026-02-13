import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

# =============================
# PARÂMETROS FIXOS DO SEU MANUAL
# =============================

CAPITAL = 5000.0
RISCO_POR_TRADE = 0.01
STOP_PERCENTUAL = 0.03

ETFS = {
    "SMAL11": "SMAL11.SA",
    "NASD11": "NASD11.SA",
    "FIND11": "FIND11.SA"
}

# =============================
# FUNÇÕES DE INDICADORES
# =============================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def stochastic(df, k_period=14, d_period=3, smooth=3):
    low_min = df['Low'].rolling(window=k_period).min()
    high_max = df['High'].rolling(window=k_period).max()

    k = 100 * (df['Close'] - low_min) / (high_max - low_min)
    k_smooth = k.rolling(window=smooth).mean()
    d = k_smooth.rolling(window=d_period).mean()

    return k_smooth, d


def dmi_adx(df, period=14):

    high = df['High']
    low = df['Low']
    close = df['Close']

    plus_dm = high.diff()
    minus_dm = low.diff().abs()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()

    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(window=period).mean()

    return plus_di, minus_di, adx


def baixar_dados(ticker, interval, period="18mo"):
    df = yf.download(ticker, interval=interval, period=period, auto_adjust=False, progress=False)
    df.dropna(inplace=True)
    return df


# =============================
# LÓGICA DO SETUP
# =============================

def analisar_ativo(nome, ticker):

    diario = baixar_dados(ticker, "1d")
    semanal = baixar_dados(ticker, "1wk", period="36mo")

    if len(diario) < 80 or len(semanal) < 80:
        return None

    diario["EMA69"] = ema(diario["Close"], 69)
    semanal["EMA69"] = ema(semanal["Close"], 69)

    k, d = stochastic(diario)
    diario["K"] = k
    diario["D"] = d

    plus_di, minus_di, adx = dmi_adx(diario)
    diario["DIp"] = plus_di
    diario["DIn"] = minus_di
    diario["ADX"] = adx

    d1 = diario.iloc[-1]
    d2 = diario.iloc[-2]

    s1 = semanal.iloc[-1]

    # =============================
    # FILTROS DIÁRIO
    # =============================

    cond_preco = d1["Close"] > d1["EMA69"]
    cond_dmi = d1["DIp"] > d1["DIn"]
    cond_adx = d1["ADX"] > 20 and d1["ADX"] > d2["ADX"]
    cond_estoc = d1["K"] > d1["D"]

    # candle de sinal simples e objetivo
    cond_candle = d1["Close"] > d2["High"]

    # =============================
    # FILTRO SEMANAL
    # =============================

    cond_semanal = s1["Close"] > s1["EMA69"]

    sinal = all([
        cond_preco,
        cond_dmi,
        cond_adx,
        cond_estoc,
        cond_candle,
        cond_semanal
    ])

    if not sinal:
        return {
            "Ativo": nome,
            "Sinal": "NÃO",
            "Entrada": None,
            "Qtd": None,
            "Valor_ordem": None
        }

    preco_entrada = round(d1["High"] + 0.01, 2)

    risco_total = CAPITAL * RISCO_POR_TRADE
    risco_por_cota = preco_entrada * STOP_PERCENTUAL

    quantidade = int(risco_total // risco_por_cota)

    if quantidade <= 0:
        return {
            "Ativo": nome,
            "Sinal": "SIM",
            "Entrada": preco_entrada,
            "Qtd": 0,
            "Valor_ordem": 0.0
        }

    valor_ordem = quantidade * preco_entrada

    return {
        "Ativo": nome,
        "Sinal": "SIM",
        "Entrada": preco_entrada,
        "Qtd": quantidade,
        "Valor_ordem": round(valor_ordem, 2)
    }


# =============================
# INTERFACE
# =============================

st.title("Scanner de ETFs – Setup do Roberson")

st.markdown("""
Ativos monitorados:
- SMAL11
- NASD11
- FIND11

Execução no diário, confirmação no semanal.
""")

if st.button("Rodar scanner agora"):

    resultados = []

    for nome, ticker in ETFS.items():
        r = analisar_ativo(nome, ticker)
        if r is not None:
            resultados.append(r)

    df = pd.DataFrame(resultados)

    st.dataframe(df, use_container_width=True)

    st.markdown("### Parâmetros de gestão utilizados")
    st.write(f"Capital: R$ {CAPITAL:,.2f}")
    st.write("Risco por trade: 1%")
    st.write("Stop ETF: 3%")
    st.write("Apenas 1 posição simultânea")

