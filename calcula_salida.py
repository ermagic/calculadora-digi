# app.py (o calcula_salida.py)
import streamlit as st
import pandas as pd
import googlemaps
import datetime as dt
import math
import locale

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Calculadora de Desplazamiento DIGI",
    page_icon="🚗",
    layout="centered"
)

# MODIFICACIÓN: Configurar el locale a español para los nombres de días y meses.
# Esto es importante para que la fecha se muestre correctamente.
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    st.warning("No se pudo configurar el idioma a español. La fecha podría mostrarse en inglés.")

# --- SISTEMA DE LOGIN CON USUARIO Y CONTRASEÑA ---
def check_login():
    """Muestra un formulario de login y devuelve True si las credenciales son correctas."""
    if st.session_state.get('authentication_status'):
        return True

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
            st.info("Asegúrate de que tu archivo '.streamlit/secrets.toml' está bien configurado.")
    
    return False

# --- LÓGICA DE LA CALCULADORA ---

@st.cache_data
def cargar_datos_csv():
    """Carga los datos del archivo 'tiempos.csv' local, incluyendo la distancia."""
    try:
        df = pd.read_csv('tiempos.csv', delimiter=';', encoding='utf-8-sig', header=0)
        
        col_municipio_idx = 5 
        # MODIFICACIÓN 4: Leemos la columna N (índice 13) para la distancia.
        col_distancia_idx = 13 
        col_minutos_idx = 16

        if len(df.columns) <= col_minutos_idx:
            st.error(f"El archivo CSV debe tener al menos {col_minutos_idx + 1} columnas.")
            return None, None, None
            
        df.rename(columns={
            df.columns[col_municipio_idx]: 'municipio',
            df.columns[col_distancia_idx]: 'distancia',
            df.columns[col_minutos_idx]: 'minutos'
        }, inplace=True)

        df_clean = df[['municipio', 'minutos', 'distancia']].dropna(subset=['municipio', 'minutos'])
        df_clean['municipio'] = df_clean['municipio'].str.strip()
        df_clean = df_clean[df_clean['municipio'] != '']
        
        df_clean['minutos'] = pd.to_numeric(df_clean['minutos'], errors='coerce').fillna(0).astype(int)
        df_clean['distancia'] = df_clean['distancia'].astype(str).str.replace(',', '.', regex=False)
        df_clean['distancia'] = pd.to_numeric(df_clean['distancia'], errors='coerce').fillna(0).astype(float)

        municipios_min = df_clean.groupby('municipio')['minutos'].max().to_dict()
        municipios_dist = df_clean.groupby('municipio')['distancia'].max().to_dict()
        lista_municipios = sorted(municipios_min.keys(), key=lambda s: s.casefold())
        
        return municipios_min, municipios_dist, lista_municipios
    except FileNotFoundError:
        st.error("❌ Error: No se pudo encontrar el archivo 'tiempos.csv'.")
        st.warning("Asegúrate de que el archivo está en la misma carpeta que el script de la aplicación.")
        return None, None, None
    except Exception as e:
        st.error(f"Error al procesar el archivo CSV: {e}")
        return None, None, None

def calcular_minutos_por_distancia(origen, destino, gmaps_client, velocidad_kmh=90):
    """Calcula el tiempo de viaje en minutos basándose en la distancia y una velocidad fija."""
    try:
        ruta = gmaps_client.directions(origen, destino, mode="driving")
        if not ruta:
            return None, None, "No se encontró una ruta."
        
        distancia_metros = ruta[0]['legs'][0]['distance']['value']
        distancia_km = distancia_metros / 1000
        tiempo_horas = distancia_km / velocidad_kmh
        tiempo_minutos = math.ceil(tiempo_horas * 60)
        
        return distancia_km, tiempo_minutos, None
    except Exception as e:
        return None, None, str(e)

# MODIFICACIÓN 3: Nueva tabla de horarios con fecha dinámica.
def mostrar_horas_de_salida(total_minutos_desplazamiento):
    """Calcula y muestra las horas de salida en una tabla de tres columnas."""
    st.markdown("---")
    st.subheader("🕒 Horas de Salida Sugeridas")

    hoy = dt.date.today()
    dia_semana_hoy = hoy.weekday()
    es_viernes = (dia_semana_hoy == 4)
    
    # Formateamos la fecha actual en español (ej: "Miércoles 29 de mayo")
    fecha_formateada = hoy.strftime('%A %d de %B').capitalize()
    
    horarios_base = {
        "Verano": (dt.time(14, 0) if es_viernes else dt.time(15, 0)),
        "Habitual Intensivo": (dt.time(15, 0) if es_viernes else dt.time(16, 0)),
        "Normal": (dt.time(16, 0) if es_viernes else dt.time(17, 0))
    }

    tabla = f"""
    | Horario              | Hora Salida Habitual | Hora Salida Hoy ({fecha_formateada}) |
    | -------------------- | -------------------- | ------------------------------------- |
    """
    
    for nombre, hora_habitual in horarios_base.items():
        salida_dt_hoy = dt.datetime.combine(hoy, hora_habitual) - dt.timedelta(minutes=total_minutos_desplazamiento)
        
        tabla += f"| **{nombre}** | {hora_habitual.strftime('%H:%M')} | **{salida_dt_hoy.strftime('%H:%M')}** |\n"
        
    st.markdown(tabla)

