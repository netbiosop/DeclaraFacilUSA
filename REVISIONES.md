# Registro de revisiones (antislop + Thermos)

Lo lee y lo actualiza la revisión nocturna antes de revisar. Cada revisión agrega una entrada arriba del historial.
- **Decisiones vigentes**: cosas que se dejaron así a propósito. No se "corrigen" ni se reportan como hallazgo
  salvo que haya una razón nueva; si la hay, se explica.
- **Pendientes**: problemas conocidos que necesitan una decisión del dueño o un trabajo más grande.
- **Historial**: qué se encontró, cómo se corrigió y en qué rama o pull request.

## Decisiones vigentes
- `main.py` es la base fija del instalador: no se modifica en correcciones de código. Las actualizaciones de
  `taxapp/`, `data/`, `docs/` y `assets/` corren sobre la base `__base__` (1.5.1). No usar módulos de Python que esa
  base no incluya (por ejemplo `logging.handlers`); ante la duda, revisar `crear_exe_windows.bat`.
- `except tk.TclError: pass` para ventanas o widgets ya cerrados se deja: es el comportamiento esperado de Tk.
- `main.py` hace `import tkinter` solo para comprobar que existe; no es un import sin uso.
- `SettingsWindow.build_*` se llaman con `getattr(self, "build_" + section)`; `redirect_request` en `updater.py` es
  un método que llama urllib. No son código muerto.
- Montos de impuestos que cambian por año van en `data/federal_<año>.json` / `data/states_<año>.json`; tasas y edades
  de la ley, como constantes con nombre en `federal.py`. Todo cambio de cálculo lleva prueba y debe dar los mismos
  resultados que antes salvo que la corrección sea justamente el cálculo.
- `actualizacion.json` lo regenera `publicar_actualizacion.bat`; las correcciones no lo tocan.
- El número de versión (`taxapp/__init__.py`) lo sube el dueño al publicar; las correcciones no lo tocan.
- `publicar_actualizacion.bat` publica la carpeta local del dueño encima de `main`: los cambios fusionados en GitHub
  deben llevarse a esa carpeta antes de publicar.

## Pendientes
- `taxapp/state.py` `_ss_subtraction`: umbrales estatales de Seguro Social (CT, MN, NM, RI, VT, WV) escritos en código e
  iguales para 2025 y 2026; MN y RI se ajustan cada año. Moverlos a `states_<año>.json` con valores 2026 verificados y
  pruebas por estado.
- `taxapp/gui/screens.py` (~1.050 líneas) y `taxapp/lang_en.py` (~1.500 líneas) conviene dividirlos.
- La interfaz (7 pruebas de GUI) no se puede probar en la nube: no hay Tkinter.

## Historial
### 2026-10-27 — revisión inicial (PR #1, rama `antislop`)
- `usuarios.json` dañado se tomaba como vacío y el asistente de inicio borraba todas las cuentas → ahora se guarda una
  copia `usuarios.danado-<fecha>.json` antes (prueba nueva).
- Registro `errores.log` en Documentos\DeclaraFacilUSA; errores de la interfaz y de abrir/calcular/exportar quedan
  con su detalle. Fallos que se ignoraban (idioma, configuración, condados, claves) ahora se anotan.
- `data_loader.read_json()` como único lector de JSON; `open_path()` en `gui/ui.py`.
- Montos por año a `data/federal_*.json`; resultados idénticos en 400 declaraciones de prueba.
- Eliminadas 10 funciones y 19 imports sin uso; `except Exception` reducidos a los errores posibles.
