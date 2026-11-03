# Arquitectura de Adaptadores de Rutinas Asistidas por Inteligencia Artificial

## Proyecto: Set to Set — Sprint 3

---

## 1. Arquitectura del Módulo de IA

El módulo de generación de rutinas asistidas por IA de **Set to Set** implementa el patrón de diseño **Adapter / Strategy** combinado con una **Factory**. Este diseño desacopla completamente el dominio de entrenamiento del proveedor de IA subyacente, garantizando extensibilidad, alta resiliencia y capacidad de prueba determinista.

```
                         +-----------------------------+
                         | POST /routines/generate-ai  |
                         +--------------+--------------+
                                        |
                         +--------------v--------------+
                         |    AIRoutineAdapterFactory  |
                         +--------------+--------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
+----------------v-----------------+         +-----------------v------------------+
|      GeminiAIRoutineAdapter      |         |     HeuristicAIRoutineAdapter      |
|  (LLM Generativo - Gemini 2.5)   |         | (Motor de Reglas Biomecánicas)     |
+----------------+-----------------+         +-----------------+------------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                         +--------------v--------------+
                         |    AssignedRoutine (Draft)  |
                         |   Status: PENDING_REVIEW    |
                         +-----------------------------+
```

### 1.1. Clases Principales

1. **`AIRoutineAdapter` (Interfaz Abstracta / Protocolo)**  
   Define el contrato común que todo adaptador debe implementar:
   ```python
   class AIRoutineAdapter(ABC):
       @abstractmethod
       def generate_adapted_routine(
           self,
           context: AIRoutineContext,
       ) -> AIRoutineProposal:
           pass
   ```
   Recibe un contexto inmutable estructurado (`AIRoutineContext`) que incluye:
   - Datos de la rutina plantilla base (`RoutineTemplate`).
   - Perfil del alumno (`StudentProfile`, cuestionario de salud PAR-Q, zonas anatómicas a proteger declaradas, objetivos de acondicionamiento físico).
   - Catálogo de ejercicios disponibles en la biblioteca del entrenador.

2. **`GeminiAIRoutineAdapter`**  
   Implementa la integración con el modelo generativo de Google (`gemini-2.5-flash`).
   - Envía un *prompt* enriquecido con el perfil fisiológico del alumno, el cuestionario PAR-Q, las restricciones de zonas a proteger y el catálogo disponible en formato JSON.
   - Configura `temperature=0.0` para maximizar la consistencia y minimizar la entropía o alucinación en prescripciones de salud.
   - Aplica un esquema estructurado de salida (`response_schema`) para obtener respuestas JSON tipadas.
   - Valida estrictamente la propuesta generada: formato de repeticiones (ej. `"8-12"`, `"30s"`), ausencia de ejercicios con identificadores inexistentes, no sustitución de un ejercicio por sí mismo y rechazo tajante de cualquier ejercicio con contraindicaciones para las zonas a proteger del alumno. Si Gemini incumple alguna regla de seguridad biomecánica, la respuesta es rechazada (HTTP 502) para evitar riesgos físicos.

3. **`HeuristicAIRoutineAdapter`**  
   Motor de inferencia y reglas biomecánicas puro en Python, libre de dependencias de red o modelos externos.
   - Analiza determinísticamente las contraindicaciones del alumno.
   - Aplica reemplazos seguros mediante un algoritmo de proximidad taxonómica y biomecánica (`find_safe_substitute`).
   - Calibra series, repeticiones, descansos e intensidad según los objetivos declarados y las respuestas del cuestionario PAR-Q.
   - Genera un resumen explicativo detallado (`adaptation_summary`) que transparenta las decisiones tomadas.

4. **`AIRoutineAdapterFactory`**  
   Responsable de instanciar el adaptador correspondiente según:
   - La variable de entorno global `AI_ROUTINE_PROVIDER` (`gemini` o `heuristic`).
   - La presencia de `GEMINI_API_KEY`.
   - La solicitud explícita del cliente vía payload HTTP (`provider: "heuristic" | "gemini"`).

