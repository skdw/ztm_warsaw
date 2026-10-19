<h1 align="center">🚍 ZTM Varsovia para Home Assistant</h1>

<p align="center">
  <strong>Las próximas salidas programadas de una línea de autobús, tranvía, metro o nocturna de Varsovia, como sensor.<br>Con los datos abiertos de la ciudad. Sin YAML y sin promesas de seguimiento en vivo.</strong>
</p>

<p align="center">
  🇬🇧 <a href="README.md">English</a>
  &nbsp;·&nbsp;
  🇵🇱 <a href="README.pl.md">Polski</a>
  &nbsp;·&nbsp;
  🇺🇦 <a href="README.uk.md">Українська</a>
  &nbsp;·&nbsp;
  🇷🇺 <a href="README.ru.md">Русский</a>
  &nbsp;·&nbsp;
  🇩🇪 <a href="README.de.md">Deutsch</a>
  &nbsp;·&nbsp;
  🇪🇸 <strong>Español</strong>
  &nbsp;·&nbsp;
  🇫🇷 <a href="README.fr.md">Français</a>
  &nbsp;·&nbsp;
  🇮🇹 <a href="README.it.md">Italiano</a>
</p>

<p align="center">
  <a href="https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml"><img src="https://github.com/solarssk/ztm_warsaw/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  &nbsp;
  <a href="https://codecov.io/gh/solarssk/ztm_warsaw"><img src="https://codecov.io/gh/solarssk/ztm_warsaw/graph/badge.svg" alt="Codecov"></a>
  &nbsp;
  <a href="https://sonarcloud.io/summary/new_code?id=solarssk_ztm_warsaw"><img src="https://sonarcloud.io/api/project_badges/measure?project=solarssk_ztm_warsaw&metric=alert_status" alt="Quality Gate Status"></a>
  &nbsp;
  <a href="https://securityscorecards.dev/viewer/?uri=github.com/solarssk/ztm_warsaw"><img src="https://api.securityscorecards.dev/projects/github.com/solarssk/ztm_warsaw/badge" alt="OpenSSF Scorecard"></a>
</p>

<p align="center">
  <a href="https://github.com/solarssk/ztm_warsaw/releases"><img src="https://img.shields.io/github/v/release/solarssk/ztm_warsaw?include_prereleases&label=release&color=066fd1" alt="release"></a>
  &nbsp;
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Default-41BDF5" alt="HACS Default"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.1%2B-41BDF5?logo=homeassistant&logoColor=white" alt="Home Assistant 2026.1+">
  &nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/github/license/solarssk/ztm_warsaw" alt="License: MIT"></a>
</p>

<details>
<summary><strong>Índice</strong></summary>

