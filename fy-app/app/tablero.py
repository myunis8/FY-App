"""Armado del tablero: presets de gabinete, distribución de bocas por piso,
protecciones generales/seccionales y asignación de una térmica por circuito.

Una "boca" es un módulo DIN (17.5mm). Una térmica monofásica ocupa 2 bocas
(bipolar, norma AEA). Una trifásica ocupa 3 (sólo fases) o 4 (fases + neutro),
según se corte neutro o no.
"""
from __future__ import annotations
from . import contrato as C

# tamaño en bocas de cada tipo de dispositivo, según polos
BOCAS_POR_POLOS = {1: 1, 2: 2, 3: 3, 4: 4}

PRESETS = [
    {"id": "8", "nombre": "8 bocas (1 piso x 8)", "bocas": 8, "pisos": 1},
    {"id": "12", "nombre": "12 bocas (2 pisos x 6)", "bocas": 12, "pisos": 2},
    {"id": "18", "nombre": "18 bocas (3 pisos x 6)", "bocas": 18, "pisos": 3},
    {"id": "24", "nombre": "24 bocas (4 pisos x 6)", "bocas": 24, "pisos": 4},
    {"id": "36", "nombre": "36 bocas (6 pisos x 6)", "bocas": 36, "pisos": 6},
    {"id": "custom", "nombre": "A medida", "bocas": 12, "pisos": 2},
]

DEFAULT_GENERAL_A = 25
DEFAULT_DIFERENCIAL_A = 40
DEFAULT_DIFERENCIAL_MA = 30


def polos_termica(fases: int, corta_neutro: bool = False) -> int:
    if fases == 1:
        return 2
    return 4 if corta_neutro else 3


