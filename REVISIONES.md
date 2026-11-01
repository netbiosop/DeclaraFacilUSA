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
- `except Exception` con `logger.exception` en `gui/app.py` (abrir, calcular, exportar…) y `forms_view.py`: registran y
  evitan que la app se cierre; se dejan. `HomeA`/`HomeB`/`HomeC` (`home.py`) se eligen por tema: no son código muerto.
- Edades: `Dependent.age` cuenta al 31-dic por aniversario (Rev. Rul. 2003-72, CTC/EITC/cuidado y el crédito AZ);
  `age_at_year_end` (contribuyente y cónyuge) sigue con la regla del día anterior (65 años, HSA 55).
- `usuarios.json` que no se puede leer (bloqueo, no daño) se carga vacío con la marca `_unreadable` y `save()` se niega
  a escribirlo; un `AccountError` que llega a un callback de Tk queda en `errores.log` (no se perdió nada).

## Pendientes
- `taxapp/state.py` `_ss_subtraction`: umbrales estatales de Seguro Social (CT, MN, NM, RI, VT, WV) escritos en código e
  iguales para 2025 y 2026; MN y RI se ajustan cada año. Moverlos a `states_<año>.json` con valores 2026 verificados y
  pruebas por estado.
- `taxapp/gui/screens.py` (~1.050 líneas) y `taxapp/lang_en.py` (~1.500 líneas) conviene dividirlos.
- La interfaz (7 pruebas de GUI) no se puede probar en la nube: no hay Tkinter.
- **QSS (alta, cambia resultados)**: `federal.pick()` pasa por `sk()` y trata a QSS como MFJ en todos los umbrales de
  reducción (EITC `federal.py:~495`, CTC, Medicare adicional, base del Seguro Social, préstamo estudiantil, AOTC/LLC,
  QBI, Schedule 1-A, CDCC 2026). La ley da el umbral conjunto solo a MFJ; QSS sí comparte tramos, deducción estándar,
  ganancias de capital, AMT y NIIT (agregar `"qss": 250000` a `niit.threshold`). Ej. 2025, 2 hijos, salario $40k:
  EITC QSS $5,145 vs HOH $3,646. `forms/build.py` f8863 ya usa el límite de "other" para QSS: formulario y cálculo no
  coinciden. Verificar tabla por tabla, corregir con pruebas por estado civil; afecta declaraciones QSS guardadas.
  `state.py:93,155` cuenta 2 personas para QSS: revisar por estado.
- Línea 16 del 1040 y EIC con fórmula en vez de la Tax Table (franjas de $50) cuando el ingreso tributable < $100,000:
  diferencias de $0–6 que el IRS corrige con aviso (`federal.py:46-105`).
- Oficina en casa (método simplificado) puede crear/aumentar pérdida del Anexo C; la Rev. Proc. 2013-13 la limita al
  ingreso bruto menos otros gastos (`models.py:~290`, `build.py:~449`).
- Actualizador: si falta el `.sha256` (o falla su descarga) se instala sin verificar y el diálogo dice "Descarga
  verificada" (`updater.py:~200,252`). Decidir si se rechaza. La versión del manifiesto se usa como nombre de carpeta sin
  validar (`updater.py:~384`, solo explotable por quien controla el repo).
- Tras una vuelta atrás automática, el proceso hijo hereda `DECLARAFACIL_CODE_ROOT` de la versión mala y
  `data_loader.app_dir()` la sigue usando; tampoco se fija `DECLARAFACIL_ROLLBACK`. Corregible en `restart()` (env sin
  `DECLARAFACIL_*`) por actualización; la parte de `data_loader` del instalador solo con un instalador nuevo.
- Medicare adicional: si la casilla 5 del W-2 está vacía se usa la casilla 1 (`federal.py:132,516`).
- Montos aún escritos en código: `build.py:617` (cuidado de dependientes 2500/5000, ¿cambia en 2026?), `screens.py:346,525`,
  `gui/tools.py:175`, `assistant.py:243-244`, `review.py:131` (IRA 7500), edades en `models.py`; textos de ayuda con montos
  de 2025 en `screens.py:637-731`; años 2025/2026 fijos en la interfaz en vez de `SUPPORTED_YEARS`. Montos estatales
  además de `_ss_subtraction` en todo `state.py` (MO, OR, AL, CT, IL, OH, MD, NM, AZ, CA, VT, UT).
- Cálculos que cambian montos y hay que verificar con la ley antes de tocar (revisión 2026-11-01):
  MFS que vivió separado los últimos 6 meses no recibe EITC (`federal.py:~478`, ARPA §32(d)(2)(B)); beneficios de
  cuidado del empleador: se resta el bruto y no lo excluido, y el 2441 no descuenta L30 (`federal.py:~376`,
  `build.py:~624`); interés de inversión sin el límite del 4952 (`federal.py:~277`); WA ganancias >$1M al 9 % (¿9,9 %
  por SB 5813?) en `states_2025/2026.json`; mínimo QBI 2026 de $400 sin exigir participación material y antes del
  tope (`federal.py:~319`); edad <13 del 2441 por aniversario (verificar Pub. 503).
