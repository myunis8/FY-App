"""Puente entre el extractor y el contrato: ejecuta, mezcla y reporta cambios."""
from __future__ import annotations
from typing import Optional

from . import almacen, contrato as C, vinculos

CAMPOS_DEL_USUARIO = ("subtipo", "alturaM", "nombre", "interruptor", "letra",
                      "notas", "tipo", "circuitoId")


def _mapa(elementos):
    return {e["id"]: e for e in elementos if e.get("id")}


def ejecutar(obra: dict, escala: Optional[float] = None,
             correcciones: Optional[dict] = None) -> dict:
    """Corre el extractor sobre el PDF de la obra y mezcla el resultado.

    Lo que el usuario marcó como revisado no se pisa: se conservan sus campos y
    sólo se actualiza la posición. Así una revisión nueva del plano no borra el
    trabajo manual.
    """
    from .extractor import extraer            # import diferido: arranque más rápido

    obra_id = obra["obra"]["id"]
    plano = obra.get("plano") or {}
    nombre = plano.get("archivo")
    ruta = almacen.ruta_plano(obra_id, nombre) if nombre else None
    if ruta is None:
        raise ValueError("Esta obra todavía no tiene un plano cargado.")

    guardadas = plano.get("correcciones") or {}
    corr = {**guardadas, **(correcciones or {})}
    r = extraer(str(ruta), escala or corr.get("escalaPtPorMetro"), corr)

    previos = _mapa(obra.get("elementos") or [])
    nuevos = _mapa(r["elementos"])
    conservados = 0
    salida = []
    for e in r["elementos"]:
        viejo = previos.get(e["id"])
        if viejo and viejo.get("revisadoPorUsuario"):
            fusion = dict(e)
            for k in CAMPOS_DEL_USUARIO:
                if k in viejo:
                    fusion[k] = viejo[k]
            fusion["revisadoPorUsuario"] = True
            conservados += 1
            salida.append(fusion)
        else:
            salida.append(e)

    manuales = {i for i, e in previos.items() if e.get("origen") == "manual"}
    altas = [i for i in nuevos if i not in previos]
    bajas = [i for i in previos if i not in nuevos and i not in manuales]

    # los elementos agregados a mano no los devuelve el extractor: se conservan
    agregados = [e for e in (obra.get("elementos") or [])
                 if e.get("origen") == "manual" and e["id"] not in nuevos]
    obra["elementos"] = salida + agregados
    obra["plano"] = {**plano,
                     "escala": r["escala"],
                     "referencia": r["referencia"],
                     "paginaPt": r["paginaPt"],
                     "correcciones": corr,
                     "avisosExtraccion": r["avisos"],
                     "extraidoEl": C.ahora()}
    obra["validacion"] = {**vinculos.recalcular(obra), "corridaEl": C.ahora()}

    return {"resumen": vinculos.resumen(obra),
            "cambios": {"altas": len(altas), "bajas": len(bajas),
                        "conservados": conservados, "manuales": len(agregados),
                        "idsBaja": bajas[:20]},
            "avisos": r["avisos"]}
