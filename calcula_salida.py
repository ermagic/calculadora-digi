# app.py (o calcula_salida.py)
import streamlit as st
import pandas as pd
import googlemaps
import datetime as dt
import math

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Calculadora de Desplazamiento DIGI",
    page_icon="🚗",
    layout="centered"
)

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
    """Carga y procesa los datos del archivo 'tiempos.csv' local."""
    try:
        df = pd.read_csv('tiempos.csv', delimiter=';', encoding='utf-8-sig', header=0)
        
        # Índices de las columnas de interés
        col_municipio_idx = 5 
        col_km_idx = 13  # Columna N para los kilómetros
        col_minutos_idx = 16

        # Verificación de que el CSV tiene suficientes columnas
        if len(df.columns) <= max(col_municipio_idx, col_km_idx, col_minutos_idx):
            st.error(f"El archivo CSV debe tener al menos {max(col_municipio_idx, col_km_idx, col_minutos_idx) + 1} columnas.")
            return None, None
            
        # Renombrar columnas para facilitar el acceso
        df.rename(columns={
            df.columns[col_municipio_idx]: 'municipio',
            df.columns[col_km_idx]: 'km',
            df.columns[col_minutos_idx]: 'minutos'
        }, inplace=True)

        # Limpieza y preparación de datos
        df_clean = df[['municipio', 'minutos', 'km']].dropna(subset=['municipio'])
        df_clean['municipio'] = df_clean['municipio'].str.strip()
        df_clean = df_clean[df_clean['municipio'] != '']
        
        # Convertir a tipos numéricos, manejando errores
        df_clean['minutos'] = pd.to_numeric(df_clean['minutos'], errors='coerce').fillna(0).astype(int)
        df_clean['km'] = pd.to_numeric(df_clean['km'], errors='coerce').fillna(0)

        # Agrupar por municipio y quedarse con el valor máximo (para evitar duplicados)
        municipios_data = df_clean.groupby('municipio').agg(
            minutos=('minutos', 'max'),
            km=('km', 'max')
        ).to_dict(orient='index')
        
        # Crear la lista de municipios para los selectores
        lista_municipios = sorted(municipios_data.keys(), key=lambda s: s.casefold())
        
        return municipios_data, lista_municipios
    except FileNotFoundError:
        st.error("❌ Error: No se pudo encontrar el archivo 'tiempos.csv'.")
        st.warning("Asegúrate de que el archivo está en la misma carpeta que el script de la aplicación.")
        return None, None
    except Exception as e:
        st.error(f"Error al procesar el archivo CSV: {e}")
        return None, None

def calcular_minutos_por_distancia(origen, destino, gmaps_client, velocidad_kmh=90):
    """
    Calcula el tiempo de viaje en minutos basándose en la distancia y una velocidad fija.
    Devuelve la distancia en km y el tiempo total en minutos.
    """
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