### 1.2. Flujo de Datos y Persistencia

1. **Recepción del Request**: El endpoint `POST /api/v1/routines/generate-ai` recibe `student_id`, `template_id` y opcionalmente `provider`.
2. **Control de Frecuencia (Rate Limiting)**: Se evalúa `ai_generate_limiter.check(user.id)`. Máximo 10 solicitudes por minuto por entrenador para proteger recursos y costos.
3. **Validación de Relación y Dominio**:
   - Se valida que el usuario sea un entrenador autenticado con perfil activo.
   - Se valida que el alumno tenga un vínculo activo (`ActiveTrainerStudent`) con el entrenador solicitante.
   - Se carga la plantilla de rutina base del entrenador y las zonas a proteger del alumno.
4. **Construcción del Contexto**: Se recopilan los datos del cuestionario PAR-Q, zonas protegidas, objetivos y ejercicios del entrenador.
5. **Generación de la Propuesta**: El adaptador seleccionado produce un `AIRoutineProposal`.
6. **Persistencia Inicial**: Se persiste la rutina en la tabla `assigned_routines` con estado inicial **`PENDING_REVIEW`**.  
   *Principio de supervisión humana (Human-in-the-Loop)*: La propuesta de la IA nunca se asigna directamente al alumno sin la aprobación explícita del entrenador.

### 1.3. Rol del Adaptador Heurístico: Resiliencia y Fallback

El adaptador heurístico desempeña un triple rol crítico en la arquitectura de Set to Set:
1. **Mecanismo de Resiliencia Operativa**: Permite que el sistema continúe funcionando normalmente si la API de Google Gemini sufre cortes, latencias excesivas (timeout HTTP 504), agotamiento de cuota (HTTP 429) o fallas de red.
2. **Fallback Manual en UI**: Cuando una llamada a Gemini falla, la interfaz de usuario ofrece un botón claro: *"Usar adaptador heurístico explícitamente"*, evitando que el entrenador quede bloqueado.
3. **Independencia en Desarrollo y Testing**: Facilita la ejecución de pruebas automatizadas masivas de integración y CI/CD sin consumir cuotas de API de terceros ni requerir secretos en entornos de prueba.

---

## 2. Algoritmo del Adaptador Heurístico

El motor del `HeuristicAIRoutineAdapter` ejecuta un algoritmo determinista estructurado en 7 fases:

### Paso 1: Análisis de la Rutina Base
Se inspeccionan los días, bloques y ejercicios de la plantilla seleccionada (`RoutineTemplate`), preservando intacta su jerarquía y el orden (`order_index`) de cada elemento.

### Paso 2: Análisis del Perfil del Alumno
Se examina la información médica y deportiva del alumno:
- Cuestionario de salud PAR-Q (respuestas afirmativas a factores de riesgo cardiovascular o articular).
- Zonas anatómicas a proteger registradas en el perfil (ej. rodilla, hombro, zona lumbar).
- Objetivos de entrenamiento declarados (ej. fuerza, hipertrofia, resistencia, salud general).

### Paso 3: Identificación de Contraindicaciones
Se cruzan las zonas a proteger del alumno con las contraindicaciones catalogadas de cada ejercicio (`contraindicated_zones`). Si un ejercicio de la rutina base impacta negativamente una zona protegida, se marca inmediatamente para sustitución obligatoria.

### Paso 4: Ajuste de Intensidad
Si el alumno presenta respuestas afirmativas en el cuestionario PAR-Q o múltiples zonas a proteger y la rutina base está configurada en intensidad `ALTA`, el adaptador reduce la intensidad recomendada a `MEDIA` o `BAJA`, documentando el motivo en el resumen de adaptación.

