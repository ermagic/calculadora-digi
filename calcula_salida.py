# app.py
import streamlit as st
import pandas as pd
import googlemaps
import datetime as dt
import math
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Calculadora y Notificaciones DIGI", page_icon="🚗", layout="centered")

# --- INICIALIZACIÓN DE ESTADO ---
if 'page' not in st.session_state: st.session_state.page = 'calculator'
if 'calculation_results' not in st.session_state: st.session_state.calculation_results = {}
if 'gmaps_results' not in st.session_state: st.session_state.gmaps_results = None

# --- SISTEMA DE LOGIN ---
def check_login():
    if st.session_state.get('authentication_status'): return True
    st.header("Inicio de Sesión")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        try:
            correct_users = st.secrets["credentials"]["usernames"]
            for user_info in correct_users:
                if user_info["username"] == username and user_info["password"] == password:
                    st.session_state['authentication_status'] = True
                    st.session_state['username'] = username
                    st.rerun()
            st.session_state['authentication_status'] = False
            st.error("😕 Usuario o contraseña incorrectos.")
        except Exception as e:
            st.error(f"Error en la configuración de credenciales: {e}")
    return False

# --- LÓGICA DE CÁLCULO ---
@st.cache_data
def cargar_datos_csv(filename):
    try:
        df = pd.read_csv(filename, delimiter=';', encoding='utf-8-sig', header=0)
        
        # --- CORRECCIÓN DE NOMBRES DE COLUMNAS ---
        col_municipio = 'Municipio/Poblacion INE'
        col_centro = 'Centro de Trabajo Nuevo'
        col_distancia = 'Distancia en Kms'
        col_minutos = 'Tiempo(Min)'

        df.rename(columns={
            col_municipio: 'municipio',
            col_centro: 'centro_trabajo',
            col_distancia: 'distancia',
            col_minutos: 'minutos'
        }, inplace=True)

        # Asegurarnos de que las columnas existen
        required_cols = ['municipio', 'minutos', 'distancia', 'centro_trabajo']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Error Crítico: El archivo '{filename}' no contiene todas las columnas necesarias. Revisa que existan: '{col_municipio}', '{col_centro}', '{col_distancia}', '{col_minutos}'.")
            return None, None

        # Limpiamos los datos
        df_clean = df[required_cols].dropna(subset=['municipio', 'minutos', 'centro_trabajo'])
        df_clean['municipio'] = df_clean['municipio'].str.strip()
        df_clean = df_clean[df_clean['municipio'] != '']
        df_clean['minutos'] = pd.to_numeric(df_clean['minutos'], errors='coerce').fillna(0).astype(int)
        df_clean['distancia'] = df_clean['distancia'].astype(str).str.replace(',', '.', regex=False)
        df_clean['distancia'] = pd.to_numeric(df_clean['distancia'], errors='coerce').fillna(0).astype(float)
        df_clean['centro_trabajo'] = df_clean['centro_trabajo'].str.strip()

        # Si hay municipios duplicados, nos quedamos con la entrada que tiene más minutos
        df_final = df_clean.loc[df_clean.groupby('municipio')['minutos'].idxmax()]

        # Creamos un único diccionario donde la clave es el municipio y el valor es otro diccionario con sus datos
        municipio_data = df_final.set_index('municipio').to_dict('index')
        
        lista_municipios = sorted(municipio_data.keys(), key=lambda s: s.casefold())
        
        return municipio_data, lista_municipios

    except Exception as e:
        st.error(f"Error al procesar el archivo '{filename}': {e}")
        return None, None

def calcular_minutos_con_limite(origen, destino, gmaps_client):
    try:
        directions_result = gmaps_client.directions(origen, destino, mode="driving", avoid="tolls")
        if not directions_result or not directions_result[0]['legs']:
            return None, None, "No se pudo encontrar una ruta para las direcciones proporcionadas."
        
        steps = directions_result[0]['legs'][0]['steps']
        total_capped_duration_seconds = 0
        total_distance_meters = 0

        for step in steps:
            distancia_metros = step['distance']['value']
            duracion_google_seg = step['duration']['value']
            total_distance_meters += distancia_metros
            
            if distancia_metros > 0:
                theoretical_duration_90kmh_seg = (distancia_metros / 1000) / (90 / 3600)
            else:
                theoretical_duration_90kmh_seg = 0
            
            capped_duration_seg = max(duracion_google_seg, theoretical_duration_90kmh_seg)
            total_capped_duration_seconds += capped_duration_seg
            
        total_distancia_km = total_distance_meters / 1000
        total_minutos_final = math.ceil(total_capped_duration_seconds / 60)
        
        return total_distancia_km, total_minutos_final, None

    except googlemaps.exceptions.ApiError as e:
        return None, None, f"Error de la API de Google: {e}"
    except Exception as e:
        return None, None, f"Error inesperado: {e}"

