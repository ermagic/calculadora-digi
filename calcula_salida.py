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
        # --- CAMBIO IMPORTANTE AQUÍ ---
        # Cambiamos la codificación a 'latin-1' para que pueda leer caracteres como tildes
        # guardados desde Excel en Windows.
        df = pd.read_csv(filename, delimiter=';', encoding='latin-1', header=0)
        
        # --- NOMBRES DE COLUMNAS NUEVOS ---
        col_poblacion = 'Poblacion_IC'
        col_centro_trabajo = 'Centro de Trabajo Nuevo'
        col_provincia_ct = 'Provincia Centro de Trabajo'
        col_distancia = 'Distancia en K'
        col_minutos_total = 'Tiempo(Min)'
        col_minutos_cargo = 'Tiempo a cargo de empresa(Min)'

        df.rename(columns={
            col_poblacion: 'poblacion',
            col_centro_trabajo: 'centro_trabajo',
            col_provincia_ct: 'provincia_ct',
            col_distancia: 'distancia',
            col_minutos_total: 'minutos_total',
            col_minutos_cargo: 'minutos_cargo'
        }, inplace=True)

        required_cols = ['poblacion', 'centro_trabajo', 'provincia_ct', 'distancia', 'minutos_total', 'minutos_cargo']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Error Crítico: El archivo '{filename}' no contiene todas las columnas necesarias. Revisa que existan: {required_cols}.")
            return None

        # Limpiamos los datos
        df_clean = df[required_cols].dropna(subset=['poblacion', 'centro_trabajo', 'provincia_ct'])
        for col in ['poblacion', 'centro_trabajo', 'provincia_ct']:
            df_clean[col] = df_clean[col].str.strip()
        
        # Convertir columnas numéricas, manejando errores
        for col in ['distancia', 'minutos_total', 'minutos_cargo']:
            df_clean[col] = df_clean[col].astype(str).str.replace(',', '.', regex=False)
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

        df_clean['minutos_total'] = df_clean['minutos_total'].astype(int)
        df_clean['minutos_cargo'] = df_clean['minutos_cargo'].astype(int)
        
        return df_clean

    except Exception as e:
        st.error(f"Error al procesar el archivo '{filename}': {e}")
        return None

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
        # También aplicamos el mismo cambio aquí por si acaso
        df = pd.read_csv(filename, delimiter='|', encoding='latin-1')
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
    
    def _cargo(minutos):
        return max(0, minutos - 30)

    tab1, tab2 = st.tabs([" Cálculo desde el archivo ", "  Cálculo fuera de la tabla  "])
    
    with tab1:
        st.header("Cálculo de tiempos desde el archivo")
        df_tiempos = cargar_datos_csv('tiempos.csv')
        
        if df_tiempos is not None:
            provincias_ct = sorted(df_tiempos['provincia_ct'].unique())
            provincia_seleccionada = st.selectbox(
                "1. Selecciona la provincia del Centro de Trabajo:",
                provincias_ct, index=None, placeholder="Elige una provincia"
            )

            if provincia_seleccionada:
                df_filtrado = df_tiempos[df_tiempos['provincia_ct'] == provincia_seleccionada]
                lista_poblaciones = sorted(df_filtrado['poblacion'].unique())
                
                st.markdown("---")

                col1, col2 = st.columns(2)
                with col1:
                    mun_entrada = st.selectbox(
                        "2. Destino del comienzo de la jornada:",
                        lista_poblaciones, index=None, placeholder="Selecciona una población"
                    )
                    if mun_entrada:
                        info = df_filtrado[df_filtrado['poblacion'] == mun_entrada].iloc[0]
                        st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

                with col2:
                    mun_salida = st.selectbox(
                        "3. Destino del final de la jornada:",
                        lista_poblaciones, index=None, placeholder="Selecciona una población"
                    )
                    if mun_salida:
                        info = df_filtrado[df_filtrado['poblacion'] == mun_salida].iloc[0]
                        st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

                if mun_entrada and mun_salida:
                    st.markdown("---")
                    
                    datos_entrada = df_filtrado[df_filtrado['poblacion'] == mun_entrada].iloc[0]
                    datos_salida = df_filtrado[df_filtrado['poblacion'] == mun_salida].iloc[0]
                    
                    min_total_entrada = int(datos_entrada['minutos_total'])
                    min_total_salida = int(datos_salida['minutos_total'])
                    dist_entrada = float(datos_entrada['distancia'])
                    dist_salida = float(datos_salida['distancia'])
                    
                    min_cargo_entrada = int(datos_entrada['minutos_cargo'])
                    min_cargo_salida = int(datos_salida['minutos_cargo'])
                    
                    st.session_state.calculation_results['aviso_pernocta'] = min_total_entrada > 80 or min_total_salida > 80
                    st.session_state.calculation_results['aviso_dieta'] = dist_entrada > 40 or dist_salida > 40
                    st.session_state.calculation_results['aviso_jornada'] = min_total_entrada > 60 or min_total_salida > 60
                    
                    if st.session_state.calculation_results['aviso_pernocta']:
                        st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80 minutos. Comprueba posible pernocta.")
                    
                    if st.session_state.calculation_results['aviso_dieta']:
                        st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")
                    
                    if st.session_state.calculation_results['aviso_jornada']:
                        st.warning("⏰ **Aviso Jornada:** Uno o ambos trayectos superan los 60 minutos. Comprueba el tipo de jornada.")

                    total_minutos_a_cargo = min_cargo_entrada + min_cargo_salida
                    
                    st.info(f"**Entrada:** De `{datos_entrada['centro_trabajo']}` a `{mun_entrada}`\n\n**Salida:** De `{mun_salida}` a `{datos_salida['centro_trabajo']}`")
                    st.success(f"**Minutos totales de desplazamiento a cargo:** {total_minutos_a_cargo}")
                    
                    mostrar_horas_de_salida(total_minutos_a_cargo)
                    st.session_state.calculation_results['total_minutos'] = total_minutos_a_cargo
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
        
        if st.button("Calcular Tiempo por Distancia", type="primary"):
            if all([origen_ida, destino_ida, origen_vuelta, destino_vuelta]):
                with st.spinner('Calculando...'):
                    dist_ida, min_ida, err_ida = calcular_minutos_con_limite(origen_ida, destino_ida, gmaps)
                    dist_vuelta, min_vuelta, err_vuelta = calcular_minutos_con_limite(origen_vuelta, destino_vuelta, gmaps)
                    if err_ida or err_vuelta:
                        if err_ida: st.error(f"Error ida: {err_ida}")
                        if err_vuelta: st.error(f"Error vuelta: {err_vuelta}")
                        st.session_state.gmaps_results = None
                    else:
                        st.session_state.gmaps_results = {
                            "dist_ida": dist_ida, "min_ida": min_ida,
                            "dist_vuelta": dist_vuelta, "min_vuelta": min_vuelta,
                            "origen_ida": origen_ida, "destino_ida": destino_ida,
                            "origen_vuelta": origen_vuelta, "destino_vuelta": destino_vuelta
                        }
            else:
                st.warning("Por favor, rellene las cuatro direcciones.")
                st.session_state.gmaps_results = None

        if st.session_state.gmaps_results:
            res = st.session_state.gmaps_results
            es_identico = res['origen_ida'].strip().lower() == res['destino_vuelta'].strip().lower() and res['destino_ida'].strip().lower() == res['origen_vuelta'].strip().lower()
            
            if es_identico:
                st.info("ℹ️ Detectado trayecto de ida y vuelta idéntico.")
                dist, mins = (res['dist_ida'], res['min_ida']) if res['min_ida'] >= res['min_vuelta'] else (res['dist_vuelta'], res['min_vuelta'])
                
                st.session_state.calculation_results['aviso_pernocta'] = mins > 80
                st.session_state.calculation_results['aviso_dieta'] = dist > 40
                st.session_state.calculation_results['aviso_jornada'] = mins > 60
                
                if st.session_state.calculation_results['aviso_pernocta']:
                    st.warning(f"🛌 **Aviso Pernocta:** El trayecto ({mins} min) supera los 80 minutos. Comprueba posible pernocta.")
                if st.session_state.calculation_results['aviso_dieta']:
                    st.warning(f"⚠️ **Aviso Media Dieta:** El trayecto ({dist:.1f} km) supera los 40km. Comprueba el tipo de jornada.")
                if st.session_state.calculation_results['aviso_jornada']:
                    st.warning(f"⏰ **Aviso Jornada:** El trayecto ({mins} min) supera los 60 minutos. Comprueba el tipo de jornada.")
                
                st.metric(f"TRAYECTO MÁS LARGO ({dist:.1f} km)", f"{_cargo(mins)} min a cargo", f"Tiempo total: {mins} min", delta_color="off")
                total_final = _cargo(mins) * 2
            else:
                st.session_state.calculation_results['aviso_pernocta'] = res['min_ida'] > 80 or res['min_vuelta'] > 80
                st.session_state.calculation_results['aviso_dieta'] = res['dist_ida'] > 40 or res['dist_vuelta'] > 40
                st.session_state.calculation_results['aviso_jornada'] = res['min_ida'] > 60 or res['min_vuelta'] > 60
                
                if st.session_state.calculation_results['aviso_pernocta']:
                    st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80 minutos. Comprueba posible pernocta.")
                if st.session_state.calculation_results['aviso_dieta']:
                    st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")
                if st.session_state.calculation_results['aviso_jornada']:
                    st.warning("⏰ **Aviso Jornada:** Uno o ambos trayectos superan los 60 minutos. Comprueba el tipo de jornada.")
                
                st.metric(f"IDA: {res['dist_ida']:.1f} km", f"{_cargo(res['min_ida'])} min a cargo", f"Tiempo total: {res['min_ida']} min", delta_color="off")
                st.metric(f"VUELTA: {res['dist_vuelta']:.1f} km", f"{_cargo(res['min_vuelta'])} min a cargo", f"Tiempo total: {res['min_vuelta']} min", delta_color="off")
                total_final = _cargo(res['min_ida']) + _cargo(res['min_vuelta'])
            
            st.markdown("---")
            st.success(f"**Minutos totales de desplazamiento a cargo:** {total_final}")
            mostrar_horas_de_salida(total_final)
            st.session_state.calculation_results['total_minutos'] = total_final
            if st.button("📧 Enviar mail al equipo", key="btn_gmaps_mail"):
                st.session_state.page = 'email_form'
                st.rerun()

