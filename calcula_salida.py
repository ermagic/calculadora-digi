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
                
                # --- INICIO DE LA MODIFICACIÓN (Pestaña CSV) ---
                
                # 1. La condición ahora comprueba los MINUTOS, no la distancia.
                st.session_state.calculation_results['aviso_pernocta'] = min_entrada > 80 or min_salida > 80
                st.session_state.calculation_results['aviso_dieta'] = (dist_entrada > 40 or dist_salida > 40)

                # 2. Se actualiza el mensaje y se usa 'if' para que sea independiente.
                if st.session_state.calculation_results['aviso_pernocta']: 
                    st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80 minutos. Comprueba posible pernocta.")
                
                # 3. Se cambia 'elif' por 'if' para que los avisos no sean excluyentes.
                if st.session_state.calculation_results['aviso_dieta'] and not st.session_state.calculation_results['aviso_pernocta']:
                    st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")

                # --- FIN DE LA MODIFICACIÓN ---

                st.session_state.calculation_results['aviso_jornada'] = min_entrada > 60 or min_salida > 60
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
        st.header("Cálculo por distancia (90 km/h)")
        try: gmaps = googlemaps.Client(key=st.secrets["google_api_key"])
        except Exception: st.error("Error: La clave de API de Google no está disponible en `secrets.toml`."); st.stop()
        
        col1, col2 = st.columns(2)
        with col1:
            origen_ida = st.text_input("Origen (ida)", key="origen_ida", on_change=lambda: st.session_state.update(gmaps_results=None))
            destino_ida = st.text_input("Destino (ida)", key="destino_ida", on_change=lambda: st.session_state.update(gmaps_results=None))
        with col2:
            origen_vuelta = st.text_input("Origen (vuelta)", key="origen_vuelta", on_change=lambda: st.session_state.update(gmaps_results=None))
            destino_vuelta = st.text_input("Destino (vuelta)", key="destino_vuelta", on_change=lambda: st.session_state.update(gmaps_results=None))
        
        if st.button("Calcular Tiempo por Distancia", type="primary"):
            if all([origen_ida, destino_ida, origen_vuelta, destino_vuelta]):
                with st.spinner('Calculando...'):
                    dist_ida, min_ida, err_ida = calcular_minutos_por_distancia(origen_ida, destino_ida, gmaps)
                    dist_vuelta, min_vuelta, err_vuelta = calcular_minutos_por_distancia(origen_vuelta, destino_vuelta, gmaps)
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
                
                # --- INICIO DE LA MODIFICACIÓN (Pestaña Google Maps - Idéntico) ---
                st.session_state.calculation_results['aviso_pernocta'] = mins > 80
                st.session_state.calculation_results['aviso_dieta'] = dist > 40

                if st.session_state.calculation_results['aviso_pernocta']: 
                    st.warning(f"🛌 **Aviso Pernocta:** El trayecto ({mins} min) supera los 80 minutos. Comprueba posible pernocta.")
                
                if st.session_state.calculation_results['aviso_dieta'] and not st.session_state.calculation_results['aviso_pernocta']:
                    st.warning(f"⚠️ **Aviso Media Dieta:** El trayecto ({dist:.1f} km) supera los 40km. Comprueba el tipo de jornada.")
                # --- FIN DE LA MODIFICACIÓN ---

                st.session_state.calculation_results['aviso_jornada'] = mins > 60
                if st.session_state.calculation_results['aviso_jornada']: 
                    st.warning(f"⏰ **Aviso Jornada:** El trayecto ({mins} min) supera los 60 minutos. Comprueba el tipo de jornada.")
                
                st.metric(f"TRAYECTO MÁS LARGO ({dist:.1f} km)", f"{_cargo(mins)} min a cargo", f"Tiempo total: {mins} min", delta_color="off")
                total_final = _cargo(mins) * 2
            else:
                # --- INICIO DE LA MODIFICACIÓN (Pestaña Google Maps - Distinto) ---
                st.session_state.calculation_results['aviso_pernocta'] = res['min_ida'] > 80 or res['min_vuelta'] > 80
                st.session_state.calculation_results['aviso_dieta'] = (res['dist_ida'] > 40 or res['dist_vuelta'] > 40)

                if st.session_state.calculation_results['aviso_pernocta']: 
                    st.warning("🛌 **Aviso Pernocta:** Uno o ambos trayectos superan los 80 minutos. Comprueba posible pernocta.")

                if st.session_state.calculation_results['aviso_dieta'] and not st.session_state.calculation_results['aviso_pernocta']:
                    st.warning("⚠️ **Aviso Media Dieta:** Uno o ambos trayectos superan los 40km. Comprueba el tipo de jornada.")
                # --- FIN DE LA MODIFICACIÓN ---
                
                st.session_state.calculation_results['aviso_jornada'] = res['min_ida'] > 60 or res['min_vuelta'] > 60
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