def bocas_por_piso(bocas: int, pisos: int) -> int:
    return max(1, -(-bocas // max(pisos, 1)))          # ceil


def tablero_nuevo(nombre: str, tipo: str, preset_id: str, fases: int) -> dict:
    preset = next((p for p in PRESETS if p["id"] == preset_id), PRESETS[1])
    bocas, pisos = preset["bocas"], preset["pisos"]
    tid = f"tab_{C.ahora()}"
    general_polos = polos_termica(fases)
    dif_polos = general_polos
    dispositivos = [
        {"id": f"{tid}_gen", "tipo": "termica", "rol": "general",
         "piso": 0, "posicion": 0, "polos": general_polos,
         "corriente": DEFAULT_GENERAL_A, "circuitoId": None, "alimentacion": "arriba"},
        {"id": f"{tid}_dif", "tipo": "diferencial", "rol": "general",
         "piso": 0, "posicion": general_polos, "polos": dif_polos,
         "corriente": DEFAULT_DIFERENCIAL_A, "sensibilidadMa": DEFAULT_DIFERENCIAL_MA,
         "circuitoId": None, "alimentacion": "arriba"},
        {"id": f"{tid}_pat", "tipo": "bornera", "rol": "tierra",
         "piso": 0, "posicion": general_polos + dif_polos, "polos": 1,
         "circuitoId": None, "alimentacion": None},
    ]
    return {
        "id": tid, "nombre": nombre or "Tablero", "tipo": tipo,          # principal | seccional
        "fases": fases, "bocas": bocas, "pisos": pisos,
        "bocasPorPiso": bocas_por_piso(bocas, pisos),
        "protectorSobretension": {"activo": False, "polos": general_polos},
        "alimentaDesde": None,               # {tableroId, dispositivoId} si es seccional
        "dispositivos": dispositivos,
        "notas": [],
    }


def _color_por_tipo(c: dict) -> str:
    return {"IUG": "#2b6ca3", "IUE": "#1f618d", "TUG": "#2f7d5c", "TUE": "#117864",
           "ACU": "#b5651d", "OCE": "#8e44ad"}.get(c.get("tipo"), "#5b6b7a")


def sincronizar_circuitos(tablero: dict, circuitos: list[dict], fases: int) -> dict:
    """Agrega una térmica por cada circuito que alimenta este tablero y todavía
    no tiene una, y quita las que quedaron de circuitos borrados. Conserva la
    posición de las que ya estaban."""
    ligados = {c["id"] for c in circuitos if c.get("tableroId") == tablero["id"]}
    existentes = {d["circuitoId"] for d in tablero["dispositivos"] if d.get("circuitoId")}

    tablero["dispositivos"] = [d for d in tablero["dispositivos"]
                               if d.get("rol") in ("general", "tierra")
                               or d.get("circuitoId") in ligados]

    ocupadas = _ocupadas(tablero)
    for c in circuitos:
        if c["id"] not in ligados or c["id"] in existentes:
            continue
        polos = polos_termica(fases)
        piso, pos = _proximo_lugar(tablero, ocupadas, polos)
        tablero["dispositivos"].append({
            "id": f"disp_{c['id']}", "tipo": "termica", "rol": "seccional",
            "piso": piso, "posicion": pos, "polos": polos,
            "corriente": c.get("proteccionA") or 10, "circuitoId": c["id"],
            "alimentacion": "arriba", "color": _color_por_tipo(c),
        })
        if piso is not None:
            for k in range(pos, pos + polos):
                ocupadas.setdefault(piso, set()).add(k)
    return tablero


def _ocupadas(tablero: dict) -> dict:
    m = {}
    for d in tablero["dispositivos"]:
        if d.get("piso") is None or d.get("posicion") is None:
            continue                        # sin lugar todavia: no ocupa nada
        for k in range(d["posicion"], d["posicion"] + d["polos"]):
            m.setdefault(d["piso"], set()).add(k)
    return m


def _proximo_lugar(tablero: dict, ocupadas: dict, polos: int):
    bpp = tablero["bocasPorPiso"]
    for piso in range(tablero["pisos"]):
        libres = ocupadas.get(piso, set())
        for pos in range(bpp - polos + 1):
            if not any((pos + k) in libres for k in range(polos)):
                return piso, pos
    return None, None                      # no entra: se avisa en la validación


def mover_dispositivo(tablero: dict, disp_id: str, piso: int, posicion: int) -> tuple[bool, str]:
    d = next((x for x in tablero["dispositivos"] if x["id"] == disp_id), None)
    if d is None:
        return False, "No existe ese dispositivo."
    if not (0 <= piso < tablero["pisos"]):
        return False, "Ese piso no existe en este tablero."
    if posicion < 0 or posicion + d["polos"] > tablero["bocasPorPiso"]:
        return False, "No entra en el ancho del piso."
    for otro in tablero["dispositivos"]:
        if otro["id"] == disp_id or otro["piso"] != piso:
            continue
        if not (posicion + d["polos"] <= otro["posicion"] or
                otro["posicion"] + otro["polos"] <= posicion):
            return False, f"Se superpone con {otro.get('rol') or otro['tipo']}."
    d["piso"], d["posicion"] = piso, posicion
    return True, ""


def validar(tablero: dict, circuitos: list[dict]) -> list[dict]:
    avisos = []
    sin_lugar = [d for d in tablero["dispositivos"] if d.get("piso") is None]
    for d in sin_lugar:
        c = next((c for c in circuitos if c["id"] == d.get("circuitoId")), None)
        nom = (c or {}).get("nombre") or d.get("circuitoId") or d.get("rol") or d["id"]
        avisos.append({"tipo": "tablero_sin_lugar", "gravedad": "error",
                       "tableroId": tablero["id"], "circuitoId": d.get("circuitoId"),
                       "detalle": f"{tablero['nombre']}: no entra {nom}. "
                                  "Agrandá el tablero o movela a otro."})
    ocup = _ocupadas(tablero)
    for piso, celdas in ocup.items():
        if piso is None:
            continue
        if max(celdas, default=-1) >= tablero["bocasPorPiso"]:
            avisos.append({"tipo": "tablero_excedido", "gravedad": "error",
                           "tableroId": tablero["id"],
                           "detalle": f"{tablero['nombre']}: el piso {piso+1} tiene "
                                      "dispositivos que exceden el ancho disponible."})
    sin_termica = [c for c in circuitos if c.get("tableroId") == tablero["id"]
                  and not any(d.get("circuitoId") == c["id"] for d in tablero["dispositivos"])]
    for c in sin_termica:
        avisos.append({"tipo": "circuito_sin_termica", "gravedad": "error",
                       "circuitoId": c["id"],
                       "detalle": f"{c.get('nombre') or c['id']} no tiene térmica en el tablero."})
    return avisos
