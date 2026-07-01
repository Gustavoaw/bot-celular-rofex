import numpy as np
import pandas as pd
import plotly.graph_objects as gr
import streamlit as st

# Configuración del Dashboard optimizada para móviles
st.set_page_config(
    page_title="Rofex Móvil",
    layout="centered",  # Forzamos diseño centrado ideal para pantallas angostas
    page_icon="📱",
)

st.title("📱 Control Multiactivo Rofex")
st.caption("Estrategia Estadística - Objetivo USD 10.000")

# --- MENÚ DESPLEGABLE EN MÓVILES (SIDEBAR) ---
st.sidebar.header("⚙️ Parámetros")
desvios = st.sidebar.slider(
    "Umbral Z-Score (Desvíos)", min_value=1.5, max_value=3.0, value=2.0, step=0.1
)


# --- GENERADOR DE DATOS SIMULADOS (MERCADO ARGENTINO REALISTA) ---
@st.cache_data
def obtener_datos_mercado():
    fechas = pd.date_range(start="2026-06-15 11:00", periods=80, freq="15min")
    fechas = fechas[(fechas.hour >= 11) & (fechas.hour <= 17)]

    np.random.seed(101)
    # Simulación con las correlaciones típicas de la plaza local
    base_rfx = 250000 + np.cumsum(np.random.normal(20, 250, len(fechas)))
    base_ggal = base_rfx * 0.022 + np.random.normal(0, 40, len(fechas))
    base_ypf = base_rfx * 0.12 + np.random.normal(0, 120, len(fechas))

    return pd.DataFrame(
        {"RFX": base_rfx, "GGAL": base_ggal, "YPF": base_ypf}, index=fechas
    )


df = obtener_datos_mercado()

# --- LÓGICA ESTADÍSTICA CRUZADA ---
df["RFX_MA"] = df["RFX"].rolling(window=20).mean()
df["Trend"] = np.where(df["RFX"] > df["RFX_MA"], 1, -1)

# Ratios contra el índice para buscar arbitraje
df["Ratio_GGAL"] = df["GGAL"] / df["RFX"]
df["Z_GGAL"] = (
    df["Ratio_GGAL"] - df["Ratio_GGAL"].rolling(20).mean()
) / df["Ratio_GGAL"].rolling(20).std()

df["Ratio_YPF"] = df["YPF"] / df["RFX"]
df["Z_YPF"] = (
    df["Ratio_YPF"] - df["Ratio_YPF"].rolling(20).mean()
) / df["Ratio_YPF"].rolling(20).std()

# Gatillos de Señales
df["Sig_GGAL"] = np.where(
    (df["Z_GGAL"] < -desvios) & (df["Trend"] == 1),
    "🟢 COMPRA",
    np.where((df["Z_GGAL"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"),
)
df["Sig_YPF"] = np.where(
    (df["Z_YPF"] < -desvios) & (df["Trend"] == 1),
    "🟢 COMPRA",
    np.where((df["Z_YPF"] > desvios) & (df["Trend"] == -1), "🔴 VENTA", "⚪ Espera"),
)


# --- DISEÑO DE PANTALLA DE INICIO (MÉTRICAS RÁPIDAS) ---
# En el celular se verán una abajo de la otra de forma compacta
m1, m2, m3 = st.columns(3)
m1.metric("Índice RFX20", f"{df['RFX'].iloc[-1]:,.0f}")
m2.metric("Galicia (GGAL)", f"${df['GGAL'].iloc[-1]:,.2f}")
m3.metric("YPFD", f"${df['YPF'].iloc[-1]:,.2f}")

st.markdown("---")

# --- PESTAÑAS RESPONSIVAS (TABS PARA EVITAR SCROLL) ---
tab_ggal, tab_ypf, tab_rfx = st.tabs(["🏦 GGAL", "🛢️ YPF", "📉 Rofex 20"])

with tab_ggal:
    estado_ggal = df["Sig_GGAL"].iloc[-1]
    st.subheader(f"Señal Actual: {estado_ggal}")

    # Gráfico adaptado para el ancho del celular
    fig_g = gr.Figure()
    fig_g.add_trace(gr.Scatter(x=df.index, y=df["GGAL"], name="Precio GGAL"))
    fig_g.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_g, use_container_width=True)

    st.write("**Historial Operativo Corto (GGAL):**")
    st.dataframe(df[["GGAL", "Sig_GGAL"]].tail(5), use_container_width=True)

with tab_ypf:
    estado_ypf = df["Sig_YPF"].iloc[-1]
    st.subheader(f"Señal Actual: {estado_ypf}")

    fig_y = gr.Figure()
    fig_y.add_trace(
        gr.Scatter(x=df.index, y=df["YPF"], name="Precio YPF", line=dict(color="orange"))
    )
    fig_y.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_y, use_container_width=True)

    st.write("**Historial Operativo Corto (YPF):**")
    st.dataframe(df[["YPF", "Sig_YPF"]].tail(5), use_container_width=True)

with tab_rfx:
    st.subheader("Filtro de Tendencia Madre")
    tendencia_actual = "📈 ALCE MACRO" if df["Trend"].iloc[-1] == 1 else "📉 BAJA MACRO"
    st.info(f"El mercado se encuentra en: {tendencia_actual}")

    fig_r = gr.Figure()
    fig_r.add_trace(gr.Scatter(x=df.index, y=df["RFX"], name="RFX20"))
    fig_r.add_trace(
        gr.Scatter(
            x=df.index,
            y=df["RFX_MA"],
            name="Media 20",
            line=dict(dash="dot", color="red"),
        )
    )
    fig_r.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig_r, use_container_width=True)
