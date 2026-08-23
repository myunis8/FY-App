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
        "dispositivos": dispositivos,
        "conexiones": [],                # peines (bus por piso) y puentes (entre pisos)
        "canos": [],                      # entradas de circuito/acometida/tierra, se van agregando
        "cables": [],                     # conexión entre dos puntos: caño, peine o nodo de un dispositivo
        "notas": [],
    }


TIPOS_CANO = ("acometida", "circuito", "tierra")


def agregar_entrada_cano(tablero: dict, lado: str, tipo: str,
                        circuito_id=None, circuito_tipo=None):
    """Una boca de caño ya no es un lugar fijo entre N posibles: se agrega
    una entrada por vez, en el orden en que se van creando los circuitos, y
    se puede reordenar después. Así entran tantos circuitos como haga falta
    por el mismo lado, sin un tope artificial.

    circuito_tipo (IUG/TUG/TUE/...) se guarda junto al caño para saber si ese
    circuito necesita también un conductor de tierra (TUG y TUE sí; el resto,
    por ahora, no) sin tener que volver a consultar la lista de circuitos.
    """
    if lado not in ("arriba", "abajo"):
        return None, "El caño entra por arriba o por abajo del tablero."
    if tipo not in TIPOS_CANO:
        return None, "Ese tipo de caño no existe."
    canos = tablero.setdefault("canos", [])
    orden = sum(1 for c in canos if c["lado"] == lado)   # se agrega al final de esa fila
    c = {"id": _id("cano"), "tipo": tipo, "lado": lado, "orden": orden,
        "circuitoId": circuito_id if tipo == "circuito" else None,
        "circuitoTipo": circuito_tipo if tipo == "circuito" else None}
    canos.append(c)
    return c, ""


def editar_entrada_cano(tablero: dict, cano_id: str, tipo: str,
                        circuito_id=None, circuito_tipo=None):
    """Cambia qué es una entrada ya puesta, sin tocar su posición ni sus cables."""
    cano = next((c for c in tablero.get("canos") or [] if c["id"] == cano_id), None)
    if cano is None:
        return None, "Esa entrada no existe."
    if tipo not in TIPOS_CANO:
        return None, "Ese tipo de caño no existe."
    cano["tipo"] = tipo
    cano["circuitoId"] = circuito_id if tipo == "circuito" else None
    cano["circuitoTipo"] = circuito_tipo if tipo == "circuito" else None
    return cano, ""


def mover_entrada_cano(tablero: dict, cano_id: str, direccion: int) -> tuple[bool, str]:
    """Reordena de izquierda a derecha dentro de su mismo lado. direccion es
    -1 (una posición a la izquierda) o +1 (a la derecha)."""
    canos = tablero.get("canos") or []
    objetivo = next((c for c in canos if c["id"] == cano_id), None)
    if objetivo is None:
        return False, "Esa entrada no existe."
    hermanos = sorted([c for c in canos if c["lado"] == objetivo["lado"]], key=lambda c: c["orden"])
    idx = hermanos.index(objetivo)
    vecino_idx = idx + (1 if direccion > 0 else -1)
    if not (0 <= vecino_idx < len(hermanos)):
        return False, "Ya está en la punta."
    vecino = hermanos[vecino_idx]
    objetivo["orden"], vecino["orden"] = vecino["orden"], objetivo["orden"]
    return True, ""


TIPOS_CON_TIERRA = ("TUG", "TUE")   # a estos circuitos se les suma el conductor de tierra


def polaridades_cano(cano: dict) -> set[str]:
    """Qué conductores salen de esta boca: fase/neutro, o sólo tierra."""
    if cano["tipo"] == "tierra":
        return {"tierra"}
    if cano["tipo"] == "acometida":
        return {"fase", "neutro"}
    base = {"fase", "neutro"}
    if cano.get("circuitoTipo") in TIPOS_CON_TIERRA:
        base.add("tierra")
    return base


