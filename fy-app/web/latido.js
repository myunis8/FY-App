/* Latido: avisa al servidor que esta pestaña sigue abierta, cada pocos
 * segundos. Si no llega ninguno (de esta pestaña ni de ninguna otra) por
 * un rato largo, el servidor se cierra solo -- ver
 * app/main.py::_vigilar_latido y app/server.py::registrar_latido. Así no
 * hace falta ir a buscar la ventana de consola para cerrar la app: alcanza
 * con cerrar el navegador.
 *
 * Se incluye en TODAS las páginas (no sólo las que editan una obra, a
 * diferencia de lock.js) y arranca solo, sin necesidad de llamarlo.
 */
(function(){
  const latido = () => fetch('/api/latido', {method:'POST'}).catch(()=>{});
  latido();
  setInterval(latido, 5000);
})();
