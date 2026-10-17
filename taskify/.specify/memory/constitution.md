<!--
### Sync Impact Report
* Version change: 1.0.0 -> 1.1.0 (MINOR - correcciones del corrector: reglas verificables, dominio transversal, errores y escalamiento)
* List of modified principles (1.1.0):
  - Principle I: umbrales numéricos (contraste WCAG 2.1 AA >= 4.5:1; objetivos táctiles >= 44x44 px).
* Added sections (1.1.0): Reglas de Dominio Transversales (normalización de emails, formatos estándar, errores RFC 7807); Convenciones de Especificación; Escalamiento ante Ambigüedad.
* Previous review (1.0.0) notes:
* List of modified principles:
  - Principle I (Enfoque en el Usuario y Accesibilidad): Replaced subjective wording with verifiable criteria (contrast, touch targets, readable hierarchy) and framed formal accessibility standards as design guidance.
  - Principle II (IA Asistiva con Supervisión Humana Obligatoria): Preserved human-in-the-loop requirement and provider decoupling.
  - Principle III (Privacidad y Protección de Datos Sensibles de Salud): Replaced presigned URLs with technology-neutral server-side authorization enforcement; added explicit immediate permission revocation upon relationship termination (US-35).
  - Principle IV (Trazabilidad e Inmutabilidad en Pagos Informales): Reaffirmed exclusion of payment gateways; added explicit cancellation-and-reissuance pattern referencing original record for error correction.
  - Principle V (Gestión Liviana de Medios Técnicos): Reaffirmed external links model (US-12, US-51) without binary video file uploads.
  - Principle VI (Calidad de Software y Verificación Continua): Replaced tight coupling to specific tool flags in core principles; distinguished CI test coverage enforcement from TDD methodology; noted TDD as pending team consensus.
* Added sections:
  - Decisiones de Implementación Pendientes de Ratificación (explicitly tracks technical decisions deferred to plan.md or team vote).
* Removed sections: None.
* Follow-up TODOs: Resolve pending implementation decisions during technical planning.
-->

# Set to Set Constitution

## Core Principles

### I. Enfoque en el Usuario y Accesibilidad Verificable
El producto atiende a perfiles diversos que van desde entrenadores independientes de alta rotación hasta alumnos de la tercera edad o en rehabilitación física (arquetipos Carmen, Roberto, Valeria del material de diseño). Toda interfaz DEBE cumplir con criterios objetivos de usabilidad:
- Diseño responsivo adaptado a dispositivos móviles y de escritorio.
- Contraste de texto sobre fondo conforme a WCAG 2.1 AA: relación mínima de 4.5 : 1 (3 : 1 para texto grande de 18 pt o 14 pt en negrita).
- Área mínima de pulsación de 44 × 44 px en todo elemento interactivo para prevenir toques accidentales durante el entrenamiento.
- Jerarquía visual clara y mensajes de error comprensibles para el usuario final, sin exponer trazas técnicas internas.
- Las pantallas de ejecución de entrenamiento y reporte post-sesión (RPE en US-60, mapa de molestias en US-61) DEBEN permitir registrar los datos con el mínimo de pasos posible.

### II. IA Asistiva con Supervisión Humana Obligatoria (Human-in-the-Loop)
La Inteligencia Artificial se concibe exclusivamente como una herramienta de apoyo para optimizar la planificación de rutinas y sugerir alternativas (US-13, US-14). El sistema NUNCA DEBE asignar, publicar o activar una rutina o progresión de ejercicios sin la revisión, ajuste y aprobación explícita y manual de un entrenador profesional. La plataforma NO es un sustituto de diagnóstico médico ni kinesiológico. El diseño DEBE desacoplar la integración del proveedor de IA mediante adaptadores o interfaces abstractas para permitir su reemplazo sin impactar las reglas del dominio.

### III. Privacidad y Protección de Datos Sensibles de Salud (Server-Side Enforcement)
Los cuestionarios médicos (US-41), antecedentes de lesiones (US-42), archivos de apto físico/médico (US-43) y reportes de dolor agudo o molestias (US-61, US-29) constituyen datos de salud protegidos:
- **Validación del lado del servidor**: La autorización DEBE validarse obligatoriamente en el backend en cada petición a la API; bajo ninguna circunstancia se confiará únicamente en restricciones del cliente o frontend.
- **Autorización por relación**: El acceso a los datos de salud está estrictamente restringido al propio alumno y al entrenador con quien mantenga una solicitud activa (US-06, US-07) o un vínculo de entrenamiento vigente.
- **Revocación inmediata**: La baja de un alumno o la finalización de la suscripción (US-35) conlleva la revocación inmediata del acceso del entrenador a los datos de salud y reportes futuros del alumno.
- **Almacenamiento protegido**: Los documentos adjuntos de apto físico DEBEN residir en almacenamiento protegido contra acceso público anónimo, requiriendo autenticación y autorización previa para su descarga o visualización. El mecanismo técnico específico se definirá en el plan técnico.

