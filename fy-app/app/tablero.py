"""Armado del tablero: presets de gabinete, distribución de bocas por piso,
protecciones generales/seccionales y asignación de una térmica por circuito.

Una "boca" es el ancho de un módulo DIN (17.5mm) — el espacio de una llave
monopolar, que no se usa porque está prohibida. Una térmica bipolar (la que
se usa siempre en instalaciones domiciliarias) ocupa 2 bocas. Un riel típico
de 12 bocas entra 6 térmicas bipolares por piso.

Nada se coloca solo: cada dispositivo nace SIN piso ni posición (queda en la
bandeja, afuera del gabinete) y el usuario lo arrastra al riel. Esto incluye
la térmica general, el diferencial y la bornera de tierra: se crean listos
para arrastrar, no ya puestos.
"""
from __future__ import annotations
import uuid
from . import contrato as C


def _id(prefijo: str) -> str:
    """Id único de verdad: C.ahora() es por milisegundo y puede repetirse
    si se crean varios objetos en la misma corrida (pasó en las pruebas)."""
    return f"{prefijo}_{uuid.uuid4().hex[:10]}"

PRESETS = [
    {"id": "12", "nombre": "12 bocas (1 piso x 12)", "bocas": 12, "pisos": 1},
    {"id": "24", "nombre": "24 bocas (2 pisos x 12)", "bocas": 24, "pisos": 2},
    {"id": "36", "nombre": "36 bocas (3 pisos x 12)", "bocas": 36, "pisos": 3},
    {"id": "48", "nombre": "48 bocas (4 pisos x 12)", "bocas": 48, "pisos": 4},
    {"id": "72", "nombre": "72 bocas (6 pisos x 12)", "bocas": 72, "pisos": 6},
    {"id": "custom", "nombre": "A medida", "bocas": 12, "pisos": 1},
]

DEFAULT_GENERAL_A = 25
DEFAULT_DIFERENCIAL_A = 40
DEFAULT_DIFERENCIAL_MA = 30

COLOR_CIRCUITO = {"IUG": "#2b6ca3", "IUE": "#1f618d", "TUG": "#2f7d5c", "TUE": "#117864",
                  "ACU": "#b5651d", "OCE": "#8e44ad"}


def polos_termica(fases: int, corta_neutro: bool = False) -> int:
    if fases == 1:
        return 2
    return 4 if corta_neutro else 3


