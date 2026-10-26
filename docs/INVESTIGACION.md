# Guía e investigación: impuestos de EE.UU. (federal, estatal y local)

Esta guía resume la investigación usada para construir DeclaraFácil USA: cómo se calculan los impuestos federales, estatales y de condado/ciudad para los años fiscales 2025 y 2026, cómo funciona TurboTax, qué ofrecía la aplicación del IRS (Direct File) y cómo la aplicación replica ese flujo.

## 1. Calendario

- Año fiscal 2025: la declaración vence el 15 de abril de 2026 (prórroga automática con Form 4868 hasta el 15 de octubre de 2026; la prórroga es para presentar, no para pagar).
- Año fiscal 2026: vence el 15 de abril de 2027.
- Pagos estimados 2026 (trabajadores independientes): 15-abr-2026, 15-jun-2026, 15-sep-2026 y 15-ene-2027.
- Excepciones estatales comunes: Virginia 1 de mayo, Delaware e Iowa 30 de abril, Louisiana 15 de mayo, Hawaii 20 de abril.

## 2. Impuesto federal (Formulario 1040)

### 2.1 Flujo del cálculo

1. Ingreso total = salarios (W-2) + intereses + dividendos + jubilación tributable + Seguro Social tributable + ganancias de capital + negocio propio (Anexo C) + desempleo + otros.
2. Menos ajustes (Anexo 1): mitad del impuesto de trabajo independiente, HSA, IRA, intereses de préstamos estudiantiles, gastos de educador, seguro médico de independientes = Ingreso Bruto Ajustado (AGI).
3. Menos la deducción estándar o las itemizadas (Anexo A), la deducción QBI (sección 199A) y las nuevas deducciones del Anexo 1-A = Ingreso tributable.
4. Impuesto por tramos (las ganancias de largo plazo y dividendos calificados usan 0%, 15% o 20%).
5. Más AMT (si aplica). Menos créditos no reembolsables (hijos, cuidado de dependientes, educación, ahorrador).
6. Más otros impuestos (trabajo independiente 15.3%, Medicare adicional 0.9%, impuesto de inversión neta 3.8%).
7. Menos pagos (retenciones, estimados) y créditos reembolsables (EITC, ACTC, 40% del AOTC) = reembolso o saldo a pagar.

### 2.2 Ley OBBBA (One Big Beautiful Bill Act, P.L. 119-21, firmada el 4 de julio de 2025)

- Hace permanentes los 7 tramos (10% a 37%) y la deducción estándar ampliada.
- Deducción estándar 2025: $15,750 soltero/casado por separado, $31,500 casados en conjunto, $23,625 cabeza de familia. 2026: $16,100 / $32,200 / $24,150.
- Crédito por hijo: $2,200 por hijo menor de 17 (2025 y 2026); parte reembolsable hasta $1,700; requiere SSN.
- Nuevo Anexo 1-A (2025-2028): propinas calificadas hasta $25,000; horas extra (solo la prima) hasta $12,500 ($25,000 en conjunto); ambas se reducen con MAGI > $150,000 ($300,000 en conjunto). Interés de préstamo de auto nuevo ensamblado en EE.UU. hasta $10,000 (se reduce con MAGI > $100,000 / $200,000). Deducción adicional de $6,000 por persona de 65+ (se reduce 6% del MAGI que exceda $75,000 / $150,000).
- Tope SALT (impuestos estatales y locales): $40,000 en 2025 y $40,400 en 2026, se reduce 30% del MAGI sobre $500,000 ($505,000 en 2026), nunca por debajo de $10,000.
- Desde 2026: deducción de donaciones en efectivo para quien no itemiza ($1,000 / $2,000), piso de 0.5% del AGI para donaciones itemizadas, y límite al beneficio de las itemizadas para el tramo del 37%.
- Crédito por cuidado de dependientes desde 2026: tasa máxima 50% (baja a 35% y luego hasta 20% según el AGI).
- AMT 2026: exención $90,100 / $140,200; eliminación gradual desde $500,000 / $1,000,000 al 50%.