def mostrar_horas_de_salida(total_minutos_desplazamiento):
    st.markdown("---"); st.subheader("🕒 Horas de Salida Sugeridas")
    dias_es = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles", "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado", "Sunday": "Domingo"}
    meses_es = {"January": "enero", "February": "febrero", "March": "marzo", "April": "abril", "May": "mayo", "June": "junio", "July": "julio", "August": "agosto", "September": "septiembre", "October": "octubre", "November": "noviembre", "December": "diciembre"}
    hoy = dt.date.today()
    dia_en, mes_en = hoy.strftime('%A'), hoy.strftime('%B')
    fecha_formateada = f"{dias_es.get(dia_en, dia_en)} {hoy.day} de {meses_es.get(mes_en, mes_en)}"
    st.session_state.calculation_results['fecha'] = fecha_formateada
    es_viernes = (hoy.weekday() == 4)
    horarios_base = {"Verano": (dt.time(14, 0) if es_viernes else dt.time(15, 0)), "Habitual Intensivo": (dt.time(15, 0) if es_viernes else dt.time(16, 0)), "Normal": (dt.time(16, 0) if es_viernes else dt.time(17, 0))}
    tabla_rows = [f"| Horario | Hora Salida Habitual | Hora Salida Hoy ({fecha_formateada}) |", "|---|---|---|"]
    horas_salida_hoy = {}
    for nombre, hora_habitual in horarios_base.items():
        salida_dt_hoy = dt.datetime.combine(hoy, hora_habitual) - dt.timedelta(minutes=total_minutos_desplazamiento)
        hora_salida_str = salida_dt_hoy.strftime('%H:%M')
        horas_salida_hoy[nombre] = hora_salida_str
        tabla_rows.append(f"| **{nombre}** | {hora_habitual.strftime('%H:%M')} | **{hora_salida_str}** |")
    st.session_state.calculation_results['horas_salida'] = horas_salida_hoy
    st.markdown("\n".join(tabla_rows))

@st.cache_data
def cargar_datos_empleados(filename="employees.csv"):
    try:
        df = pd.read_csv(filename, delimiter='|', encoding='utf-8-sig')
    except FileNotFoundError: st.error(f"❌ Error: No se encuentra el archivo '{filename}'."); return None
    except Exception as e: st.error(f"Error al procesar '{filename}'. Revisa que el separador sea '|'. Error: {e}"); return None
    try:
        required_cols = ['PROVINCIA', 'EQUIPO', 'NOMBRE COMPLETO', 'EMAIL']
        df = df.dropna(subset=required_cols)
        for col in required_cols: df[col] = df[col].str.strip()
        return df
    except KeyError as e: st.error(f"El archivo '{filename}' no tiene la columna requerida: {e}."); return None
    except Exception as e: st.error(f"Error inesperado al limpiar datos de empleados: {e}"); return None

# --- APLICACIÓN DE CÁLCULO ---
def full_calculator_app():
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")
    tab1, tab2 = st.tabs([" Cálculo Dentro de la Provincia (CSV) ", "  Cálculo Interprovincial (Google)  "])
    
    with tab1:
        st.header("Cálculo Dentro de la Provincia (tiempos.csv)")
        municipio_data, lista_municipios = cargar_datos_csv('tiempos.csv')
        
        if municipio_data and lista_municipios:
            st.markdown("---")

            col1, col2 = st.columns(2)

            with col1:
                mun_entrada = st.selectbox(
                    "Destino del comienzo de la jornada:",
                    lista_municipios, index=None, placeholder="Selecciona un municipio"
                )
                if mun_entrada and mun_entrada in municipio_data:
                    info = municipio_data.get(mun_entrada)
                    st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

            with col2:
                mun_salida = st.selectbox(
                    "Destino del final de la jornada:",
                    lista_municipios, index=None, placeholder="Selecciona un municipio"
                )
                if mun_salida and mun_salida in municipio_data:
                    info = municipio_data.get(mun_salida)
                    st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

            if mun_entrada and mun_salida:
                st.markdown("---")
                
                min_entrada = int(municipio_data[mun_entrada]['minutos'])
                min_salida = int(municipio_data[mun_salida]['minutos'])
                dist_entrada = float(municipio_data[mun_entrada]['distancia'])
                dist_salida = float(municipio_data[mun_salida]['distancia'])
                
                st.session_state.calculation_results['aviso_pernocta'] = min_entrada > 80 or min_salida > 80
                st.session_state.calculation_results['aviso_dieta'] = dist_entrada > 40 or dist_salida > 40
                st.session_state.calculation_results['aviso_jornada'] = min_entrada > 60 or min_salida > 60
                
                if st.session_state.calculation_results['aviso_pernocta']:
                    st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80 minutos. Comprueba posible pernocta.")
                
                if st.session_state.calculation_results['aviso_dieta']:
                    st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")
                
                if st.session_state.calculation_results['aviso_jornada']:
                    st.warning("⏰ **Aviso Jornada:** Uno o ambos trayectos superan los 60 minutos. Comprueba el tipo de jornada.")

                total = min_entrada + min_salida
                st.info(f"Minutos (entrada): **{min_entrada}** | Minutos (salida): **{min_salida}**")
                st.success(f"**Minutos totales de desplazamiento:** {total}")
                
                mostrar_horas_de_salida(total)
                st.session_state.calculation_results['total_minutos'] = total
                if st.button("📧 Enviar mail al equipo", key="btn_csv_mail"):
                    st.session_state.page = 'email_form'
                    st.rerun()

    with tab2:
        st.header("Cálculo por distancia (Regla 90 km/h)")
        try: gmaps = googlemaps.Client(key=st.secrets["google_api_key"])
        except Exception: st.error("Error: La clave de API de Google no está disponible en `secrets.toml`."); st.stop()
        
        col1_g, col2_g = st.columns(2)
        with col1_g:
            origen_ida = st.text_input("Origen (ida)", key="origen_ida", on_change=lambda: st.session_state.update(gmaps_results=None))
            destino_ida = st.text_input("Destino (ida)", key="destino_ida", on_change=lambda: st.session_state.update(gmaps_results=None))
        with col2_g:
            origen_vuelta = st.text_input("Origen (vuelta)", key="origen_vuelta", on_change=lambda: st.session_state.update(gmaps_results=None))
            destino_vuelta = st.text_input("Destino (vuelta)", key="destino_vuelta", on_change=lambda: st.session_state.update(gmaps_results=None))
        
        if st.