def main_app():
    """La aplicación principal que se muestra después del login."""
    
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")

    tab1, tab2 = st.tabs([" Cálculo Dentro de la Provincia (CSV) ", "  Cálculo Interprovincial (Google)  "])

    with tab1:
        st.header("Cálculo Dentro de la Provincia (tiempos.csv)")
        
        municipios_min, municipios_dist, lista_municipios = cargar_datos_csv()
        
        if municipios_min and lista_municipios and municipios_dist:
            st.markdown("---")
            mun_entrada = st.selectbox("Destino del comienzo de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")
            mun_salida = st.selectbox("Destino del final de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")

            if mun_entrada and mun_salida:
                min_entrada = int(municipios_min.get(mun_entrada, 0))
                min_salida = int(municipios_min.get(mun_salida, 0))
                total = min_entrada + min_salida

                # MODIFICACIÓN 4: Añadimos aviso de dieta para el CSV.
                dist_entrada = municipios_dist.get(mun_entrada, 0)
                dist_salida = municipios_dist.get(mun_salida, 0)
                if dist_entrada > 40 or dist_salida > 40:
                    st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")

                st.info(f"Minutos (entrada): **{min_entrada}** | Minutos (salida): **{min_salida}**")
                st.success(f"**Minutos totales de desplazamiento:** {total}")
                
                mostrar_horas_de_salida(total)
        else:
            st.info("Esperando a que el archivo 'tiempos.csv' sea válido o esté disponible.")

    with tab2:
        st.header("Cálculo por distancia (90 km/h)")
        
        try:
            gmaps = googlemaps.Client(key=st.secrets["google_api_key"])
        except Exception:
            st.error("Error de configuración: La clave de API de Google no está disponible.")
            st.info("Revisa tu archivo `.streamlit/secrets.toml`.")
            st.stop()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Trayecto de Ida")
            origen_ida = st.text_input("Origen (ida)")
            destino_ida = st.text_input("Destino (ida)")
        with col2:
            st.subheader("Trayecto de Vuelta")
            origen_vuelta = st.text_input("Origen (vuelta)")
            destino_vuelta = st.text_input("Destino (vuelta)")

        if st.button("Calcular Tiempo por Distancia", type="primary"):
            if not all([origen_ida, destino_ida, origen_vuelta, destino_vuelta]):
                st.warning("Por favor, rellene las cuatro direcciones.")
            else:
                with st.spinner('Calculando distancias y tiempos...'):
                    
                    dist_ida, min_ida_brutos, err_ida = calcular_minutos_por_distancia(origen_ida, destino_ida, gmaps)
                    dist_vuelta, min_vuelta_brutos, err_vuelta = calcular_minutos_por_distancia(origen_vuelta, destino_vuelta, gmaps)

                    if err_ida or err_vuelta:
                        if err_ida: st.error(f"Error en ruta de ida: {err_ida}")
                        if err_vuelta: st.error(f"Error en ruta de vuelta: {err_vuelta}")
                    else:
                        def _calcular_minutos_a_cargo(minutos_totales):
                            return max(0, minutos_totales - 30)

                        origen_ida_norm = origen_ida.strip().lower()
                        destino_ida_norm = destino_ida.strip().lower()
                        origen_vuelta_norm = origen_vuelta.strip().lower()
                        destino_vuelta_norm = destino_vuelta.strip().lower()

                        # MODIFICACIÓN 1 Y 2: Lógica para trayectos idénticos.
                        if origen_ida_norm == destino_vuelta_norm and destino_ida_norm == origen_vuelta_norm:
                            st.info("ℹ️ Detectado trayecto de ida y vuelta idéntico.")
                            
                            # Determinamos cuál es el trayecto más largo
                            if min_ida_brutos >= min_vuelta_brutos:
                                dist_max = dist_ida
                                min_max = min_ida_brutos
                            else:
                                dist_max = dist_vuelta
                                min_max = min_vuelta_brutos
                            
                            # Mostramos solo un resultado para el trayecto más largo
                            st.markdown("---")
                            # MODIFICACIÓN 4: Aviso de dieta
                            if dist_max > 40:
                                st.warning("⚠️ **Aviso Media Dieta:** El trayecto supera los 40km. Comprueba el tipo de jornada.")

                            min_a_cargo_unico = _calcular_minutos_a_cargo(min_max)
                            st.metric(
                                label=f"TRAYECTO MÁS LARGO ({dist_max:.1f} km)",
                                value=f"{min_a_cargo_unico} min a cargo",
                                delta=f"Tiempo total: {min_max} min",
                                delta_color="off"
                            )
                            # El total a cargo es el del trayecto más largo x 2 (ida y vuelta)
                            total_final = min_a_cargo_unico * 2
                        else:
                            # Lógica original para trayectos diferentes
                            min_a_cargo_ida = _calcular_minutos_a_cargo(min_ida_brutos)
                            min_a_cargo_vuelta = _calcular_minutos_a_cargo(min_vuelta_brutos)
                            total_final = min_a_cargo_ida + min_a_cargo_vuelta
                            
                            st.markdown("---")
                            # MODIFICACIÓN 4: Aviso de dieta
                            if dist_ida > 40 or dist_vuelta > 40:
                                st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")
                            
                            st.metric(label=f"IDA: {dist_ida:.1f} km", value=f"{min_a_cargo_ida} min a cargo", delta=f"Tiempo total: {min_ida_brutos} min", delta_color="off")
                            st.metric(label=f"VUELTA: {dist_vuelta:.1f} km", value=f"{min_a_cargo_vuelta} min a cargo", delta=f"Tiempo total: {min_vuelta_brutos} min", delta_color="off")
                        
                        st.markdown("---")
                        st.success(f"**Minutos totales de desplazamiento a cargo:** {total_final}")
                        
                        mostrar_horas_de_salida(total_final)

# --- ESTRUCTURA PRINCIPAL DEL SCRIPT ---
if check_login():
    main_app()