### 2.3 Tramos federales

| Tasa | Soltero 2025 | Casados conj. 2025 | Soltero 2026 | Casados conj. 2026 |
|------|------|------|------|------|
| 10% | $0 | $0 | $0 | $0 |
| 12% | $11,925 | $23,850 | $12,400 | $24,800 |
| 22% | $48,475 | $96,950 | $50,400 | $100,800 |
| 24% | $103,350 | $206,700 | $105,700 | $211,400 |
| 32% | $197,300 | $394,600 | $201,775 | $403,550 |
| 35% | $250,525 | $501,050 | $256,225 | $512,450 |
| 37% | $626,350 | $751,600 | $640,600 | $768,700 |

Cabeza de familia y casados por separado tienen tablas propias (incluidas en data/federal_AAAA.json).

### 2.4 Otros valores clave

- EITC máximo: $8,046 (2025) y $8,231 (2026) con 3+ hijos; límite de ingresos de inversión $11,950 / $12,200.
- Base salarial del Seguro Social: $176,100 (2025) y $184,500 (2026).
- Interés de préstamo estudiantil: máximo $2,500.
- Educadores: $300 (2025), $350 (2026).
- Crédito del ahorrador 2026: límites de AGI $80,500 (conjunto), $60,375 (cabeza de familia), $40,250 (otros).
- IRS Direct File: NO estará disponible en la temporada 2026. Alternativas gratuitas: IRS Free File (software de socios del IRS para AGI bajo), VITA/TCE y formularios rellenables.

## 3. Impuestos estatales

- 8 estados no cobran impuesto sobre salarios: Alaska, Florida, Nevada, New Hampshire (eliminó el impuesto a intereses/dividendos en 2025), South Dakota, Tennessee, Texas y Wyoming. Washington solo grava ganancias de capital de largo plazo (7%, y 9% sobre $1 millón).
- 15 estados tienen tasa única en 2026 (AZ 2.5%, CO 4.4%, GA 5.19%, ID 5.3%, IL 4.95%, IN 2.95%, IA 3.8%, KY 3.5%, LA 3%, MI 4.25%, MS 4%, NC 3.99%, OH 2.75%, PA 3.07%, UT 4.5%).
- Los demás (más DC) usan tramos progresivos; la tasa más alta es California 13.3% (incluye 1% de salud mental sobre $1M).
- Casi todos parten del AGI federal; Colorado, Idaho, Iowa, Montana, New Mexico, North Dakota y South Carolina parten del ingreso tributable federal.
- La mayoría exenta el Seguro Social; lo gravan total o parcialmente CO, CT, MN, MT, NM, RI, UT y VT.
- Varios estados no se habían actualizado a la deducción estándar de OBBBA a inicios de 2026 (p. ej., AZ, ME, SC): verifique las instrucciones del estado.
- Cambios 2026: bajaron tasas IN, KY, MS, MT, NE, NC, OH (pasa a tasa única) y OK (3 tramos). Cambios retroactivos a 2025: GA 5.19%, ID 5.3%, UT 4.5%, MD nuevos tramos de 6.25% y 6.5% con deducción estándar fija ($3,350 / $6,700) y recargo de 2% a ganancias de capital con AGI > $350,000.
- Ohio (ORC 5747.02): 2025 = $342 + 2.75% sobre $26,050 y $2,394.32 + 3.125% sobre $100,000; 2026 = $332 + 2.75% sobre $26,050.

## 4. Impuestos locales (condados y ciudades)

