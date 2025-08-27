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
        col_municipio_idx, col_distancia_idx, col_minutos_idx = 5, 13, 16
        df.rename(columns={ df.columns[col_municipio_idx]: 'municipio', df.columns[col_distancia_idx]: 'distancia', df.columns[col_minutos_idx]: 'minutos' }, inplace=True)
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
    except Exception as e:
        st.error(f"Error al procesar el archivo '{filename}': {e}")
        return None, None, None

def calcular_minutos_por_distancia(origen, destino, gmaps_client):
    try:
        ruta = gmaps_client.directions(origen, destino, mode="driving", avoid="tolls")
        if not ruta: return None, None, "No se encontró una ruta sin peajes."
        distancia_km = ruta[0]['legs'][0]['distance']['value'] / 1000
        tiempo_minutos = math.ceil((distancia_km / 90) * 60)
        return distancia_km, tiempo_minutos, None
    except Exception as e: return None, None, str(e)

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

# --- FUNCIÓN CORREGIDA PARA CARGAR EMPLEADOS CON SEPARADOR '|' ---
@st.cache_data
def cargar_datos_empleados(filename="employees.csv"):
    try:
        # AQUÍ ESTÁ EL CAMBIO: Usamos el delimitador de pipe '|'
        df = pd.read_csv(filename, delimiter='|', encoding='utf-8-sig')
    except FileNotFoundError:
        st.error(f"❌ Error: No se encuentra el archivo '{filename}'. Asegúrate de que está en la misma carpeta que la aplicación.")
        return None
    except Exception as e:
        st.error(f"Error al procesar el archivo '{filename}'. Revisa que el separador sea '|'. Error: {e}")
        return None
    
    try:
        # Limpieza de datos
        df = df.dropna(subset=['PROVINCIA', 'EQUIPO', 'NOMBRE COMPLETO', 'EMAIL'])
        df['PROVINCIA'] = df['PROVINCIA'].str.strip()
        df['EQUIPO'] = df['EQUIPO'].str.strip()
        df['NOMBRE COMPLETO'] = df['NOMBRE COMPLETO'].str.strip()
        df['EMAIL'] = df['EMAIL'].str.strip()
        return df
    except KeyError as e:
        st.error(f"El archivo '{filename}' no tiene la columna requerida: {e}. Revisa el nombre de las columnas en tu CSV.")
        return None
    except Exception as e:
        st.error(f"Error inesperado al limpiar los datos del archivo de empleados: {e}")
        return None

