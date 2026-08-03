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
    # HISTOGRAMAS (ÚLTIMO SNAPSHOT)
    # ======================================
    col_sell, col_buy = st.columns(2)
    xmin = min(buy["Precio"].min(), sell["Precio"].min()) if not buy.empty and not sell.empty else 0
    xmax = max(buy["Precio"].max(), sell["Precio"].max()) if not buy.empty and not sell.empty else 10
    bin_size = 0.50
    
    with col_sell:
        fig = px.histogram(sell, x="Precio", title="Distribución SELL", nbins=int((xmax - xmin) / bin_size) if xmax > xmin else 10)
        fig.update_traces(xbins=dict(start=xmin, end=xmax, size=bin_size))
        st.plotly_chart(fig, use_container_width=True)
    
    with col_buy:
        fig = px.histogram(buy, x="Precio", title="Distribución BUY", nbins=int((xmax - xmin) / bin_size) if xmax > xmin else 10)
        fig.update_traces(xbins=dict(start=xmin, end=xmax, size=bin_size))
        st.plotly_chart(fig, use_container_width=True)
    
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

    df_h = df_h.sort_values(["Sucursal", "Producto", "Fecha"])
    df_h["Variacion_Abs"] = df_h.groupby(["Sucursal", "Producto"])["Precio"].diff()

    ultima_fecha = df_h["Fecha"].max()
    df_ult = df_h[df_h["Fecha"] == ultima_fecha].copy()

    variacion_total = df_ult["Variacion_Abs"].fillna(0).sum()
    variacion_promedio = df_ult["Variación diaria precio"].mean() * 100 if "Variación diaria precio" in df_ult.columns else 0
    productos_suben = (df_ult["Variacion_Abs"] > 0).sum()
    productos_total = df_ult["Producto"].nunique()
    pct_suben = (productos_suben / productos_total * 100) if productos_total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Variación Total Precio", f"Bs {variacion_total:,.2f}")
    col2.metric("Variación Promedio %", f"{variacion_promedio:.2f}%")
    col3.metric("% Productos que Suben", f"{pct_suben:.2f}%")
    col4.metric("Última Actualización", ultima_fecha.strftime("%d/%m/%Y") if pd.notnull(ultima_fecha) else "-")

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