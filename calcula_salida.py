# REEMPLAZA LA FUNCIÓN ANTIGUA CON ESTA
def full_calculator_app():
    st.image("logo_digi.png", width=250)
    st.title(f"Bienvenido, {st.session_state['username']}!")
    tab1, tab2 = st.tabs([" Cálculo Dentro de la Provincia (CSV) ", "  Cálculo Interprovincial (Google)  "])
    
    with tab1:
        st.header("Cálculo Dentro de la Provincia (tiempos.csv)")
        # Ahora la función devuelve nuestro nuevo diccionario de datos
        municipio_data, lista_municipios = cargar_datos_csv('tiempos.csv')
        
        if municipio_data and lista_municipios:
            st.markdown("---")

            # Usamos columnas para una mejor presentación
            col1, col2 = st.columns(2)

            with col1:
                mun_entrada = st.selectbox(
                    "Destino del comienzo de la jornada:",
                    lista_municipios, index=None, placeholder="Selecciona un municipio"
                )
                # Si se selecciona un municipio, mostramos su información
                if mun_entrada and mun_entrada in municipio_data:
                    info = municipio_data.get(mun_entrada)
                    st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

            with col2:
                mun_salida = st.selectbox(
                    "Destino del final de la jornada:",
                    lista_municipios, index=None, placeholder="Selecciona un municipio"
                )
                # Si se selecciona un municipio, mostramos su información
                if mun_salida and mun_salida in municipio_data:
                    info = municipio_data.get(mun_salida)
                    st.info(f"**Centro de Trabajo:** {info['centro_trabajo']}\n\n**Distancia:** {info['distancia']} km")

            # El resto del cálculo solo se ejecuta si se han seleccionado AMBOS municipios
            if mun_entrada and mun_salida:
                st.markdown("---") # Añadimos un separador visual
                
                # Obtenemos los datos del diccionario
                min_entrada = int(municipio_data[mun_entrada]['minutos'])
                min_salida = int(municipio_data[mun_salida]['minutos'])
                dist_entrada = float(municipio_data[mun_entrada]['distancia'])
                dist_salida = float(municipio_data[mun_salida]['distancia'])
                
                # La lógica de avisos y cálculo total no cambia
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

    # La Tab2 no ha sufrido ningún cambio
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
            def _cargo(minutos): return max(0, minutos - 30)
            st.markdown("---")
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