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
- Parentesco del dependiente: se guarda la clave en español de `RELATIONSHIPS`; `_CHILD_RELATION_RE` (`models.py`) usa
  palabras completas en inglés para archivos con texto libre ("son" por subcadena aceptaba "Otra persona del hogar").
- `usuarios.json` que no se puede leer (bloqueo, no daño) se carga vacío con la marca `_unreadable` y `save()` se niega
  a escribirlo; un `AccountError` que llega a un callback de Tk queda en `errores.log` (no se perdió nada).
- `data_loader.user_dir()`: gana la carpeta (Documentos o USERPROFILE) que ya tiene `usuarios.json`, después la que
  exista; solo se crea si no hay ninguna. No volver a elegir por "existe Documentos" en cada llamada.
- `updater.save_config` guarda solo lo que difiere de `data/actualizaciones.json`. Un cambio de repositorio en `data/`
  debe publicarse en una versión posterior a la 2026-11-03 (las PC que ya guardaron `repo` lo conservan hasta que
  coincida con el publicado).
- `user_dir()` también reconoce `~/.declarafacilusa` (la carpeta de respaldo si Documentos está bloqueado) cuando tiene
  `usuarios.json`.
- `login_failed` de un usuario que no existe se anota con usuario vacío a propósito: lo escrito puede ser la contraseña
  puesta en el campo equivocado (`actividad.log` lo ven Supervisores y va en los respaldos).
- Al eliminar un usuario, lo que queda en su carpeta (PDF exportados) pasa a `<quien recibe>/<usuario>_eliminado_<fecha>/`
  con `rename` (todo o nada); `list_returns` no lo muestra como declaración, `can_access_path` sí lo permite a quien lo recibe.

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
- Cálculos que cambian montos, encontrados el 2026-11-02 (verificar con la ley/Pub. antes de tocar):
  recién nacido/fallecido en el año con `months_lived` ≤ 6 pierde CTC/EITC (Pub. 501: cuenta todo el año; ¿regla en
  código o texto de ayuda?, `models.py:~128`); `qualifies_care` sin `months_lived` ni parentesco (§21(b)(1), padre no
  custodio, `models.py:~140`); quien `can_be_claimed` recibe CTC/ODC/ACTC (§152(b)(1); el AOTC usa "otro lo reclama",
  `federal.py:~440`); MFS que vivió separado todo el año usa base $0 del Seguro Social (`federal.py:~180`, falta el
  campo); Maine sin `hoh` en `states_2025/2026.json` (usa la de soltero) y AZ 2026 `hoh` = soltero.
- `clean_money_text`: "1.500,50" → 1.5005 y "45.000" → 45 (formato con punto de miles). Decidir cómo leer "12.345".
- Cierre por inactividad (`gui/app.py:~454`): con una declaración nueva sin guardar la sesión nunca se cierra y los datos
  quedan a la vista. ¿Autoguardar en `recuperado_<fecha>.dfusa` o pantalla de bloqueo?
- Asistente de IA: `include_data=True` por defecto envía montos de la declaración al proveedor sin consentimiento del
  cliente (IRC §7216 para preparadores). Decidir aviso/consentimiento.
- Actualizador: las tablas `data/*.json` que el admin edita (la pantalla lo invita) se reemplazan sin aviso en cada
  actualización de código (`updater.py:~397`). "Actualización cancelada" (`gui/updates.py:~135`) se muestra cuando
  `apply_code()` ya dejó la versión nueva activa para el próximo arranque.
- Formularios: al volver a generar quedan en la carpeta PDF de la vez anterior (Anexo C, 1040-V con otro saldo)
  (`forms/__init__.py:~111`). Borrar archivos del usuario es decisión del dueño.
- `gui/theme.py:~150` `except Exception` silencioso al leer fuentes (y guarda un conjunto vacío para siempre); Tk no
  se puede probar en la nube.
- Duplicación que conviene unir (resultados iguales): aritmética del 1-A/8812/2441 recalculada en `build.py`; gastos
  del Anexo C escritos dos veces (`build.py:~442`, `models.py:~310`); `_get_json`/`_fetch` del actualizador con
  encabezados distintos; edad 65 y 55 sin constante en 9 sitios (`SENIOR_AGE`, `HSA_CATCHUP_AGE`); `compute_federal`
  (~485 líneas) por secciones.