### Paso 5: Sustitución Segura de Ejercicios (`find_safe_substitute`)
Cuando un ejercicio `E` resulta contraindicado, el motor invoca la función determinista `find_safe_substitute(orig, protected_zones, catalog, exclude_ids)`:
1. **Candidatos de Nivel 1**: Ejercicios de la biblioteca que comparten el **mismo grupo muscular principal** y la **misma categoría biomecánica**, y que **NO** presentan ninguna contraindicación para las zonas protegidas del alumno.
2. **Candidatos de Nivel 2**: Ejercicios que comparten el **mismo grupo muscular**, sin contraindicaciones.
3. **Candidatos de Nivel 3**: Ejercicios que comparten la **misma categoría**, sin contraindicaciones.
4. **Candidatos de Nivel 4**: Cualquier ejercicio del catálogo libre de contraindicaciones.

**Reglas Críticas de Seguridad**:
- Un ejercicio **nunca** se sustituye por sí mismo ni por una variante que comparta su mismo nombre normalizado.
- Un ejercicio sustituto **nunca** puede contener contraindicaciones activas para el alumno.
- Si no existe ningún ejercicio seguro en el catálogo del entrenador, el ejercicio contraindicado se omite de forma controlada y se deja una advertencia explícita en el resumen, impidiendo que el alumno realice un movimiento lesivo.
- En las notas de adaptación (`adaptation_notes`) del ejercicio se registra explícitamente:
  `"Sustituto seguro para proteger: [Zonas]. Reemplaza a [Ejercicio Original]."`

### Paso 6: Calibración de Series, Repeticiones y Descansos
Según el objetivo principal del alumno, el adaptador adapta los parámetros de carga:
- **Fuerza**: 3-4 series, 4-6 repeticiones, descansos de 120-180 segundos.
- **Hipertrofia**: 3-4 series, 8-12 repeticiones, descansos de 60-90 segundos.
- **Resistencia**: 2-3 series, 15-20 repeticiones o tiempos isométricos (ej. `"30s"`, `"45s"`), descansos cortos de 30-45 segundos.
- **Salud General / Reacondicionamiento**: 3 series, 10-12 repeticiones controladas, descansos de 60 segundos.

### Paso 7: Construcción del Resumen Explicativo (`adaptation_summary`)
El adaptador compila una justificación técnica en lenguaje claro para el entrenador, detallando:
- Las adaptaciones biomecánicas realizadas.
- Cada ejercicio sustituido y las zonas protegidas que motivaron el reemplazo.
- El perfil de series y repeticiones aplicado en función de los objetivos del alumno.
- Recordatorio de que la rutina permanece en revisión preliminar hasta la aprobación del profesional.

---

## 3. Análisis de Determinismo

El adaptador heurístico ofrece **determinismo matemático estricto**:

$$\forall (A, T, C), \quad \text{Adapter}(A, T, C) \equiv \text{Adapter}(A, T, C)$$

Donde $A$ es el perfil del alumno, $T$ es la plantilla de rutina y $C$ es el catálogo de ejercicios.

### 3.1. Propiedades Clave de la Implementación
1. **Ausencia de Aleatoriedad**: No se utiliza el módulo `random` ni funciones pseudoaleatorias.
2. **Ordenamiento Estable**: La selección de candidatos en `find_safe_substitute` evalúa el catálogo en orden determinista por identificador (`id`), garantizando que la elección del sustituto sea siempre idéntica.
3. **Preservación Estricta de Secuencia**: El orden de los días (`order_index`), bloques y ejercicios se conserva de manera exacta.
4. **Valor Técnico y Médico**:
   - **Auditoría médica**: Ante una prescripción de ejercicio, es posible reconstruir exactamente por qué se sugirió cada movimiento.
   - **Pruebas Automatizadas**: Permite tests de regresión con aserciones exactas de entrada y salida, asegurando que futuras modificaciones al código no alteren prescripciones aprobadas.
   - **Predictibilidad**: El entrenador sabe con certeza qué comportamiento esperar ante perfiles y patologías conocidas.

---

## 4. Calidad de las Propuestas y Limitaciones Conocidas

