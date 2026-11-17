"""
Módulo de Autenticación, Seguridad y Gestión de Usuarios para Streamlit.
Soporta almacenamiento JSON, PBKDF2-SHA256 con Salt aleatorio, RBAC (Roles)
y vistas optimizadas para PC y dispositivos móviles Android.
"""

import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
import streamlit as st

# Ruta al archivo de almacenamiento persistente
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.json")

# Roles del sistema
ROLES = ["admin", "operador", "lector"]
ROLES_EMOJI = {
    "admin": "👑 Administrador",
    "operador": "⚙️ Operador",
    "lector": "👁️ Lector / Auditor"
}


# ==============================================================================
# 1. CRIPTOGRAFÍA Y GESTIÓN DE CONTRASEÑAS (SALT + PBKDF2-SHA256)
# ==============================================================================

def generar_salt() -> str:
    """Genera un salt criptográficamente seguro de 16 bytes en hexadecimal."""
    return secrets.token_hex(16)


def hashear_password(password: str, salt: str) -> str:
    """
    Genera un hash seguro utilizando PBKDF2-HMAC-SHA256 con 100.000 iteraciones.
    Estándar recomendado por NIST, seguro contra ataques de diccionario y rainbow tables.
    """
    salt_bytes = salt.encode("utf-8")
    pwd_bytes = password.encode("utf-8")
    key = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, 100000)
    return key.hex()


def verificar_password(password: str, salt: str, password_hash: str) -> bool:
    """Compara una contraseña ingresada contra el hash almacenado en tiempo constante."""
    hash_calculado = hashear_password(password, salt)
    return secrets.compare_digest(hash_calculado, password_hash)


# ==============================================================================
# 2. CAPA DE PERSISTENCIA (JSON)
# ==============================================================================

def inicializar_almacenamiento() -> dict:
    """
    Garantiza que el archivo usuarios.json exista con la estructura requerida.
    Crea el usuario administrador por defecto si es la primera ejecución.
    """
    estructura_base = {
        "usuarios": {},
        "pendientes": {},
        "recuperaciones": {}
    }

    if not os.path.exists(DB_FILE):
        # Crear usuario admin inicial por defecto
        salt_admin = generar_salt()
        hash_admin = hashear_password("admin123", salt_admin)
        
        estructura_base["usuarios"]["admin@empresa.com"] = {
            "nombre": "Administrador Inicial",
            "email": "admin@empresa.com",
            "username": "admin",
            "salt": salt_admin,
            "hash": hash_admin,
            "rol": "admin",
            "activo": True,
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "debe_cambiar_password": True
        }
        guardar_db(estructura_base)
        return estructura_base

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Asegurar claves mínimas
            for key in ["usuarios", "pendientes", "recuperaciones"]:
                if key not in data:
                    data[key] = {}
            return data
    except Exception:
        guardar_db(estructura_base)
        return estructura_base


def cargar_db() -> dict:
    """Lee y retorna la base de datos de usuarios."""
    return inicializar_almacenamiento()


