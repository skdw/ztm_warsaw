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

Muestra **cuándo sale el próximo autobús, tranvía o tren de tu parada**: un sensor para una línea en un punto de parada, para tu panel y para automatizaciones como «avísame cuándo salir». Usa los datos abiertos de la ciudad de Varsovia y no necesita hardware adicional.

Muestra salidas **programadas**: sin retrasos ni avisos de incidencias, solo el día de servicio actual y sin planificación de viajes (para eso está [wtp.waw.pl](https://wtp.waw.pl)). El vehículo de la próxima salida puede mostrarse en el mapa (opcional, requiere un token).

---

## 🔧 Funciones

- ✅ Autobuses, tranvías, metro y cercanías (SKM), incluidas las líneas nocturnas, exprés y locales.
- ✅ La próxima salida es el estado del sensor; las tres siguientes, y la primera y la última salida del día, son atributos.
- ✅ Un sensor de *Estado* explica con palabras sencillas qué ocurre («Ya salió la última salida del día»).
- ✅ Configuración buscando el nombre de la parada y eligiendo después el punto de parada y la línea: sin buscar números.
- ✅ Varias líneas y paradas, un tiempo de paseo opcional, un calendario opcional y una marca opcional del vehículo en el mapa.
- ✅ Ocho idiomas: inglés, polaco, ucraniano, ruso, alemán, español, francés e italiano. Los seis más recientes están traducidos automáticamente; las correcciones son bienvenidas como pull request.

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

Consigue un token gratuito en [dane.um.warszawa.pl/pl/key-api](https://dane.um.warszawa.pl/pl/key-api): escribe un apodo, acepta las condiciones y descárgalo. Es un texto largo en tres partes separadas por puntos.

Una clave antigua de la API (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, de [api.um.warszawa.pl](https://api.um.warszawa.pl)) sigue funcionando, pero ese servidor deja de responder a ratos, la ciudad no ha dado fecha de cierre y el vehículo en el mapa necesita un token. Para cambiar, abre el aviso en **Reparaciones** o elige **Configurar** en la línea y pega el token. Tus ajustes se conservan.

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
3. Pega tu token y escribe parte del nombre de la parada (por ejemplo, `Marcelin`) o su ID.
4. Elige el punto de parada (su número está en el cartel de la parada, uno por sentido) y la línea. Solo aparecen las líneas que paran allí hoy.

El sensor se llama algo como `sensor.line_151_from_7009_01`. Otra parada de la línea se añade con **Añadir parada**. Si ya conoces los números, marca **Conozco los números** en la primera pantalla. El tiempo de paseo, el calendario, la marca del vehículo y cómo quitar una línea están en la [wiki](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration).

---

## 🩺 Solución de problemas

- **El sensor está en `unknown` y muestra «No service».** La línea no circula hoy o ya salió su última salida. Es lo esperado. Qué caso es lo dice el sensor de *Estado*; el horario está en [wtp.waw.pl](https://wtp.waw.pl), o llama al 19115.
- **El sensor está en `unavailable`.** La ciudad no devolvió un horario válido: un token rechazado, o una parada, un punto de parada o una línea que no conoce. El motivo está en el registro de Home Assistant (las claves y los tokens nunca se registran).
- **Errores de red, y usas una clave antigua.** El servidor antiguo de la ciudad deja de responder a ratos. Los sensores conservan el horario que tienen y vuelven a preguntar más tarde; pasar a un token lo soluciona.
- **Home Assistant pide una clave nueva.** La ciudad rechazó la clave tres veces seguidas. Introduce una clave o un token nuevo en el formulario; tus ajustes se conservan.
- **Informar de un problema.** Elige *Descargar diagnósticos* en la entrada y adjunta el archivo a tu issue. La clave o el token aparece como `**REDACTED**`.

Hay más respuestas en la [wiki](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting).

---

## 📚 Documentación

La [wiki](https://github.com/solarssk/ztm_warsaw/wiki) es el manual de usuario: [Configuración](https://github.com/solarssk/ztm_warsaw/wiki/1.-Configuration) (tiempo de paseo, quitar una línea), [Conceptos](https://github.com/solarssk/ztm_warsaw/wiki/2.-Concepts) (el día de servicio, qué muestra cada entidad), [Ejemplos](https://github.com/solarssk/ztm_warsaw/wiki/3.-Examples) (tarjetas y automatizaciones para copiar) y [Solución de problemas](https://github.com/solarssk/ztm_warsaw/wiki/4.-Troubleshooting). Está en inglés; el código fuente está en [`docs/wiki/`](docs/wiki).

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
