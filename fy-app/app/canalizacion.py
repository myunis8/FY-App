"""Canalización: se integra la app de referencia "Canaliza" tal cual —con
todas sus funciones intactas (DRC, cableado de iluminación, exportación a
PDF multi-hoja)— en vez de reimplementarla. Acá no hay un modelo de datos
propio que mantener sincronizado: se guarda y se lee el proyecto exactamente
como lo produce la función `buildProjectData()` de esa app.

`web/canaliza.html` es el archivo real, con tres agregados mínimos y
puntuales para poder integrarlo (`window.canalizaExportar`,
`window.canalizaImportar`, y una bandera para saltear el diálogo de
autoguardado del navegador cuando corre integrado). El resto del archivo
—DRC, trazado de cableado, PDF— es el mismo que ya se usaba antes de esto.
"""
from __future__ import annotations

# tipo de circuito de esta app -> "kind" que espera Canaliza, y sus defaults
# (ver CIRCUIT_TYPES / WIRE_COLOR_MAP en canaliza.html)
KIND_DE_TIPO = {
    "IUG": "iluminacion", "IUE": "iluminacion",
    "TUG": "tomas", "TUE": "especial", "ACU": "especial", "OCE": "especial",
}
PALETA = ["#c2410c", "#1d4ed8", "#047857", "#7c3aed", "#b91c1c", "#0e7490", "#a16207", "#be185d"]

# tipo de elemento de esta app -> (kind de caja, device) que espera Canaliza
# (ver KINDS / DEVICES en canaliza.html). "otros" y "desconocido" son casos
# raros del extractor; se mandan como caja rectangular de "punto especial"
# porque es la opción más neutra, no porque sea siempre correcta.
KIND_DE_ELEMENTO = {
    "artefacto": ("oct", "luminaria"),
    "toma": ("rect", "toma"),
    "llave": ("rect", "interruptor"),
    "otros": ("rect", "especial"),
    "desconocido": ("rect", "especial"),
}
PREFIJO_ETIQUETA = {"toma": "T", "especial": "O"}
ZOOM_PLANO = 2.0  # debe coincidir con el ?zoom= de /api/obras/{id}/plano.png


def leer_proyecto(obra: dict) -> dict | None:
    return obra.get("canalizacion")


def guardar_proyecto(obra: dict, datos: dict) -> None:
    obra["canalizacion"] = datos


def circuitos_para_canaliza(obra: dict) -> list[dict]:
    """Los circuitos ya armados en el módulo de Circuitos, traducidos a la
    forma que espera Canaliza — para no tener que redefinirlos ahí también.
    Sólo se usa para el primer arranque; una vez que el usuario guarda un
    proyecto de canalización, ese guardado manda."""
    salida = []
    for i, c in enumerate(obra.get("circuitos") or []):
        kind = KIND_DE_TIPO.get(c.get("tipo"), "especial")
        salida.append({
            "id": c["id"], "name": c.get("nombre") or c["id"],
            "kind": kind, "color": PALETA[i % len(PALETA)],
            "section": c.get("seccionMm2") or 1.5,
            "cables": 2 if kind == "iluminacion" else 3,
            "prot": c.get("proteccionA") or 10,
            "dash": False, "detail": "", "ctype": c.get("tipo") or "OTRO",
        })
    return salida


def _circuito_de(obra: dict, elemento_id: str) -> dict | None:
    for c in obra.get("circuitos") or []:
        if elemento_id in (c.get("elementos") or []):
            return c
    return None


def nodos_para_canaliza(obra: dict, zoom: float = ZOOM_PLANO) -> list[dict]:
    """Los elementos ya extraídos del plano (cajas de luz, tomas, llaves),
    traducidos a nodos de Canaliza en la misma posición real sobre el plano
    (mismo `plano.png?zoom=` que se usa como fondo), con una nota indicando
    el circuito al que ya pertenecen si tienen uno asignado en el módulo de
    Circuitos. Sirven directo como extremo de un tramo, sin volver a
    marcarlos a mano. Igual que `circuitos_para_canaliza()`, sólo se usan la
    primera vez que se abre el módulo — después manda el proyecto guardado.
    """
    salida = []
    contador: dict[str, int] = {}
    for e in obra.get("elementos") or []:
        par = KIND_DE_ELEMENTO.get(e.get("tipo"))
        pos = e.get("posicionPdfPt")
        if not par or not pos:
            continue
        kind, device = par
        etiqueta = (e.get("nombre") or e.get("letra") or "").strip()
        if not etiqueta:
            contador[device] = contador.get(device, 0) + 1
            etiqueta = PREFIJO_ETIQUETA.get(device, device[:1].upper()) + str(contador[device])
        circ = _circuito_de(obra, e["id"])
        salida.append({
            "id": f"fy_{e['id']}", "kind": kind, "device": device,
            "x": round(pos["x"] * zoom, 1), "y": round(pos["y"] * zoom, 1),
            "label": etiqueta,
            "note": f"Circuito: {circ.get('nombre') or circ['id']}" if circ else "",
            "zAuto": True,
        })
    return salida


def pxpermetro_para_canaliza(obra: dict, zoom: float = ZOOM_PLANO) -> float | None:
    """Escala ya calibrada en el extractor, convertida a px/m sobre el mismo
    `plano.png?zoom=` que Canaliza usa de fondo — así no hay que calibrar de
    nuevo a mano marcando dos puntos."""
    ppm = ((obra.get("plano") or {}).get("escala") or {}).get("ptPorMetro")
    return round(ppm * zoom, 2) if ppm else None
