def main_app():
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")

    tab1, tab2 = st.tabs([" Cáculo Local (CSV) ", "  Cálculo Interprovincial (Google)  "])

    # TAB 1
    with tab1:
        st.header("Cálculo desde archivo local (tiempos.csv)")
        municipios_min, lista_municipios = cargar_datos_csv()
        if municipios_min and lista_municipios:
            st.markdown("---")
            mun_entrada = st.selectbox("Destino del comienzo de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")
            mun_salida = st.selectbox("Destino del final de la jornada:", lista_municipios, index=None, placeholder="Selecciona un municipio")

            if mun_entrada and mun_salida:
                min_entrada = int(municipios_min.get(mun_entrada, 0))
                min_salida = int(municipios_min.get(mun_salida, 0))
                total = min_entrada + min_salida

                st.info(f"Minutos (entrada): **{min_entrada}** | Minutos (salida): **{min_salida}**")
                st.success(f"**Minutos totales de desplazamiento:** {total}")
                
                dia_semana_hoy = dt.date.today().weekday()
                hora_base = dt.time(14, 0) if dia_semana_hoy == 4 else dt.time(15, 0)
                salida_dt = dt.datetime.combine(dt.date.today(), hora_base) - dt.timedelta(minutes=total)
                st.success(f"## Hora de salida hoy: {salida_dt.strftime('%H:%M')}")
        else:
            st.info("Esperando a que el archivo 'tiempos.csv' sea válido o esté disponible.")

    # TAB 2
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
                        st.success(f"## Hora de salida hoy: {salida_dt.strftime('%H:%M')}")

                        # --- NUEVOS MAPAS EMBEBIDOS ---
                        st.markdown("### 🗺️ Mapa de ruta de ida")
                        mapa_ida_url = generar_mapa_embed(origen_ida, destino_ida, st.secrets["google_api_key"])
                        st.components.v1.iframe(mapa_ida_url, height=400)

                        st.markdown("### 🗺️ Mapa de ruta de vuelta")
                        mapa_vuelta_url = generar_mapa_embed(origen_vuelta, destino_vuelta, st.secrets["google_api_key"])
                        st.components.v1.iframe(mapa_vuelta_url, height=400)