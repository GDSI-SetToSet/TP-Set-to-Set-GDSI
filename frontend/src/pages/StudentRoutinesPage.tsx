import { isAxiosError } from 'axios';
import { ArrowLeft, Dumbbell, History, Home, PlusCircle, Video, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SafeVariantNotice } from '../components/SafeVariantNotice';
import { ExerciseAlternativesPanel } from '../components/ExerciseAlternativesPanel';
import type { ExerciseAlternative } from '../types/exerciseAlternative';
import { ROUTES } from '../constants/routes';
import {
  createAssignedRoutineWorkoutLog,
  getAssignedRoutineWorkoutLogs,
  getAssignedStudentRoutine,
  updateAssignedRoutineModality,
} from '../services/routineTemplateService';
import type {
  RoutineExercise,
  RoutineModality,
  RoutineTemplate,
  WorkoutSetLog,
} from '../types/routineTemplate';
import { ROUTINE_MODALITIES } from '../types/routineTemplate';
import '../styles/student-daily-routine-layout.css';

interface SetLogDraft {
  setNumber: string;
  repsCompleted: string;
  weightKg: string;
}

interface ProblemDetailPayload {
  detail?: string;
  errors?: Array<{ field?: string; message?: string }>;
}

export function StudentRoutinesPage() {
  const [routine, setRoutine] = useState<RoutineTemplate | null>(null);
  const [selectedDayId, setSelectedDayId] = useState('');
  const [openVideoExerciseId, setOpenVideoExerciseId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [skipped, setSkipped] = useState<string[]>([]);
  // US-54: reemplazos de la sesión en curso (id del ítem → alternativa); no modifican la rutina
  const [replacements, setReplacements] = useState<Record<string, ExerciseAlternative>>({});
  const [blockedExerciseIds, setBlockedExerciseIds] = useState<string[]>([]);

  const [switchingModality, setSwitchingModality] = useState(false);
  const [modalityError, setModalityError] = useState('');
  const [modalityBlockingReasons, setModalityBlockingReasons] = useState<string[]>([]);

  const [workoutLogs, setWorkoutLogs] = useState<WorkoutSetLog[]>([]);
  const [logDrafts, setLogDrafts] = useState<Record<string, SetLogDraft>>({});
  const [savingExerciseId, setSavingExerciseId] = useState<string | null>(null);
  const [logError, setLogError] = useState('');

  useEffect(() => {
    Promise.all([getAssignedStudentRoutine(), getAssignedRoutineWorkoutLogs().catch(() => [])])
      .then(([assigned, logs]) => {
        setRoutine(assigned);
        setSelectedDayId(assigned?.days[0]?.id ?? '');
        setWorkoutLogs(logs);
      })
      .catch(() => setError('No pudimos cargar tu rutina. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando tu rutina…</main>;

  const activeModality: RoutineModality = routine?.modality ?? 'GYM';
  const isHomeModality = activeModality === 'HOME';
  const selectedDay = routine?.days.find((day) => day.id === selectedDayId) ?? routine?.days[0];
  const totalDuration = selectedDay?.blocks.reduce((total, block) => total + (block.estimated_duration_minutes ?? 0), 0) ?? 0;

  const getDraftForItem = (item: RoutineExercise): SetLogDraft => {
    const existing = logDrafts[item.id];
    if (existing) return existing;
    const exerciseLogsCount = workoutLogs.filter(
      (log) => log.exercise_id === item.exercise.id && log.day_name === (selectedDay?.name ?? ''),
    ).length;
    const nextSet = Math.min(item.sets, exerciseLogsCount + 1);
    const defaultWeight = isHomeModality ? '0' : item.target_weight_kg !== null ? String(item.target_weight_kg) : '';
    return {
      setNumber: String(nextSet),
      repsCompleted: item.reps,
      weightKg: defaultWeight,
    };
  };

  const updateDraftField = (item: RoutineExercise, field: keyof SetLogDraft, value: string) => {
    const base = getDraftForItem(item);
    setLogDrafts((prev) => ({
      ...prev,
      [item.id]: {
        ...base,
        [field]: value,
      },
    }));
  };

  const handleSelectModality = async (targetModality: RoutineModality) => {
    if (!routine || switchingModality) return;
    setModalityError('');
    setModalityBlockingReasons([]);

    if (targetModality === activeModality) return;

    setSwitchingModality(true);
    try {
      const updated = await updateAssignedRoutineModality(targetModality);
      setRoutine(updated);
      setLogDrafts({});
    } catch (err) {
      if (isAxiosError<ProblemDetailPayload>(err) && err.response?.data) {
        const data = err.response.data;
        setModalityError(
          data.detail ?? 'No fue posible cambiar a la modalidad Casa/Viaje.',
        );
        const reasons = (data.errors ?? [])
          .map((item) => item.message)
          .filter((msg): msg is string => Boolean(msg));
        setModalityBlockingReasons(reasons);
      } else {
        setModalityError('No pudimos cambiar la modalidad en este momento. Intentá nuevamente.');
      }
    } finally {
      setSwitchingModality(false);
    }
  };

  const handleRecordSet = async (item: RoutineExercise) => {
    if (!routine || !selectedDay || savingExerciseId) return;
    setLogError('');
    const draft = getDraftForItem(item);
    const parsedSet = Number.parseInt(draft.setNumber, 10);
    const parsedWeight = draft.weightKg.trim() === '' ? null : Number.parseFloat(draft.weightKg);

    if (Number.isNaN(parsedSet) || parsedSet < 1 || parsedSet > 20) {
      setLogError('El número de serie debe estar entre 1 y 20.');
      return;
    }
    if (!draft.repsCompleted.trim()) {
      setLogError('Indicá las repeticiones o tiempo completado.');
      return;
    }
    if (parsedWeight !== null && (Number.isNaN(parsedWeight) || parsedWeight < 0)) {
      setLogError('La carga registrada debe ser un valor mayor o igual a 0 kg.');
      return;
    }

    setSavingExerciseId(item.id);
    try {
      const created = await createAssignedRoutineWorkoutLog({
        exercise_id: replacements[item.id]?.exercise_id ?? item.exercise.id,
        day_name: selectedDay.name,
        set_number: parsedSet,
        reps_completed: draft.repsCompleted.trim(),
        weight_kg: parsedWeight,
        modality: activeModality,
      });
      setWorkoutLogs((prev) => [created, ...prev]);
      const nextSet = Math.min(20, parsedSet + 1);
      setLogDrafts((prev) => ({
        ...prev,
        [item.id]: {
          ...draft,
          setNumber: String(nextSet),
        },
      }));
    } catch (caught) {
      const detail = isAxiosError(caught) ? caught.response?.data?.detail : undefined;
      setLogError(typeof detail === 'string' ? detail : 'No pudimos guardar el registro de la serie. Intentá nuevamente.');
    } finally {
      setSavingExerciseId(null);
    }
  };

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card student-daily-routine">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Rutina del día</h1>
          <p>Consultá los ejercicios y tiempos de la rutina que te asignó tu entrenador.</p>
        </div>

        {error ? (
          <p className="form-alert" role="alert">{error}</p>
        ) : !routine ? (
          <div className="student-daily-routine__empty" role="status">
            <h2>No tenés una rutina asignada</h2>
            <p>Cuando tu entrenador te asigne una rutina, vas a poder consultarla acá.</p>
          </div>
        ) : (
          <>
            <div className="student-daily-routine__summary">
              <div>
                <span>Rutina asignada</span>
                <h2>{routine.name}</h2>
              </div>
              <label htmlFor="routine-day">Día de la rutina
                <select
                  id="routine-day"
                  className="exercise-select"
                  value={selectedDay?.id ?? ''}
                  onChange={(event) => {
                    setSelectedDayId(event.target.value);
                    setOpenVideoExerciseId(null);
                  }}
                >
                  {routine.days.map((day) => <option key={day.id} value={day.id}>{day.name}</option>)}
                </select>
              </label>
              <strong>Duración estimada: {selectedDay?.blocks.some((block) => block.estimated_duration_minutes === null) ? 'Parcial' : `${totalDuration} min`}</strong>
            </div>

            <div className="student-routine-modality" aria-label="Selector rápido de modalidad de rutina">
              <div className="student-routine-modality__info">
                <span className="student-routine-modality__label">Modalidad de entrenamiento</span>
                <p className="student-routine-modality__hint">
                  {isHomeModality
                    ? 'Estás viendo la versión Casa/Viaje (Sin materiales). Tus registros se guardan en el mismo historial general.'
                    : 'Estás viendo la versión de Gimnasio con el equipamiento habitual prescripto.'}
                </p>
              </div>
              <div className="student-routine-modality__toggle" role="group" aria-label="Alternar entre Gimnasio y Casa/Viaje">
                <button
                  type="button"
                  className={`student-routine-modality__btn ${!isHomeModality ? 'student-routine-modality__btn--active' : ''}`}
                  aria-pressed={!isHomeModality}
                  disabled={switchingModality}
                  onClick={() => handleSelectModality('GYM')}
                >
                  <Dumbbell size={18} />
                  {ROUTINE_MODALITIES.GYM}
                </button>
                <button
                  type="button"
                  className={`student-routine-modality__btn ${isHomeModality ? 'student-routine-modality__btn--active' : ''}`}
                  aria-pressed={isHomeModality}
                  disabled={switchingModality}
                  onClick={() => handleSelectModality('HOME')}
                >
                  <Home size={18} />
                  {ROUTINE_MODALITIES.HOME}
                </button>
              </div>
            </div>

            {modalityError && (
              <div className="form-alert student-routine-modality__alert" role="alert">
                <strong>{modalityError}</strong>
                {modalityBlockingReasons.length > 0 && (
                  <ul className="student-routine-modality__blocking-list">
                    {modalityBlockingReasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {logError && (
              <p className="form-alert" role="alert">{logError}</p>
            )}

            {selectedDay?.blocks.map((block) => (
              <section key={block.id} className="student-daily-routine__block">
                <header>
                  <h3>{block.name}</h3>
                  <span>{block.estimated_duration_minutes === null ? 'Duración sin configurar' : `${block.estimated_duration_minutes} min estimados`}</span>
                </header>
                <ol>
                  {block.exercises.filter((item) => !skipped.includes(item.id)).map((item) => {
                    const draft = getDraftForItem(item);
                    return (
                      <li key={item.id}>
                        <div className="student-routine-exercise__summary">
                          <div className="student-routine-exercise__title-row">
                            <h4>{replacements[item.id]?.name ?? item.exercise.name}</h4>
                            <span
                              className={`student-routine-exercise__modality-badge ${
                                isHomeModality
                                  ? 'student-routine-exercise__modality-badge--home'
                                  : 'student-routine-exercise__modality-badge--gym'
                              }`}
                            >
                              {isHomeModality ? 'Versión Casa/Viaje · Sin materiales' : `Gimnasio · ${item.exercise.equipment_needed}`}
                            </span>
                          </div>
                          <p>{item.exercise.description}</p>
                          <span className="student-routine-exercise__muscle">
                            Músculo principal: {item.exercise.target_muscle_group}
                            {isHomeModality
                              ? ` · Ejecución sin materiales / peso corporal (reemplaza: ${item.exercise.equipment_needed})`
                              : ` · Equipamiento: ${item.exercise.equipment_needed}`}
                          </span>
                        </div>
                        <SafeVariantNotice
                          exerciseId={item.exercise.id}
                          onSkip={() => setSkipped((current) => [...current, item.id])}
                          onResolved={(status) => setBlockedExerciseIds((current) => {
                            const isBlocked = current.includes(item.exercise.id);
                            if (status === 'BLOCKED') return isBlocked ? current : [...current, item.exercise.id];
                            return isBlocked ? current.filter((id) => id !== item.exercise.id) : current;
                          })}
                        />
                        <ExerciseAlternativesPanel
                          exerciseId={item.exercise.id}
                          dayName={selectedDay?.name ?? ''}
                          chosen={replacements[item.id] ?? null}
                          onChosen={(alt) => setReplacements((current) => {
                            const { [item.id]: _removed, ...rest } = current;
                            return alt ? { ...rest, [item.id]: alt } : rest;
                          })}
                          onSkip={() => setSkipped((current) => [...current, item.id])}
                        />
                        <p>{item.sets} series · {item.reps} repeticiones</p>
                        <p>
                          {isHomeModality
                            ? `Peso corporal / Sin materiales${item.target_weight_kg !== null && item.target_weight_kg > 0 ? ` (ref. gimnasio: ${item.target_weight_kg} kg)` : ''}`
                            : item.target_weight_kg === null
                              ? 'Sin carga indicada'
                              : `${item.target_weight_kg} kg`}{' '}
                          · {item.rest_seconds} s de descanso
                        </p>
                        {(item.exercise.technical_cues || item.exercise.breathing_cues) && (
                          <dl className="student-routine-exercise__cues">
                            {item.exercise.technical_cues && (
                              <>
                                <dt>Notas técnicas y de postura</dt>
                                <dd>{item.exercise.technical_cues}</dd>
                              </>
                            )}
                            {item.exercise.breathing_cues && (
                              <>
                                <dt>Claves de respiración</dt>
                                <dd>{item.exercise.breathing_cues}</dd>
                              </>
                            )}
                          </dl>
                        )}
                        {item.exercise.video_url && (
                          <div className="student-routine-exercise__media">
                            <button
                              className="student-routine-exercise__video-toggle"
                              type="button"
                              aria-expanded={openVideoExerciseId === item.id}
                              aria-controls={`exercise-video-${item.id}`}
                              onClick={() => setOpenVideoExerciseId((current) => current === item.id ? null : item.id)}
                            >
                              {openVideoExerciseId === item.id ? <X size={18} /> : <Video size={18} />}
                              {openVideoExerciseId === item.id ? 'Ocultar video' : 'Ver video técnico'}
                            </button>
                            {openVideoExerciseId === item.id && (
                              <iframe
                                id={`exercise-video-${item.id}`}
                                className="exercise-video"
                                src={item.exercise.video_url}
                                title={`Video técnico de ${item.exercise.name}`}
                                loading="lazy"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                allowFullScreen
                                referrerPolicy="strict-origin-when-cross-origin"
                              />
                            )}
                          </div>
                        )}

                        {(replacements[item.id] || !blockedExerciseIds.includes(item.exercise.id)) && <div className="student-routine-exercise__logger">
                          <label>
                            Serie
                            <input
                              type="number"
                              min={1}
                              max={20}
                              value={draft.setNumber}
                              onChange={(event) => updateDraftField(item, 'setNumber', event.target.value)}
                            />
                          </label>
                          <label>
                            Repeticiones
                            <input
                              type="text"
                              value={draft.repsCompleted}
                              onChange={(event) => updateDraftField(item, 'repsCompleted', event.target.value)}
                            />
                          </label>
                          <label>
                            Carga (kg)
                            <input
                              type="number"
                              min={0}
                              step="0.5"
                              placeholder={isHomeModality ? '0 (Peso corporal)' : 'Kg'}
                              value={draft.weightKg}
                              onChange={(event) => updateDraftField(item, 'weightKg', event.target.value)}
                            />
                          </label>
                          <button
                            type="button"
                            className="student-routine-exercise__log-btn"
                            disabled={savingExerciseId === item.id}
                            onClick={() => handleRecordSet(item)}
                          >
                            <PlusCircle size={16} />
                            {savingExerciseId === item.id ? 'Guardando…' : 'Registrar serie'}
                          </button>
                        </div>}
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}

            <section className="student-routine-history" aria-labelledby="workout-history-heading">
              <header className="student-routine-history__header">
                <div className="student-routine-history__title">
                  <History size={20} />
                  <h3 id="workout-history-heading">Historial general consolidado</h3>
                </div>
                <span>
                  {workoutLogs.length === 0
                    ? 'Sin series registradas'
                    : `${workoutLogs.length} ${workoutLogs.length === 1 ? 'registro consolidado' : 'registros consolidados'}`}
                </span>
              </header>
              <p className="student-routine-history__subtitle">
                Tus series y cargas registradas en Gimnasio y en Casa/Viaje se unifican en este mismo historial sin fragmentarse ni perderse al alternar de modalidad.
              </p>

              {workoutLogs.length === 0 ? (
                <p className="student-routine-history__empty">
                  Todavía no registraste series. Usá el botón &ldquo;Registrar serie&rdquo; en cualquier ejercicio para guardar tu progreso.
                </p>
              ) : (
                <ul className="student-routine-history__list">
                  {workoutLogs.map((log) => (
                    <li key={log.id} className="student-routine-history__item">
                      <div className="student-routine-history__item-main">
                        <strong>{log.exercise_name}</strong>
                        <span className="student-routine-history__meta">
                          {log.day_name} · Serie {log.set_number} · {log.reps_completed} reps ·{' '}
                          {log.weight_kg === null || log.weight_kg === 0
                            ? 'Peso corporal (0 kg)'
                            : `${log.weight_kg} kg`}
                        </span>
                      </div>
                      <span
                        className={`student-routine-exercise__modality-badge ${
                          log.modality === 'HOME'
                            ? 'student-routine-exercise__modality-badge--home'
                            : 'student-routine-exercise__modality-badge--gym'
                        }`}
                      >
                        {ROUTINE_MODALITIES[log.modality] ?? log.modality}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </section>
    </main>
  );
}