- Maryland: los 23 condados y Baltimore City cobran 2.25% a 3.30% sobre el ingreso tributable de MD (Anne Arundel y Frederick con tasas por tramos). Para 2026 Allegany sube a 3.20% y Kent a 3.30%.
- Indiana: los 92 condados cobran entre 0.5% y 3.0% (p. ej., Marion 2.02%). En 2026 suben Carroll, Grant, Greene, Howard, Shelby y Union.
- New York City: 3.078% a 3.876% sobre el ingreso tributable de NY. Yonkers: 16.75% del impuesto estatal.
- Pennsylvania: Filadelfia (Wage Tax de residente 3.74% desde julio de 2025, 3.735% desde julio de 2026); casi todos los municipios cobran EIT (~1%; Pittsburgh 3%).
- Ohio, Michigan, Kentucky, Missouri (Kansas City y St. Louis 1%), Alabama, Delaware (Wilmington), Iowa (recargo escolar), Oregon (Portland Metro y Multnomah sobre ingresos altos) y Colorado (impuestos ocupacionales mensuales de Denver y Aurora).
- En el resto de los condados no hay impuesto sobre la renta; sí impuestos a la propiedad (deducibles en el Anexo A dentro del tope SALT) y a las ventas (promedio combinado nacional 7.53% en 2026).

## 5. Cómo funciona TurboTax (y qué replica esta aplicación)

1. Perfil e importación: datos personales, estado civil, dependientes; importa el año anterior y formularios W-2/1099.
2. Entrevista guiada: preguntas en lenguaje sencillo por secciones (ingresos, deducciones y créditos, otros impuestos), mientras un medidor de reembolso se actualiza en vivo en la parte superior.
3. Comparación automática entre deducción estándar e itemizada.
4. Declaración estatal: se prepara después de la federal reutilizando los datos.
5. Revisión ("CompleteCheck"): busca errores, campos faltantes y montos inusuales.
6. Presentación electrónica (e-file) federal y estatal, pago o depósito del reembolso.

DeclaraFácil USA replica los pasos 1 a 5 (menú principal, entrevista por secciones con barra lateral, medidor de reembolso federal/estatal/local en vivo, revisión con hallazgos y exportación del borrador 1040 + estatal + local a PDF/HTML). No hace e-file: para transmitir al IRS se requiere ser proveedor autorizado (EFIN y pruebas de MeF).

## 6. La aplicación del IRS

- IRS Direct File (2024-2025): permitía presentar gratis directamente al IRS en estados participantes, con una entrevista sencilla para W-2, Seguro Social, desempleo, intereses, EITC y CTC. Fue descontinuado: no estará disponible en 2026.
- IRS2Go (app móvil) y la cuenta en línea del IRS: consultar reembolso, pagar (Direct Pay), ver transcripciones.
- La aplicación toma de Direct File la idea de una entrevista corta en lenguaje sencillo y la de mostrar el resultado línea por línea.

## 7. Limitaciones del estimador

No modela: depreciación y bienes de negocio, alquileres (Anexo E), K-1, multas por pago insuficiente (2210), multa del 10% por retiros anticipados, créditos de energía, impuesto de ganancias no recapturadas (25%/28%), reglas de residentes parciales detalladas, recapturas de tramos de NY y CT, ni créditos estatales específicos (agréguelos como "otros créditos estatales"). Las tasas están en data/*.json y pueden editarse.

## Fuentes

- IRS, Rev. Proc. 2025-32 e IR-2025-103 (ajustes 2026 con OBBBA): irs.gov/newsroom
- IRS, fact sheet OBBBA (propinas, horas extra, auto, mayores) y Anexo 1-A
- IRS, Rev. Proc. 2024-40 (ajustes 2025); límites de retiro 2026 (Notice 2025-67)
- Tax Foundation: State Individual Income Tax Rates and Brackets 2025 y 2026; State and Local Sales Tax Rates 2026
- Comptroller of Maryland: Withholding Tax Facts 2025 y Tax Alert de la sesión legislativa 2025
- Indiana Department of Revenue: tasas de condados 2025 y cambios 2026
- City of Philadelphia (Wage Tax); Ohio Revised Code 5747.02
- Información sobre el cierre de IRS Direct File (Kiplinger, NATP, prensa)