def guardar_db(data: dict) -> None:
    """Escribe de forma segura en usuarios.json."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==============================================================================
# 3. LÓGICA DE NEGOCIO (LOGIN, REGISTRO, AUTORIZACIÓN, RESETEO)
# ==============================================================================

def registrar_solicitud_cuenta(nombre: str, email: str, password: str) -> tuple[bool, str]:
    """Registra un nuevo operador en estado 'pendiente' de autorización."""
    email_clean = email.strip().lower()
    db = cargar_db()

    if not email_clean or not nombre.strip() or not password:
        return False, "Todos los campos son obligatorios."

    if email_clean in db["usuarios"]:
        return False, "El correo ya se encuentra registrado y activo."

    if email_clean in db["pendientes"]:
        return False, "Ya existe una solicitud pendiente con este correo electrónico."

    salt = generar_salt()
    pwd_hash = hashear_password(password, salt)

    db["pendientes"][email_clean] = {
        "nombre": nombre.strip(),
        "email": email_clean,
        "salt": salt,
        "hash": pwd_hash,
        "fecha_solicitud": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    guardar_db(db)
    return True, "Solicitud enviada con éxito. Un administrador debe autorizar tu cuenta para que puedas ingresar."


def autenticar_usuario(identificador: str, password: str) -> tuple[bool, str, dict | None]:
    """
    Autentica al usuario por correo o nombre de usuario.
    Retorna (éxito, mensaje, datos_usuario).
    """
    id_clean = identificador.strip().lower()
    db = cargar_db()

    # 1. Comprobar si está en solicitudes pendientes
    for pend_email, pend_data in db["pendientes"].items():
        if id_clean == pend_email or id_clean == pend_data.get("email", "").lower():
            return False, "Tu cuenta fue registrada pero aún se encuentra pendiente de autorización por el Administrador.", None

    # 2. Buscar en usuarios activos (por email o por username)
    user_encontrado = None
    user_email = None

    for email, data in db["usuarios"].items():
        if email.lower() == id_clean or data.get("username", "").lower() == id_clean:
            user_encontrado = data
            user_email = email
            break

    if not user_encontrado:
        return False, "Correo electrónico o contraseña incorrectos.", None

    if not user_encontrado.get("activo", True):
        return False, "Esta cuenta ha sido desactivada por el Administrador.", None

    # 3. Validar contraseña
    if not verificar_password(password, user_encontrado["salt"], user_encontrado["hash"]):
        return False, "Correo electrónico o contraseña incorrectos.", None

    # Copia segura de datos de usuario para la sesión
    usuario_sesion = {
        "email": user_email,
        "nombre": user_encontrado.get("nombre", user_email),
        "username": user_encontrado.get("username", user_email),
        "rol": user_encontrado.get("rol", "operador"),
        "debe_cambiar_password": user_encontrado.get("debe_cambiar_password", False)
    }
    return True, f"¡Bienvenido, {usuario_sesion['nombre']}!", usuario_sesion


def autorizar_solicitud(email: str, rol: str = "operador") -> tuple[bool, str]:
    """El Administrador aprueba una solicitud pendiente y le asigna un rol."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["pendientes"]:
        return False, "La solicitud seleccionada ya no se encuentra pendiente."

    solicitud = db["pendientes"].pop(email_clean)
    db["usuarios"][email_clean] = {
        "nombre": solicitud["nombre"],
        "email": email_clean,
        "username": email_clean.split("@")[0],
        "salt": solicitud["salt"],
        "hash": solicitud["hash"],
        "rol": rol if rol in ROLES else "operador",
        "activo": True,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "debe_cambiar_password": False
    }
    guardar_db(db)
    return True, f"Cuenta de {solicitud['nombre']} ({email_clean}) autorizada con rol {ROLES_EMOJI.get(rol, rol)}."


def crear_usuario_directo(nombre: str, email: str, password: str, rol: str = "operador") -> tuple[bool, str]:
    """El Administrador da de alta directamente a un usuario sin requerir solicitud previa."""
    email_clean = email.strip().lower()
    db = cargar_db()

    if not email_clean or not nombre.strip() or not password:
        return False, "Todos los campos son obligatorios."

    if email_clean in db["usuarios"]:
        return False, "Ya existe un usuario con este correo electrónico."

    if len(password) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."

    salt = generar_salt()
    pwd_hash = hashear_password(password, salt)

    if email_clean in db.get("pendientes", {}):
        del db["pendientes"][email_clean]

    db["usuarios"][email_clean] = {
        "nombre": nombre.strip(),
        "email": email_clean,
        "username": email_clean.split("@")[0],
        "salt": salt,
        "hash": pwd_hash,
        "rol": rol if rol in ROLES else "operador",
        "activo": True,
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "debe_cambiar_password": True
    }
    guardar_db(db)
    return True, f"Usuario {nombre.strip()} ({email_clean}) dado de alta con éxito con rol {ROLES_EMOJI.get(rol, rol)}."