def bocas_por_piso(bocas: int, pisos: int) -> int:
    return max(1, -(-bocas // max(pisos, 1)))          # ceil


def _sin_ubicar(base: dict) -> dict:
    return {**base, "piso": None, "posicion": None, "alimentacion": "arriba"}


def tablero_nuevo(nombre: str, tipo: str, preset_id: str, fases: int) -> dict:
    preset = next((p for p in PRESETS if p["id"] == preset_id), PRESETS[0])
    bocas, pisos = preset["bocas"], preset["pisos"]
    tid = _id("tab")
    polos = polos_termica(fases)
    dispositivos = [
        _sin_ubicar({"id": f"{tid}_gen", "tipo": "termica", "rol": "general",
                     "polos": polos, "corriente": DEFAULT_GENERAL_A, "circuitoId": None}),
        _sin_ubicar({"id": f"{tid}_dif", "tipo": "diferencial", "rol": "general",
                     "polos": polos, "corriente": DEFAULT_DIFERENCIAL_A,
                     "sensibilidadMa": DEFAULT_DIFERENCIAL_MA, "circuitoId": None}),
        _sin_ubicar({"id": f"{tid}_pat", "tipo": "bornera", "rol": "tierra",
                     "polos": 1, "circuitoId": None}),
    ]
    return {
        "id": tid, "nombre": nombre or "Tablero", "tipo": tipo,      # principal | seccional
        "fases": fases, "bocas": bocas, "pisos": pisos,
        "bocasPorPiso": bocas_por_piso(bocas, pisos),
        "alimentaDesde": None,           # {tableroId, dispositivoId} si es seccional
        "vivoIzquierda": True,           # convención del instalador: vivo a la izquierda de
                                          # cada protección bipolar, neutro a la derecha (o al
                                          # revés) -- afecta todo el tablero, no dispositivo
                                          # por dispositivo
        "dispositivos": dispositivos,
        "peines": [],                    # barras que unen varias térmicas de un mismo riel
        "conexiones": [],                # cables sueltos entre dos pines/peines/entradas
        "notas": [],
    }


# Mismo criterio que canalizacion.KIND_DE_TIPO ("tomas"/"especial" = 3
# cables, con tierra; "iluminacion" = 2 cables, sin tierra) -- pero acá sólo
# nos importa si hace falta o no el conductor de protección.
TIPOS_CON_TIERRA = ("TUG", "TUE", "ACU", "OCE")

POLARIDADES = ("fase", "neutro", "tierra")


def polaridad_de_polo(d: dict, polo: int, vivo_izquierda: bool = True) -> str | None:
    """Fase, neutro o tierra de un polo puntual, según la convención del
    tablero (vivo a la izquierda o a la derecha). La bornera no tiene
    "polos" como una térmica -- todos sus terminales son el mismo bus de
    tierra, así que cualquier polo pedido da tierra."""
    if d["tipo"] == "bornera":
        return "tierra"
    polos = d.get("polos", 1)
    if polo < 0 or polo >= polos:
        return None
    if polos == 2:
        es_primero = polo == 0
        return "fase" if es_primero == vivo_izquierda else "neutro"
    if polos == 4:
        return "fase" if polo < 3 else "neutro"
    return "fase"


def polaridades_entrada(d: dict, circuitos: list[dict]) -> tuple[str, ...]:
    """Qué conductores trae el cablecito de entrada de ESTE dispositivo: la
    general trae la acometida (fase+neutro); una térmica de circuito trae lo
    que ese circuito necesite (fase+neutro, +tierra si corresponde). El
    diferencial y la bornera no tienen entrada propia -- se alimentan por
    conexión directa desde otro pin o peine."""
    if d.get("rol") == "general" and d["tipo"] == "termica":
        return ("fase", "neutro")
    cid = d.get("circuitoId")
    if cid:
        c = next((x for x in circuitos if x["id"] == cid), None)
        if c is None:
            return ()
        base = ["fase", "neutro"]
        if c.get("tipo") in TIPOS_CON_TIERRA:
            base.append("tierra")
        return tuple(base)
    return ()


def _dispositivo(tablero: dict, disp_id: str) -> dict | None:
    return next((x for x in tablero["dispositivos"] if x["id"] == disp_id), None)


def _polaridad_endpoint(tablero: dict, circuitos: list[dict], ep: dict) -> str | None:
    """Fase, neutro o tierra de un extremo de conexión. None si no es válido.
    Es la base tanto para validar el extremo como para el DRC: dos extremos
    sólo se pueden unir si dan la misma polaridad."""
    if not isinstance(ep, dict):
        return None
    tipo = ep.get("tipo")
    if tipo == "entrada":
        d = _dispositivo(tablero, ep.get("dispositivoId"))
        if d is None or d.get("piso") is None:
            return None
        pol = ep.get("polaridad")
        return pol if pol in polaridades_entrada(d, circuitos) else None
    if tipo == "pin":
        d = _dispositivo(tablero, ep.get("dispositivoId"))
        if d is None or d.get("piso") is None:
            return None
        polo, lado = ep.get("polo"), ep.get("lado")
        if not isinstance(polo, int) or lado not in ("arriba", "abajo"):
            return None
        if d["tipo"] == "bornera":
            return "tierra" if polo == 0 else None
        return polaridad_de_polo(d, polo, tablero.get("vivoIzquierda", True))
    if tipo == "peine":
        pe = next((p for p in tablero.get("peines") or [] if p["id"] == ep.get("id")), None)
        if pe is None:
            return None
        pol = ep.get("polaridad")
        return pol if pol in ("fase", "neutro") else None
    return None


def crear_conexion(tablero: dict, circuitos: list[dict], origen: dict, destino: dict,
                   ruta: list | None = None) -> tuple[dict | None, str]:
    """Conexión entre dos pines, entradas o peines. La polaridad no se
    elige a mano: se calcula de cada extremo, y si no coinciden (fase con
    neutro, por ejemplo) se rechaza acá -- es el DRC de cortocircuito.
    `ruta` son puntos intermedios opcionales (coordenadas del lienzo del
    editor) para que el que cablea elija por dónde pasa el cable."""
    pol_o = _polaridad_endpoint(tablero, circuitos, origen)
    if pol_o is None:
        return None, "El primer punto no es válido, o el dispositivo no está en el riel."
    pol_d = _polaridad_endpoint(tablero, circuitos, destino)
    if pol_d is None:
        return None, "El segundo punto no es válido, o el dispositivo no está en el riel."
    if origen == destino:
        return None, "El origen y el destino no pueden ser el mismo punto."
    if pol_o != pol_d:
        return None, (f"Eso conecta {pol_o} con {pol_d}: es un cortocircuito. "
                      "Fase, neutro y tierra no se unen entre sí.")
    ruta_limpia = []
    for p in (ruta or []):
        if isinstance(p, (list, tuple)) and len(p) == 2:
            try:
                ruta_limpia.append([float(p[0]), float(p[1])])
            except (TypeError, ValueError):
                pass
    con = {"id": _id("con"), "origen": origen, "destino": destino,
          "polaridad": pol_o, "ruta": ruta_limpia}
    tablero.setdefault("conexiones", []).append(con)
    return con, ""


def eliminar_conexion(tablero: dict, con_id: str) -> bool:
    n = len(tablero.get("conexiones") or [])
    tablero["conexiones"] = [c for c in tablero.get("conexiones") or [] if c["id"] != con_id]
    return len(tablero["conexiones"]) < n


def _dispositivos_en(tablero: dict, piso: int, desde: int, hasta: int) -> list[dict]:
    lo, hi = min(desde, hasta), max(desde, hasta)
    return [d for d in tablero["dispositivos"] if d.get("piso") == piso
            and d["posicion"] is not None and d["posicion"] >= lo
            and d["posicion"] + d["polos"] - 1 <= hi]


def crear_peine(tablero: dict, piso: int, desde: int, hasta: int) -> tuple[dict | None, str]:
    """Un peine junta en paralelo (fase con fase, neutro con neutro) todas
    las térmicas contiguas de un mismo riel que caen dentro de [desde,
    hasta] (en bocas) -- para no tener que cablear una por una cuando varias
    comparten el mismo origen."""
    if not (0 <= piso < tablero["pisos"]):
        return None, "Ese piso no existe."
    lo, hi = min(desde, hasta), max(desde, hasta)
    alcanzados = _dispositivos_en(tablero, piso, lo, hi)
    if len(alcanzados) < 2:
        return None, "Un peine necesita al menos dos térmicas colocadas en ese tramo."
    for p in tablero.get("peines") or []:
        if p["piso"] == piso and not (hi < p["desde"] or lo > p["hasta"]):
            return None, "Ya hay un peine que se superpone en ese tramo."
    peine = {"id": _id("peine"), "piso": piso, "desde": lo, "hasta": hi}
    tablero.setdefault("peines", []).append(peine)
    return peine, ""


def _endpoint_es_peine(ep, peine_id: str) -> bool:
    return isinstance(ep, dict) and ep.get("tipo") == "peine" and ep.get("id") == peine_id


def eliminar_peine(tablero: dict, peine_id: str) -> bool:
    n = len(tablero.get("peines") or [])
    tablero["peines"] = [p for p in tablero.get("peines") or [] if p["id"] != peine_id]
    tablero["conexiones"] = [c for c in tablero.get("conexiones") or []
                             if not _endpoint_es_peine(c.get("origen"), peine_id)
                             and not _endpoint_es_peine(c.get("destino"), peine_id)]
    return len(tablero["peines"]) < n


def _endpoint_es_dispositivo(ep, disp_id: str) -> bool:
    return isinstance(ep, dict) and ep.get("tipo") in ("entrada", "pin") and ep.get("dispositivoId") == disp_id


def _quitar_conexiones_de(tablero: dict, disp_id: str) -> None:
    tablero["conexiones"] = [c for c in tablero.get("conexiones") or []
                             if not _endpoint_es_dispositivo(c.get("origen"), disp_id)
                             and not _endpoint_es_dispositivo(c.get("destino"), disp_id)]


def agregar_dispositivo(tablero: dict, tipo: str, extra: dict | None = None) -> dict:
    """Crea un dispositivo suelto (sin ubicar) para que el usuario lo arrastre."""
    extra = extra or {}
    polos = polos_termica(tablero.get("fases", 1))
    base = {"id": _id("disp"), "tipo": tipo, "rol": extra.get("rol", "seccional"),
           "circuitoId": None}
    if tipo == "termica":
        base.update({"polos": extra.get("polos", polos), "corriente": extra.get("corriente", 16)})
    elif tipo == "diferencial":
        base.update({"polos": extra.get("polos", polos), "corriente": extra.get("corriente", 40),
                     "sensibilidadMa": extra.get("sensibilidadMa", 30)})
    elif tipo == "bornera":
        base.update({"polos": 1, "rol": "tierra"})
    elif tipo == "protector":
        base.update({"polos": extra.get("polos", polos), "tensionV": extra.get("tensionV", 220)})
    else:
        raise ValueError("Tipo de dispositivo desconocido")
    d = _sin_ubicar(base)
    tablero["dispositivos"].append(d)
    return d


def sincronizar_circuitos(tablero: dict, circuitos: list[dict], fases: int,
                          reclamar_sueltos: bool = False) -> dict:
    """Crea (sin ubicar) una térmica por cada circuito nuevo asignado a este
    tablero, y quita las que quedaron de circuitos que ya no le pertenecen o
    que se borraron. Nunca las coloca sola en el riel.

    reclamar_sueltos=True hace que los circuitos SIN tablero asignado
    (tableroId vacío) se consideren de este tablero y se los marca como tales.
    Sin esto, un circuito armado antes de crear el tablero quedaba sin
    término y sin ningún aviso visible: el usuario tenía que abrir circuitos.html
    y elegir el tablero a mano, circuito por circuito, para que apareciera acá.
    El servidor activa esta reclamación cuando la obra tiene un solo tablero,
    que es el caso normal.
    """
    ligados = {c["id"] for c in circuitos if c.get("tableroId") == tablero["id"]}
    if reclamar_sueltos:
        for c in circuitos:
            if not c.get("tableroId"):
                c["tableroId"] = tablero["id"]
                ligados.add(c["id"])
    existentes = {d["circuitoId"] for d in tablero["dispositivos"] if d.get("circuitoId")}

    tablero["dispositivos"] = [d for d in tablero["dispositivos"]
                               if d.get("rol") in ("general", "tierra")
                               or d.get("circuitoId") in ligados]

    por_id = {c["id"]: c for c in circuitos}
    for cid in ligados - existentes:
        c = por_id[cid]
        polos = polos_termica(fases)
        tablero["dispositivos"].append(_sin_ubicar({
            "id": f"disp_{cid}", "tipo": "termica", "rol": "seccional",
            "polos": polos, "corriente": c.get("proteccionA") or 10,
            "circuitoId": cid, "color": COLOR_CIRCUITO.get(c.get("tipo"), "#5b6b7a")}))
    return tablero


def mover_dispositivo(tablero: dict, disp_id: str, piso, posicion) -> tuple[bool, str]:
    """piso=None quita el dispositivo del riel y lo vuelve a la bandeja."""
    d = next((x for x in tablero["dispositivos"] if x["id"] == disp_id), None)
    if d is None:
        return False, "No existe ese dispositivo."
    if piso is None:
        d["piso"], d["posicion"] = None, None
        _quitar_conexiones_de(tablero, disp_id)
        return True, ""
    if not (0 <= piso < tablero["pisos"]):
        return False, "Ese piso no existe en este tablero."
    if posicion is None or posicion < 0 or posicion + d["polos"] > tablero["bocasPorPiso"]:
        return False, "No entra en el ancho del riel."
    for otro in tablero["dispositivos"]:
        if otro["id"] == disp_id or otro.get("piso") != piso:
            continue
        if not (posicion + d["polos"] <= otro["posicion"] or
                otro["posicion"] + otro["polos"] <= posicion):
            return False, f"Se superpone con {etiqueta_corta(otro)}."
    d["piso"], d["posicion"] = piso, posicion
    return True, ""


def etiqueta_corta(d: dict) -> str:
    if d.get("rol") == "general" and d["tipo"] == "termica":
        return "la general"
    if d["tipo"] == "diferencial":
        return "el diferencial"
    if d["tipo"] == "bornera":
        return "la bornera de tierra"
    if d["tipo"] == "protector":
        return "el DPS"
    return d.get("circuitoId") or "otro dispositivo"


def eliminar_dispositivo(tablero: dict, disp_id: str) -> bool:
    n = len(tablero["dispositivos"])
    tablero["dispositivos"] = [d for d in tablero["dispositivos"] if d["id"] != disp_id]
    _quitar_conexiones_de(tablero, disp_id)
    return len(tablero["dispositivos"]) < n


def validar(tablero: dict, circuitos: list[dict]) -> list[dict]:
    avisos = []
    sin_ubicar = [d for d in tablero["dispositivos"] if d.get("piso") is None]
    for d in sin_ubicar:
        c = next((c for c in circuitos if c["id"] == d.get("circuitoId")), None)
        nom = (c or {}).get("nombre") or etiqueta_corta(d)
        avisos.append({"tipo": "sin_ubicar", "gravedad": "advertencia",
                       "tableroId": tablero["id"], "circuitoId": d.get("circuitoId"),
                       "detalle": f"{tablero['nombre']}: {nom} todavía está en la bandeja, "
                                  "sin colocar en el riel."})
    sin_termica = [c for c in circuitos if c.get("tableroId") == tablero["id"]
                  and not any(d.get("circuitoId") == c["id"] for d in tablero["dispositivos"])]
    for c in sin_termica:
        avisos.append({"tipo": "circuito_sin_termica", "gravedad": "error",
                       "circuitoId": c["id"],
                       "detalle": f"{c.get('nombre') or c['id']} no tiene ninguna térmica "
                                  f"creada en {tablero['nombre']}."})
    return avisos