# --- APLICACIÓN DE CÁLCULO ---
def full_calculator_app():
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")
    tab1, tab2 = st.tabs([" Cálculo Dentro de la Provincia (CSV) ", "  Cálculo Interprovincial (Google)  "])
    
    with tab1:
        st.header("Cálculo Dentro de la Provincia (tiempos.csv)")
        municipios_min, municipios_dist, lista_municipios = cargar_datos_csv('tiempos.csv')
        if municipios_min and lista_municipios and municipios_dist:
            st.markdown("---")
            mun_entrada = st.selectbox("Destino del comienzo de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")
            mun_salida = st.selectbox("Destino del final de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")
            if mun_entrada and mun_salida:
                min_entrada, min_salida = int(municipios_min.get(mun_entrada, 0)), int(municipios_min.get(mun_salida, 0))
                dist_entrada, dist_salida = municipios_dist.get(mun_entrada, 0), municipios_dist.get(mun_salida, 0)
                st.session_state.calculation_results['aviso_pernocta'] = dist_entrada > 80 or dist_salida > 80
                st.session_state.calculation_results['aviso_dieta'] = (dist_entrada > 40 or dist_salida > 40) and not st.session_state.calculation_results['aviso_pernocta']
                st.session_state.calculation_results['aviso_jornada'] = min_entrada > 60 or min_salida > 60
                if st.session_state.calculation_results['aviso_pernocta']: st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80km.")
                elif st.session_state.calculation_results['aviso_dieta']: st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km.")
                if st.session_state.calculation_results['aviso_jornada']: st.warning("⏰ **Aviso Jornada:** Uno o ambos trayectos superan los 60 minutos.")
                total = min_entrada + min_salida
                st.info(f"Minutos (entrada): **{min_entrada}** | Minutos (salida): **{min_salida}**")
                st.success(f"**Minutos totales de desplazamiento:** {total}")
                mostrar_horas_de_salida(total)
                st.session_state.calculation_results['total_minutos'] = total
                if st.button("📧 Enviar mail al equipo", key="btn_csv_mail"):
                    st.session_state.page = 'email_form'
                    st.rerun()

    with tab2:
        st.header("Cálculo por distancia (90 km/h)")
        try: gmaps = googlemaps.Client(key=st.secrets["google_api_key"])
        except Exception: st.error("Error: La clave de API de Google no está disponible en `secrets.toml`."); st.stop()
        col1, col2 = st.columns(2)
        with col1:
            origen_ida = st.text_input("Origen (ida)", key="origen_ida")
            destino_ida = st.text_input("Destino (ida)", key="destino_ida")
        with col2:
            origen_vuelta = st.text_input("Origen (vuelta)", key="origen_vuelta")
            destino_vuelta = st.text_input("Destino (vuelta)", key="destino_vuelta")
        if st.button("Calcular Tiempo por Distancia", type="primary"):
            if all([origen_ida, destino_ida, origen_vuelta, destino_vuelta]):
                with st.spinner('Calculando...'):
                    dist_ida, min_ida, err_ida = calcular_minutos_por_distancia(origen_ida, destino_ida, gmaps)
                    dist_vuelta, min_vuelta, err_vuelta = calcular_minutos_por_distancia(origen_vuelta, destino_vuelta, gmaps)
                    if err_ida or err_vuelta:
                        if err_ida: st.error(f"Error ida: {err_ida}"); 
                        if err_vuelta: st.error(f"Error vuelta: {err_vuelta}")
                    else:
                        def _cargo(minutos): return max(0, minutos - 30)
                        st.markdown("---")
                        es_identico = origen_ida.strip().lower() == destino_vuelta.strip().lower() and destino_ida.strip().lower() == origen_vuelta.strip().lower()
                        if es_identico:
                            st.info("ℹ️ Detectado trayecto de ida y vuelta idéntico.")
                            dist, mins = (dist_ida, min_ida) if min_ida >= min_vuelta else (dist_vuelta, min_vuelta)
                            st.session_state.calculation_results['aviso_pernocta'] = dist > 80
                            st.session_state.calculation_results['aviso_dieta'] = dist > 40 and not st.session_state.calculation_results['aviso_pernocta']
                            st.session_state.calculation_results['aviso_jornada'] = mins > 60
                            if st.session_state.calculation_results['aviso_pernocta']: st.warning(f"🛌 **Aviso Pernocta:** El trayecto ({dist:.1f} km) supera los 80km.")
                            elif st.session_state.calculation_results['aviso_dieta']: st.warning(f"⚠️ **Aviso Media Dieta:** El trayecto ({dist:.1f} km) supera los 40km.")
                            if st.session_state.calculation_results['aviso_jornada']: st.warning(f"⏰ **Aviso Jornada:** El trayecto ({mins} min) supera los 60 minutos.")
                            st.metric(f"TRAYECTO MÁS LARGO ({dist:.1f} km)", f"{_cargo(mins)} min a cargo", f"Tiempo total: {mins} min", delta_color="off")
                            total_final = _cargo(mins) * 2
                        else:
                            st.session_state.calculation_results['aviso_pernocta'] = dist_ida > 80 or dist_vuelta > 80
                            st.session_state.calculation_results['aviso_dieta'] = (dist_ida > 40 or dist_vuelta > 40) and not st.session_state.calculation_results['aviso_pernocta']
                            st.session_state.calculation_results['aviso_jornada'] = min_ida > 60 or min_vuelta > 60
                            if st.session_state.calculation_results['aviso_pernocta']: st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80km.")
                            elif st.session_state.calculation_results['aviso_dieta']: st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km.")
                            if st.session_state.calculation_results['aviso_jornada']: st.warning("⏰ **Aviso Jornada:** Uno o ambos trayectos superan los 60 minutos.")
                            st.metric(f"IDA: {dist_ida:.1f} km", f"{_cargo(min_ida)} min a cargo", f"Tiempo total: {min_ida} min", delta_color="off")
                            st.metric(f"VUELTA: {dist_vuelta:.1f} km", f"{_cargo(min_vuelta)} min a cargo", f"Tiempo total: {min_vuelta} min", delta_color="off")
                            total_final = _cargo(min_ida) + _cargo(min_vuelta)
                        st.markdown("---")
                        st.success(f"**Minutos totales de desplazamiento a cargo:** {total_final}")
                        mostrar_horas_de_salida(total_final)
                        st.session_state.calculation_results['total_minutos'] = total_final
                        if st.button("📧 Enviar mail al equipo", key="btn_gmaps_mail"):
                            st.session_state.page = 'email_form'
                            st.rerun()
            else:
                st.warning("Por favor, rellene las cuatro direcciones.")

# --- PÁGINA DE EMAIL ---
def email_form_app():
    st.title("📧 Redactar y Enviar Notificación")
    if st.button("⬅️ Volver a la calculadora"): st.session_state.page = 'calculator'; st.rerun()
    st.markdown("---")
    
    employees_df = cargar_datos_empleados()
    if employees_df is None: return

    st.header("1. Selecciona Destinatarios")
    col1, col2 = st.columns(2)
    with col1:
        delegacion_sel = st.selectbox("Filtrar por Delegación:", employees_df['PROVINCIA'].unique())
    with col2:
        equipos_en_delegacion = employees_df[employees_df['PROVINCIA'] == delegacion_sel]['EQUIPO'].unique()
        equipo_sel = st.selectbox("Filtrar por Equipo:", equipos_en_delegacion)
    
    personas_disponibles = employees_df[(employees_df['PROVINCIA'] == delegacion_sel) & (employees_df['EQUIPO'] == equipo_sel)]
    
    nombres_seleccionados = st.multiselect(
        "Añadir o quitar personas:",
        options=personas_disponibles['NOMBRE COMPLETO'].tolist(),
        placeholder="Selecciona uno o más trabajadores"
    )
    
    if not nombres_seleccionados:
        st.info("Selecciona al menos un destinatario para continuar.")
        return

    destinatarios_df = employees_df[employees_df['NOMBRE COMPLETO'].isin(nombres_seleccionados)]
    recipient_emails = destinatarios_df['EMAIL'].tolist()

    def crear_saludo(nombres):
        if not nombres: return "Hola,"
        nombres_cortos = [name.split()[0] for name in nombres]
        if len(nombres_cortos) == 1: return f"Hola {nombres_cortos[0]},"
        return f"Hola {', '.join(nombres_cortos[:-1])} y {nombres_cortos[-1]},"

    saludo = crear_saludo(nombres_seleccionados)
    
    st.info(f"Se enviará un correo a: **{', '.join(nombres_seleccionados)}**")

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
        cuerpo_pred = f"{saludo}\n\nEl cálculo de desplazamiento para hoy, {res.get('fecha', '')}, ha generado un aviso por superar los 80km, lo que podría implicar una pernocta.\n\nPor favor, revisa la planificación y gestiona la reserva de hotel si es necesario.\n\nSaludos,\n{st.session_state['username']}"

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