def polaridad_de_polo(d: dict, polo: int) -> str:
    """Convención del estudio: en un dispositivo bipolar, el polo 0 (el de la
    izquierda) siempre es fase y el polo 1 es neutro. Un tetrapolar con corte
    de neutro tiene el neutro en el último polo. Un tripolar sin neutro es
    todo fase. La bornera de tierra es tierra en todos sus terminales."""
    if d["tipo"] == "bornera":
        return "tierra"
    polos = d.get("polos", 1)
    if polos == 2:
        return "fase" if polo == 0 else "neutro"
    if polos == 4:
        return "fase" if polo < 3 else "neutro"
    return "fase"


def eliminar_entrada_cano(tablero: dict, cano_id: str) -> bool:
    canos = tablero.get("canos") or []
    objetivo = next((c for c in canos if c["id"] == cano_id), None)
    if objetivo is None:
        return False
    lado, orden_borrado = objetivo["lado"], objetivo["orden"]
    tablero["canos"] = [c for c in canos if c["id"] != cano_id]
    for c in tablero["canos"]:                    # se corre el orden de los que quedaron atrás
        if c["lado"] == lado and c["orden"] > orden_borrado:
            c["orden"] -= 1
    tablero["cables"] = [cb for cb in tablero.get("cables") or []
                         if not _endpoint_es_cano(cb.get("origen"), cano_id)
                         and not _endpoint_es_cano(cb.get("destino"), cano_id)]
    return True



def _endpoint_es_cano(ep, cano_id) -> bool:
    return isinstance(ep, dict) and ep.get("tipo") == "cano" and ep.get("id") == cano_id


BOCAS_BORNERA = 6   # cantidad de terminales laterales que dibuja svgBornera en el frontend


def _cantidad_polos_nodo(tablero: dict, d: dict) -> int | None:
    """Cuántos nodos tiene ese lado del dispositivo. None si el tipo no aplica."""
    if d["tipo"] == "bornera":
        return BOCAS_BORNERA
    return d.get("polos", 1)


def _endpoint_valido(tablero: dict, ep: dict) -> bool:
    return _polaridad_endpoint(tablero, ep) is not None


def _polaridad_endpoint(tablero: dict, ep: dict) -> str | None:
    """Fase, neutro o tierra de ese punto. None si el punto no es válido.
    Es la base tanto para validar el extremo como para impedir el
    cortocircuito: dos extremos sólo se pueden unir si son de la misma."""
    if not isinstance(ep, dict):
        return None
    tipo = ep.get("tipo")
    if tipo == "cano":
        cano = next((c for c in tablero.get("canos") or [] if c["id"] == ep.get("id")), None)
        if cano is None:
            return None
        pol = ep.get("polaridad")
        return pol if pol in polaridades_cano(cano) else None
    if tipo == "dispositivo":
        d = next((x for x in tablero["dispositivos"] if x["id"] == ep.get("id")), None)
        if d is None or d.get("piso") is None:
            return None
        lado, polo = ep.get("lado"), ep.get("polo")
        if not isinstance(polo, int):
            return None
        if d["tipo"] == "bornera":
            if lado != "costado" or not (0 <= polo < BOCAS_BORNERA):
                return None
            return "tierra"
        if lado not in ("arriba", "abajo") or not (0 <= polo < _cantidad_polos_nodo(tablero, d)):
            return None
        return polaridad_de_polo(d, polo)
    if tipo == "peine":
        peine = next((c for c in tablero.get("conexiones") or []
                     if c["id"] == ep.get("id") and c["tipo"] == "peine"), None)
        if peine is None:
            return None
        pol = ep.get("polaridad")
        return pol if pol in ("fase", "neutro") else None
    return None


