import numpy as np
import pandas as pd

# ==========================================
# 1. TRATAMIENTO DE OUTLIERS
# ==========================================
def eliminar_outliers_iqr(df, columna="Precio"):
    """Elimina outliers utilizando el criterio del Rango Intercuartílico (IQR)."""
    if df.empty or len(df) < 4:
        return df.copy()
    
    q1 = df[columna].quantile(0.25)
    q3 = df[columna].quantile(0.75)
    iqr = q3 - q1

    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    return df[
        (df[columna] >= limite_inferior) &
        (df[columna] <= limite_superior)
    ].copy()

# ==========================================
# 2. ASIGNACIÓN DINÁMICA DE SNAPSHOTS
# ==========================================
def asignar_snapshot_dinamico(df, frecuencia="15min"):
    """
    Agrupa los timestamps continuos redondeando al intervalo mas cercano
    para solucionar la diferencia de segundos entre descargas BUY y SELL.
    """
    df = df.copy()
    df["Snapshot"] = df["Timestamp"].dt.round(frecuencia)
    return df

# ==========================================
# 3. PRECIO PROMEDIO ROBUSTO
# ==========================================
def serie_precio_promedio_robusto(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for (snapshot, tipo), grupo in df.groupby(["Snapshot", "Tipo"]):
        limpio = eliminar_outliers_iqr(grupo)
        if not limpio.empty:
            resultados.append({
                "Snapshot": snapshot,
                "Tipo": tipo,
                "Precio": round(limpio["Precio"].mean(), 4),
                "N_original": len(grupo),
                "N_utilizado": len(limpio)
            })

    return pd.DataFrame(resultados)

# ==========================================
# 4. CONSTRUCCIÓN DE SNAPSHOT ANALÍTICO
# ==========================================
def construir_snapshot(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for (snapshot, tipo), grupo in df.groupby(["Snapshot", "Tipo"]):
        limpio = eliminar_outliers_iqr(grupo)
        if not limpio.empty:
            resultados.append({
                "Snapshot": snapshot,
                "Tipo": tipo,
                "Precio": limpio["Precio"].mean(),
                "Disponible": limpio["Disponible"].sum()
            })

    if not resultados:
        return pd.DataFrame()

    snapshot_df = pd.DataFrame(resultados)
    snapshot_df = snapshot_df.pivot(
        index="Snapshot",
        columns="Tipo",
        values=["Precio", "Disponible"]
    )
    snapshot_df.columns = [f"{col[0]}_{col[1]}" for col in snapshot_df.columns]
    return snapshot_df.reset_index()

# ==========================================
# 5. COMPONENTES E ÍNDICE DE TENSIÓN
# ==========================================
def calcular_spread(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for snapshot, grupo_snapshot in df.groupby("Snapshot"):
        fila = {"Snapshot": snapshot}
        for tipo in ["BUY", "SELL"]:
            grupo = grupo_snapshot[grupo_snapshot["Tipo"] == tipo]
            if grupo.empty:
                fila[f"Precio_{tipo}"] = np.nan
            else:
                limpio = eliminar_outliers_iqr(grupo)
                fila[f"Precio_{tipo}"] = limpio["Precio"].mean()
        resultados.append(fila)

    spread = pd.DataFrame(resultados)
    if "Precio_BUY" in spread.columns and "Precio_SELL" in spread.columns:
        spread["Spread"] = (
            (spread["Precio_BUY"] - spread["Precio_SELL"])
            / spread["Precio_SELL"] * 100
        )
    else:
        spread["Spread"] = np.nan
    return spread.sort_values("Snapshot").reset_index(drop=True)

def calcular_liquidez(df, ventana=60):
    df = asignar_snapshot_dinamico(df)
    liquidez = (
        df.groupby("Snapshot", as_index=False)["Disponible"]
        .sum()
        .sort_values("Snapshot")
        .rename(columns={"Disponible": "Liquidez"})
    )

    liquidez["Liquidez_Base"] = liquidez["Liquidez"].rolling(window=ventana, min_periods=1).mean()
    liquidez["Liquidez_Relativa"] = liquidez["Liquidez"] / liquidez["Liquidez_Base"]
    return liquidez

def calcular_cv(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for snapshot, grupo_snapshot in df.groupby("Snapshot"):
        fila = {"Snapshot": snapshot}
        cvs = []
        for tipo in ["BUY", "SELL"]:
            grupo = grupo_snapshot[grupo_snapshot["Tipo"] == tipo]
            if grupo.empty:
                fila[f"CV_{tipo}"] = np.nan
                continue
            limpio = eliminar_outliers_iqr(grupo)
            media = limpio["Precio"].mean()
            cv = (limpio["Precio"].std() / media * 100) if media and not np.isnan(media) else np.nan
            fila[f"CV_{tipo}"] = cv
            cvs.append(cv)
        fila["CV_TOTAL"] = np.nanmean(cvs) if cvs else np.nan
        resultados.append(fila)

    return pd.DataFrame(resultados).sort_values("Snapshot").reset_index(drop=True)

def calcular_outliers(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for snapshot, grupo_snapshot in df.groupby("Snapshot"):
        fila = {"Snapshot": snapshot}
        tasas = []
        for tipo in ["BUY", "SELL"]:
            grupo = grupo_snapshot[grupo_snapshot["Tipo"] == tipo]
            if grupo.empty:
                fila[f"Outliers_{tipo}"] = np.nan
                continue
            n_original = len(grupo)
            limpio = eliminar_outliers_iqr(grupo)
            tasa = ((n_original - len(limpio)) / n_original * 100) if n_original > 0 else 0
            fila[f"Outliers_{tipo}"] = tasa
            tasas.append(tasa)
        fila["Outliers_TOTAL"] = np.nanmean(tasas) if tasas else np.nan
        resultados.append(fila)

    return pd.DataFrame(resultados).sort_values("Snapshot").reset_index(drop=True)

def normalizar_percentil(serie):
    if serie.dropna().empty:
        return serie
    return serie.rank(method="average", pct=True) * 100

def construir_componentes(df):
    spread = calcular_spread(df)
    liquidez = calcular_liquidez(df)
    cv = calcular_cv(df)
    outliers = calcular_outliers(df)

    componentes = spread.merge(liquidez[["Snapshot", "Liquidez", "Liquidez_Base", "Liquidez_Relativa"]], on="Snapshot", how="left")
    componentes = componentes.merge(cv, on="Snapshot", how="left")
    componentes = componentes.merge(outliers, on="Snapshot", how="left")

    componentes["Score_Spread"] = normalizar_percentil(componentes["Spread"])
    componentes["Score_Liquidez"] = 100 - normalizar_percentil(componentes["Liquidez_Relativa"])
    componentes["Score_CV"] = normalizar_percentil(componentes["CV_TOTAL"])
    componentes["Score_Outliers"] = normalizar_percentil(componentes["Outliers_TOTAL"])

    return componentes.sort_values("Snapshot").reset_index(drop=True)

def calcular_indice_tension(componentes):
    componentes = componentes.copy()
    componentes["Indice_Tension"] = (
        componentes["Score_Spread"].fillna(0) * 0.40 +
        componentes["Score_Liquidez"].fillna(0) * 0.25 +
        componentes["Score_CV"].fillna(0) * 0.20 +
        componentes["Score_Outliers"].fillna(0) * 0.15
    )

    componentes["Estado"] = pd.cut(
        componentes["Indice_Tension"],
        bins=[0, 20, 40, 60, 80, 100],
        labels=["Muy Baja", "Baja", "Moderada", "Alta", "Extrema"],
        include_lowest=True
    )
    return componentes

def calcular_contribuciones(componentes):
    componentes = componentes.copy()
    componentes["Contrib_Spread"] = componentes["Score_Spread"].fillna(0) * 0.40
    componentes["Contrib_Liquidez"] = componentes["Score_Liquidez"].fillna(0) * 0.25
    componentes["Contrib_CV"] = componentes["Score_CV"].fillna(0) * 0.20
    componentes["Contrib_Outliers"] = componentes["Score_Outliers"].fillna(0) * 0.15
    return componentes

def generar_diagnostico(componentes):
    if componentes.empty:
        return "N/A", 0.0, 0.0
    ultimo = componentes.iloc[-1]
    contribuciones = {
        "Spread": ultimo.get("Contrib_Spread", 0),
        "Liquidez": ultimo.get("Contrib_Liquidez", 0),
        "Volatilidad": ultimo.get("Contrib_CV", 0),
        "Outliers": ultimo.get("Contrib_Outliers", 0)
    }

    componente = max(contribuciones, key=contribuciones.get)
    valor = contribuciones[componente]
    total = ultimo.get("Indice_Tension", 1)
    participacion = (valor / total * 100) if total > 0 else 0

    return componente, valor, participacion

# ==========================================
# 6. CONCENTRACIÓN DE MERCADO (HHI)
# ==========================================
def calcular_hhi(df):
    df = asignar_snapshot_dinamico(df)
    resultados = []

    for (snapshot, tipo), grupo in df.groupby(["Snapshot", "Tipo"]):
        vendedores = grupo.groupby("Vendedor")["Disponible"].sum().reset_index()
        n_vendedores = len(vendedores)
        total = vendedores["Disponible"].sum()

        if total == 0:
            hhi = np.nan
        else:
            vendedores["Participacion"] = (vendedores["Disponible"] / total) * 100
            hhi = (vendedores["Participacion"] ** 2).sum()

        resultados.append({
            "Snapshot": snapshot,
            "Tipo": tipo,
            "HHI": hhi,
            "N_Vendedores": n_vendedores
        })

    return pd.DataFrame(resultados)

def interpretar_hhi(hhi):
    if pd.isna(hhi):
        return "Sin información"
    if hhi < 1500:
        return "🟢 Mercado competitivo"
    elif hhi < 2500:
        return "🟡 Concentración moderada"
    else:
        return "🔴 Alta concentración"

def generar_resumen_ejecutivo(componentes, hhi_df):
    if componentes.empty or hhi_df.empty:
        return "Datos insuficientes para generar resumen."
    
    ultimo = componentes.iloc[-1]
    hhi_buy = hhi_df[hhi_df["Tipo"] == "BUY"].sort_values("Snapshot").iloc[-1]
    hhi_sell = hhi_df[hhi_df["Tipo"] == "SELL"].sort_values("Snapshot").iloc[-1]

    contribuciones = {
        "Spread": ultimo.get("Contrib_Spread", 0),
        "Liquidez": ultimo.get("Contrib_Liquidez", 0),
        "Volatilidad": ultimo.get("Contrib_CV", 0),
        "Outliers": ultimo.get("Contrib_Outliers", 0)
    }

    principal = max(contribuciones, key=contribuciones.get)
    total = ultimo.get("Indice_Tension", 1)
    participacion = (contribuciones[principal] / total * 100) if total > 0 else 0

    return f"""
**Índice de Tensión:** {ultimo['Indice_Tension']:.1f}

El principal impulsor de la tensión es **{principal}**, con una contribución de **{participacion:.1f}%**.

• HHI BUY: {hhi_buy['HHI']:.0f} ({interpretar_hhi(hhi_buy['HHI'])})
• HHI SELL: {hhi_sell['HHI']:.0f} ({interpretar_hhi(hhi_sell['HHI'])})
"""