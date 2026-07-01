import numpy as np
import pandas as pd
import plotly.graph_objects as gr
import streamlit as st
import pyrofex

# Configuración del Dashboard optimizada para móviles
st.set_page_config(
    page_title="Rofex Directo",
    layout="centered",
    page_icon="📱",
)

st.title("📱 Control Real-Time (Ecovalores)")
st.caption("Conexión directa a Matba-Rofex sin delay")

# --- PARAMETROS DE CONTROL ---
st.sidebar.header("⚙️ Parámetros")
desvios = st.sidebar.slider(
    "Umbral Z-Score (Desvíos)", min_value=1.5, max_value=3.0, value=2.0, step=0.1
)

# --- CONEXIÓN DIRECTA A ECOVALORES ---
@st.cache_resource
def inicializar_conexion_broker():
    try:
        # Extraemos las credenciales ocultas de Streamlit Secrets
        pyrofex.initialize(
            user=st.secrets["ECO_USER"],
            password=st.secrets["ECO_PASSWORD"],
            account=st.secrets["ECO_ACCOUNT"],
            environment=pyrofex.Environment.REMARKET # Cambiar a LIVE cuando Ecovalores te dé el ok de producción
        )
        return True
    except Exception as e:
        st.error(f"Error de autenticación con Ecovalores: {e}")
        return False

conectado = inicializar_conexion_broker()

# --- DESCARGA DE PRECIOS REALES DEL MERCADO LOCAL ---
@st.cache_data(ttl=5) # Actualiza cada 5 segundos al tocar la pantalla del cel
def obtener_datos_ecovalores():
    if not conectado:
        return pd.DataFrame()
        
    # Definimos los contratos correctos de Matba-Rofex
    # NOTA: Debes actualizar el mes del vencimiento según el contrato activo (ej: RFX20Ago26, GGALAgo26)
    contrato_rfx = "RFX20Ago26" 
    contrato_ggal = "GGALAgo26"
    contrato_ypf = "YPFAgo26"
    
    ticker_list = [contrato_rfx, contrato_ggal, contrato_ypf]
    
    df_mercado = pd.DataFrame()
    
    # Traemos el histórico reciente (velas) directo del broker
    for t in ticker_list:
        try:
            # Traemos las últimas barras de 5 minutos
            historico = pyrofex.get_historical_candles(
                market=pyrofex.Market.ROFEX,
                symbol=t,
                date_from="2026-06-20", # Ajustar fecha dinámicamente si es necesario
                date_to="2026-07-02",
                bar_size=pyrofex.BarSize.FIVE_MINUTES
            )
            
            if 'candles' in historico:
                candles_df = pd.DataFrame(historico['candles'])
                # Usamos la fecha como índice
                candles_df['timestamp'] = pd.to_datetime(candles_df['timestamp'])
                candles_df.set_index('timestamp', inplace=True)
                df_mercado[t] = candles_df['close']
        except Exception as e:
            st.warning(f"No se pudo mapear el contrato {t}: {e}")
            
    # Renombramos para compatibilidad con el resto del script viejo
    df_mercado.columns = ["RFX", "GGAL", "YPF"]
    return df_mercado.ffill().dropna()

# Procesamos datos si la conexión está viva
if conectado:
    df = obtener_datos_ecovalores()
    
    if df.empty:
        st.info("Esperando datos de la rueda de Ecovalores... Verificá los nombres de los contratos.")
        st.stop()
        
    # --- LÓGICA ESTADÍSTICA (IDÉNTICA A LA ANTERIOR) ---
    df["RFX_MA"] = df["RFX"].rolling(window=20).mean()
    df["Trend"] = np.where(df["RFX"] > df["RFX_MA"], 1, -1)

    df["Ratio_GGAL"] = df["GGAL"] / df["RFX"]
    df["Z_GGAL"] = (df["Ratio_GGAL"] - df["Ratio_GGAL"].rolling(20).mean()) / df["Ratio_GGAL"].rolling(20).std()

    df["Ratio_YPF"] = df["YPF"] / df["RFX"]
    df["Z_YPF"] = (df["Ratio_YPF"] - df["Ratio_YPF"].rolling(20).mean()) / df["Ratio_YPF"].rolling(20).std()

    df["Sig_GGAL"] = np.where((df["Z_GGAL"] < -desvios) & (df["Trend"] == 1), "🟢 COMPRA", np.where((df["Z_GGAL"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"))
    df["Sig_YPF"] = np.where((df["Z_YPF"] < -desvios) & (df["Trend"] == 1), "🟢 COMPRA", np.where((df["Z_YPF"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"))

    # --- INTERFAZ PARA EL CELULAR ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Índice RFX20", f"{df['RFX'].iloc[-1]:,.0f}")
    m2.metric("Galicia Local", f"${df['GGAL'].iloc[-1]:,.2f}")
    m3.metric("YPF Local", f"${df['YPF'].iloc[-1]:,.2f}")

    st.markdown("---")

    tab_ggal, tab_ypf, tab_rfx = st.tabs(["🏦 GGAL", "🛢️ YPF", "📉 Rofex 20"])

    with tab_ggal:
        st.subheader(f"Señal Galicia: {df['Sig_GGAL'].iloc[-1]}")
        fig_g = gr.Figure(gr.Scatter(x=df.index, y=df["GGAL"]))
        fig_g.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_g, use_container_width=True)
        st.dataframe(df[["GGAL", "Sig_GGAL"]].tail(3), use_container_width=True)

    with tab_ypf:
        st.subheader(f"Señal YPF: {df['Sig_YPF'].iloc[-1]}")
        fig_y = gr.Figure(gr.Scatter(x=df.index, y=df["YPF"], line=dict(color="orange")))
        fig_y.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_y, use_container_width=True)
        st.dataframe(df[["YPF", "Sig_YPF"]].tail(3), use_container_width=True)

    with tab_rfx:
        tendencia_actual = "📈 ALCE MACRO" if df["Trend"].iloc[-1] == 1 else "📉 BAJA MACRO"
        st.info(f"Filtro General: {tendencia_actual}")
        fig_r = gr.Figure(gr.Scatter(x=df.index, y=df["RFX"]))
        fig_r.update_layout(height=230, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_r, use_container_width=True)