### IV. Trazabilidad e Inmutabilidad en la Gestión de Pagos Informales
El alcance del MVP excluye de manera terminante el procesamiento transaccional mediante pasarelas de pago automatizadas integradas (como Mercado Pago o Stripe). El módulo de pagos (US-34, US-71) gestiona exclusivamente el registro manual y el control de vencimientos de pagos realizados por fuera de la aplicación (efectivo, transferencia bancaria):
- **Inmutabilidad y prohibición de borrado**: Los registros de pago confirmados o registrados no pueden ser eliminados físicamente de la base de datos (`NO DELETE`).
- **Mecanismo de corrección por anulación y reemisión**: Ante un error de carga, el registro erróneo DEBE marcarse como anulado, dejando constancia obligatoria del motivo, fecha y usuario responsable. Para corregir los datos, se DEBE emitir un nuevo registro que referencie al identificador del registro original anulado, preservando el historial de auditoría completo para ambas partes.

### V. Gestión Liviana de Medios Técnicos (Enlaces Externos)
Para evitar costos de infraestructura y complejidad de almacenamiento y transcodificación en el MVP, la plataforma NO almacena archivos binarios de video en sus servidores:
- **Vinculación por URL**: La asociación de videos demostrativos de técnica (US-12) se realiza exclusivamente mediante enlaces a plataformas soportadas (YouTube, Vimeo, Google Drive).
- **Reproducción embebida**: El reproductor del cliente DEBE mostrar el video embebido dentro de la vista del ejercicio sin redirigir al alumno fuera de la aplicación (US-51). Si un ejercicio carece de video, el sistema mostrará las notas técnicas y claves de postura (US-52).

### VI. Calidad de Software y Verificación Continua en CI (NON-NEGOTIABLE)
La calidad del código es una condición de aceptación mandatoria y no negociable:
- **Automatización de pruebas**: Todo componente de backend DEBE contar con pruebas automatizadas (unitarias y de integración) que validen los requerimientos funcionales y casos de borde.
- **Barrera de calidad en CI**: Ningún cambio podrá integrarse a la rama principal (`main`) si rompe pruebas existentes, si introduce errores de análisis estático o si reduce el umbral de cobertura mínimo requerido por el pipeline.
- **Compilación limpia de frontend**: Todo cambio en el cliente debe superar la verificación de compilación del pipeline sin errores de construcción.

## Reglas de Dominio Transversales

Reglas no negociables que aplican a todas las funcionalidades y que las specs NO deben redefinir:

- **Normalización de identificadores**: los emails DEBEN normalizarse en el backend (eliminar espacios al inicio y al final y convertir a minúsculas) antes de cualquier chequeo de unicidad, registro, autenticación o recuperación de contraseña.
- **Formatos estándar**:
  - Teléfono/WhatsApp: solo dígitos con prefijo `+` opcional, entre 8 y 15 dígitos; se rechazan cadenas vacías o con otros caracteres.
  - Moneda por defecto: pesos argentinos (ARS) cuando no se indique otra.
  - Fechas y horas: persistidas en UTC con formato ISO 8601.
- **Errores HTTP unificados**: toda respuesta de error de la API DEBE seguir RFC 7807 (`application/problem+json`) con los campos `type`, `title`, `status`, `detail` e `instance`; los errores de validación por campo se informan en la extensión `errors[]` (campo y mensaje). Ningún módulo define un formato de error propio.

## Restricciones Arquitectónicas y Tecnológicas

- **Estructura del Repositorio**: Las especificaciones, artefactos de Spec Kit y memoria de gobernanza residen en `taskify/`. El código fuente de la aplicación residirá en la raíz del repositorio en las carpetas `backend/` y `frontend/`, en concordancia con el pipeline de Integración Continua.
- **Backend Confirmado**: Python 3.12. Estilo de código y análisis estático gestionado con Ruff. Pruebas automatizadas con Pytest exigiendo una cobertura mínima del 90% en el pipeline (`.github/workflows/ci.yml`).
- **Frontend Confirmado**: Node.js 20. Compilación y empaquetado verificados mediante `npm run build` en el pipeline de CI.
- **Principios de Diseño de Software**: Arquitectura modular con estricta separación de responsabilidades y desacople entre la lógica de negocio (dominio), los mecanismos de persistencia y las interfaces de comunicación (APIs). Los detalles específicos de capas y estructura de directorios se formalizarán en cada plan técnico.
- **Seguridad**: Autenticación con almacenamiento seguro de contraseñas (hash con salt), bloqueo temporal de cuentas por 15 minutos tras 5 intentos fallidos consecutivos (US-75), enlaces de recuperación de un solo uso con vigencia máxima de 1 hora (US-76) y respuestas agnósticas en flujos de acceso y recuperación para mitigar ataques de enumeración de usuarios.