# --- PÁGINA DE EMAIL (sin cambios) ---
def email_form_app():
    st.title("📧 Redactar y Enviar Notificación")
    if st.button("⬅️ Volver a la calculadora"): st.session_state.page = 'calculator'; st.rerun()
    st.markdown("---")
    
    employees_df = cargar_datos_empleados()
    if employees_df is None: return

    st.header("1. Filtrar y Seleccionar Destinatarios")
    col1, col2 = st.columns(2)
    with col1:
        provincia_sel = st.selectbox("Filtrar por Provincia:", employees_df['PROVINCIA'].unique())
    with col2:
        equipos_en_provincia = employees_df[employees_df['PROVINCIA'] == provincia_sel]['EQUIPO'].unique()
        equipo_sel = st.selectbox("Filtrar por Equipo:", equipos_en_provincia)
    
    personas_en_provincia = employees_df[employees_df['PROVINCIA'] == provincia_sel]
    personas_en_equipo = personas_en_provincia[personas_en_provincia['EQUIPO'] == equipo_sel]
    
    nombres_seleccionados = st.multiselect(
        "Destinatarios (equipo preseleccionado, puedes añadir/quitar gente de la provincia):",
        options=personas_en_provincia['NOMBRE COMPLETO'].tolist(),
        default=personas_en_equipo['NOMBRE COMPLETO'].tolist(),
        placeholder="Busca y selecciona más trabajadores"
    )
    
    if not nombres_seleccionados:
        st.info("Selecciona al menos un destinatario para continuar."); return

    destinatarios_df = employees_df[employees_df['NOMBRE COMPLETO'].isin(nombres_seleccionados)]
    recipient_emails = destinatarios_df['EMAIL'].tolist()

    def crear_saludo(nombres):
        if not nombres: return "Hola,"
        nombres_cortos = [name.split()[0] for name in nombres]
        if len(nombres_cortos) == 1: return f"Hola {nombres_cortos[0]},"
        return f"Hola {', '.join(nombres_cortos[:-1])} y {nombres_cortos[-1]},"

    saludo = crear_saludo(nombres_seleccionados)
    
    with st.expander("Confirmar destinatarios y correos", expanded=True):
        if not destinatarios_df.empty:
            info_list = [f"- **{row['NOMBRE COMPLETO']}** ({row['EMAIL']})" for index, row in destinatarios_df.iterrows()]
            st.markdown("\n".join(info_list))
        else:
            st.write("No hay destinatarios seleccionados.")

    tipo_mail = st.radio("Selecciona el tipo de notificación:", ["Comunicar Horario de Salida", "Notificar Tipo de Jornada", "Informar de Pernocta"], horizontal=True)
    st.header("2. Revisa y Edita el Correo")
    res = st.session_state.calculation_results
    asunto_pred, cuerpo_pred = "", ""

    if tipo_mail == "Comunicar Horario de Salida":
        asunto_pred = f"Horario de salida para el {res.get('fecha', 'día de hoy')}"
        cuerpo_pred = f"{saludo}\n\nTe informo del horario de salida calculado para hoy, {res.get('fecha', '')}, basado en un desplazamiento total a cargo de **{res.get('total_minutos', 0)} minutos**:\n\n- Salida en horario de Verano: **{res.get('horas_salida', {}).get('Verano', 'N/A')}**\n- Salida en horario Intensivo: **{res.get('horas_salida', {}).get('Habitual Intensivo', 'N/A')}**\n- Salida en horario Normal: **{res.get('horas_salida', {}).get('Normal', 'N/A')}**\n\nSaludos,\n{st.session_state['username']}"
    elif tipo_mail == "Notificar Tipo de Jornada":
        asunto_pred = f"Confirmación de jornada para el {res.get('fecha', 'día de hoy')}"
        cuerpo_pred = f"{saludo}\n\nDebido a los desplazamientos del día de hoy ({res.get('fecha', '')}), por favor, confirma el tipo de jornada a aplicar.\n\nRecuerda que los avisos generados han sido:\n- Media Dieta (>40km): **{'Sí' if res.get('aviso_dieta') else 'No'}**\n- Jornada Especial (>60min): **{'Sí' if res.get('aviso_jornada') else 'No'}**\n\nQuedo a la espera de tu confirmación.\n\nSaludos,\n{st.session_state['username']}"
    elif tipo_mail == "Informar de Pernocta":
        asunto_pred = f"Aviso de posible pernocta - {res.get('fecha', 'día de hoy')}"
        cuerpo_pred = f"{saludo}\n\nEl cálculo de desplazamiento para hoy, {res.get('fecha', '')}, ha generado un aviso por superar los 80 minutos, lo que podría implicar una pernocta.\n\nPor favor, revisa la planificación y gestiona la reserva de hotel si es necesario.\n\nSaludos,\n{st.session_state['username']}"

    asunto = st.text_input("Asunto:", asunto_pred)
    cuerpo = st.text_area("Cuerpo del Mensaje:", cuerpo_pred, height=250)
    st.markdown("---")
    if st.button("🚀 Enviar Email", type="primary"):
        with st.spinner("Enviando correo..."):
            if send_email(recipient_emails, asunto, cuerpo):
                st.success("¡Correo enviado correctamente!")
            else:
                st.error("Hubo un problema al enviar el correo. Revisa la configuración en `secrets.toml` y la consola para más detalles.")

def send_email(recipients, subject, body):
    try:
        smtp_cfg = st.secrets["smtp"]
        sender, password = smtp_cfg["username"], smtp_cfg["password"]
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = sender, ", ".join(recipients), subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(smtp_cfg["server"], smtp_cfg["port"])
        server.starttls(); server.login(sender, password)
        server.send_message(msg); server.quit()
        return True
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return False

# --- CONTROLADOR PRINCIPAL ---
if check_login():
    if st.session_state.page == 'calculator':
        full_calculator_app()
    elif st.session_state.page == 'email_form':
        email_form_app()