def crear_cable(tablero: dict, origen: dict, destino: dict,
                ruta: list | None = None) -> tuple[dict | None, str]:
    """Un cable conecta dos puntos cualquiera: un caño, un peine, o el nodo de
    un polo puntual de un dispositivo. Así se arma la serie real: acometida ->
    general -> diferencial -> peine -> cada térmica, en vez de que todo tenga
    que pasar por un solo tipo de conexión.

    Antes de crear el cable se verifica que los dos extremos sean de la misma
    polaridad (fase, neutro o tierra): conectar fase con neutro es un
    cortocircuito y se rechaza acá, no se detecta después.

    `ruta` son puntos intermedios opcionales (coordenadas del propio lienzo)
    para que el cable no tenga que ir siempre recto: el que lo dibuja elige
    por dónde pasa.
    """
    pol_o = _polaridad_endpoint(tablero, origen)
    if pol_o is None:
        return None, "El primer punto no es válido, o el dispositivo no está en el riel."
    pol_d = _polaridad_endpoint(tablero, destino)
    if pol_d is None:
        return None, "El segundo punto no es válido, o el dispositivo no está en el riel."
    if origen == destino:
        return None, "El origen y el destino no pueden ser el mismo punto."
    if pol_o != pol_d:
        nombres = {"fase": "fase", "neutro": "neutro", "tierra": "tierra"}
        return None, (f"Eso conecta {nombres[pol_o]} con {nombres[pol_d]}: es un "
                      "cortocircuito. Fase, neutro y tierra no se unen entre sí.")
    ruta_limpia = []
    for p in (ruta or []):
        if isinstance(p, (list, tuple)) and len(p) == 2:
            try:
                ruta_limpia.append([float(p[0]), float(p[1])])
            except (TypeError, ValueError):
                pass
    cable = {"id": _id("cable"), "origen": origen, "destino": destino,
            "ruta": ruta_limpia, "polaridad": pol_o}
    tablero.setdefault("cables", []).append(cable)
    return cable, ""


def eliminar_cable(tablero: dict, cable_id: str) -> bool:
    n = len(tablero.get("cables") or [])
    tablero["cables"] = [cb for cb in tablero.get("cables") or [] if cb["id"] != cable_id]
    return len(tablero.get("cables") or []) < n


def _dispositivos_en(tablero: dict, piso: int, desde: int, hasta: int) -> list[dict]:
    lo, hi = min(desde, hasta), max(desde, hasta)
    return [d for d in tablero["dispositivos"] if d.get("piso") == piso
            and d["posicion"] is not None and d["posicion"] >= lo
            and d["posicion"] + d["polos"] - 1 <= hi]


def crear_peine(tablero: dict, piso: int, desde: int, hasta: int) -> tuple[dict | None, str]:
    """Un peine junta en paralelo todas las térmicas contiguas de un mismo
    riel que caen dentro del rango [desde, hasta] (en bocas)."""
    if not (0 <= piso < tablero["pisos"]):
        return None, "Ese piso no existe."
    lo, hi = min(desde, hasta), max(desde, hasta)
    alcanzados = _dispositivos_en(tablero, piso, lo, hi)
    if len(alcanzados) < 2:
        return None, "Un peine necesita al menos dos térmicas colocadas en ese tramo."
    for c in tablero["conexiones"]:
        if c["tipo"] == "peine" and c["piso"] == piso and not (hi < c["desde"] or lo > c["hasta"]):
            return None, "Ya hay un peine que se superpone en ese tramo."
    peine = {"id": _id("peine"), "tipo": "peine", "piso": piso, "desde": lo, "hasta": hi}
    tablero["conexiones"].append(peine)
    return peine, ""


def crear_puente(tablero: dict, piso_origen: int, x: int, piso_destino: int) -> tuple[dict | None, str]:
    """El conector que baja el peine (o la salida de una térmica) de un piso
    al riel del piso siguiente, tal como en la foto de referencia."""
    if piso_destino != piso_origen + 1:
        return None, "Un conector siempre baja al piso inmediatamente siguiente."
    if not (0 <= piso_origen < tablero["pisos"] and 0 <= piso_destino < tablero["pisos"]):
        return None, "Ese piso no existe."
    puente = {"id": _id("puente"), "tipo": "puente",
             "pisoOrigen": piso_origen, "pisoDestino": piso_destino, "x": x}
    tablero["conexiones"].append(puente)
    return puente, ""


def eliminar_conexion(tablero: dict, con_id: str) -> bool:
    n = len(tablero["conexiones"])
    tablero["conexiones"] = [c for c in tablero["conexiones"] if c["id"] != con_id]
    return len(tablero["conexiones"]) < n


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