## Metodología y Flujo de Desarrollo (Spec-Driven Development)

El equipo adopta Spec-Driven Development (SDD) como marco de trabajo para asegurar la trazabilidad entre requerimientos y código:
1. **Especificación (`/speckit-specify`)**: Cada funcionalidad del backlog (`Backlog-US-MVP`) debe formalizarse en una especificación antes de implementar la solución técnica.
2. **Clarificación (`/speckit-clarify`)**: Detección y resolución temprana de ambigüedades o vacíos de alcance.
3. **Planificación (`/speckit-plan`)**: Diseño técnico, definición de contratos, modelos de datos y validación de conformidad contra esta Constitución.
4. **Descomposición en Tareas (`/speckit-tasks`)**: Desglose del plan en tareas atómicas, secuenciadas por dependencia y verificables.
5. **Implementación Incremental (`/speckit-implement`)**: Desarrollo en ramas dedicadas (`feature/*`), pruebas automatizadas y Pull Requests obligatorios hacia `main`.

### Convenciones de Especificación
- Los criterios de aceptación DEBEN escribirse con la estructura **Dado que [contexto] / Cuando [acción] / Entonces [resultado observable en interfaz o persistencia]**; no se aceptan escenarios narrativos.
- Los mensajes de error y estados se describen como comportamiento observable del sistema, sin lenguaje coloquial.
- Las specs siguen el principio de caja negra: describen reglas de negocio y no mencionan tipos de datos de base de datos (`String(36)`, `UUID`, etc.); esos detalles pertenecen exclusivamente a `data-model.md`.

### Escalamiento ante Ambigüedad
Ante cualquier ambigüedad, vacío o contradicción en una spec, el equipo y los agentes automatizados NO DEBEN asumir libremente una interpretación. DEBEN detener el trabajo y resolverla mediante `/speckit-clarify` o `/grill-me`, y registrar la decisión en la spec antes de continuar con el plan o la implementación.

## Decisiones de Implementación Pendientes de Ratificación

Las siguientes definiciones técnicas y metodológicas quedan expresamente delegadas a la etapa de planificación técnica o a consenso del equipo, sin constituir aún mandatos constitucionales:
1. **Disciplina TDD estricta (Red-Green-Refactor)**: Si bien la cobertura $\ge 90\%$ y las pruebas automatizadas en CI son obligatorias, la imposición formal del ciclo TDD estricto como proceso de autoría queda pendiente de acuerdo explícito del equipo.
2. **Base de Datos y ORM definitivos**: PostgreSQL y SQLAlchemy son la opción inicial de referencia, sujeta a ratificación en el primer plan técnico.
3. **Mecanismo de almacenamiento privado para aptos médicos**: La elección entre almacenamiento en servidor local con endpoint autenticado o almacenamiento en objetos con URLs temporales firmadas se definirá en el plan técnico de la US-43.
4. **Proveedor de Inteligencia Artificial**: La elección de la API o modelo para la US-13 (OpenAI, Gemini u otro) se seleccionará durante la planificación técnica de dicha funcionalidad.
5. **Verificación de tipos estática independiente en Frontend**: La incorporación de un paso específico de type-check (ej. `tsc --noEmit`) en CI queda como propuesta de mejora para el equipo.

## Governance

- Esta Constitución representa el acuerdo fundacional y la máxima autoridad técnica del proyecto Set to Set, superando cualquier decisión verbal o no documentada.
- Todos los integrantes del equipo y los agentes automatizados DEBEN verificar el cumplimiento irrestricto de estos principios en cada revisión de Pull Request y generación de especificaciones.
- **Procedimiento de Enmienda**: Cualquier cambio a esta Constitución requiere:
  - Registro de issue/propuesta justificando la necesidad técnica o de negocio.
  - Consenso y aprobación de los integrantes del equipo.
  - Actualización formal del archivo de constitución con incremento de versión según SemVer (MAJOR para modificaciones o eliminación de principios no negociables; MINOR para adición o expansión de secciones; PATCH para aclaraciones y correcciones no semánticas).
  - Actualización del correspondiente reporte de impacto (*Sync Impact Report*).

**Version**: 1.1.0 | **Ratified**: 2026-10-15 | **Last Amended**: 2026-10-17