def cambiar_estado_activo(email: str, nuevo_estado: bool) -> tuple[bool, str]:
    """Suspende (baja temporal) o reactiva la cuenta de un usuario."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        return False, "Usuario no encontrado."

    if not nuevo_estado and db["usuarios"][email_clean].get("rol") == "admin":
        admins_activos = [u for u in db["usuarios"].values() if u.get("rol") == "admin" and u.get("activo", True)]
        if len(admins_activos) <= 1:
            return False, "No puedes dar de baja al único administrador activo del sistema."

    db["usuarios"][email_clean]["activo"] = nuevo_estado
    guardar_db(db)
    estado_str = "🟢 Activada (Alta)" if nuevo_estado else "🔴 Suspendida (Baja)"
    return True, f"La cuenta de {db['usuarios'][email_clean].get('nombre')} ahora está {estado_str}."


def rechazar_solicitud(email: str) -> tuple[bool, str]:
    """El Administrador descarta una solicitud pendiente."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean in db["pendientes"]:
        nombre = db["pendientes"][email_clean]["nombre"]
        del db["pendientes"][email_clean]
        guardar_db(db)
        return True, f"Solicitud de {nombre} ({email_clean}) rechazada."
    return False, "La solicitud no fue encontrada."


def actualizar_rol_usuario(email: str, nuevo_rol: str) -> tuple[bool, str]:
    """Cambia el nivel de permisos de un usuario existente."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        return False, "Usuario no encontrado."

    if nuevo_rol not in ROLES:
        return False, "Rol no válido."

    db["usuarios"][email_clean]["rol"] = nuevo_rol
    guardar_db(db)
    return True, f"Rol actualizado a {ROLES_EMOJI.get(nuevo_rol, nuevo_rol)}."


def resetear_password_admin(email: str, nueva_pass: str) -> tuple[bool, str]:
    """Un Administrador fuerza el reseteo de la clave de un usuario."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        return False, "Usuario no encontrado."

    if len(nueva_pass) < 4:
        return False, "La contraseña debe tener al menos 4 caracteres."

    salt = generar_salt()
    pwd_hash = hashear_password(nueva_pass, salt)
    db["usuarios"][email_clean]["salt"] = salt
    db["usuarios"][email_clean]["hash"] = pwd_hash
    db["usuarios"][email_clean]["debe_cambiar_password"] = True
    guardar_db(db)
    return True, "Contraseña reseteada exitosamente. Se exigirá cambio en su próximo ingreso."


def cambiar_password_propia(email: str, pass_actual: str, pass_nueva: str) -> tuple[bool, str]:
    """Permite a cualquier usuario conectado cambiar su propia contraseña."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        return False, "Usuario no encontrado."

    user = db["usuarios"][email_clean]
    if not verificar_password(pass_actual, user["salt"], user["hash"]):
        return False, "La contraseña actual ingresada es incorrecta."

    if len(pass_nueva) < 4:
        return False, "La nueva contraseña debe tener al menos 4 caracteres."

    salt = generar_salt()
    pwd_hash = hashear_password(pass_nueva, salt)
    user["salt"] = salt
    user["hash"] = pwd_hash
    user["debe_cambiar_password"] = False
    guardar_db(db)
    return True, "¡Tu contraseña fue actualizada correctamente!"


def eliminar_usuario(email: str) -> tuple[bool, str]:
    """Elimina definitivamente un usuario."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        return False, "El usuario no existe."

    # Prevenir que se quede el sistema sin ningún administrador
    admins = [u for u in db["usuarios"].values() if u.get("rol") == "admin"]
    if db["usuarios"][email_clean].get("rol") == "admin" and len(admins) <= 1:
        return False, "No puedes eliminar el único administrador del sistema."

    nombre = db["usuarios"][email_clean].get("nombre", email_clean)
    del db["usuarios"][email_clean]
    guardar_db(db)
    return True, f"Usuario {nombre} eliminado correctamente."