- [Funciones](#-funciones)
- [Capturas de pantalla](#-capturas-de-pantalla)
- [Requisitos](#-requisitos)
- [Cómo conseguir una clave o un token](#-cómo-conseguir-una-clave-o-un-token)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Solución de problemas](#-solución-de-problemas)
- [Documentación](#-documentación)
- [Colaboración y seguridad](#-colaboración-y-seguridad)
- [Datos y agradecimientos](#-datos-y-agradecimientos)
- [Licencia](#-licencia)

</details>

Muestra las próximas **salidas programadas** de una línea del transporte público de Varsovia (autobús, tranvía, metro, tren urbano o línea nocturna) en un poste de parada como sensor en Home Assistant, a partir de los datos abiertos de la ciudad de Varsovia. Sirve para paneles y automatizaciones como «sal dentro de ocho minutos» sin abrir una aplicación de horarios.

Muestra el **horario**, no los vehículos en vivo. Lo que **no** hace:

- no muestra posiciones en vivo, retrasos ni incidencias: la ciudad publica salidas planificadas, actualizadas una vez al día;
- no muestra horarios de otros días: la API sirve solo el día de servicio actual;
- no planifica viajes: para eso está [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funciones

- ✅ Líneas de autobús, tranvía, metro, nocturnas, de cementerio, exprés y locales.
- ✅ Varias instancias: sigue tantas paradas y líneas como quieras.
- ✅ La próxima salida como marca de tiempo, utilizable en la interfaz y en automatizaciones, y las tres siguientes como atributos (`Next 1` ... `Next 3`).
- ✅ Un estado claro «No service» los días en que una línea no circula y `unavailable` cuando falla la API de la ciudad (véase [Solución de problemas](#-solución-de-problemas)).
- ✅ Configuración completa en la interfaz de Home Assistant, en inglés, polaco, ucraniano, ruso, alemán, español, francés o italiano (los textos distintos del inglés y el polaco están traducidos automáticamente: las correcciones son bienvenidas como pull request).
- ✅ Atributos con la parada (su nombre y posición, así aparece como un marcador en la tarjeta de mapa), la dirección, un enlace al horario y notas.
- ✅ Cambia la clave API o el token de una entrada en cualquier momento en **Configurar**, por ejemplo de la API antigua de la ciudad a la nueva.
- ✅ Una entidad de **calendario** por sensor (desactivada por defecto: actívala en los ajustes de la entidad) con cada salida del día como evento de un minuto: ves todo el horario en la vista de calendario de Home Assistant e inicias automatizaciones con el disparador de calendario («8 minutos antes de una salida») sin plantillas.

---

## 📸 Capturas de pantalla

### Configuración de la integración
*Indica tu clave API y los datos de la parada...*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspecto de la entidad

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Atributos
*Entidad de ejemplo con salidas y atributos como la hora, la dirección...*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Requisitos

- Home Assistant 2026.1 o posterior
- Una clave API o un token de la ciudad de Varsovia (abajo)

---

## 🧭 Cómo conseguir una clave o un token

La ciudad tiene dos portales, y la integración acepta la clave de cualquiera de ellos:

- **Nuevo (recomendado):** en [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api) escribe un apodo, acepta las condiciones y descarga tu propio token. Es un texto largo en tres partes separadas por puntos.
- **Antiguo:** una clave de [api.um.warszawa.pl](https://api.um.warszawa.pl) tiene el aspecto `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Las claves antiguas existentes siguen funcionando al escribir esto, pero la ciudad no da fecha ni promesa de cuánto, así que pasa a un token cuando puedas.

La integración reconoce cuál has pegado y habla solo con la API correspondiente. Para pasar una entrada existente a un token, usa **Configurar** en esa entrada e introduce el token (la parada y la línea se mantienen); no añadas una segunda entrada, porque dos entradas de la misma parada, poste y línea no pueden coexistir y el asistente rechaza la segunda.

---

## 📦 Instalación

### Con HACS

1. En Home Assistant, ve a **HACS → Integraciones**.
2. Busca **Warsaw Public Transport**.
3. Pulsa **Descargar** y confirma.
4. Reinicia Home Assistant.

### Manualmente

1. Descarga la última versión de [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copia la carpeta `ztm_warsaw` en `/config/custom_components/`.
3. Reinicia Home Assistant.

---

## 🔌 Configuración

1. Ve a **Ajustes → Dispositivos y servicios**.
2. Pulsa **+ Añadir integración** y busca **Warsaw Public Transport**.
3. Rellena:
   - **clave API o token** (véase arriba),
   - **ID de la parada** y **número de poste** (por ejemplo 7009 y 01),
   - **número de línea** (por ejemplo 151).

La entidad se llama según la parada y la línea, por ejemplo `sensor.line_151_from_7009_01`. Para cambiar la clave API o el token de una entrada (por ejemplo, de una clave antigua a un token), usa **Ajustes → Dispositivos y servicios → Warsaw Public Transport → Configurar** en esa entrada; la parada y la línea se mantienen. Una entrada que aún usa una clave antigua muestra un aviso descartable en **Ajustes → Reparaciones**.

**El ID de la parada y el número de poste** no son lo mismo: el ID de la parada es común a todos los postes de una parada, y el número de poste (normalmente 01, 02, ...) es el número pintado en el cartel del poste (*słupek*). Una parada con varias direcciones tiene un número distinto para cada una.

---

## 🩺 Solución de problemas

- **El estado es `unknown` y el atributo dice «No service».** La línea no circula hoy o ya pasó su última salida. No es un error: consulta [wtp.waw.pl](https://wtp.waw.pl) o llama al 19115.
- **El sensor está `unavailable`.** La API de la ciudad respondió, pero no con un horario: se rechazó la clave o el token, la parada, el poste y la línea no son conocidos por la API, o la respuesta tenía un formato que la integración no entiende. Si falla ya la primera carga (no por una clave rechazada, véase abajo), la integración aparece como *reintentando la configuración* y Home Assistant reintenta solo. El error está en el registro de Home Assistant (la clave nunca se registra), y el sensor se recupera solo cuando la API vuelve a responder bien; si no, revisa en los ajustes la clave y la parada, el poste y la línea.
- **Home Assistant pide una clave nueva (reautenticación).** La API antigua respondió «clave rechazada» tres veces seguidas (los reintentos de una configuración también cuentan; una caída intermedia reinicia la cuenta). Introduce una clave o un token nuevos en el aviso; la parada y la línea se mantienen, y se acepta una clave aunque la línea hoy no circule. Hasta entonces, el sensor sigue `unavailable`. La API nueva responde igual a cualquier solicitud rechazada, así que un token rechazado no se distingue allí de una caída: el sensor conserva el horario guardado hasta el final de su día de servicio, luego pasa a `unavailable` y no aparece ningún aviso; si revocaste el token, introduce uno nuevo en **Configurar** en la entrada.
- **Informar de un problema.** Abre la entrada de la integración, usa *Descargar diagnóstico* y adjunta el archivo al issue: muestra la entrada y el estado del horario, con la clave o el token sustituidos por `**REDACTED**`.
- **Los datos parecen obsoletos durante una caída.** Un tiempo de espera, un error de red o un error del servidor (HTTP 5xx) tras una carga correcta **no** deja el sensor `unavailable`: conserva el último horario y vuelve a intentarlo cada hora, porque el horario son datos planificados que no cambian en un día. El sensor de diagnóstico **Last update** (desactivado por defecto; actívalo en los ajustes de la entidad) muestra cuándo se obtuvieron los datos por última vez con éxito.
- **La configuración dice que no se encontró la línea.** La API lista solo las líneas que circulan hoy. Una línea que hoy no circula (por ejemplo, una línea de días laborables en domingo) no se puede añadir hasta el día en que circula.
- **Falta aquí una línea de wtp.waw.pl.** El planificador de viajes tiene más datos que la API pública. Eso no se puede arreglar en la integración.
- **Líneas nocturnas** (`N01`, `N44` ...): la ciudad cuenta toda la noche como parte del día de servicio anterior, así que un autobús a las `24:50` o `26:20` sigue en el horario de ese día. La integración lee bien esas horas, de modo que una salida a las `02:15` (`26:15` en la API) a las 02:00 se muestra como «en 15 minutos».

---

## 📚 Documentación

La [wiki](https://github.com/solarssk/ztm_warsaw/wiki) es el manual de usuario: instalación, configuración, cómo funcionan el horario y el día de servicio, y solución de problemas. Se publica desde [`docs/wiki/`](docs/wiki) en este repositorio (en inglés).

---

## 🧑‍💻 Colaboración y seguridad

Las ideas, los informes de errores y los pull requests son bienvenidos: véase [CONTRIBUTING.md](CONTRIBUTING.md). Para informar de una vulnerabilidad, véase [SECURITY.md](SECURITY.md).

---

## 🙌 Datos y agradecimientos

Datos: la ciudad de Varsovia (**Miasto Stołeczne Warszawa**) y la Autoridad de Transporte Público de Varsovia (**Zarząd Transportu Miejskiego**, ZTM), a través del portal de datos abiertos de la ciudad ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), bajo la licencia [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.es).

Este proyecto fue planificado y diseñado por completo por mí: desde el concepto y el comportamiento esperado de la integración hasta cómo interactúa con la API pública de la ciudad de Varsovia. No soy un desarrollador profesional de Python, pero entiendo lo esencial lo bastante bien como para definir la estructura, la lógica y las funciones que quería que ofreciera.

Para darle vida usé apoyo de IA (ChatGPT), que me ayudó sobre todo con la sintaxis, la depuración y detalles de implementación. Sin embargo, el diseño general, el comportamiento y el flujo de trabajo los planteé yo.

Un agradecimiento especial a [@peetereczek](https://github.com/peetereczek/ztm), cuyo proyecto anterior me inspiró al principio. Aunque esta versión final se construyó de forma independiente desde cero, su trabajo me dio el primer impulso para abordar las cosas a mi manera.

Si te interesa mejorar o ampliar el proyecto, ¡adelante! Las contribuciones, ideas y pull requests siempre son bienvenidos.

---

## 📄 Licencia

Licencia MIT