- Anexo B: el límite de $1,500 está 5 veces (`questions.py:142-151`, `build.py:146`) y `build.py` también lo genera por
  `foreign_trust`, pero entonces la pregunta desaparece. Decidir la condición y una sola `needs_schedule_b()`.
- `earned_tp` (2441) se calcula igual en `federal.py:~378` y `build.py:~613`: devolverlo en el resultado.
- Propuestas de estructura: una sola función para tareas en segundo plano en `ui.py` (hoy 8 copias), `ListEditor` para
  dependientes/W-2/locales en `screens.py`, unificar estado civil→clave, `ask_ai_action` por clave y no por posición.

## Historial
### 2026-11-01 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `models.py` `Dependent.age`: un niño nacido el 1-ene salía un año mayor (regla del día anterior) y perdía CTC/EITC/
  cuidado → edad al 31-dic por aniversario.
- `federal.py:~480`: EITC conjunto sin SSN válido del cónyuge → se exigen los dos (§32(c)(1)(E), §32(m)).
- `federal.py:248,377` y `build.py:613`: la pérdida del Anexo C no restaba del ingreso del trabajo (EITC, ACTC, 2441,
  deducción estándar del dependiente) → `max(0, salario + ganancia − mitad SE)` (Pub. 596).
  Las tres comparadas en 2.000 declaraciones: solo cambian las que cumplen alguna condición.
- `build.py:605`: el 2441 contaba personas cuidadas distinto que el cálculo → usa `credits.n_care`.
- `accounts.py`: con `manage_users` un Supervisor podía hacerse Administrador, crear admins, restablecer su contraseña,
  borrarlo o cambiar la tabla de permisos → `_require_admin()` (pruebas nuevas).
- `review.py`: todo ITIN salía como "formato inválido" → se aceptan los grupos de ITIN y se avisa si un ITIN está marcado
  como SSN (contribuyente, cónyuge, dependiente).
- `gui/assistant.py`, `gui/updates.py`: `except Exception` sin registro → errores esperados + `logger.exception`.
  Clave `'Usted'` duplicada en `lang_en.py`; `self.state_cb` sin uso.
- Pendiente: MFS separado y EITC, beneficios de cuidado, interés de inversión, WA 9,9 %, QBI mínimo, Anexo B (ver arriba).
### 2026-10-28 — revisión nocturna (rama `revision-nocturna`, sobre `antislop`)
- `accounts.load()`: un `usuarios.json` bloqueado (OSError) se tomaba como vacío y el inicio de sesión lo guardaba encima
  en cada intento → marca `_unreadable`, `save()` lo rechaza, `authenticate` avisa; `update_settings` ya no escribe si
  nada cambió (pruebas nuevas).
- `gui/forms_view.py:255`, `gui/updates.py:113`: la lambda usaba `e` tras el `except` → NameError, `_failed` nunca corría
  (pantalla "Descargando…" para siempre) → `lambda err=e:` y registro.
- `gui/workspace.py:39`, `assistant.py:195-208`: casillas sí/no contaban como montos → `models.nonzero_amounts()`.
- `gui/app.py` `save()`: fallo de disco silencioso y ruta `.json` no actualizada al guardar como `.dfusa` → `_write()`
  con aviso; autoguardados con `quiet=True`.
- `widgets.parse_money` / `models._num`: "1500,50" se guardaba como 150,050 → `clean_money_text()` (coma decimal).
- `updater.py` errores de `.sha256` y `check_any` ignorados; `gui/settings.py:577` `except Exception` silencioso.
- `forms/build.py`: tasas y límites AOTC/LLC/CTC/QBI/Medicare leídos del JSON (1.500 declaraciones: formularios
  idénticos). Código muerto: `widgets.FONT`, `widgets.card`, `accounts.owner_of`, rama de `federal.pick`.
- Pendiente: QSS, Tax Table, oficina en casa, política de `.sha256`, entorno tras vuelta atrás (ver Pendientes).
### 2026-10-27 — revisión inicial (PR #1, rama `antislop`)
- `usuarios.json` dañado se tomaba como vacío y el asistente de inicio borraba todas las cuentas → ahora se guarda una
  copia `usuarios.danado-<fecha>.json` antes (prueba nueva).
- Registro `errores.log` en Documentos\DeclaraFacilUSA; errores de la interfaz y de abrir/calcular/exportar quedan
  con su detalle. Fallos que se ignoraban (idioma, configuración, condados, claves) ahora se anotan.
- `data_loader.read_json()` como único lector de JSON; `open_path()` en `gui/ui.py`.
- Montos por año a `data/federal_*.json`; resultados idénticos en 400 declaraciones de prueba.
- Eliminadas 10 funciones y 19 imports sin uso; `except Exception` reducidos a los errores posibles.
