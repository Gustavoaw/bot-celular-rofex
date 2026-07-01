import numpy as np
import pandas as pd
import plotly.graph_objects as gr
import streamlit as st
import pyRofex
import yfinance as yf

# Configuración móvil
st.set_page_config(page_title="Rofex RealTime", layout="centered", page_icon="📱")
st.title("📱 Control Real-Time (Ecovalores)")

# --- PARAMETROS ---
st.sidebar.header("⚙️ Parámetros")
desvios = st.sidebar.slider("Umbral Z-Score", min_value=1.5, max_value=3.0, value=2.0, step=0.1)

# --- CONEXIÓN AL BROKER ---
@st.cache_resource
def conectar_broker():
    try:
        pyrofex.initialize(
            user=st.secrets["ECO_USER"],
            password=st.secrets["ECO_PASSWORD"],
            account=st.secrets["ECO_ACCOUNT"],
            environment=pyrofex.Environment.REMARKET # Cambiar a LIVE si estás en producción
        )
        return True
    except:
        return False

broker_vivo = conectar_broker()

# --- CAPTURA HÍBRIDA DE DATOS ---
@st.cache_data(ttl=10) # Actualiza cada 10 segundos al tocar la pantalla
def obtener_datos_limpios():
    # 1. Traemos el grueso del historial desde Yahoo (Velas de 15 min de los últimos 5 días)
    tickers = ["^RFX20", "GGAL", "YPF"]
    datos = yf.download(tickers, period="5d", interval="15m")["Close"].ffill().dropna()
    
    df_pesos = pd.DataFrame(index=datos.index)
    df_pesos["RFX"] = datos["^RFX20"]
    df_pesos["GGAL"] = datos["GGAL"] * 10 * 1320  # Estimación base en pesos
    df_pesos["YPF"] = datos["YPF"] * 1 * 1320
    
    # 2. Si el broker está conectado, pisamos el ÚLTIMO valor con el precio real del milisegundo
    if broker_vivo:
        try:
            # Reemplazar por los tickers que uses en Ecovalores (ej: RFX20Ago26, GGAL/AGO26)
            rfx_real = pyrofex.get_market_data(ticker="RFX20Ago26", entries=[pyrofex.MarketDataEntry.LAST])
            ggal_real = pyrofex.get_market_data(ticker="GGALAgo26", entries=[pyrofex.MarketDataEntry.LAST])
            
            if rfx_real and 'marketData' in rfx_real and rfx_real['marketData']['LA']:
                df_pesos["RFX"].iloc[-1] = rfx_real['marketData']['LA']['price']
            if ggal_real and 'marketData' in ggal_real and ggal_real['marketData']['LA']:
                df_pesos["GGAL"].iloc[-1] = ggal_real['marketData']['LA']['price']
        except:
            pass # Si falla el broker en el segundo actual, preserva el dato de Yahoo para que no se rompa la app
            
    return df_pesos.dropna()

df = obtener_datos_limpios()

# --- LÓGICA ESTADÍSTICA ---
df["RFX_MA"] = df["RFX"].rolling(window=20).mean()
df["Trend"] = np.where(df["RFX"] > df["RFX_MA"], 1, -1)

df["Ratio_GGAL"] = df["GGAL"] / df["RFX"]
df["Z_GGAL"] = (df["Ratio_GGAL"] - df["Ratio_GGAL"].rolling(20).mean()) / df["Ratio_GGAL"].rolling(20).std()

df["Ratio_YPF"] = df["YPF"] / df["RFX"]
df["Z_YPF"] = (df["Ratio_YPF"] - df["Ratio_YPF"].rolling(20).mean()) / df["Ratio_YPF"].rolling(20).std()

df["Sig_GGAL"] = np.where((df["Z_GGAL"] < -desvios) & (df["Trend"] == 1), "🟢 COMPRA", np.where((df["Z_GGAL"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"))
df["Sig_YPF"] = np.where((df["Z_YPF"] < -desvios) & (df["Trend"] == 1), "🟢 COMPRA", np.where((df["Z_YPF"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"))

# --- INTERFAZ MÓVIL ---
if broker_vivo:
    st.success("⚡ Conectado a Ecovalores (Tiempo Real Activo)")
else:
    st.warning("⚠️ Usando datos de respaldo (Modo Consulta)")

m1, m2, m3 = st.columns(3)
m1.metric("Índice RFX20", f"{df['RFX'].iloc[-1]:,.0f}")
m2.metric("Galicia (GGAL)", f"${df['GGAL'].iloc[-1]:,.2f}")
m3.metric("YPFD", f"${df['YPF'].iloc[-1]:,.2f}")

st.markdown("---")

tab_ggal, tab_ypf, tab_rfx = st.tabs(["🏦 GGAL", "🛢️ YPF", "📉 Rofex 20"])

with tab_ggal:
    st.subheader(f"Señal Galicia: {df['Sig_GGAL'].iloc[-1]}")
    fig_g = gr.Figure(gr.Scatter(x=df.index, y=df["GGAL"]))
    fig_g.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig_g, use_container_width=True)

with tab_ypf:
    st.subheader(f"Señal YPF: {df['Sig_YPF'].iloc[-1]}")
    fig_y = gr.Figure(gr.Scatter(x=df.index, y=df["YPF"], line=dict(color="orange")))
    fig_y.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig_y, use_container_width=True)

with tab_rfx:
    tendencia_actual = "📈 ALCE MACRO" if df["Trend"].iloc[-1] == 1 else "📉 BAJA MACRO"
    st.info(f"Filtro General: {tendencia_actual}")
    fig_r = gr.Figure(gr.Scatter(x=df.index, y=df["RFX"]))
    fig_r.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig_r, use_container_width=True)