def main_app():
    """La aplicación principal que se muestra después del login."""
    
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")

    tab1, tab2 = st.tabs([" Cáculo Local (CSV) ", "  Cálculo Interprovincial (Google)  "])

    with tab1:
        st.header("Cálculo desde archivo local (tiempos.csv)")
        
        municipios_data, lista_municipios = cargar_datos_csv()
        
        if municipios_data and lista_municipios:
            st.markdown("---")
            mun_entrada = st.selectbox("Destino del comienzo de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")
            mun_salida = st.selectbox("Destino del final de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")

            if mun_entrada and mun_salida:
                # Obtener datos de minutos y KM para cada trayecto
                datos_entrada = municipios_data.get(mun_entrada, {'minutos': 0, 'km': 0})
                datos_salida = municipios_data.get(mun_salida, {'minutos': 0, 'km': 0})

                min_entrada = int(datos_entrada['minutos'])
                km_entrada = datos_salida['km']
                
                min_salida = int(datos_salida['minutos'])
                km_salida = datos_salida['km']

                total = min_entrada + min_salida

                st.info(f"Minutos (entrada): **{min_entrada}** | Minutos (salida): **{min_salida}**")
                st.success(f"**Minutos totales de desplazamiento:** {total}")
                
                # --- INICIO DE CAMBIOS ---
                # Aviso si algún trayecto individual supera los 40 km
                if km_entrada > 40 or km_salida > 40:
                    st.warning("⚠️ **Aviso:** Uno de los trayectos supera los 40 km.")
                # --- FIN DE CAMBIOS ---
                
                # Aviso si algún trayecto individual supera los 60 minutos
                if min_entrada > 60 or min_salida > 60:
                    st.warning("⚠️ **Aviso:** Uno de los trayectos supera los 60 minutos.")

                # Aviso si el total de minutos supera los 80 minutos
                if total > 80:
                    st.warning("⚠️ **Aviso:** El tiempo total de desplazamiento supera los 80 minutos.")
                
                dia_semana_hoy = dt.date.today().weekday()
                hora_base = dt.time(14, 0) if dia_semana_hoy == 4 else dt.time(15, 0)
                salida_dt = dt.datetime.combine(dt.date.today(), hora_base) - dt.timedelta(minutes=total)
                st.success(f"## Hora de salida hoy: {salida_dt.strftime('%H:%M')}")
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
                    
                    def _calcular_minutos_a_cargo(minutos_totales):
                        return max(0, minutos_totales - 30)

                    dist_ida, min_ida_brutos, err_ida = calcular_minutos_por_distancia(origen_ida, destino_ida, gmaps)
                    dist_vuelta, min_vuelta_brutos, err_vuelta = calcular_minutos_por_distancia(origen_vuelta, destino_vuelta, gmaps)

                    if err_ida or err_vuelta:
                        if err_ida: st.error(f"Error en ruta de ida: {err_ida}")
                        if err_vuelta: st.error(f"Error en ruta de vuelta: {err_vuelta}")
                    else:
                        min_a_cargo_ida = _calcular_minutos_a_cargo(min_ida_brutos)
                        min_a_cargo_vuelta = _calcular_minutos_a_cargo(min_vuelta_brutos)
                        
                        total_final = min_a_cargo_ida + min_a_cargo_vuelta
                        dia_semana_hoy = dt.date.today().weekday()
                        hora_base = dt.time(14, 0) if dia_semana_hoy == 4 else dt.time(15, 0)
                        salida_dt = dt.datetime.combine(dt.date.today(), hora_base) - dt.timedelta(minutes=total_final)
                        
                        st.markdown("---")
                        st.metric(
                            label=f"IDA: {dist_ida:.1f} km",
                            value=f"{min_a_cargo_ida} min a cargo",
                            delta=f"Tiempo total: {min_ida_brutos} min",
                            delta_color="off"
                        )
                        st.metric(
                            label=f"VUELTA: {dist_vuelta:.1f} km",
                            value=f"{min_a_cargo_vuelta} min a cargo",
                            delta=f"Tiempo total: {min_vuelta_brutos} min",
                            delta_color="off"
                        )
                        st.markdown("---")
                        
                        st.success(f"**Minutos totales de desplazamiento a cargo:** {total_final}")

                        # Aviso si algún trayecto individual supera los 60 minutos
                        if min_a_cargo_ida > 60 or min_a_cargo_vuelta > 60:
                            st.warning("⚠️ **Aviso:** Uno de los trayectos a cargo de la empresa supera los 60 minutos.")

                        # Aviso si el total de minutos supera los 80 minutos
                        if total_final > 80:
                            st.warning("⚠️ **Aviso:** El tiempo total de desplazamiento a cargo supera los 80 minutos.")
                        
                        st.success(f"## Hora de salida hoy: {salida_dt.strftime('%H:%M')}")

# --- ESTRUCTURA PRINCIPAL DEL SCRIPT ---
if check_login():
    main_app()