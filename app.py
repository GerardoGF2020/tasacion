"""
Aplicación Principal Streamlit integrada con el Sistema de Autenticación,
Gestión de Usuarios (RBAC) y Carga Colaborativa de Tasaciones.
Optimizado para ordenadores y teléfonos móviles Android.
"""

import streamlit as st
from auth import (
    init_session,
    usuario_conectado,
    tiene_rol,
    render_login_ui,
    render_sidebar_usuario,
    render_panel_admin,
    inyectar_css_responsivo
)
from expedientes import (
    cargar_expedientes,
    guardar_o_actualizar_expediente,
    eliminar_expediente
)

# 1. Configuración de página adaptable
st.set_page_config(
    page_title="Sistema de Tasaciones y Gestión",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inyección de estilos táctiles y responsivos para Android / PC
inyectar_css_responsivo()

# Estilos adicionales para navegación móvil prominente
st.markdown("""
<style>
/* Botón de barra lateral móvil bien visible */
[data-testid="collapsedControl"] {
    display: flex !important;
    background-color: #2563eb !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    margin: 6px !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.4) !important;
}
[data-testid="collapsedControl"] svg {
    fill: white !important;
    width: 24px !important;
    height: 24px !important;
}

/* Tarjetas de estado */
.card-metric {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# 3. Inicializar variables de sesión
init_session()

if "expediente_en_edicion" not in st.session_state:
    st.session_state.expediente_en_edicion = None

if "nav_modulo" not in st.session_state:
    st.session_state.nav_modulo = "📊 Dashboard"

# ==============================================================================
# BARRERA DE SEGURIDAD (GATEWAY DE AUTENTICACIÓN)
# ==============================================================================
usuario = usuario_conectado()

if not usuario:
    render_login_ui()
    st.stop()

# ==============================================================================
# BARRA LATERAL (PERFIL Y CONFIGURACIÓN)
# ==============================================================================
render_sidebar_usuario()

rol_actual = usuario.get("rol", "lector")

# Definición de módulos según rol
opciones_menu = ["📊 Dashboard"]

if rol_actual in ["admin", "operador"]:
    opciones_menu.append("📝 Cargar / Editar Tasación")
    opciones_menu.append("📁 Expedientes Compartidos")
elif rol_actual == "lector":
    opciones_menu.append("📁 Expedientes Compartidos")

if rol_actual == "admin":
    opciones_menu.append("⚙️ Panel de Administración")

# Sincronizar selección de navegación si se cambió en sidebar
st.sidebar.markdown("### 📌 Módulos")
modulo_sidebar = st.sidebar.radio(
    "Módulos:",
    options=opciones_menu,
    index=opciones_menu.index(st.session_state.nav_modulo) if st.session_state.nav_modulo in opciones_menu else 0,
    key="sb_nav_modulo",
    label_visibility="collapsed"
)
if modulo_sidebar != st.session_state.nav_modulo:
    st.session_state.nav_modulo = modulo_sidebar

# ==============================================================================
# BARRA DE NAVEGACIÓN SUPERIOR (100% VISIBLE EN CELULARES Y PC)
# ==============================================================================
# Cabecera principal con indicador de conexión
col_tit, col_ref = st.columns([3, 1])
with col_tit:
    st.markdown(f"### ⚖️ Sistema de Tasaciones y Metrología")
    st.caption(f"Conectado como: **{usuario.get('nombre')}** ({usuario.get('rol').upper()}) | 🟢 Sincronizado en la Nube")

with col_ref:
    if st.button("🔄 Sincronizar", use_container_width=True, help="Refrescar datos en vivo"):
        st.session_state.expediente_en_edicion = None
        st.rerun()

# MENÚ HORIZONTAL SIEMPRE PRESENTE EN LA PANTALLA PRINCIPAL
modulo_superior = st.radio(
    "Menú de Navegación:",
    options=opciones_menu,
    index=opciones_menu.index(st.session_state.nav_modulo) if st.session_state.nav_modulo in opciones_menu else 0,
    horizontal=True,
    key="top_nav_selector"
)
st.session_state.nav_modulo = modulo_superior

st.markdown("---")

modulo_seleccionado = st.session_state.nav_modulo

# ==============================================================================
# 1. DASHBOARD PRINCIPAL
# ==============================================================================
if modulo_seleccionado == "📊 Dashboard":
    expedientes = cargar_expedientes()
    total_exp = len(expedientes)
    a_medias = len([e for e in expedientes if "Borrador" in e.get("estado", "") or "medias" in e.get("estado", "").lower()])
    finalizados = len([e for e in expedientes if "Finalizada" in e.get("estado", "") or "Aprobada" in e.get("estado", "")])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Expedientes", total_exp, delta="Compartidos")
    with col2:
        st.metric("🟡 Tasaciones a Medias", a_medias, delta="Para completar", delta_color="inverse")
    with col3:
        st.metric("🟢 Tasaciones Finalizadas", finalizados, delta="Validadas")

    st.write("")
    st.markdown("#### ⚡ Acceso Rápido:")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if tiene_rol(["admin", "operador"]):
            if st.button("➕ Iniciar Nueva Tasación en Campo", use_container_width=True, type="primary"):
                st.session_state.expediente_en_edicion = None
                st.session_state.nav_modulo = "📝 Cargar / Editar Tasación"
                st.rerun()
    with col_a2:
        if st.button("📁 Ver Expedientes Compartidos en Vivo", use_container_width=True):
            st.session_state.nav_modulo = "📁 Expedientes Compartidos"
            st.rerun()

    st.markdown("---")
    st.info("💡 **Trabajo Colaborativo:** Si un operador inicia una tasación en el campo con su celular y la guarda como *Borrador*, cualquier otro usuario o perito puede abrirla desde su PC o móvil y completarla parcialmente o en su totalidad.")

# ==============================================================================
# 2. CARGAR / EDITAR TASACIÓN (COLABORATIVO ENTRE OPERADORES Y PERITOS)
# ==============================================================================
elif modulo_seleccionado == "📝 Cargar / Editar Tasación":
    if not tiene_rol(["admin", "operador"]):
        st.error("⛔ Acceso restringido. Solo Administradores y Operadores pueden cargar datos.")
        st.stop()

    exp_edit = st.session_state.expediente_en_edicion or {}
    es_edicion = bool(exp_edit.get("id"))

    if es_edicion:
        st.markdown(f"## ✏️ Editando Tasación: `{exp_edit.get('id')}`")
        st.caption(f"Iniciada por: **{exp_edit.get('creado_por')}** el {exp_edit.get('fecha_creacion')}. Cualquier cambio se sincronizará inmediatamente.")
        if st.button("❌ Cancelar edición y crear una nueva"):
            st.session_state.expediente_en_edicion = None
            st.rerun()
    else:
        st.markdown("## ➕ Carga de Nueva Tasación")
        st.caption("Complete los datos disponibles. Puede guardarla a medias para que otro colega la continúe luego.")

    with st.form("form_carga_tasacion"):
        col_id, col_tit = st.columns([1, 2])
        with col_id:
            siguiente_num = len(cargar_expedientes()) + 1
            default_id = exp_edit.get("id") or f"TAS-2026-{siguiente_num:03d}"
            f_id = st.text_input("N° de Expediente:", value=default_id)
        with col_tit:
            f_titulo = st.text_input("Título / Referencia:", value=exp_edit.get("titulo", ""), placeholder="Ej: Loteo Barrio Bernel - Lote 14")

        col_tipo, col_dir = st.columns([1, 2])
        with col_tipo:
            tipos = ["Terreno Urbano", "Casa Residencial", "Departamento", "Local Comercial", "Galpón Industrial", "Fracción Rural", "Maquinaria / Rodado"]
            tipo_actual = exp_edit.get("tipo_inmueble", "Terreno Urbano")
            idx_t = tipos.index(tipo_actual) if tipo_actual in tipos else 0
            f_tipo = st.selectbox("Tipo de Inmueble:", tipos, index=idx_t)
        with col_dir:
            f_direccion = st.text_input("Ubicación / Dirección:", value=exp_edit.get("direccion", ""), placeholder="Ej: Barrio Bernel, Yerba Buena")

        st.markdown("##### 📐 Medidas y Metrología:")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            f_frente = st.number_input("Frente (m):", min_value=0.0, value=float(exp_edit.get("frente", 10.0)), step=0.5)
        with col_m2:
            f_fondo = st.number_input("Fondo (m):", min_value=0.0, value=float(exp_edit.get("fondo", 30.0)), step=0.5)
        with col_m3:
            f_sup = st.number_input("Superficie Total (m²):", min_value=0.0, value=float(exp_edit.get("superficie_m2", f_frente * f_fondo)), step=1.0)

        st.markdown("##### 💰 Estimación de Valor:")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            f_val_unit = st.number_input("Valor Unitario Estimado ($ / m²):", min_value=0.0, value=float(exp_edit.get("valor_unitario", 75000.0)), step=1000.0)
        with col_p2:
            calc_val_tot = float(exp_edit.get("valor_total", f_sup * f_val_unit))
            f_val_total = st.number_input("Valor Total Tasado ($):", min_value=0.0, value=calc_val_tot if calc_val_tot > 0 else (f_sup * f_val_unit), step=50000.0)

        f_obs = st.text_area("Observaciones técnicas y relevamiento de campo:", value=exp_edit.get("observaciones", ""), placeholder="Indicar estado del terreno, servicios disponibles, mejoras, etc.")

        st.markdown("##### 📌 Estado de la Tasación:")
        estados = ["🟡 Borrador (A medias)", "🟠 En Revisión / Peritaje", "🟢 Finalizada"]
        estado_act = exp_edit.get("estado", "🟡 Borrador (A medias)")
        idx_e = estados.index(estado_act) if estado_act in estados else 0
        f_estado = st.radio("Definir estado:", estados, index=idx_e, horizontal=True)

        st.write("")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            btn_guardar_borrador = st.form_submit_button("💾 Guardar como Borrador (A medias)", use_container_width=True)
        with col_b2:
            btn_guardar_finalizado = st.form_submit_button("✅ Guardar como Tasación Finalizada", use_container_width=True, type="primary")

    if btn_guardar_borrador or btn_guardar_finalizado:
        if not f_titulo.strip() or not f_id.strip():
            st.error("El N° de Expediente y el Título son obligatorios.")
        else:
            estado_elegido = "🟢 Finalizada" if btn_guardar_finalizado else ("🟡 Borrador (A medias)" if btn_guardar_borrador else f_estado)
            datos_guardar = {
                "id": f_id.strip(),
                "titulo": f_titulo.strip(),
                "tipo_inmueble": f_tipo,
                "direccion": f_direccion.strip(),
                "frente": f_frente,
                "fondo": f_fondo,
                "superficie_m2": f_sup,
                "valor_unitario": f_val_unit,
                "valor_total": f_val_total,
                "estado": estado_elegido,
                "observaciones": f_obs.strip()
            }
            ok_g, msg_g = guardar_o_actualizar_expediente(datos_guardar, usuario.get("nombre"))
            if ok_g:
                st.success(msg_g)
                st.session_state.expediente_en_edicion = None
                st.session_state.nav_modulo = "📁 Expedientes Compartidos"
                st.rerun()
            else:
                st.error(msg_g)

# ==============================================================================
# 3. EXPEDIENTES COMPARTIDOS (BANDEJA EN VIVO)
# ==============================================================================
elif modulo_seleccionado == "📁 Expedientes Compartidos":
    st.markdown("## 📁 Bandeja de Expedientes y Tasaciones")
    st.caption("Todos los registros guardados en la nube. Seleccione cualquiera para verlo o continuarlo.")

    expedientes = cargar_expedientes()

    if not expedientes:
        st.info("No hay expedientes registrados aún. Presione '➕ Iniciar Nueva Tasación' para comenzar.")
    else:
        # Filtro de estado
        col_filtro, col_cant = st.columns([3, 1])
        with col_filtro:
            filtro = st.radio("Filtrar por estado:", ["Todos", "Solo Borradores (A medias)", "Solo Finalizadas"], horizontal=True)

        exp_filtrados = expedientes
        if filtro == "Solo Borradores (A medias)":
            exp_filtrados = [e for e in expedientes if "Borrador" in e.get("estado", "") or "medias" in e.get("estado", "").lower()]
        elif filtro == "Solo Finalizadas":
            exp_filtrados = [e for e in expedientes if "Finalizada" in e.get("estado", "")]

        # Tabla resumen
        filas = []
        for e in exp_filtrados:
            filas.append({
                "N° Expediente": e.get("id"),
                "Título": e.get("titulo"),
                "Tipo": e.get("tipo_inmueble"),
                "Superficie": f"{e.get('superficie_m2', 0):,.1f} m²",
                "Valor Total": f"${e.get('valor_total', 0):,.0f}",
                "Estado": e.get("estado"),
                "Iniciado Por": e.get("creado_por"),
                "Última Modif.": e.get("fecha_modificacion")
            })
        st.dataframe(filas, use_container_width=True)

        st.write("---")
        st.markdown("#### 🔍 Abrir o Continuar Tasación:")
        
        col_sel_exp, col_btn_exp = st.columns([3, 1])
        with col_sel_exp:
            opciones_exp = {e["id"]: f"{e['id']} - {e.get('titulo')} [{e.get('estado')}]" for e in expedientes}
            id_seleccionado = st.selectbox("Seleccione un expediente:", options=list(opciones_exp.keys()), format_func=lambda x: opciones_exp[x])

        exp_detalle = next((e for e in expedientes if e["id"] == id_seleccionado), None)

        if exp_detalle:
            with st.expander(f"👁️ Ver Ficha Técnica de {exp_detalle.get('id')}", expanded=True):
                st.markdown(f"**Título:** {exp_detalle.get('titulo')}")
                st.markdown(f"**Ubicación:** {exp_detalle.get('direccion')}")
                st.markdown(f"**Medidas:** Frente: {exp_detalle.get('frente')} m | Fondo: {exp_detalle.get('fondo')} m | Superficie: {exp_detalle.get('superficie_m2')} m²")
                st.markdown(f"**Valor Estimado:** ${exp_detalle.get('valor_total', 0):,.2f} (${exp_detalle.get('valor_unitario', 0):,.2f} / m²)")
                st.markdown(f"**Estado:** {exp_detalle.get('estado')}")
                st.markdown(f"**Observaciones:** {exp_detalle.get('observaciones') or 'Sin observaciones adicionales.'}")

            col_acc1, col_acc2 = st.columns(2)
            with col_acc1:
                if tiene_rol(["admin", "operador"]):
                    if st.button("✏️ Continuar / Editar esta Tasación", use_container_width=True, type="primary"):
                        st.session_state.expediente_en_edicion = exp_detalle
                        st.session_state.nav_modulo = "📝 Cargar / Editar Tasación"
                        st.rerun()

            with col_acc2:
                if tiene_rol(["admin"]):
                    if st.button("🗑️ Eliminar Expediente", use_container_width=True):
                        ok_el, msg_el = eliminar_expediente(id_seleccionado)
                        if ok_el:
                            st.success(msg_el)
                            st.rerun()
                        else:
                            st.error(msg_el)

# ==============================================================================
# 4. PANEL DE ADMINISTRACIÓN (EXCLUSIVO ADMIN)
# ==============================================================================
elif modulo_seleccionado == "⚙️ Panel de Administración":
    if not tiene_rol(["admin"]):
        st.error("⛔ Acceso denegado. Este panel está reservado exclusivamente para Administradores.")
        st.stop()

    render_panel_admin()
