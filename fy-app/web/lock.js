/* Bloqueo blando de edición por obra: evita que dos personas trabajen a la
 * vez sobre la misma obra en distintos módulos. Se apoya en un archivo
 * lock.json dentro de la carpeta de la obra en el repositorio (ver
 * app/sync.py) -- por eso sólo tiene efecto si hay un repositorio
 * configurado; si no, fyLock.iniciar() no hace nada (no hay con quién
 * coordinarse). Es un bloqueo blando: vence solo si nadie manda latido
 * durante un rato largo, y se puede forzar -- no hay forma de garantizar
 * exclusión real entre equipos que pueden estar sin conexión. El respaldo
 * real contra pisadas sigue siendo la verificación de sha al "Subir al
 * repositorio".
 *
 * Uso, en cada módulo que edita la obra (después de tener OBRA_ID definido):
 *   <script src="/lock.js"></script>
 *   ...
 *   fyLock.iniciar(OBRA_ID);
 * Deja la página bloqueada con un cartel hasta conseguir el lock (o hasta
 * que el usuario elija "Forzar apertura"). El latido y la liberación al
 * salir quedan andando solos.
 */
const fyLock = (() => {
  const LATIDO_MS = 4 * 60 * 1000;
  let obraId = null, latidoId = null, liberado = false;

  function minutosDesde(ts) {
    return Math.max(1, Math.round((Date.now() - ts) / 60000));
  }

  function mostrarCartel(info, onForzar) {
    quitarCartel();
    const div = document.createElement('div');
    div.id = 'fy-lock-overlay';
    div.style.cssText = 'position:fixed;inset:0;background:rgba(14,28,46,.72);'
      + 'display:flex;align-items:center;justify-content:center;z-index:99999;'
      + 'font-family:system-ui,sans-serif;padding:20px';
    const quien = (info.usuario || 'Otro usuario').replace(/[<>&]/g, '');
    const desde = info.desde ? `hace ${minutosDesde(info.desde)} min` : 'ahora mismo';
    div.innerHTML = `<div style="background:#fff;border-radius:12px;padding:22px 26px;max-width:420px;
        box-shadow:0 20px 60px rgba(0,0,0,.35)">
      <h2 style="margin:0 0 8px;font-size:1.05rem;color:#16283f;font-family:inherit">Obra en uso</h2>
      <p style="margin:0 0 16px;font-size:.88rem;color:#3a4552;line-height:1.5">
        <b>${quien}</b> la está editando ${desde}. Para no pisarse, esperá a que
        termine o coordiná antes de forzar la apertura.</p>
      <div style="display:flex;justify-content:flex-end;gap:8px">
        <button id="fy-lock-volver" style="border:1px solid #dde3e2;background:#fff;padding:8px 14px;
          border-radius:8px;cursor:pointer;font-size:.83rem;font-family:inherit">Volver</button>
        <button id="fy-lock-forzar" style="border:1px solid #c07f1f;background:#e2a33d;padding:8px 14px;
          border-radius:8px;cursor:pointer;font-weight:600;font-size:.83rem;font-family:inherit">Forzar apertura</button>
      </div>
    </div>`;
    document.body.appendChild(div);
    document.getElementById('fy-lock-volver').onclick = () => history.back();
    document.getElementById('fy-lock-forzar').onclick = () => { quitarCartel(); onForzar(); };
  }
  function quitarCartel() {
    document.getElementById('fy-lock-overlay')?.remove();
  }

  async function pedir(ruta, body) {
    try {
      const r = await fetch(ruta, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      const d = await r.json().catch(() => ({}));
      // un error del servidor (github caído, rate limit, etc.) no es un
      // conflicto real: no hay con qué compararse, así que no se bloquea
      return r.ok ? d : { ok: true };
    } catch (err) {
      return { ok: true };            // sin red: no se puede coordinar, no se bloquea la edición
    }
  }

  async function intentar(forzar) {
    const d = await pedir(`/api/obras/${obraId}/lock/tomar`, { forzar });
    if (d.ok) {
      quitarCartel();
      if (!latidoId) latidoId = setInterval(() => pedir(`/api/obras/${obraId}/lock/latido`, {}), LATIDO_MS);
      window.addEventListener('beforeunload', liberar);
      return;
    }
    mostrarCartel(d, () => intentar(true));
  }

  function liberar() {
    if (liberado || !obraId) return;
    liberado = true;
    if (latidoId) clearInterval(latidoId);
    navigator.sendBeacon?.(`/api/obras/${obraId}/lock/liberar`, new Blob([], { type: 'application/json' }));
  }

  return {
    iniciar(id) {
      obraId = id;
      if (obraId) intentar(false);
    },
  };
})();