### 4.1. Calidad Biomecánica
En casos de entrenamiento estándar y patologías articulares frecuentes (como lumbalgia, condromalacia rotuliana o pinzamiento subacromial con zonas protegidas bien catalogadas), el adaptador heurístico produce rutinas con un estándar de seguridad equiparable o superior al de un modelo de lenguaje, debido a que su cumplimiento de restricciones es axiomático y no probabilístico.

### 4.2. Limitaciones del Adaptador Heurístico
1. **Comprensión Semántica Limitada**: No procesa texto libre desestructurado (por ejemplo, comentarios anecdóticos del alumno no reflejados en campos estándar).
2. **Variabilidad Estilística Baja**: El texto de las justificaciones sigue plantillas estructuradas predefinidas.
3. **Taxonomía Discreta**: Las decisiones se basan en metadatos discretos (`target_muscle_group`, `category`, `contraindicated_zones`). Si un ejercicio no tiene sus metadatos correctamente cargados por el entrenador, el motor heurístico no puede inferir su cinemática.

### 4.3. Mitigación por Diseño: *Human-in-the-Loop*
Set to Set resuelve estas limitaciones mediante el principio de diseño **Human-in-the-Loop (HITL)**:
- La IA nunca asigna la rutina de forma automática.
- El entrenador visualiza la propuesta en estado `PENDING_REVIEW`.
- Dispone de herramientas completas de **edición manual** (modificar pesos, series, repeticiones como `"8-12"` o `"30s"`, intercambiar ejercicios o añadir notas personales) sin costo computacional ni llamadas a la IA.
- Solo tras la confirmación explícita del entrenador la rutina adquiere vigencia y pasa a estado `APPROVED`.

---

## 5. Comparación Detallada: Gemini vs. Adaptador Heurístico

| Dimensión | Google Gemini (`GeminiAIRoutineAdapter`) | Adaptador Heurístico (`HeuristicAIRoutineAdapter`) |
| :--- | :--- | :--- |
| **Consistencia y Reproducibilidad** | Alta con `temperature=0.0`, pero sujeta a cambios menores en versiones del modelo o alineación. | Absoluta. Dos ejecuciones con los mismos datos producen exactamente el mismo resultado. |
| **Determinismo** | Estocástico / probabilístico controlado por Greedy Decoding. | 100% determinista y formalmente verificable. |
| **Adaptación a Casos Complejos** | Muy alta. Puede correlacionar múltiples variables heterogéneas simultáneamente. | Moderada. Depende de las reglas de inferencia codificadas en el algoritmo. |
| **Interpretación de Texto Libre** | Excelente. Comprende notas médicas, preferencias y observaciones subjetivas. | Nula. Opera exclusivamente sobre campos y taxonomías tabuladas. |
| **Seguridad Biomecánica** | Dependiente del prompt y validación posterior en backend. | Axiomática. Rechazo y filtro garantizado por código determinista. |
| **Velocidad de Respuesta** | 1.5 a 4.0 segundos (depende de latencia de red y carga de Google Cloud). | Menor a 20 milisegundos (procesamiento local en memoria). |
| **Dependencias Externas** | Requiere conexión a Internet, cuenta en Google AI Studio y API Key válida. | Ninguna. Funciona en entornos offline, aislados o locales. |
| **Costos Operativos** | Variable según volumen de tokens (sujeto a límites de cuota gratuita o facturación). | Costo marginal cero ($0.00). |
| **Manejo de Alucinaciones** | Requiere sanitización y validación estricta de IDs y parámetros en backend. | No alucina. Solo selecciona ejercicios existentes en el catálogo. |
| **Disponibilidad** | Sujeta al uptime de Google Cloud Platform y cuotas de servicio (HTTP 429). | 100% disponible siempre que el servicio backend esté activo. |

---

## 6. Conclusión de Arquitectura

La coexistencia de ambos adaptadores bajo una interfaz unificada proporciona el equilibrio óptimo para una plataforma de salud y entrenamiento: la **flexibilidad y sofisticación analítica de Google Gemini** cuando los servicios externos están disponibles, respaldada por la **velocidad, seguridad y robustez infalible del Adaptador Heurístico** como motor de resiliencia ininterrumpida.
