import streamlit as st
import pandas as pd
import plotly.express as px
import datetime

import binance_utils as bu
from binance_utils import (
    serie_precio_promedio_robusto,
    construir_snapshot,
    construir_componentes,
    calcular_indice_tension,
    generar_diagnostico,
    calcular_hhi,
    interpretar_hhi
)

st.set_page_config(
    page_title="Dashboard Económico",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
div[data-baseweb="tab-list"]{ gap: 20px; }
button[data-baseweb="tab"]{
    font-size: 26px !important;
    font-weight: 700 !important;
    padding: 14px 28px !important;
    height: 60px !important;
    border-radius: 8px 8px 0px 0px;
}
button[data-baseweb="tab"] p{
    font-size: 26px !important;
    font-weight: 700 !important;
}
button[data-baseweb="tab"][aria-selected="true"]{ color: #4FC3F7 !important; }
div[data-baseweb="tab-highlight"]{ height:4px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CARGA DE DATOS OPTIMIZADA
# ==========================================

@st.cache_data(ttl=600)
def cargar_binance():
    df = pd.read_csv("data/detalle_binance3.csv", sep=";", encoding="utf-8")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], dayfirst=True, errors="coerce")
    for col in ["Precio", "Limite_min", "Limite_max", "Disponible"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Timestamp"])

@st.cache_data(ttl=300)
def cargar_hipermaxi():
    df = pd.read_csv("data/hipermaxi_detallado_suc.csv")
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    return df

df_binance = cargar_binance()
df_hiper = cargar_hipermaxi()

# ==========================================
# TÍTULO
# ==========================================

st.title("📊 Observatorio del Mercado Cambiario P2P – Bolivia")
st.markdown("---")

tab1, tab2 = st.tabs([
    "💵 Binance USDT/BOB",
    "🛒 Hipermaxi"
])

# ====================================================
# BINANCE
# ====================================================

with tab1:

    # ======================================
    # FILTRO CON HORAS (SLIDER CONTINUO)
    # ======================================

    ts_min = df_binance["Timestamp"].min().to_pydatetime()
    ts_max = df_binance["Timestamp"].max().to_pydatetime()

    rango = st.slider(
        "Periodo y Horario de Análisis",
        min_value=ts_min,
        max_value=ts_max,
        value=(ts_min, ts_max),
        format="DD/MM/YY HH:mm",
        step=datetime.timedelta(hours=1)
    )

    inicio, fin = rango

    # Filtrado preciso por timestamp completo
    df_b = df_binance[
        (df_binance["Timestamp"] >= inicio) &
        (df_binance["Timestamp"] <= fin)
    ].sort_values("Timestamp").copy()

    # ======================================
    # BASE ANALÍTICA INTRA-DÍA
    # ======================================

    snapshot_df = construir_snapshot(df_b)
    componentes_df = construir_componentes(df_b)
    componentes_df = calcular_indice_tension(componentes_df)
    componentes_df = bu.calcular_contribuciones(componentes_df)
    
    hhi_df = calcular_hhi(df_b)
    
    hhi_buy = hhi_df[hhi_df["Tipo"] == "BUY"].sort_values("Snapshot").iloc[-1]
    hhi_sell = hhi_df[hhi_df["Tipo"] == "SELL"].sort_values("Snapshot").iloc[-1]

    estado_buy = interpretar_hhi(hhi_buy["HHI"])
    estado_sell = interpretar_hhi(hhi_sell["HHI"])
    
    # ======================================
    # ÚLTIMO SNAPSHOT Y COMPARATIVA
    # ======================================
    
    ultimo = componentes_df.iloc[-1]
    anterior = componentes_df.iloc[-2] if len(componentes_df) > 1 else ultimo

    variacion = ultimo["Indice_Tension"] - anterior["Indice_Tension"]
    estado = ultimo["Estado"]

    ultimo_buy_ts = df_b[df_b["Tipo"] == "BUY"]["Timestamp"].max()
    ultimo_sell_ts = df_b[df_b["Tipo"] == "SELL"]["Timestamp"].max()

    buy = df_b[(df_b["Tipo"] == "BUY") & (df_b["Timestamp"] == ultimo_buy_ts)]
    sell = df_b[(df_b["Tipo"] == "SELL") & (df_b["Timestamp"] == ultimo_sell_ts)]

    ultimo_ts = max(ultimo_buy_ts, ultimo_sell_ts)

    st.header("💵 Mercado Binance P2P USDT/BOB")
    
    # ======================================
    # KPIS PRINCIPALES
    # ======================================

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Precio Máximo BUY", f"{buy['Precio'].max():.2f}")
    col2.metric("Precio Mínimo BUY", f"{buy['Precio'].min():.2f}")
    col3.metric("Precio Promedio BUY", f"{buy['Precio'].mean():.2f}")
    col4.metric("Disponible BUY", f"{buy['Disponible'].sum():,.0f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Disponible SELL", f"{sell['Disponible'].sum():,.0f}")
    col6.metric("Vendedores BUY", buy["Vendedor"].nunique())
    col7.metric("Vendedores SELL", sell["Vendedor"].nunique())
    col8.metric("Actualizado", ultimo_ts.strftime("%d/%m %H:%M"))

    st.markdown("---")
    
    # ======================================
    # KPI ÍNDICE DE TENSIÓN 
    # ======================================
    st.markdown("## 📈 Índice de Tensión Cambiaria P2P")
    col1, col2 = st.columns([1, 2])    
    with col1:
        st.metric(
            label="Índice",
            value=f"{ultimo['Indice_Tension']:.1f}",
            delta=f"{variacion:+.1f}"
        )
    with col2:    
        st.info(
            f"""
    **Estado:** {estado}
    
    **Último Snapshot:** {ultimo['Snapshot']:%d/%m/%Y %H:%M}
    """
        )

    # Eventos hitos
    eventos = [
        {"fecha": "2026-06-29", "texto": "🏛 Flexibilización TC"}
    ]
    
    # ======================================
    # GRÁFICO EVOLUCIÓN DEL ÍNDICE
    # ======================================
    fig = px.line(
        componentes_df,
        x="Snapshot",
        y="Indice_Tension",
        title="Evolución del Índice de Tensión Cambiaria P2P",
        markers=True
    )
    
    fig.update_traces(line=dict(width=4), marker=dict(size=5))

    fig.add_hrect(y0=0, y1=20, fillcolor="#00C853", opacity=0.18, line_width=0)
    fig.add_hrect(y0=20, y1=40, fillcolor="limegreen", opacity=0.18, line_width=0)
    fig.add_hrect(y0=40, y1=60, fillcolor="yellow", opacity=0.20, line_width=0)
    fig.add_hrect(y0=60, y1=80, fillcolor="orange", opacity=0.18, line_width=0)
    fig.add_hrect(y0=80, y1=100, fillcolor="#FF5252", opacity=0.18, line_width=0)

    fig.update_layout(
        yaxis=dict(range=[0,100]),
        xaxis_title="Fecha y Hora",
        yaxis_title="Índice",
        hovermode="x unified"
    )
    fig.update_xaxes(tickformat="%d-%b %H:%M")

    st.plotly_chart(fig, use_container_width=True)

    # ======================================
    # DESCOMPOSICIÓN DEL ÍNDICE
    # ======================================
    st.subheader("🔎 Descomposición del Índice de Tensión")
    df_contrib = pd.DataFrame({
        "Componente": ["Spread", "Liquidez", "Volatilidad", "Outliers"],
        "Contribución": [
            ultimo["Contrib_Spread"],
            ultimo["Contrib_Liquidez"],
            ultimo["Contrib_CV"],
            ultimo["Contrib_Outliers"]
        ]
    })

    fig = px.bar(
        df_contrib,
        x="Contribución",
        y="Componente",
        orientation="h",
        text="Contribución",
        title="Descomposición del Índice"
    )

    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Diagnóstico automático
    componente, valor, participacion = generar_diagnostico(componentes_df)
    st.info(
        f"""
    🧠 Diagnóstico
    
    El principal factor que explica la tensión actual es **{componente}**.
    Su contribución asciende a **{valor:.1f} puntos**, equivalente al **{participacion:.1f}%** del Índice de Tensión Cambiaria.
    """
    )

    # ======================================
    # KPI HHI
    # ======================================
    st.subheader("🏛 Concentración del Mercado (Índice Herfindahl-Hirschman)")
    col1, col2 = st.columns(2)
    with col1:    
        st.metric("🏛 HHI BUY", f"{hhi_buy['HHI']:.0f}")
        st.caption(estado_buy)
        st.caption(f"👥 {int(hhi_buy['N_Vendedores'])} vendedores")
    with col2:
        st.metric("🏛 HHI SELL", f"{hhi_sell['HHI']:.0f}")
        st.caption(estado_sell)
        st.caption(f"👥 {int(hhi_sell['N_Vendedores'])} vendedores")

    # ======================================
    # PRECIOS PROMEDIOS Y ROBUSTOS
    # ======================================
    precio_robusto = serie_precio_promedio_robusto(df_b).dropna(subset=["Precio"])

    precio_snapshot = (
        df_b.groupby(["Timestamp", "Tipo"], as_index=False)["Precio"].mean()
    )
    
    fig = px.line(
        precio_snapshot,
        x="Timestamp",
        y="Precio",
        color="Tipo",
        markers=True,
        title="Precio Promedio USDT/BOB"
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=6))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d-%b %H:%M")
    st.plotly_chart(fig, use_container_width=True)

    fig = px.line(
        precio_robusto,
        x="Snapshot",
        y="Precio",
        color="Tipo",
        markers=True,
        title="Precio Promedio Robusto (IQR)"
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=6))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d-%b %H:%M")
    st.plotly_chart(fig, use_container_width=True)

    # ======================================
    # MEJOR PRECIO BID VS ASK
    # ======================================
    precio_buy = df_b[df_b["Tipo"] == "BUY"].groupby("Timestamp", as_index=False)["Precio"].min()
    precio_buy["Tipo"] = "BUY"
    
    precio_sell = df_b[df_b["Tipo"] == "SELL"].groupby("Timestamp", as_index=False)["Precio"].max()
    precio_sell["Tipo"] = "SELL"    
    
    precio_snapshot = pd.concat([precio_buy, precio_sell], ignore_index=True)
    
    fig = px.line(
        precio_snapshot,
        x="Timestamp",
        y="Precio",
        color="Tipo",
        markers=True,
        title="Mejor Precio BUY (Bid) vs SELL (Ask)"
    )    
    fig.update_traces(line=dict(width=3), marker=dict(size=6))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d-%b %H:%M")
    st.plotly_chart(fig, use_container_width=True)
    
    # ======================================
    # DISPONIBILIDAD BUY VS SELL
    # ======================================
    disponibilidad = df_b.groupby(["Timestamp", "Tipo"], as_index=False)["Disponible"].sum()

    fig = px.line(
        disponibilidad,
        x="Timestamp",
        y="Disponible",
        color="Tipo",
        markers=True,
        title="Disponibilidad USDT"
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=6))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%d-%b %H:%M")
    st.plotly_chart(fig, use_container_width=True)
    
    # ======================================
    # HISTOGRAMAS (ÚLTIMO SNAPSHOT - ESCALAS INDEPENDIENTES)
    # ======================================
    col_sell, col_buy = st.columns(2)
    bin_size = 0.50
    
    with col_sell:
        if not sell.empty:
            xmin_s, xmax_s = sell["Precio"].min(), sell["Precio"].max()
            nbins_s = max(int((xmax_s - xmin_s) / bin_size), 5) if xmax_s > xmin_s else 10
            
            fig_sell = px.histogram(
                sell, 
                x="Precio", 
                title="Distribución SELL",
                labels={"Precio": "Precio (BOB)", "count": "Cantidad de vendedores"},
                nbins=nbins_s
            )
            fig_sell.update_traces(xbins=dict(start=xmin_s, end=xmax_s, size=bin_size))
            fig_sell.update_layout(
                yaxis_title="Cantidad de vendedores",
                xaxis_title="Precio (BOB)"
            )
            st.plotly_chart(fig_sell, use_container_width=True)
    
    with col_buy:
        if not buy.empty:
            xmin_b, xmax_b = buy["Precio"].min(), buy["Precio"].max()
            nbins_b = max(int((xmax_b - xmin_b) / bin_size), 5) if xmax_b > xmin_b else 10
            
            fig_buy = px.histogram(
                buy, 
                x="Precio", 
                title="Distribución BUY",
                labels={"Precio": "Precio (BOB)", "count": "Cantidad de vendedores"},
                nbins=nbins_b
            )
            fig_buy.update_traces(xbins=dict(start=xmin_b, end=xmax_b, size=bin_size))
            fig_buy.update_layout(
                yaxis_title="Cantidad de vendedores",
                xaxis_title="Precio (BOB)"
            )
            st.plotly_chart(fig_buy, use_container_width=True)  
            
    # ======================================
    # TOP 10 VENDEDORES (ÚLTIMO SNAPSHOT)
    # ======================================
    col_sell, col_buy = st.columns(2)
    
    with col_sell:
        top_sell = (
            sell.groupby("Vendedor", as_index=False)
            .agg(Disponible=("Disponible", "sum"), Precio=("Precio", "mean"))
            .sort_values(by="Disponible", ascending=False)
            .head(10)
        )
        
        # Formatos limpios
        top_sell["Texto_Barra"] = top_sell["Disponible"].apply(lambda x: f"{x:,.0f}")
        top_sell["Disp_Hover"] = top_sell["Disponible"].apply(lambda x: f"{x:,.2f} USDT")
        top_sell["Precio_Hover"] = top_sell["Precio"].apply(lambda x: f"{x:.2f} Bs/USDT")

        fig = px.bar(
            top_sell,
            y="Vendedor",
            x="Disponible",
            orientation="h",
            text="Texto_Barra",
            title="Top 10 Liquidez SELL",
            custom_data=["Disp_Hover", "Precio_Hover"]
        )
        
        fig.update_traces(
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Disponible: %{customdata[0]}<br>Precio: %{customdata[1]}<extra></extra>"
        )
        fig.update_layout(
            yaxis=dict(autorange="reversed", title=""),
            xaxis_title="USDT Disponibles"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col_buy:
        top_buy = (
            buy.groupby("Vendedor", as_index=False)
            .agg(Disponible=("Disponible", "sum"), Precio=("Precio", "mean"))
            .sort_values(by="Disponible", ascending=False)
            .head(10)
        )

        # Formatos limpios
        top_buy["Texto_Barra"] = top_buy["Disponible"].apply(lambda x: f"{x:,.0f}")
        top_buy["Disp_Hover"] = top_buy["Disponible"].apply(lambda x: f"{x:,.2f} USDT")
        top_buy["Precio_Hover"] = top_buy["Precio"].apply(lambda x: f"{x:.2f} Bs/USDT")

        fig = px.bar(
            top_buy,
            y="Vendedor",
            x="Disponible",
            orientation="h",
            text="Texto_Barra",
            title="Top 10 Liquidez BUY",
            custom_data=["Disp_Hover", "Precio_Hover"]
        )
        
        fig.update_traces(
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Disponible: %{customdata[0]}<br>Precio: %{customdata[1]}<extra></extra>"
        )
        fig.update_layout(
            yaxis=dict(autorange="reversed", title=""),
            xaxis_title="USDT Disponibles"
        )
        st.plotly_chart(fig, use_container_width=True)

    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # ====================================================
    # ANÁLISIS DE CORRELACIÓN Y LIQUIDEZ BUY VS PRECIO
    # ====================================================
    st.markdown("---")
    st.subheader("📊 Análisis de Liquidez (Disponibilidad BUY) vs. Precio Robusto BUY")
    
    # 1. Preparación y alineación de series temporales
    df_buy = df_b[df_b["Tipo"] == "BUY"].copy()
    
    # Disponibilidad total BUY por Snapshot
    disp_buy = (
        df_buy.groupby("Timestamp")["Disponible"]
        .sum()
        .rename("Disponibilidad_BUY")
    )
    
    # Precio Robusto BUY por Snapshot
    p_robusto_buy = (
        precio_robusto[precio_robusto["Tipo"] == "BUY"]
        .set_index("Snapshot")["Precio"]
        .rename("Precio_Robusto_BUY")
    )
    
    # Consolidación de dataset alineado
    df_corr = pd.concat([disp_buy, p_robusto_buy], axis=1).dropna().sort_index()
    
    if len(df_corr) > 12:
        # Coeficiente contemporáneo
        r_corr = df_corr["Disponibilidad_BUY"].corr(df_corr["Precio_Robusto_BUY"])
        
        # ----------------------------------------------------
        # 1. GRÁFICO EVOLUTIVO DUAL (FULL WIDTH)
        # ----------------------------------------------------
        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Serie 1: Disponibilidad BUY (Eje Izquierdo - Celeste Tipo)
        fig_dual.add_trace(
            go.Scatter(
                x=df_corr.index,
                y=df_corr["Disponibilidad_BUY"],
                name="Disponibilidad BUY (USDT)",
                mode="lines+markers",
                line=dict(color="#29B6F6", width=2),
                marker=dict(size=4)
            ),
            secondary_y=False,
        )
        
        # Serie 2: Precio Robusto BUY (Eje Derecho - Verde Azulado Contraste)
        fig_dual.add_trace(
            go.Scatter(
                x=df_corr.index,
                y=df_corr["Precio_Robusto_BUY"],
                name="Precio Robusto BUY (BOB)",
                mode="lines+markers",
                line=dict(color="#00E676", width=2.5),
                marker=dict(size=4)
            ),
            secondary_y=True,
        )
        
        # Cálculo de margen dinámico en eje X para visibilidad en extremos
        dt_min = df_corr.index.min()
        dt_max = df_corr.index.max()
        delta_padding = (dt_max - dt_min) * 0.03  # 3% de padding
        
        fig_dual.update_layout(
            title=f"Evolución Temporal de Liquidez vs. Precio Robusto BUY | Correlación contemporánea r: <b>{r_corr:.3f}</b>",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        fig_dual.update_xaxes(
            title_text="Timestamp",
            tickformat="%d-%b %H:%M",
            range=[dt_min - delta_padding, dt_max + delta_padding]
        )
        fig_dual.update_yaxes(title_text="Disponibilidad BUY (USDT)", secondary_y=False)
        fig_dual.update_yaxes(title_text="Precio Robusto BUY (BOB)", secondary_y=True)
        
        st.plotly_chart(fig_dual, use_container_width=True)
        
        st.markdown("---")
        
        # ----------------------------------------------------
        # 2. GRÁFICO DE CORRELACIONES CRUZADAS (100% PLOTLY)
        # ----------------------------------------------------
        max_lag = 12
        lags = list(range(-max_lag, max_lag + 1))
        cross_corrs = []
        
        s_disp = df_corr["Disponibilidad_BUY"]
        s_prec = df_corr["Precio_Robusto_BUY"]
        
        for lag in lags:
            if lag < 0:
                corr = s_disp.corr(s_prec.shift(-lag))
            elif lag > 0:
                corr = s_disp.shift(lag).corr(s_prec)
            else:
                corr = s_disp.corr(s_prec)
            cross_corrs.append(corr)
        
        df_cc = pd.DataFrame({
            "Rezago": lags,
            "Correlacion": cross_corrs
        })
        
        df_cc["Texto_Barra"] = df_cc["Correlacion"].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        df_cc["Hover_Val"] = df_cc["Correlacion"].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
        
        fig_cc = px.bar(
            df_cc,
            x="Rezago",
            y="Correlacion",
            color="Correlacion",
            color_continuous_scale="RdBu_r",  # Equivalente nativo de Plotly a coolwarm (-1 Rojo, +1 Azul)
            range_color=[-1, 1],
            text="Texto_Barra",
            custom_data=["Hover_Val"],
            title="Correlaciones Cruzadas: Liquidez (BUY) vs. Precio Robusto (BUY) (Rezagos -12 a +12)"
        )
        
        fig_cc.update_traces(
            textposition="outside",
            hovertemplate="<b>Rezago: %{x}</b><br>Correlación: <b>%{customdata[0]}</b><extra></extra>"
        )
        
        fig_cc.update_layout(
            yaxis_title="Coeficiente de Correlación",
            xaxis_title="Rezago (Snapshots)",
            yaxis=dict(range=[-1.15, 1.15]),
            xaxis=dict(dtick=1),
            hovermode="x",
            coloraxis_showscale=False  # Oculta la barra de escala lateral
        )
        
        fig_cc.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
        fig_cc.add_vline(x=0, line_dash="solid", line_color="white", line_width=1)
        
        st.plotly_chart(fig_cc, use_container_width=True)
    
    else:
        st.warning("No hay suficientes snapshots cargados para realizar el análisis de correlaciones cruzadas (mínimo 12 datos).")
    
    # ====================================================
    # CUADRO COMPONENTES (MANTENIDO COMENTADO)
    # ====================================================    
    # st.subheader("Componentes del Índice de Tensión")
    # st.dataframe(
    #     componentes_df.tail(),
    #     use_container_width=True
    # )

# ========================================================================================================
# HIPERMAXI
# ========================================================================================================

with tab2:
    st.header("🛒 Monitoreo de Precios Hipermaxi")

    fecha_min = df_hiper["Fecha"].min().date()
    fecha_max = df_hiper["Fecha"].max().date()

    if fecha_min == fecha_max:
        inicio, fin = fecha_min, fecha_max
        st.info(f"Solo existe información para la fecha {fecha_max}")
    else:
        inicio, fin = st.slider(
            "Periodo",
            min_value=fecha_min,
            max_value=fecha_max,
            value=(fecha_min, fecha_max),
            key="hiper_fecha"
        )

    # Filtrado optimizado para la pestaña
    df_h = df_hiper[
        (df_hiper["Fecha"].dt.date >= inicio) &
        (df_hiper["Fecha"].dt.date <= fin)
    ].copy()

    sucursales = sorted(df_h["Sucursal"].dropna().unique())
    sucursal = st.selectbox("Sucursal", ["Todas"] + list(sucursales))
    if sucursal != "Todas":
        df_h = df_h[df_h["Sucursal"] == sucursal]

    categorias = sorted(df_h["Categoría"].dropna().unique())
    categoria = st.selectbox("Categoría", ["Todas"] + list(categorias))
    if categoria != "Todas":
        df_h = df_h[df_h["Categoría"] == categoria]

    # ====================================================
    # HIPERMAXI: CÁLCULOS Y KPIs
    # ====================================================
    
    # Se asegura el orden de fechas
    df_h = df_h.sort_values(["Sucursal", "Producto", "Fecha"])
    df_h["Variacion_Abs"] = df_h.groupby(["Sucursal", "Producto"])["Precio"].diff()

    fechas_disponibles = sorted(df_h["Fecha"].dt.date.unique())
    
    if len(fechas_disponibles) > 0:
        ultima_fecha = fechas_disponibles[-1]
        
        # ----------------------------------------------------
        # 1. CÁLCULO DE VARIACIONES TEMPORALES (FILA SUPERIOR)
        # ----------------------------------------------------
        # Precio promedio general de la última fecha
        p_actual = df_h[df_h["Fecha"].dt.date == ultima_fecha]["Precio"].mean()
        
        # A) Variación 7 capturas atrás
        idx_7 = max(0, len(fechas_disponibles) - 8)
        fecha_7 = fechas_disponibles[idx_7]
        p_7d = df_h[df_h["Fecha"].dt.date == fecha_7]["Precio"].mean()
        var_7d = ((p_actual - p_7d) / p_7d * 100) if p_7d > 0 else 0.0

        # B) Variación respecto al último dato del mes pasado
        primer_dia_mes_actual = ultima_fecha.replace(day=1)
        fechas_mes_pasado = [f for f in fechas_disponibles if f < primer_dia_mes_actual]
        
        if fechas_mes_pasado:
            fecha_mes_pasado = fechas_mes_pasado[-1]
            p_mes_pasado = df_h[df_h["Fecha"].dt.date == fecha_mes_pasado]["Precio"].mean()
            var_mes_pasado = ((p_actual - p_mes_pasado) / p_mes_pasado * 100) if p_mes_pasado > 0 else 0.0
            label_mes_pasado = f"vs Mes Anterior ({fecha_mes_pasado.strftime('%d/%m')})"
        else:
            var_mes_pasado = 0.0
            label_mes_pasado = "vs Mes Anterior (Sin datos)"

        # C) Variación respecto al primer dato de la serie
        fecha_inicio = fechas_disponibles[0]
        p_inicio = df_h[df_h["Fecha"].dt.date == fecha_inicio]["Precio"].mean()
        var_inicio = ((p_actual - p_inicio) / p_inicio * 100) if p_inicio > 0 else 0.0

        # ----------------------------------------------------
        # DESPLIEGUE FILA 1: VARIACIONES TEMPORALES
        # ----------------------------------------------------
        st.subheader("📈 Variaciones Temporales Promedio")
        c1, c2, c3, c4 = st.columns(4)
        
        c1.metric(
            label="Precio Promedio Actual", 
            value=f"Bs {p_actual:,.2f}",
            delta=f"Última fecha: {ultima_fecha.strftime('%d/%m/%Y')}",
            delta_color="off"
        )
        c2.metric(
            label="Var. 7 Capturas Atrás", 
            value=f"{var_7d:+.2f}%",
            delta=f"Base: {fecha_7.strftime('%d/%m')}"
        )
        c3.metric(
            label=label_mes_pasado, 
            value=f"{var_mes_pasado:+.2f}%",
            delta="Cierre mes anterior"
        )
        c4.metric(
            label=f"Var. vs Inicio ({fecha_inicio.strftime('%d/%m/%Y')})", 
            value=f"{var_inicio:+.2f}%",
            delta="Serie completa"
        )

        st.markdown("---")

        # ----------------------------------------------------
        # 2. CÁLCULO DE METRICAS GENERALES (FILA INFERIOR)
        # ----------------------------------------------------
        df_ult = df_h[df_h["Fecha"].dt.date == ultima_fecha].copy()

        variacion_total = df_ult["Variacion_Abs"].fillna(0).sum()
        variacion_promedio = df_ult["Variación diaria precio"].mean() * 100 if "Variación diaria precio" in df_ult.columns else 0
        productos_suben = (df_ult["Variacion_Abs"] > 0).sum()
        productos_total = df_ult["Producto"].nunique()
        pct_suben = (productos_suben / productos_total * 100) if productos_total > 0 else 0

        # ----------------------------------------------------
        # DESPLIEGUE FILA 2: METRICAS GENERALES DEL DÍA
        # ----------------------------------------------------
        st.subheader("🛒 Métricas de la Última Actualización")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Variación Total Precio", f"Bs {variacion_total:,.2f}")
        col2.metric("Variación Promedio %", f"{variacion_promedio:.2f}%")
        col3.metric("% Productos que Suben", f"{pct_suben:.2f}%")
        col4.metric("Última Actualización", ultima_fecha.strftime("%d/%m/%Y"))

        st.markdown("---")

    precios = df_h.groupby("Fecha")["Precio"].mean().reset_index()
    fig = px.line(precios, x="Fecha", y="Precio", markers=True, title="Precio Promedio")
    st.plotly_chart(fig, use_container_width=True)

    if len(df_h["Fecha"].unique()) > 1:
        fechas_ordenadas = sorted(df_h["Fecha"].unique())
        actual = df_h[df_h["Fecha"] == fechas_ordenadas[-1]][["Producto", "Precio"]].rename(columns={"Precio": "Precio_Actual"})
        anterior = df_h[df_h["Fecha"] == fechas_ordenadas[-2]][["Producto", "Precio"]].rename(columns={"Precio": "Precio_Anterior"})
        
        variaciones = actual.merge(anterior, on="Producto", how="inner")
        variaciones["Variacion_Abs"] = variaciones["Precio_Actual"] - variaciones["Precio_Anterior"]
        
        top_subidas = variaciones.sort_values("Variacion_Abs", ascending=False).head(10)
        top_bajadas = variaciones.sort_values("Variacion_Abs", ascending=True).head(10)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🔺 Top 10 Productos con Variación Positiva")
            st.dataframe(top_subidas[["Producto", "Precio_Anterior", "Precio_Actual", "Variacion_Abs"]], use_container_width=True, hide_index=True)
        with col2:
            st.subheader("🔻 Top 10 Productos con Variación Negativa")
            st.dataframe(top_bajadas[["Producto", "Precio_Anterior", "Precio_Actual", "Variacion_Abs"]], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔍 Evolución Histórica de Producto")
    productos = sorted(df_h["Producto"].dropna().unique())
    producto_sel = st.selectbox("Seleccione un producto", productos) if productos else None

    if producto_sel:
        df_prod = df_h[df_h["Producto"] == producto_sel].sort_values("Fecha")
        if not df_prod.empty:
            precio_actual = df_prod["Precio"].iloc[-1]
            precio_inicial = df_prod["Precio"].iloc[0]
            precio_min = df_prod["Precio"].min()
            precio_max = df_prod["Precio"].max()
            variacion_acum = ((precio_actual / precio_inicial - 1) * 100) if precio_inicial > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Precio Actual", f"Bs {precio_actual:,.2f}")
            c2.metric("Precio Mínimo", f"Bs {precio_min:,.2f}")
            c3.metric("Precio Máximo", f"Bs {precio_max:,.2f}")
            c4.metric("Variación Acumulada", f"{variacion_acum:.2f}%")

            fig = px.line(df_prod, x="Fecha", y="Precio", markers=True, title=f"Evolución de {producto_sel}")
            st.plotly_chart(fig, use_container_width=True)

    categorias_df = df_h.groupby("Categoría")["Producto"].count().reset_index()
    fig = px.pie(categorias_df, names="Categoría", values="Producto", title="Participación por Categoría")
    st.plotly_chart(fig, use_container_width=True)

    if "Variación diaria precio" in df_h.columns:
        heat = df_h.groupby(["Categoría", "Fecha"])["Variación diaria precio"].mean().reset_index()
        heatmap = heat.pivot(index="Categoría", columns="Fecha", values="Variación diaria precio")
        fig = px.imshow(heatmap, aspect="auto", title="Heatmap Variación por Categoría")
        st.plotly_chart(fig, use_container_width=True)