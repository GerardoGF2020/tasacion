"""
Módulo de Gestión y Sincronización de Expedientes de Tasación.
Permite trabajo colaborativo: un operador carga en campo desde su celular,
y otro usuario/perito puede continuar la tasación a medias desde su PC o móvil.
"""

import os
import json
from datetime import datetime

EXP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expedientes.json")

# Ejemplos iniciales para demostración si el archivo no existe
DATOS_INICIALES = [
    {
        "id": "TAS-2026-001",
        "titulo": "Terreno Barrio Bernel - Lote 12",
        "tipo_inmueble": "Terreno Urbano",
        "direccion": "Barrio Bernel, Manzana C, Yerba Buena",
        "frente": 15.0,
        "fondo": 30.0,
        "superficie_m2": 450.0,
        "valor_unitario": 85000.0,
        "valor_total": 38250000.0,
        "estado": "🟡 Borrador (A medias)",
        "creado_por": "Carlos Gómez (Operador)",
        "ultima_modificacion_por": "Carlos Gómez (Operador)",
        "fecha_creacion": "2026-11-18 10:15",
        "fecha_modificacion": "2026-11-18 10:15",
        "observaciones": "Relevamiento de medidas en campo. Pendiente aplicar coeficiente Fitte y Cervini por perito."
    },
    {
        "id": "TAS-2026-002",
        "titulo": "Vivienda Unifamiliar Calle San Martín",
        "tipo_inmueble": "Casa Residencial",
        "direccion": "San Martín 1420, San Miguel de Tucumán",
        "frente": 10.0,
        "fondo": 25.0,
        "superficie_m2": 250.0,
        "valor_unitario": 120000.0,
        "valor_total": 30000000.0,
        "estado": "🟢 Finalizada",
        "creado_por": "Administrador General",
        "ultima_modificacion_por": "Administrador General",
        "fecha_creacion": "2026-11-17 16:40",
        "fecha_modificacion": "2026-11-17 18:20",
        "observaciones": "Tasación completa con método comparativo y valores de mercado validados."
    }
]


def inicializar_expedientes() -> list[dict]:
    """Crea el archivo expedientes.json con datos de muestra si no existe."""
    if not os.path.exists(EXP_FILE):
        guardar_todos_los_expedientes(DATOS_INICIALES)
        return DATOS_INICIALES
    try:
        with open(EXP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        guardar_todos_los_expedientes(DATOS_INICIALES)
        return DATOS_INICIALES


def cargar_expedientes() -> list[dict]:
    """Lee y devuelve la lista fresca de expedientes."""
    return inicializar_expedientes()


def guardar_todos_los_expedientes(expedientes: list[dict]) -> None:
    """Sobrescribe el archivo de expedientes."""
    with open(EXP_FILE, "w", encoding="utf-8") as f:
        json.dump(expedientes, f, indent=2, ensure_ascii=False)


def guardar_o_actualizar_expediente(datos: dict, usuario_nombre: str) -> tuple[bool, str]:
    """
    Inserta un nuevo expediente o actualiza uno existente.
    Permite colaboración continua entre usuarios.
    """
    lista = cargar_expedientes()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    exp_id = datos.get("id", "").strip()

    if not exp_id:
        return False, "El N° de Expediente no puede estar vacío."

    # Buscar si ya existe para editar
    indice_existente = -1
    for i, exp in enumerate(lista):
        if exp["id"] == exp_id:
            indice_existente = i
            break

    if indice_existente >= 0:
        # Actualización de tasación existente
        original = lista[indice_existente]
        datos["creado_por"] = original.get("creado_por", usuario_nombre)
        datos["fecha_creacion"] = original.get("fecha_creacion", ahora)
        datos["ultima_modificacion_por"] = usuario_nombre
        datos["fecha_modificacion"] = ahora
        lista[indice_existente] = datos
        guardar_todos_los_expedientes(lista)
        return True, f"✅ Expediente {exp_id} actualizado exitosamente por {usuario_nombre}."
    else:
        # Nueva tasación
        datos["creado_por"] = usuario_nombre
        datos["ultima_modificacion_por"] = usuario_nombre
        datos["fecha_creacion"] = ahora
        datos["fecha_modificacion"] = ahora
        lista.insert(0, datos)
        guardar_todos_los_expedientes(lista)
        return True, f"✅ Nuevo expediente {exp_id} guardado exitosamente."


def eliminar_expediente(exp_id: str) -> tuple[bool, str]:
    """Elimina un expediente por ID."""
    lista = cargar_expedientes()
    nueva_lista = [e for e in lista if e["id"] != exp_id]
    if len(nueva_lista) == len(lista):
        return False, "Expediente no encontrado."
    guardar_todos_los_expedientes(nueva_lista)
    return True, f"Expediente {exp_id} eliminado."