- Impuesto local del lugar de trabajo (`local.py:~120`) con la tasa de residente y sin crédito: Columbus/Cleveland
  $50k → $2,500 (real ~$1,250, Columbus acredita hasta 2,5 %); no residente en Detroit 2,4 % en vez de 1,2 % y suma
  intereses/dividendos. Falta `nonresident_rate` en `local_<año>.json` y el crédito de OH. Cambia montos: verificar tasas.
- ODC $500 para un dependiente que no vive en EE. UU. (`federal.py:~442`): §24(h)(4) exige ciudadano/nacional/residente;
  la casilla `lived_in_us` no es eso. ¿Campo de ciudadanía/residencia? Cambia montos.
- Cerrar la app en los 5 s tras actualizar (`gui/app.py:73`, `after(5000, confirm_code_ok)`) marca la versión como mala
  para siempre. Llamar también `confirm_code_ok()` en `quit_app()` (interfaz: no se prueba en la nube).
- Inicio de sesión: un usuario inexistente responde distinto y más rápido (sin PBKDF2) que uno existente ("Intentos
  restantes: N") → revela qué usuarios existen. ¿Mismo mensaje y mismo cálculo?
- "Ajustes generales y seguridad" (intentos, minutos de bloqueo, largo de contraseña) los cambia quien tenga
  `manage_users` (`gui/settings.py:29`, `accounts.update_settings`). ¿Solo Administrador?
- Duplicación menor: `storage.returns_dir()` arma a mano `accounts.returns_dir()`; `gui/app.py` `_activity` =
  `reset_idle_timer` y `_open_folder` solo llama a `_open_path`; User-Agent `DeclaraFacilUSA/...` en `counties.py` y 3
  veces en `updater.py`; números sueltos `0.94/0.88` (`layout.py`), `[:8]` recientes (`storage.py`), `30_000` (`app.py`).
- Propuestas de estructura: una sola función para tareas en segundo plano en `ui.py` (hoy 8 copias), `ListEditor` para
  dependientes/W-2/locales en `screens.py`, unificar estado civil→clave, `ask_ai_action` por clave y no por posición.
- Encontrados el 2026-11-04 (cambian montos o necesitan la interfaz):
  - Pérdida de capital arrastrada: un solo campo y siempre se resta del corto plazo (`federal.py:136`, `build.py:541`,
    `screens.py:431`). Con arrastre de largo plazo grava de más (ej. 2025: $350). ¿Campo aparte para la línea 14 del Anexo D?
  - Pensilvania (y el EIT local de `local.py:49`) usa la casilla 1 del W-2; PA grava los aportes al 401(k) (casilla 16,
    `box16_state_wages`, se pide pero no se usa). Verificar la regla de PA y del EIT.
  - W-2 del cónyuge en MFS/soltero: la revisión ya lo marca como error, pero el cálculo lo sigue sumando
    (`federal.py:121`, `state.py:101`, `local.py:49,132`). ¿Filtrarlo también en el cálculo?
  - Carpetas de usuarios eliminados antes del 2026-11-04 siguen en `Declaraciones/<usuario>/` y un usuario nuevo con ese
    nombre las ve. ¿Archivarlas al crear el usuario?
  - "Guardar como" `Garcia.Maria` dos veces pisa `Garcia.Maria.dfusa` sin preguntar: el diálogo comprueba el nombre sin
    extensión (`gui/app.py:~370`). Pedir confirmación si `p + ".dfusa"` existe.
  - `gui/settings.py:237` descarga de fuentes con `except Exception` sin `logger.exception` (interfaz).
  - Limpieza con resultados iguales: `models.py` conversión a número repetida en 10 `__post_init__` (dos con listas a
    mano); `build.py:517,934` vuelve a leer como texto un monto ya formateado (`_num`; puede cambiar $1 por redondeo);
    regla "el 1040-SR no lleva su última página" en `forms/__init__.py:105` y `build.py:272`; caso especial `"s3"` en
    el bucle de `build.py:162`; números sin nombre en `build.py` (2210 1000, 1116 300/600, 8283 500, 8949 11 filas,
    Anexo B 14/15, Anexo C 9/8).

## Historial
### 2026-11-04 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `storage.py:34` "Guardar como" con punto (`Garcia.Maria`) usaba `with_suffix` y pisaba `Garcia.dfusa` sin aviso → se
  agrega la extensión (y `.json` antiguo pasa a `.dfusa`). Prueba en `test_engine.py`.
- `review.py`: W-2 del cónyuge en una declaración no conjunta se sumaba como salario propio → error en la revisión.
- `data_loader.py:49` las cuentas en `~/.declarafacilusa` (Documentos bloqueado) se ignoraban al desbloquearse → cuenta
  como carpeta con `usuarios.json`. `accounts.py:322` el texto de un usuario inexistente iba tal cual a `actividad.log`.
- `accounts.py:277` al eliminar un usuario sus PDF (SSN, cuenta) quedaban para un usuario nuevo con el mismo nombre →
  `_archive_leftovers`. Prueba con la carpeta `*_formularios`.
- `questions.py:124` número de ruta solo por largo → dígito de control ABA (`_routing_ok`).
- Limpieza sin cambio de montos (3.000 declaraciones aleatorias iguales al centavo): `state.py` 4 copias de
  `phase_factor`; `federal.py` `ctc_allowed` = `has_ssn` y `_excess_ss` dos veces; `build.py` `self.other` muerto y
  edad del cónyuge repetida. `except Exception` acotados en `assistant.py:316` y `generar_manifiesto.py:49` (ahora avisa).
- Revisión del propio cambio (ponytail-review + Thermos): `rename` en vez de `shutil.move`, `isdecimal`, prueba de
  respaldo que había quedado partida, `HOME` fijo en las pruebas de cuentas, `http.client.HTTPException`.
- Pruebas: 135 → 141 pasan (7 de interfaz omitidas). Pendientes nuevos arriba.

### 2026-11-03 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `accounts.transfer_returns`/`unlock`: un Supervisor con "Crear usuarios" se llevaba las declaraciones del Administrador
  y lo desbloqueaba → `_require_admin` si la cuenta afectada es admin; la pantalla muestra el error.
- `data_loader.user_dir()`: si aparecía Documentos la app cambiaba a una carpeta vacía y pedía un admin nuevo → gana la
  carpeta con `usuarios.json` (ver Decisiones).
- `accounts.USERNAME_RE`: "ana." (Windows quita el punto: misma carpeta que "ana") y CON/NUL/COM1 → rechazados al crear.
- `updater.save_config`: `repo` quedaba congelado en la PC → solo se guarda lo distinto de `data/`.
- `local.py`: rama de Baltimore muerta, "threshold" copiaba `bracket_tax`, condición repetida, `earned_income` sin uso
  de `ret` (94.200 casos contra la versión anterior: 0 diferencias). `counties`: "…del Censo: None" → dice cuántos
  estados llegaron; `MIN_STATES`. Color `primary_dark` sin uso.
- Pendiente: local de trabajo (OH/MI), ODC fuera de EE. UU., cierre en 5 s tras actualizar, enumeración de usuarios,
  ajustes de seguridad (ver arriba).
### 2026-11-02 — revisión nocturna (PR #2, rama `revision-nocturna`)
- `models.py:~117` `is_child_relation`: "son" por subcadena → "Otra persona del hogar" recibía CTC y EITC (HOH $30k:
  $2,200 + $3,265) → regex de palabras completas (acepta Stepchild/Grandchild, rechaza Godson).
- `models.py` `qualifies_eitc`: ignoraba `lived_in_us` (§32(c)(3)(C)). Dependiente nacido después del año calificaba
  para CTC/EITC/cuidado y ODC → `born_by()`; `review.py` marca fechas imposibles ("2015-02-30") y futuras.
- `federal.py:~404` y `build.py` 8863: AOTC sin medio tiempo o con 4 años completados → `Student.aotc_eligible()`;
  sin líneas 26-30 tras el "Stop". 3.000 declaraciones contra la versión anterior: solo cambian las que tienen estos casos.
- `accounts.delete_user`: no dejaba borrar un admin ya desactivado.
- `assistant._dedupe`: enlaces de "Fuentes" de la IA abiertos con `webbrowser.open` sin revisar esquema (en Windows
  ejecuta rutas locales/UNC) → solo http/https.
- Pendiente: recién nacido, cuidado, `can_be_claimed`, MFS SS, Maine HOH, coma decimal, inactividad, consentimiento IA,
  tablas editadas, PDF viejos (ver arriba).
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