def solicitar_token_recuperacion(email: str) -> tuple[bool, str, str | None]:
    """Genera un código temporal de recuperación válido por 30 minutos."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["usuarios"]:
        # Mensaje neutro por seguridad contra enumeración de usuarios
        return True, "Si el correo está registrado, se ha generado el código de recuperación.", None

    codigo = f"{secrets.randbelow(900000) + 100000}"  # Código de 6 dígitos numéricos
    expira = (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    db["recuperaciones"][email_clean] = {
        "codigo": codigo,
        "expira": expira
    }
    guardar_db(db)
    return True, "Código de recuperación generado.", codigo


def aplicar_recuperacion_con_codigo(email: str, codigo: str, nueva_pass: str) -> tuple[bool, str]:
    """Aplica el cambio de contraseña tras validar el código temporal."""
    db = cargar_db()
    email_clean = email.strip().lower()

    if email_clean not in db["recuperaciones"]:
        return False, "No hay solicitudes de recuperación activas para este correo."

    recup = db["recuperaciones"][email_clean]
    if recup["codigo"].strip() != codigo.strip():
        return False, "El código ingresado es incorrecto."

    expira_dt = datetime.strptime(recup["expira"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expira_dt:
        del db["recuperaciones"][email_clean]
        guardar_db(db)
        return False, "El código ha caducado (validez: 30 minutos). Solicita uno nuevo."

    if len(nueva_pass) < 4:
        return False, "La nueva contraseña debe tener al menos 4 caracteres."

    salt = generar_salt()
    pwd_hash = hashear_password(nueva_pass, salt)
    db["usuarios"][email_clean]["salt"] = salt
    db["usuarios"][email_clean]["hash"] = pwd_hash
    db["usuarios"][email_clean]["debe_cambiar_password"] = False

    # Limpiar recuperación usada
    del db["recuperaciones"][email_clean]
    guardar_db(db)
    return True, "¡Contraseña restablecida con éxito! Ya puedes iniciar sesión."


# ==============================================================================
# 4. GESTIÓN DE ESTADO DE SESIÓN (STREAMLIT SESSION_STATE)
# ==============================================================================

def init_session():
    """Inicializa las variables necesarias en st.session_state."""
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "usuario_actual" not in st.session_state:
        st.session_state.usuario_actual = None


def login(usuario_dict: dict):
    """Guarda los datos del usuario en la sesión y recarga."""
    st.session_state.autenticado = True
    st.session_state.usuario_actual = usuario_dict
    st.rerun()


def logout():
    """Cierra la sesión y limpia las credenciales."""
    st.session_state.autenticado = False
    st.session_state.usuario_actual = None
    st.rerun()


def usuario_conectado() -> dict | None:
    """Devuelve los datos del usuario activo o None."""
    init_session()
    return st.session_state.usuario_actual if st.session_state.autenticado else None


def tiene_rol(roles_permitidos: list[str]) -> bool:
    """Verifica si el usuario actual cuenta con uno de los roles requeridos."""
    user = usuario_conectado()
    if not user:
        return False
    return user.get("rol") in roles_permitidos


# ==============================================================================
# 5. INYECCIÓN CSS RESPONSIVO (OPTIMIZADO PARA PC Y ANDROID)
# ==============================================================================

def inyectar_css_responsivo():
    """
    Inyecta reglas CSS adaptadas para Android y pantallas táctiles:
    - Altura táctil mínima de 44px (estándar ergonómico móvil).
    - Evita scroll horizontal.
    - Reducción de márgenes y paddings en pantallas estrechas.
    """
    css = """
    <style>
    /* Ergonomía táctil para botones en móviles y PC */
    .stButton > button {
        min-height: 44px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease-in-out !important;
    }
    
    /* Adaptación de campos de texto */
    .stTextInput input {
        min-height: 42px !important;
        border-radius: 6px !important;
    }
    
    /* Caja de login centrada y elegante */
    .auth-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }

    /* Insignias de roles */
    .badge-admin {
        background-color: #fef3c7;
        color: #92400e;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: bold;
        font-size: 0.85em;
        display: inline-block;
    }
    .badge-operador {
        background-color: #dbeafe;
        color: #1e40af;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: bold;
        font-size: 0.85em;
        display: inline-block;
    }
    .badge-lector {
        background-color: #f3f4f6;
        color: #374151;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: bold;
        font-size: 0.85em;
        display: inline-block;
    }

    /* Optimización de espacios para pantallas móviles (<= 768px) */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        .stButton > button {
            width: 100% !important;
        }
        h1 {
            font-size: 1.6rem !important;
        }
        h2 {
            font-size: 1.3rem !important;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ==============================================================================
# 6. COMPONENTES VISUALES DE STREAMLIT (UI)
# ==============================================================================

def render_login_ui():
    """
    Renderiza la pantalla completa de acceso bloqueando la app principal.
    Incluye 3 pestañas: Iniciar Sesión, Solicitar Cuenta y Recuperar Clave.
    """
    inyectar_css_responsivo()

    # Contenedor centrado
    col1, col2, col3 = st.columns([1, 2, 1]) if not st.session_state.get("is_mobile", False) else (None, st.container(), None)
    
    with col2 if col2 else st.container():
        # Detectar IP local para facilitar acceso móvil
        import socket
        try:
            _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            _s.connect(('8.8.8.8', 80))
            lan_ip = _s.getsockname()[0]
            _s.close()
        except Exception:
            lan_ip = "192.168.1.87"

        st.markdown("<h2 style='text-align: center; margin-bottom: 4px;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #64748b; font-size: 0.9em;'>PC: <code>localhost:8501</code> | Android / Wi-Fi: <code>http://{lan_ip}:8501</code></p>", unsafe_allow_html=True)

        tab_login, tab_registro, tab_recuperar = st.tabs([
            "🔑 Iniciar Sesión",
            "📝 Solicitar Cuenta",
            "🔄 Recuperar Contraseña"
        ])

        # -------------------------------------------------------------
        # PESTAÑA 1: INICIAR SESIÓN
        # -------------------------------------------------------------
        with tab_login:
            st.write("")
            with st.form("form_login", clear_on_submit=False):
                usuario_o_email = st.text_input(
                    "Correo electrónico o Usuario:",
                    placeholder="ej: usuario@empresa.com o admin",
                    key="login_user"
                )
                password = st.text_input(
                    "Contraseña:",
                    type="password",
                    placeholder="••••••••",
                    key="login_pass"
                )
                btn_ingresar = st.form_submit_button(
                    "🚀 Ingresar al Sistema",
                    use_container_width=True,
                    type="primary"
                )

            if btn_ingresar:
                if not usuario_o_email or not password:
                    st.warning("Por favor complete su usuario/correo y contraseña.")
                else:
                    ok, msg, datos_user = autenticar_usuario(usuario_o_email, password)
                    if ok:
                        st.success(msg)
                        login(datos_user)
                    else:
                        st.error(msg)

            # Notificación amigable de credenciales iniciales de prueba
            db_check = cargar_db()
            if "admin@empresa.com" in db_check["usuarios"] and db_check["usuarios"]["admin@empresa.com"].get("debe_cambiar_password"):
                st.info("💡 **Acceso inicial por defecto:** Usuario: `admin@empresa.com` | Contraseña: `admin123` *(Se recomienda cambiarla tras ingresar)*.")

        # -------------------------------------------------------------
        # PESTAÑA 2: SOLICITAR CUENTA NUEVA (AUTO-REGISTRO)
        # -------------------------------------------------------------
        with tab_registro:
            st.write("")
            st.caption("Complete el formulario para solicitar su alta como operador. Un administrador autorizará su acceso.")
            with st.form("form_registro", clear_on_submit=True):
                reg_nombre = st.text_input("Nombre y Apellido:", placeholder="Ej: Lic. Carlos Gómez")
                reg_email = st.text_input("Correo electrónico:", placeholder="carlos.gomez@empresa.com")
                reg_pass1 = st.text_input("Contraseña:", type="password", placeholder="Mínimo 4 caracteres")
                reg_pass2 = st.text_input("Confirmar Contraseña:", type="password", placeholder="Repita la contraseña")

                btn_solicitar = st.form_submit_button(
                    "📤 Enviar Solicitud de Registro",
                    use_container_width=True
                )

            if btn_solicitar:
                if not reg_nombre or not reg_email or not reg_pass1:
                    st.warning("Todos los campos son requeridos.")
                elif "@" not in reg_email or "." not in reg_email:
                    st.error("Ingrese una dirección de correo electrónico válida.")
                elif reg_pass1 != reg_pass2:
                    st.error("Las contraseñas ingresadas no coinciden.")
                elif len(reg_pass1) < 4:
                    st.error("La contraseña debe tener al menos 4 caracteres.")
                else:
                    ok_reg, msg_reg = registrar_solicitud_cuenta(reg_nombre, reg_email, reg_pass1)
                    if ok_reg:
                        st.success(msg_reg)
                    else:
                        st.error(msg_reg)

        # -------------------------------------------------------------
        # PESTAÑA 3: RECUPERAR CONTRASEÑA
        # -------------------------------------------------------------
        with tab_recuperar:
            st.write("")
            st.caption("Solicite un código de restablecimiento de seguridad ingresando su correo registrado.")
            
            paso = st.radio("Paso a realizar:", ["1. Generar código de restablecimiento", "2. Aplicar nueva contraseña con código"], horizontal=True)

            if paso.startswith("1"):
                with st.form("form_pedir_codigo"):
                    recup_email = st.text_input("Su correo registrado:", placeholder="ej: mi_correo@empresa.com")
                    btn_enviar_cod = st.form_submit_button("📩 Generar Código de Seguridad", use_container_width=True)

                if btn_enviar_cod:
                    if not recup_email:
                        st.warning("Ingrese su correo electrónico.")
                    else:
                        ok_rec, msg_rec, cod_gen = solicitar_token_recuperacion(recup_email)
                        st.info(msg_rec)
                        if cod_gen:
                            st.success(f"🔑 **Código generado para {recup_email}:** `{cod_gen}` *(Válido por 30 minutos)*")

            else:
                with st.form("form_aplicar_codigo"):
                    app_email = st.text_input("Correo electrónico:", placeholder="mi_correo@empresa.com")
                    app_codigo = st.text_input("Código de 6 dígitos:", placeholder="123456")
                    app_nueva_pass = st.text_input("Nueva Contraseña:", type="password")
                    btn_aplicar = st.form_submit_button("✅ Restablecer Contraseña", use_container_width=True)

                if btn_aplicar:
                    ok_ap, msg_ap = aplicar_recuperacion_con_codigo(app_email, app_codigo, app_nueva_pass)
                    if ok_ap:
                        st.success(msg_ap)
                    else:
                        st.error(msg_ap)


def render_sidebar_usuario():
    """
    Renderiza la tarjeta de perfil en la barra lateral con:
    - Nombre del usuario y rol actual (con badge coloreado).
    - Desplegable para cambio de contraseña propio.
    - Botón de cierre de sesión.
    """
    user = usuario_conectado()
    if not user:
        return

    st.sidebar.markdown("---")
    
    # Badge con estilo
    rol = user.get("rol", "operador")
    badge_class = f"badge-{rol}"
    rol_label = ROLES_EMOJI.get(rol, rol)

    st.sidebar.markdown(f"""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; margin-bottom: 12px;">
        <div style="font-weight: bold; font-size: 1.05em; color: #0f172a;">👤 {user.get('nombre')}</div>
        <div style="font-size: 0.85em; color: #64748b; margin-bottom: 8px;">{user.get('email')}</div>
        <span class="{badge_class}">{rol_label}</span>
    </div>
    """, unsafe_allow_html=True)

    # Menú desplegable para autoservicio de contraseña
    with st.sidebar.expander("🔑 Cambiar mi contraseña"):
        with st.form("form_cambio_clave_sidebar", clear_on_submit=True):
            p_actual = st.text_input("Contraseña actual:", type="password")
            p_nueva = st.text_input("Nueva contraseña:", type="password")
            p_conf = st.text_input("Confirmar nueva:", type="password")
            btn_cambiar = st.form_submit_button("Actualizar Clave", use_container_width=True)

        if btn_cambiar:
            if not p_actual or not p_nueva:
                st.sidebar.warning("Complete todos los campos.")
            elif p_nueva != p_conf:
                st.sidebar.error("Las nuevas contraseñas no coinciden.")
            else:
                ok_c, msg_c = cambiar_password_propia(user["email"], p_actual, p_nueva)
                if ok_c:
                    st.sidebar.success(msg_c)
                else:
                    st.sidebar.error(msg_c)

    # Botón de desconexión
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
        logout()

    # Información de enlace para dispositivos móviles
    import socket
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        lan_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        lan_ip = "192.168.1.87"

    with st.sidebar.expander("📱 Conectar desde Android / Otra PC"):
        st.markdown(f"""
        **En la misma red Wi-Fi:**
        1. Abra el navegador Chrome en su teléfono.
        2. Ingrese la dirección:
        `http://{lan_ip}:8501`
        """)


def render_panel_admin():
    """
    Panel de Control Exclusivo para Administradores.
    - Pestaña 1: Solicitudes Pendientes (Aprobar con rol o rechazar).
    - Pestaña 2: Usuarios Activos (Cambio de rol, reseteo de clave, eliminación).
    """
    if not tiene_rol(["admin"]):
        st.error("⛔ Acceso restringido. Esta sección es exclusiva para Administradores.")
        return

    st.markdown("## ⚙️ Panel de Administración de Usuarios")
    st.caption("Autorización de nuevas altas, asignación de roles y control de credenciales.")

    db = cargar_db()
    pendientes = db.get("pendientes", {})
    usuarios = db.get("usuarios", {})

    tab_pend, tab_activos, tab_alta = st.tabs([
        f"📬 Solicitudes Pendientes ({len(pendientes)})",
        f"👥 Usuarios Registrados ({len(usuarios)})",
        "➕ Alta Directa de Usuario"
    ])

    # ==========================================================================
    # PESTAÑA 1: SOLICITUDES PENDIENTES
    # ==========================================================================
    with tab_pend:
        if not pendientes:
            st.success("🎉 ¡Excelente! No hay solicitudes pendientes de autorización en este momento.")
        else:
            st.info(f"Hay **{len(pendientes)}** solicitud(es) esperando revisión.")
            
            filas_pend = []
            for email, p in pendientes.items():
                filas_pend.append({
                    "Nombre": p.get("nombre", "-"),
                    "Correo Electrónico": email,
                    "Fecha de Solicitud": p.get("fecha_solicitud", "-")
                })
            st.dataframe(filas_pend, use_container_width=True)

            st.write("---")
            st.markdown("#### ⚡ Resolver Solicitud:")

            col_sel, col_rol = st.columns([2, 1])
            with col_sel:
                email_elegido = st.selectbox(
                    "Seleccionar solicitante:",
                    options=list(pendientes.keys()),
                    format_func=lambda x: f"{pendientes[x].get('nombre')} ({x})"
                )
            with col_rol:
                rol_asignado = st.selectbox(
                    "Rol a otorgar:",
                    options=ROLES,
                    index=1,
                    format_func=lambda r: ROLES_EMOJI.get(r, r)
                )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🟢 Autorizar Cuenta (Dar de Alta)", use_container_width=True, type="primary"):
                    ok_a, msg_a = autorizar_solicitud(email_elegido, rol_asignado)
                    if ok_a:
                        st.success(msg_a)
                        st.rerun()
                    else:
                        st.error(msg_a)

            with col_btn2:
                if st.button("🔴 Rechazar Solicitud", use_container_width=True):
                    ok_r, msg_r = rechazar_solicitud(email_elegido)
                    if ok_r:
                        st.warning(msg_r)
                        st.rerun()
                    else:
                        st.error(msg_r)

    # ==========================================================================
    # PESTAÑA 2: USUARIOS REGISTRADOS (GESTIÓN, ALTA/BAJA, ROLES)
    # ==========================================================================
    with tab_activos:
        filas_users = []
        for email, u in usuarios.items():
            activo = u.get("activo", True)
            filas_users.append({
                "Nombre": u.get("nombre", "-"),
                "Correo Electrónico": email,
                "Rol": ROLES_EMOJI.get(u.get("rol"), u.get("rol")),
                "Fecha Alta": u.get("fecha_registro", "-"),
                "Estado de Acceso": "🟢 Habilitado (Activo)" if activo else "🔴 Bloqueado (Baja)"
            })
        st.dataframe(filas_users, use_container_width=True)

        st.write("---")
        st.markdown("#### 🛠️ Administrar Cuenta de Usuario:")
        
        user_gestionar = st.selectbox(
            "Seleccionar usuario:",
            options=list(usuarios.keys()),
            format_func=lambda x: f"{usuarios[x].get('nombre')} ({x}) - [{usuarios[x].get('rol')}] {'[ACTIVO]' if usuarios[x].get('activo', True) else '[BAJA]'}"
        )

        if user_gestionar:
            u_info = usuarios[user_gestionar]
            esta_activo = u_info.get("activo", True)
            
            sub_col1, sub_col2, sub_col3, sub_col4 = st.columns(4)
            
            # 1. Cambiar Rol
            with sub_col1:
                st.markdown("**1. Nivel de Permisos:**")
                rol_actual = u_info.get("rol", "operador")
                idx_rol = ROLES.index(rol_actual) if rol_actual in ROLES else 1
                nuevo_rol = st.selectbox("Nuevo Rol:", options=ROLES, index=idx_rol, key="sel_nuevo_rol", format_func=lambda r: ROLES_EMOJI.get(r, r))
                if st.button("💾 Guardar Rol", use_container_width=True):
                    ok_ur, msg_ur = actualizar_rol_usuario(user_gestionar, nuevo_rol)
                    if ok_ur:
                        st.success(msg_ur)
                        st.rerun()
                    else:
                        st.error(msg_ur)

            # 2. Resetear Contraseña
            with sub_col2:
                st.markdown("**2. Resetear Clave:**")
                nueva_clave_admin = st.text_input("Nueva contraseña:", type="password", key="pwd_temp_admin")
                if st.button("🔑 Asignar Clave", use_container_width=True):
                    if not nueva_clave_admin:
                        st.warning("Ingrese una contraseña.")
                    else:
                        ok_pw, msg_pw = resetear_password_admin(user_gestionar, nueva_clave_admin)
                        if ok_pw:
                            st.success(msg_pw)
                        else:
                            st.error(msg_pw)

            # 3. Alta / Baja de Acceso (Suspender o Reactivar)
            with sub_col3:
                st.markdown("**3. Control de Acceso:**")
                if esta_activo:
                    st.caption("Estado: 🟢 Cuenta Activa")
                    if st.button("🔴 Dar de Baja (Suspender)", use_container_width=True):
                        ok_b, msg_b = cambiar_estado_activo(user_gestionar, False)
                        if ok_b:
                            st.warning(msg_b)
                            st.rerun()
                        else:
                            st.error(msg_b)
                else:
                    st.caption("Estado: 🔴 Cuenta Suspendida")
                    if st.button("🟢 Dar de Alta (Reactivar)", use_container_width=True, type="primary"):
                        ok_b, msg_b = cambiar_estado_activo(user_gestionar, True)
                        if ok_b:
                            st.success(msg_b)
                            st.rerun()
                        else:
                            st.error(msg_b)

            # 4. Eliminar definitivamente
            with sub_col4:
                st.markdown("**4. Eliminar Registro:**")
                st.caption("Borrado permanente.")
                if st.button("🗑️ Eliminar Usuario", use_container_width=True, type="secondary"):
                    ok_del, msg_del = eliminar_usuario(user_gestionar)
                    if ok_del:
                        st.success(msg_del)
                        st.rerun()
                    else:
                        st.error(msg_del)

    # ==========================================================================
    # PESTAÑA 3: ALTA DIRECTA DE USUARIOS (CREACIÓN POR ADMINISTRADOR)
    # ==========================================================================
    with tab_alta:
        st.markdown("#### ➕ Registrar y Activar un Nuevo Usuario Directamente")
        st.caption("Permite al Administrador dar de alta a un operador, lector o administrador sin esperar que solicite cuenta.")

        with st.form("form_alta_directa_admin", clear_on_submit=True):
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                alta_nombre = st.text_input("Nombre Completo:", placeholder="Ej: Arq. María Fernández")
                alta_email = st.text_input("Correo electrónico / Usuario:", placeholder="maria.fernandez@empresa.com")
            with col_a2:
                alta_rol = st.selectbox("Rol a Asignar:", options=ROLES, index=1, format_func=lambda r: ROLES_EMOJI.get(r, r))
                alta_pass = st.text_input("Contraseña Inicial:", type="password", placeholder="Mínimo 4 caracteres")

            btn_crear_directo = st.form_submit_button("🟢 Dar de Alta y Habilitar Acceso", use_container_width=True, type="primary")

        if btn_crear_directo:
            if not alta_nombre or not alta_email or not alta_pass:
                st.warning("Por favor complete todos los campos requeridos.")
            else:
                ok_cd, msg_cd = crear_usuario_directo(alta_nombre, alta_email, alta_pass, alta_rol)
                if ok_cd:
                    st.success(msg_cd)
                    st.rerun()
                else:
                    st.error(msg_cd)
