<h1 align="center">🚍 ZTM Varsovia para Home Assistant</h1>

<p align="center">
  <strong>Horarios del transporte público de Varsovia en Home Assistant.<br>Próximas salidas en tus paneles y automatizaciones. Configuración sin YAML.</strong>
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

La integración muestra **salidas programadas** a partir de los datos abiertos de la ciudad de Varsovia. Cada sensor muestra las salidas de una línea en un punto de parada concreto. Puedes añadirlas a tu panel de Home Assistant o usarlas en automatizaciones, por ejemplo para recordar cuándo salir de casa antes de que pase el autobús.

Los datos proceden de los horarios publicados. La integración tiene las siguientes limitaciones:

- no muestra la ubicación de los vehículos en tiempo real, retrasos ni incidencias: la API proporciona salidas programadas, actualizadas una vez al día;
- solo ofrece horarios para el día de servicio actual: la API pública no proporciona otras fechas;
- no planifica rutas ni transbordos: para ello, utiliza [wtp.waw.pl](https://wtp.waw.pl).

---

## 🔧 Funciones

- ✅ Autobuses, tranvías, metro y trenes SKM, incluidas las líneas nocturnas, de acceso a cementerios, exprés y locales.
- ✅ Compatibilidad con varias líneas y paradas.
- ✅ La hora de la próxima salida como estado del sensor, disponible en paneles y automatizaciones. Las tres salidas siguientes se guardan en los atributos (`Next 1`–`Next 3`).
- ✅ El mensaje «No service» cuando ya no quedan salidas y el estado `unavailable` cuando no se puede obtener un horario válido (véase [Solución de problemas](#-solución-de-problemas)).
- ✅ Configuración en la interfaz de Home Assistant en ocho idiomas: inglés, polaco, ucraniano, ruso, alemán, español, francés e italiano. Las seis nuevas versiones se han traducido automáticamente; puedes proponer correcciones mediante pull requests.
- ✅ Atributos con el nombre y las coordenadas de la parada, el sentido de circulación, un enlace al horario y notas. Las coordenadas permiten mostrar la parada en un mapa.
- ✅ Cambio de clave API o token mediante **Configurar**, también al pasar a la nueva API de la ciudad.
- ✅ Una entidad de **calendario** independiente para cada sensor, desactivada por defecto. Al activarla en los ajustes de la entidad, cada salida del día de servicio aparece como un evento de un minuto. El disparador de calendario permite iniciar una automatización, por ejemplo ocho minutos antes de la salida, sin crear plantillas.

---

## 📸 Capturas de pantalla

### Configuración de la integración
*Formulario de configuración con las credenciales y los datos de la línea y la parada.*

<div align="center"><img width="478" alt="image" src="https://github.com/user-attachments/assets/9a77591e-5b1a-4fe5-a29d-637d3c9b566c" /></div>

### Aspecto de la entidad

<div align="center"><img width="555" alt="image" src="https://github.com/user-attachments/assets/ef709b81-1575-4718-9c39-f6c135cf3cca" /></div>

### Atributos
*Detalles del horario, incluidas las horas de salida y el sentido de circulación.*

<div align="center"><img width="530" alt="image" src="https://github.com/user-attachments/assets/95cde9db-1182-41ba-9ae6-3187bd6a527c" /></div>

---

## 📋 Requisitos

- Home Assistant 2026.1 o posterior
- Una clave API o un token de la ciudad de Varsovia (abajo)

---

## 🧭 Cómo conseguir una clave o un token

La integración admite las credenciales de ambas API de la ciudad de Varsovia:

- **Token para la nueva API (recomendado):** en [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api), introduce un seudónimo, acepta las condiciones y descarga tu token. Es una cadena larga de caracteres dividida en tres partes separadas por puntos.
- **Clave para la API antigua:** una clave de [api.um.warszawa.pl](https://api.um.warszawa.pl) tiene el formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. La API antigua sigue funcionando, pero la ciudad no ha anunciado cuándo dejará de estar disponible. Recomendamos cambiar a la nueva API.

La integración reconoce el tipo de credencial y la envía únicamente a la API correspondiente. Para sustituir una clave antigua por un token, selecciona **Configurar** en la línea y pega el token. Se conservarán los ajustes de la línea y de las paradas. No hace falta volver a añadir la integración: el asistente rechaza configuraciones duplicadas de la misma línea y punto de parada.

---

## 📦 Instalación

### Con HACS

1. En Home Assistant, ve a **HACS → Integraciones**.
2. Busca **Transporte público de Varsovia**.
3. Pulsa **Descargar** y confirma.
4. Reinicia Home Assistant.

### Manualmente

1. Descarga la última versión de [GitHub Releases](https://github.com/solarssk/ztm_warsaw/releases).
2. Copia la carpeta `ztm_warsaw` en `/config/custom_components/`.
3. Reinicia Home Assistant.

---

## 🔌 Configuración

1. Ve a **Configuración → Dispositivos y servicios**.
2. Pulsa **+ Añadir integración** y busca **Transporte público de Varsovia**.
3. Rellena:
   - **clave API o token** (véase arriba),
   - **ID de la parada** y **número del punto de parada** (por ejemplo 7009 y 01),
   - **número de línea** (por ejemplo 151).

El ID de la entidad incluye el número de línea, el ID de la parada y el número del punto de parada; por ejemplo, `sensor.line_151_from_7009_01`. Para cambiar la clave API o el token, abre **Configuración → Dispositivos y servicios → Transporte público de Varsovia** y selecciona **Configurar** en la línea. Se conservarán los ajustes de la línea y de las paradas. Si aún se utiliza una clave antigua, aparecerá un aviso en **Reparaciones** con instrucciones para cambiar a un token. Puedes ignorarlo.

El **ID de la parada** es común a todos los puntos de parada que pertenecen a la misma parada. El **número del punto de parada** identifica el lugar concreto donde se sube al vehículo, normalmente para un sentido de circulación. Suele tener dos dígitos, como 01 o 02, y figura en la señal de la parada. En polaco, este punto numerado se denomina *słupek*.

---

## 🩺 Solución de problemas

- **El sensor tiene el estado `unknown` y sus atributos muestran «No service».** La línea no circula hoy o ya han pasado todas las salidas. Es el comportamiento previsto. Consulta el horario en [wtp.waw.pl](https://wtp.waw.pl) o llama al 19115.
- **El sensor tiene el estado `unavailable` (no disponible).** La API no ha devuelto un horario válido. Puede deberse a una clave rechazada, datos incorrectos de la parada, del punto de parada o de la línea, o un formato de respuesta no compatible. Si la primera descarga falla por un motivo distinto del rechazo de la clave, Home Assistant reintenta la configuración automáticamente. Las claves rechazadas se gestionan como se explica a continuación. Encontrarás los detalles del error en el registro de Home Assistant; las claves y los tokens no se guardan en él. El sensor vuelve a estar disponible al recibir datos válidos. Si el problema continúa, revisa las credenciales y los datos de la parada y de la línea.
- **Home Assistant pide una nueva clave.** Esto ocurre cuando la API antigua rechaza la clave tres veces seguidas. También cuentan los reintentos durante la configuración; un error de red o del servidor interrumpe la secuencia. Introduce una nueva clave API o un token en el formulario. Se conservarán los ajustes y se aceptará una clave válida aunque la línea no circule ese día. El sensor seguirá sin estar disponible hasta que actualices las credenciales. La nueva API no permite distinguir un token rechazado de una interrupción del servicio. Si ya se ha descargado un horario, el sensor lo utiliza hasta que termina el día de servicio y después deja de estar disponible. No aparecerá automáticamente ningún formulario para cambiar las credenciales. Si has revocado el token, introduce uno nuevo mediante **Configurar** en la línea.
- **Informar de un problema.** Abre la configuración de la línea, selecciona *Descargar diagnósticos* y adjunta el archivo al informe de error. Contiene información sobre la configuración y el horario. La clave API o el token se sustituye por `**REDACTED**`.
- **Siguen apareciendo salidas durante una interrupción de la API.** Tras una descarga correcta, un tiempo de espera agotado, un error de red o un error del servidor (HTTP 5xx) no hace que el sensor deje de estar disponible de inmediato. La integración utiliza el horario guardado hasta el final del día de servicio y reintenta la descarga cada hora. Las salidas programadas no cambian a lo largo del día. El sensor de diagnóstico **Last update**, desactivado por defecto, muestra la última descarga correcta. Puedes activarlo en los ajustes de la entidad.
- **Durante la configuración no se encuentra la línea.** La API solo incluye las líneas que circulan ese día. Por ejemplo, no se puede añadir un domingo una línea que solo funciona en días laborables. Vuelve a intentarlo un día en el que tenga salidas programadas.
- **Una línea aparece en wtp.waw.pl, pero no en la integración.** El planificador de rutas utiliza más datos que la API pública. La integración solo puede mostrar los datos que proporciona la API.
- **Horarios de las líneas nocturnas** (`N01`, `N44`, etc.). El día de servicio puede continuar después de medianoche: `24:50` significa las 00:50 del día siguiente y `26:20`, las 02:20. La integración convierte estas horas correctamente. Una salida registrada como `26:15` corresponde a las 02:15 del día siguiente; a las 02:00 se mostrará como una salida dentro de 15 minutos.

---

## 📚 Documentación

El [manual de usuario de la wiki](https://github.com/solarssk/ztm_warsaw/wiki) explica la instalación, la configuración, los horarios, el día de servicio y la solución de problemas. Está disponible en inglés y sus archivos fuente se encuentran en [`docs/wiki/`](docs/wiki).

---

## 🧑‍💻 Colaboración y seguridad

Puedes proponer ideas, informar de errores o enviar pull requests. Encontrarás las pautas de colaboración en [CONTRIBUTING.md](CONTRIBUTING.md). Para comunicar vulnerabilidades, sigue las instrucciones de [SECURITY.md](SECURITY.md).

---

## 🙌 Datos y agradecimientos

Datos: la ciudad de Varsovia (**Miasto Stołeczne Warszawa**) y la Autoridad de Transporte Público de Varsovia (**Zarząd Transportu Miejskiego**, ZTM), a través del portal de datos abiertos de la ciudad ([dane.um.warszawa.pl](https://dane.um.warszawa.pl)), bajo la licencia [Creative Commons Attribution](https://creativecommons.org/licenses/by/4.0/deed.es).

He diseñado el concepto, las funciones, la estructura y la conexión con la API pública de la ciudad de Varsovia. No soy desarrollador profesional de Python, pero mis conocimientos básicos me han permitido planificar el funcionamiento del proyecto.

He utilizado ChatGPT como apoyo para la sintaxis, la depuración y los detalles de implementación. Las decisiones sobre el diseño y el funcionamiento del proyecto las he tomado yo.

Gracias a [@peetereczek](https://github.com/peetereczek/ztm), cuyo proyecto anterior me sirvió de inspiración. Esta integración se ha creado desde cero como un proyecto independiente.

Te invito a participar en el desarrollo del proyecto con ideas, informes de errores y propuestas de mejora.

---

## 📄 Licencia

Licencia MIT
