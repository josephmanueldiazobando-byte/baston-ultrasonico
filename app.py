"""
================================================================================
BASTON ULTRASONICO INTELIGENTE - DASHBOARD DE PRUEBAS Y MONITOREO
PROGRAMA SENATIC 2026 - IEM ARTEMIO MENDOZA
Sensores:   2 HC-SR04 (frontal e inferior), nivel de bateria, boton SOS
Actuadores: 2 motores vibradores y zumbador
Flujo:      Wokwi (ESP32) -> ThingSpeak -> GitHub -> Streamlit
================================================================================
"""

import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# ============================================================================
# 1. CONFIGURACION DE LA PAGINA
# ============================================================================
st.set_page_config(
    page_title="Bastón Ultrasónico",
    page_icon="🦯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 2. CREDENCIALES THINGSPEAK (Settings -> Secrets en Streamlit)
# ============================================================================
try:
    API_KEY = st.secrets["THINGSPEAK_READ_KEY"]
    CHANNEL_ID = st.secrets["THINGSPEAK_CHANNEL_ID"]
except Exception:
    API_KEY = ""            # canal publico: puede quedar vacio
    CHANNEL_ID = "1234567"  # reemplazar por el Channel ID real

CAMPOS = {
    "field1": "Frontal",
    "field2": "Inferior",
    "field3": "Nivel",
    "field4": "Vibracion",
    "field5": "Bateria",
    "field6": "Respuesta",
    "field7": "Obstaculos",
    "field8": "SOS",
}
NUMERICAS = list(CAMPOS.values())
NIVELES = {0: "Libre", 1: "Lejos", 2: "Medio", 3: "Cerca"}

PAG_INICIO = "🏠 Inicio"
PAG_GRAFICAS = "📈 Distancias"
PAG_PRUEBAS = "⏱️ Pruebas de desempeño"
PAG_BATERIA = "🔋 Batería y autonomía"
PAG_ALARMAS = "🔔 Alarmas y SOS"
PAG_DESCARGAS = "📥 Descargas"


# ============================================================================
# 3. FUNCIONES AUXILIARES
# ============================================================================
@st.cache_data(ttl=20)
def obtener_datos(num_puntos=100):
    """Descarga las ultimas lecturas del canal de ThingSpeak."""
    url = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json"
    params = {"results": num_puntos}
    if API_KEY:
        params["api_key"] = API_KEY
    try:
        respuesta = requests.get(url, params=params, timeout=10)
        respuesta.raise_for_status()
        feeds = respuesta.json().get("feeds", [])
    except Exception as e:
        st.error(f"No se pudo conectar con ThingSpeak: {e}")
        return None

    if not feeds:
        return pd.DataFrame()

    df = pd.DataFrame(feeds).rename(columns=CAMPOS)
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_convert("America/Bogota")
    for col in NUMERICAS:
        if col not in df:
            df[col] = None
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Frontal", "Inferior"]).reset_index(drop=True)


def crear_gauge(valor, minimo, maximo, titulo, unidad, zonas):
    """Indicador semicircular con zonas de color."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valor,
        title={"text": titulo, "font": {"size": 18}},
        number={"suffix": unidad, "font": {"size": 40}},
        gauge={
            "axis": {"range": [minimo, maximo], "tickwidth": 1},
            "bar": {"color": "#1e3a5f", "thickness": 0.7},
            "steps": zonas,
        },
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=60, b=20))
    return fig


def texto_nivel(valor):
    return NIVELES.get(int(valor), "Sin dato") if pd.notna(valor) else "Sin dato"


def estimar_autonomia(df):
    """Horas restantes segun el ritmo de descarga observado."""
    datos = df.dropna(subset=["Bateria"])
    if len(datos) < 2:
        return None, None
    horas = (datos["created_at"].iloc[-1] - datos["created_at"].iloc[0]).total_seconds() / 3600
    caida = datos["Bateria"].iloc[0] - datos["Bateria"].iloc[-1]
    if horas <= 0 or caida <= 0:
        return 0.0, None
    ritmo = caida / horas
    return ritmo, datos["Bateria"].iloc[-1] / ritmo


def verificar_alarmas(df, ultima):
    alertas = []
    if (df["SOS"] == 1).any():
        momento = df.loc[df["SOS"] == 1, "created_at"].iloc[-1].strftime("%Y-%m-%d %H:%M")
        alertas.append(("CRITICA", f"Botón SOS pulsado ({momento})"))
    b = ultima["Bateria"]
    if pd.notna(b) and b < 10:
        alertas.append(("CRITICA", f"Batería casi agotada: {b:.0f} %"))
    elif pd.notna(b) and b < 20:
        alertas.append(("MEDIA", f"Batería baja: {b:.0f} %"))
    r = ultima["Respuesta"]
    if pd.notna(r) and r > 100:
        alertas.append(("MEDIA", f"Tiempo de respuesta lento: {r:.0f} ms"))
    if ultima["Nivel"] == 3:
        alertas.append(("INFO", "En la última lectura había un obstáculo a menos de 50 cm"))
    return alertas


# ============================================================================
# 4. SIDEBAR - NAVEGACION
# ============================================================================
with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center; padding:16px 0;'>
            <div style='font-size:40px;'>🦯</div>
            <div style='font-weight:bold; font-size:18px;'>Bastón Ultrasónico</div>
            <div style='font-size:12px; color:gray;'>Un paso seguro, una vida más independiente</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    pagina = st.radio(
        "Navegación",
        [PAG_INICIO, PAG_GRAFICAS, PAG_PRUEBAS, PAG_BATERIA, PAG_ALARMAS, PAG_DESCARGAS],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.subheader("⚙️ Configuración")
    num_puntos = st.slider("Lecturas a mostrar", 10, 500, 100, 10)
    auto_refresh = st.checkbox("⚡ Actualizar cada 20 s", value=False)
    if st.button("🔄 Actualizar ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================================================
# 5. CARGAR DATOS
# ============================================================================
df = obtener_datos(num_puntos)

if df is None or df.empty:
    st.error("❌ No hay datos. Verifique el Channel ID, la Read API Key y que Wokwi esté enviando.")
    st.stop()

ultima = df.iloc[-1]
anterior = df.iloc[-2] if len(df) > 1 else ultima

# ============================================================================
# 6. PAGINA: INICIO
# ============================================================================
if pagina == PAG_INICIO:
    st.markdown("# 🦯 Bastón ultrasónico inteligente")
    st.markdown("Registro de uso del bastón: distancias detectadas, alertas por vibración y batería.")
    st.caption(f"Última lectura: {ultima['created_at'].strftime('%Y-%m-%d %H:%M:%S')} (hora Colombia)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Obstáculo frontal (cm)", f"{ultima['Frontal']:.0f}",
              f"{ultima['Frontal'] - anterior['Frontal']:+.0f}")
    c2.metric("Sensor inferior (cm)", f"{ultima['Inferior']:.0f}",
              f"{ultima['Inferior'] - anterior['Inferior']:+.0f}")
    c3.metric("Nivel de alerta", texto_nivel(ultima["Nivel"]))
    c4.metric("Vibración (%)", f"{ultima['Vibracion']:.0f}")

    c5, c6, c7 = st.columns(3)
    c5.metric("Batería (%)", f"{ultima['Bateria']:.0f}", f"{ultima['Bateria'] - anterior['Bateria']:+.0f}")
    c6.metric("Tiempo de respuesta (ms)", f"{ultima['Respuesta']:.0f}")
    c7.metric("Obstáculos detectados", f"{ultima['Obstaculos']:.0f}")

    st.markdown("---")
    criticas = [a for a in verificar_alarmas(df, ultima) if a[0] == "CRITICA"]
    if criticas:
        for _, msg in criticas:
            st.error(f"🚨 {msg}")
    else:
        st.success("✅ Bastón funcionando, sin alertas críticas")

# ============================================================================
# 7. PAGINA: DISTANCIAS
# ============================================================================
elif pagina == PAG_GRAFICAS:
    st.markdown("# 📈 Distancias medidas")
    st.markdown("Las franjas de color marcan los niveles de alerta del sensor frontal.")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        subplot_titles=("Sensor frontal (cm)", "Sensor inferior (cm)"))
    for y0, y1, color in [(0, 50, "rgba(220,38,38,0.12)"), (50, 100, "rgba(234,88,12,0.10)"),
                          (100, 150, "rgba(202,138,4,0.08)")]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0, row=1, col=1)
    fig.add_trace(go.Scatter(x=df["created_at"], y=df["Frontal"], name="Frontal",
                             line=dict(color="#1e3a5f", width=2)), row=1, col=1)
    fig.add_hrect(y0=0, y1=40, fillcolor="rgba(220,38,38,0.12)", line_width=0, row=2, col=1)
    fig.add_hrect(y0=120, y1=400, fillcolor="rgba(220,38,38,0.12)", line_width=0, row=2, col=1)
    fig.add_trace(go.Scatter(x=df["created_at"], y=df["Inferior"], name="Inferior",
                             line=dict(color="#0f766e", width=2)), row=2, col=1)
    fig.update_yaxes(range=[0, 400])
    fig.update_layout(height=650, showlegend=False, template="plotly_white", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Sensor inferior: menos de 40 cm es un obstáculo a la altura del pie; "
               "más de 120 cm indica un escalón o hueco hacia abajo.")

# ============================================================================
# 8. PAGINA: PRUEBAS DE DESEMPENO
# ============================================================================
elif pagina == PAG_PRUEBAS:
    st.markdown("# ⏱️ Pruebas de desempeño")
    st.markdown("Datos para la evaluación del objetivo: tiempo de respuesta y comportamiento de las alertas.")

    resp = df["Respuesta"].dropna()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Respuesta promedio (ms)", f"{resp.mean():.1f}" if len(resp) else "—")
    c2.metric("Respuesta máxima (ms)", f"{resp.max():.0f}" if len(resp) else "—")
    c3.metric("Lecturas analizadas", f"{len(df)}")
    c4.metric("Obstáculos en el periodo",
              f"{df['Obstaculos'].max() - df['Obstaculos'].min():.0f}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Tiempo de respuesta")
        fig_r = go.Figure(go.Histogram(x=resp, nbinsx=20, marker_color="#1e3a5f"))
        fig_r.add_vline(x=100, line_dash="dash", line_color="#dc2626",
                        annotation_text="Meta: ≤ 100 ms")
        fig_r.update_layout(height=340, template="plotly_white",
                            xaxis_title="ms", yaxis_title="Lecturas")
        st.plotly_chart(fig_r, use_container_width=True)
    with col2:
        st.markdown("#### Lecturas por nivel de alerta")
        conteo = df["Nivel"].map(texto_nivel).value_counts().reindex(list(NIVELES.values()), fill_value=0)
        fig_n = go.Figure(go.Bar(x=conteo.index, y=conteo.values,
                                 marker_color=["#16a34a", "#ca8a04", "#ea580c", "#dc2626"]))
        fig_n.update_layout(height=340, template="plotly_white", yaxis_title="Lecturas")
        st.plotly_chart(fig_n, use_container_width=True)

    st.info("Para la bitácora: anote en cada prueba con voluntarios la fecha, el recorrido, "
            "los obstáculos reales y compare con estos registros.")

# ============================================================================
# 9. PAGINA: BATERIA Y AUTONOMIA
# ============================================================================
elif pagina == PAG_BATERIA:
    st.markdown("# 🔋 Batería y autonomía")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.plotly_chart(crear_gauge(
            ultima["Bateria"], 0, 100, "Batería", " %",
            [{"range": [0, 20], "color": "#fecaca"},
             {"range": [20, 50], "color": "#fef3c7"},
             {"range": [50, 100], "color": "#bbf7d0"}],
        ), use_container_width=True)
        ritmo, horas = estimar_autonomia(df)
        if ritmo is None:
            st.info("Se necesitan más lecturas para estimar la autonomía.")
        elif horas is None:
            st.info("La batería no ha bajado en este periodo.")
        else:
            st.metric("Ritmo de descarga", f"{ritmo:.1f} %/hora")
            st.metric("Autonomía estimada", f"{horas:.1f} horas")
    with col2:
        fig_b = go.Figure(go.Scatter(x=df["created_at"], y=df["Bateria"], fill="tozeroy",
                                     line=dict(color="#16a34a", width=2)))
        fig_b.add_hline(y=20, line_dash="dash", line_color="#dc2626",
                        annotation_text="Batería baja (20 %)")
        fig_b.update_layout(height=360, template="plotly_white", yaxis=dict(range=[0, 100], title="%"))
        st.plotly_chart(fig_b, use_container_width=True)

# ============================================================================
# 10. PAGINA: ALARMAS Y SOS
# ============================================================================
elif pagina == PAG_ALARMAS:
    st.markdown("# 🔔 Alarmas y SOS")
    alertas = verificar_alarmas(df, ultima)
    if alertas:
        for tipo, mensaje in alertas:
            if tipo == "CRITICA":
                st.error(f"🚨 {mensaje}")
            elif tipo == "MEDIA":
                st.warning(f"⚠️ {mensaje}")
            else:
                st.info(f"ℹ️ {mensaje}")
    else:
        st.success("✅ No hay alarmas activas.")

    st.markdown("### Historial de SOS")
    sos = df[df["SOS"] == 1][["created_at", "Frontal", "Bateria"]].copy()
    if sos.empty:
        st.info("No se ha pulsado el botón SOS en este periodo.")
    else:
        sos["created_at"] = sos["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
        sos.columns = ["Fecha y hora", "Distancia frontal (cm)", "Batería (%)"]
        st.dataframe(sos.iloc[::-1], use_container_width=True, hide_index=True)

# ============================================================================
# 11. PAGINA: DESCARGAS
# ============================================================================
elif pagina == PAG_DESCARGAS:
    st.markdown("# 📥 Descarga de datos")

    df_export = df[["created_at"] + NUMERICAS].copy()
    df_export["created_at"] = df_export["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_export["Nivel"] = df_export["Nivel"].map(texto_nivel)
    df_export = df_export.rename(columns={"created_at": "Fecha_Hora"})
    hoy = datetime.now().strftime("%Y%m%d")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("📄 CSV", df_export.to_csv(index=False).encode("utf-8"),
                           f"baston_{hoy}.csv", "text/csv", use_container_width=True)
    with c2:
        st.download_button("📋 JSON", df_export.to_json(orient="records").encode("utf-8"),
                           f"baston_{hoy}.json", "application/json", use_container_width=True)
    with c3:
        st.markdown(f"**{len(df_export)} registros** disponibles")

    st.markdown("### 📋 Vista previa")
    st.dataframe(df_export.sort_values("Fecha_Hora", ascending=False),
                 use_container_width=True, hide_index=True)

# ============================================================================
# 12. PIE DE PAGINA
# ============================================================================
st.markdown("---")
st.markdown(
    """
    <div style='text-align:center; color:gray; font-size:12px;'>
        <p>🦯 Bastón Ultrasónico · PROGRAMA SENATIC 2026 - IEM ARTEMIO MENDOZA</p>
        <p>ESP32 + 2 HC-SR04 + Motores vibradores → ThingSpeak → GitHub → Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# 13. ACTUALIZACION AUTOMATICA
# ============================================================================
if auto_refresh:
    time.sleep(20)
    st.cache_data.clear()
    st.rerun()
