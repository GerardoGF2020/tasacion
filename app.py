"""
Aplicación Principal Streamlit integrada con el Sistema de Autenticación y RBAC.
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

# 1. Configuración de página adaptable
st.set_page_config(
    page_title="Sistema de Gestión y Operaciones",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inyección de estilos táctiles y responsivos para Android / PC
inyectar_css_responsivo()

# 3. Inicializar variables de sesión
init_session()

# ==============================================================================
# BARRERA DE SEGURIDAD (GATEWAY DE AUTENTICACIÓN)
# ==============================================================================
usuario = usuario_conectado()

if not usuario:
    # Si no hay sesión activa, bloquea la app y muestra el formulario de login/registro
    render_login_ui()
    st.stop()

# ==============================================================================
# BARRA LATERAL (PERFIL DE USUARIO Y NAVEGACIÓN)
# ==============================================================================
render_sidebar_usuario()

rol_actual = usuario.get("rol", "lector")

# Definición de páginas disponibles según el rol (RBAC)
opciones_menu = []

if rol_actual == "admin":
    opciones_menu = [
        "📊 Dashboard Principal",
        "⚙️ Operaciones y Carga",
        "📈 Reportes y Estadísticas",
        "⚙️ Panel de Administración"
    ]
elif rol_actual == "operador":
    opciones_menu = [
        "📊 Dashboard Principal",
        "⚙️ Operaciones y Carga",
        "📈 Reportes y Estadísticas"
    ]
elif rol_actual == "lector":
    opciones_menu = [
        "📊 Dashboard Principal",
        "📈 Reportes y Estadísticas"
    ]

st.sidebar.markdown("### 📌 Módulos")
modulo_seleccionado = st.sidebar.radio(
    "Seleccione una sección:",
    options=opciones_menu,
    label_visibility="collapsed"
)

# Advertencia de primer inicio si debe cambiar su clave
if usuario.get("debe_cambiar_password"):
    st.warning("⚠️ **Atención:** Está utilizando una contraseña provisional. Por favor, cámbiela en el menú de la barra lateral ('🔑 Cambiar mi contraseña').")

# ==============================================================================
# CONTENIDO MODULAR SEGÚN EL ROL
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. DASHBOARD PRINCIPAL (Visible para todos los roles)
# ------------------------------------------------------------------------------
if modulo_seleccionado == "📊 Dashboard Principal":
    st.markdown(f"## 👋 Bienvenido, {usuario.get('nombre')}")
    st.caption(f"Rol asignado: **{usuario.get('rol').upper()}** | Identificador: `{usuario.get('email')}`")
    
    st.write("")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estado de Conexión", "🟢 Activo", delta="Sesión Segura")
    with col2:
        st.metric("Nivel de Acceso", usuario.get("rol").capitalize(), delta="RBAC Habilitado")
    with col3:
        st.metric("Dispositivo", "Adaptable", delta="Touch / Android OK")

    st.markdown("---")
    st.info("💡 Este sistema cuenta con almacenamiento seguro de contraseñas con **Salt y PBKDF2-SHA256**, autoregistro de operadores con autorización previa del administrador y control de acceso basado en roles.")

# ------------------------------------------------------------------------------
# 2. OPERACIONES Y CARGA (Exclusivo para Operador y Admin)
# ------------------------------------------------------------------------------
elif modulo_seleccionado == "⚙️ Operaciones y Carga":
    if not tiene_rol(["admin", "operador"]):
        st.error("⛔ No tienes permisos para acceder al módulo de carga operativa.")
        st.stop()

    st.markdown("## ⚙️ Módulo de Operaciones y Carga de Datos")
    st.caption("Espacio de trabajo habilitado para roles con permisos de escritura (Operador y Admin).")

    with st.form("form_carga_operaciones"):
        st.markdown("#### Registro de Nuevo Expediente / Tarea")
        titulo_tarea = st.text_input("Título o Referencia:", placeholder="Ej: Inspección Técnica Lote 45")
        tipo_tarea = st.selectbox("Categoría:", ["Inspección", "Mantenimiento", "Auditoría de Campo", "Tasación"])
        descripcion = st.text_area("Observaciones técnicas:")
        
        btn_guardar_tarea = st.form_submit_button("💾 Guardar Registro", use_container_width=True, type="primary")

    if btn_guardar_tarea:
        if not titulo_tarea:
            st.warning("Por favor ingrese al menos un título o referencia.")
        else:
            st.success(f"✅ Registro '{titulo_tarea}' guardado correctamente por el operador {usuario.get('nombre')}.")

# ------------------------------------------------------------------------------
# 3. REPORTES Y ESTADÍSTICAS (Visible para todos: Lector, Operador, Admin)
# ------------------------------------------------------------------------------
elif modulo_seleccionado == "📈 Reportes y Estadísticas":
    st.markdown("## 📈 Informes y Visualización de Métricas")
    st.caption("Módulo de solo lectura disponible para todos los perfiles de usuario.")

    # Gráfico y métricas de demostración
    import pandas as pd
    import numpy as np

    chart_data = pd.DataFrame(
        np.random.randn(20, 3),
        columns=["Operaciones", "Rendimiento", "Eficiencia"]
    )
    st.line_chart(chart_data)

    st.dataframe(chart_data.head(5), use_container_width=True)

# ------------------------------------------------------------------------------
# 4. PANEL DE ADMINISTRACIÓN (Exclusivo para Admin)
# ------------------------------------------------------------------------------
elif modulo_seleccionado == "⚙️ Panel de Administración":
    if not tiene_rol(["admin"]):
        st.error("⛔ Acceso denegado. Este panel está reservado exclusivamente para Administradores.")
        st.stop()

    # Invoca el componente administrativo completo definido en auth.py
    render_panel_admin()
