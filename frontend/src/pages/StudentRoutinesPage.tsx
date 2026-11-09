import { isAxiosError } from 'axios';
import { ArrowLeft, Dumbbell, History, Home, PlusCircle, Video, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { SafeVariantNotice } from '../components/SafeVariantNotice';
import { RestTimer } from '../components/RestTimer';
import { ROUTES } from '../constants/routes';
import {
  createAssignedRoutineWorkoutLog,
  getAssignedRoutineWorkoutLogs,
  getAssignedRoutineWorkoutSessions,
  getAssignedStudentRoutine,
  startAssignedWorkoutSession,
  finishAssignedWorkoutSession,
  updateAssignedRoutineModality,
} from '../services/routineTemplateService';
import type {
  RoutineExercise,
  RoutineModality,
  RoutineTemplate,
  WorkoutSetLog,
  WorkoutSession,
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

function formatWorkoutDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes} min ${seconds} s` : `${seconds} s`;
}

function parseSessionTimestamp(value: string | null): number | null {
  if (!value) return null;
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 0) return numeric;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function StudentRoutinesPage({ sessionMode = false }: { sessionMode?: boolean }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const requestedDayId = searchParams.get('day');
  const sessionId = searchParams.get('session');
  const sessionStartedAt = searchParams.get('startedAt');
  const [sessionStartedAtMs, setSessionStartedAtMs] = useState<number | null>(() => parseSessionTimestamp(sessionStartedAt));
  const [routine, setRoutine] = useState<RoutineTemplate | null>(null);
  const [selectedDayId, setSelectedDayId] = useState('');
  const [openVideoExerciseId, setOpenVideoExerciseId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [skipped, setSkipped] = useState<string[]>([]);
  const [blockedExerciseIds, setBlockedExerciseIds] = useState<string[]>([]);

  const [switchingModality, setSwitchingModality] = useState(false);
  const [modalityError, setModalityError] = useState('');
  const [modalityBlockingReasons, setModalityBlockingReasons] = useState<string[]>([]);

  const [workoutLogs, setWorkoutLogs] = useState<WorkoutSetLog[]>([]);
  const [workoutSessions, setWorkoutSessions] = useState<WorkoutSession[]>([]);
  const [logDrafts, setLogDrafts] = useState<Record<string, SetLogDraft>>({});
  const [savingExerciseId, setSavingExerciseId] = useState<string | null>(null);
  const [logError, setLogError] = useState('');
  const [startingWorkout, setStartingWorkout] = useState(false);
  const [finishingWorkout, setFinishingWorkout] = useState(false);
  const [activeSet, setActiveSet] = useState<{ exerciseId: string; startedAt: number } | null>(null);
  const [finishedSet, setFinishedSet] = useState<{ exerciseId: string; durationSeconds: number } | null>(null);
  const [activeRest, setActiveRest] = useState<{ exerciseName: string; durationSeconds: number; key: string } | null>(null);
  const [clockNow, setClockNow] = useState(Date.now());
  const [autoFinishPending, setAutoFinishPending] = useState(false);

  useEffect(() => {
    Promise.all([getAssignedStudentRoutine(), getAssignedRoutineWorkoutLogs().catch(() => []), getAssignedRoutineWorkoutSessions().catch(() => [])])
      .then(([assigned, logs, sessions]) => {
        setRoutine(assigned);
        setSelectedDayId(assigned?.days.some((day) => day.id === requestedDayId) ? requestedDayId ?? '' : assigned?.days[0]?.id ?? '');
        setWorkoutLogs(logs);
        setWorkoutSessions(sessions);
      })
      .catch(() => setError('No pudimos cargar tu rutina. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, [requestedDayId]);

  useEffect(() => {
    if (!activeSet && !sessionMode) return undefined;
    const tick = () => setClockNow(Date.now());
    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [activeSet, sessionMode]);

  useEffect(() => {
    if (!sessionMode || !sessionId || sessionStartedAtMs !== null) return;
    const storageKey = `workout-started-at:${sessionId}`;
    const stored = Number(window.localStorage.getItem(storageKey));
    const startedAt = Number.isFinite(stored) && stored > 0 ? stored : Date.now();
    if (!(Number.isFinite(stored) && stored > 0)) window.localStorage.setItem(storageKey, String(startedAt));
    setSessionStartedAtMs(startedAt);
  }, [sessionMode, sessionId, sessionStartedAtMs]);

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando tu rutina…</main>;

  const activeModality: RoutineModality = routine?.modality ?? 'GYM';
  const isHomeModality = activeModality === 'HOME';
  const selectedDay = routine?.days.find((day) => day.id === selectedDayId) ?? routine?.days[0];
  const totalDuration = selectedDay?.blocks.reduce((total, block) => total + (block.estimated_duration_minutes ?? 0), 0) ?? 0;
  const showCelebration = searchParams.get('completed') === '1';
  const currentSessionLogs = workoutLogs.filter((log) => Boolean(sessionId) && log.session_id === sessionId);
  const routineWorkoutSummaries = (() => {
    const routineLogs = workoutLogs.filter((entry) => routine && entry.routine_id === routine.id);
    const completedSessions = workoutSessions.filter((session) =>
      routine && session.routine_id === routine.id && session.finished_at,
    );
    const summaries = completedSessions.map((session) => {
      const logs = routineLogs.filter((log) => log.session_id === session.id);
      const average = (values: Array<number | null>) => {
        const valid = values.filter((value): value is number => value !== null && Number.isFinite(value));
        return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
      };
      const reps = logs.map((log) => {
        const value = Number.parseFloat(log.reps_completed.replace(',', '.'));
        return Number.isFinite(value) ? value : null;
      });
      const startedAt = Date.parse(session.started_at);
      const finishedAt = Date.parse(session.finished_at ?? session.started_at);
      return {
        key: session.id,
        logs,
        day: session.day_name,
        recordedAt: session.started_at,
        totalDuration: Number.isFinite(startedAt) && Number.isFinite(finishedAt) ? Math.max(0, Math.round((finishedAt - startedAt) / 1000)) : null,
        averageReps: average(reps),
        averageWeight: average(logs.map((log) => log.weight_kg === null ? null : Number(log.weight_kg))),
        averageDuration: average(logs.map((log) => log.duration_seconds)),
      };
    });
    const knownSessionIds = new Set(completedSessions.map((session) => session.id));
    const legacyGroups = new Map<string, WorkoutSetLog[]>();
    for (const log of routineLogs.filter((entry) => !entry.session_id || !knownSessionIds.has(entry.session_id))) {
      const dateKey = log.recorded_at.slice(0, 10);
      const key = `legacy:${dateKey}:${log.day_name}`;
      legacyGroups.set(key, [...(legacyGroups.get(key) ?? []), log]);
    }
    for (const [key, logs] of legacyGroups) {
      const average = (values: Array<number | null>) => {
        const valid = values.filter((value): value is number => value !== null && Number.isFinite(value));
        return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
      };
      const reps = logs.map((log) => {
        const value = Number.parseFloat(log.reps_completed.replace(',', '.'));
        return Number.isFinite(value) ? value : null;
      });
      summaries.push({
        key,
        logs,
        day: logs[0].day_name,
        recordedAt: logs.map((log) => log.recorded_at).sort()[0],
        totalDuration: null,
        averageReps: average(reps),
        averageWeight: average(logs.map((log) => log.weight_kg === null ? null : Number(log.weight_kg))),
        averageDuration: average(logs.map((log) => log.duration_seconds)),
      });
    }
    return summaries.sort((left, right) => right.recordedAt.localeCompare(left.recordedAt));
  })();
  const getRecordedSetCount = (item: RoutineExercise) => currentSessionLogs.filter(
    (log) => log.exercise_id === item.exercise.id && log.day_name === (selectedDay?.name ?? ''),
  ).length;
  const activeSetSeconds = activeSet ? Math.max(0, Math.floor((clockNow - activeSet.startedAt) / 1000)) : 0;
  const formatClock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

  const getDraftForItem = (item: RoutineExercise): SetLogDraft => {
    const existing = logDrafts[item.id];
    if (existing) return existing;
    const exerciseLogsCount = getRecordedSetCount(item);
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

  const handleBeginWorkout = async () => {
    if (!selectedDay || startingWorkout) return;
    setLogError('');
    setStartingWorkout(true);
    try {
      const session = await startAssignedWorkoutSession(selectedDay.name);
      const startedAt = Date.now();
      window.localStorage.setItem(`workout-started-at:${session.id}`, String(startedAt));
      navigate(ROUTES.studentRoutineSession + '?day=' + encodeURIComponent(selectedDay.id) + '&session=' + encodeURIComponent(session.id) + '&startedAt=' + encodeURIComponent(String(startedAt)));
    } catch {
      setLogError('No pudimos iniciar el entrenamiento. Intentá nuevamente.');
    } finally {
      setStartingWorkout(false);
    }
  };

  const handleFinishWorkout = async (automatic = false) => {
    if (!sessionId || activeSet || (!automatic && (finishedSet || savingExerciseId)) || finishingWorkout) return;
    setLogError('');
    setFinishingWorkout(true);
    try {
      await finishAssignedWorkoutSession(sessionId);
      window.localStorage.removeItem(`workout-started-at:${sessionId}`);
      setActiveRest(null);
      setAutoFinishPending(false);
      navigate(ROUTES.studentRoutines + '?session=' + encodeURIComponent(sessionId) + (automatic ? '&completed=1' : ''));
    } catch {
      setLogError('No pudimos finalizar el entrenamiento. Intentá nuevamente.');
    } finally {
      setFinishingWorkout(false);
    }
  };

  const handleStartSet = (item: RoutineExercise) => {
    if (activeRest || activeSet || finishedSet || blockedExerciseIds.includes(item.exercise.id)) return;
    setActiveSet({ exerciseId: item.id, startedAt: Date.now() });
  };

  const handleFinishSet = (item: RoutineExercise) => {
    if (!activeSet || activeSet.exerciseId !== item.id) return;
    const durationSeconds = Math.max(1, Math.round((Date.now() - activeSet.startedAt) / 1000));
    setActiveSet(null);
    setFinishedSet({ exerciseId: item.id, durationSeconds });
  };

  const handleRecordSet = async (item: RoutineExercise) => {
    if (!routine || !selectedDay || savingExerciseId || finishedSet?.exerciseId !== item.id || (sessionMode && !sessionId)) return;
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
        exercise_id: item.exercise.id,
        day_name: selectedDay.name,
        set_number: parsedSet,
        reps_completed: draft.repsCompleted.trim(),
        weight_kg: parsedWeight,
        duration_seconds: finishedSet.durationSeconds,
        session_id: sessionMode ? sessionId ?? undefined : undefined,
        modality: activeModality,
      });
      const updatedLogs = [created, ...workoutLogs];
      setWorkoutLogs(updatedLogs);
      setFinishedSet(null);
      const allRequiredSetsDone = Boolean(selectedDay) && selectedDay.blocks
        .flatMap((block) => block.exercises)
        .filter((exercise) => !skipped.includes(exercise.id))
        .every((exercise) => updatedLogs.filter((log) =>
          log.session_id === sessionId
          && log.day_name === selectedDay.name
          && log.exercise_id === exercise.exercise.id,
        ).length >= exercise.sets);
      setAutoFinishPending(allRequiredSetsDone);
      if (item.rest_seconds > 0) {
        setActiveRest({ exerciseName: item.exercise.name, durationSeconds: item.rest_seconds, key: created.id });
      } else if (allRequiredSetsDone) {
        await handleFinishWorkout(true);
      }
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
    <main className={`profile-shell ${sessionMode ? 'profile-shell--session' : 'profile-shell--overview'}`}>
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className={`profile-card student-daily-routine ${sessionMode ? 'student-daily-routine--session' : 'student-daily-routine--overview'}`}>
        <div className="profile-heading">
          <span>{sessionMode ? 'ENTRENAMIENTO EN CURSO' : 'RESUMEN DE TU PLAN'}</span>
          <h1>{sessionMode ? 'Tu entrenamiento' : 'Rutina del día'}</h1>
          <p>{sessionMode ? 'Registrá cada serie y seguí el descanso indicado por tu entrenador.' : 'Consultá los ejercicios y tiempos de la rutina que te asignó tu entrenador.'}</p>
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
                  disabled={sessionMode && Boolean(activeSet || finishedSet || activeRest || savingExerciseId)}
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
            {sessionMode && <div className="student-routine-session-heading">
              <div>
                <span className="student-routine-session-heading__badge">SESIÓN ACTIVA</span>
                <h2>{selectedDay?.name ?? 'Rutina'}</h2>
                <p>Iniciá una serie, finalizala y registrá las repeticiones y la carga.</p>
                <span className="student-routine-session-heading__elapsed" role="timer" aria-label="Tiempo transcurrido del entrenamiento">Tiempo de entrenamiento: {formatClock(sessionStartedAtMs ? Math.max(0, Math.floor((clockNow - sessionStartedAtMs) / 1000)) : 0)}</span>
              </div>
            </div>}
            {sessionMode && activeRest && <RestTimer key={activeRest.key} exerciseName={activeRest.exerciseName} durationSeconds={activeRest.durationSeconds} onFinish={() => {
              setActiveRest(null);
              if (autoFinishPending) void handleFinishWorkout(true);
            }} />}

            {!sessionMode && <div className="student-routine-modality" aria-label="Selector rápido de modalidad de rutina">
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
            </div>}

            {!sessionMode && modalityError && (
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
                            <h4>{item.exercise.name}</h4>
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
                        <p>{item.sets} series · {item.reps} repeticiones</p>
                        <p>
                          {isHomeModality
                            ? `Peso corporal / Sin materiales${item.target_weight_kg !== null && item.target_weight_kg > 0 ? ` (ref. gimnasio: ${item.target_weight_kg} kg)` : ''}`
                            : item.target_weight_kg === null
                              ? 'Sin carga indicada'
                              : `${item.target_weight_kg} kg`}{' '}
                          · {item.rest_seconds} s de descanso
                        </p>
                        {sessionMode && (item.exercise.technical_cues || item.exercise.breathing_cues) && (
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
                        {sessionMode && item.exercise.video_url && (
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

                        {sessionMode && !blockedExerciseIds.includes(item.exercise.id) && !activeSet && !finishedSet && !activeRest && <div className="student-routine-exercise__session-actions"><button type="button" className="student-routine-exercise__log-btn" disabled={getRecordedSetCount(item) >= item.sets} onClick={() => handleStartSet(item)}>{getRecordedSetCount(item) >= item.sets ? 'Series completadas' : 'Iniciar serie'}</button></div>}
                        {sessionMode && activeSet?.exerciseId === item.id && <div className="student-routine-exercise__session-actions">
                          <span className="student-routine-exercise__elapsed-clock" role="timer" aria-label="Duración de la serie">{formatClock(activeSetSeconds)}</span>
                          <button type="button" className="student-routine-exercise__log-btn" onClick={() => handleFinishSet(item)}>Finalizar serie</button>
                        </div>}
                        {sessionMode && finishedSet?.exerciseId === item.id && !blockedExerciseIds.includes(item.exercise.id) && <p className="student-routine-exercise__elapsed">Duración de la serie: {finishedSet.durationSeconds} s</p>}
                        {sessionMode && finishedSet?.exerciseId === item.id && !blockedExerciseIds.includes(item.exercise.id) && <div className="student-routine-exercise__logger">
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

            {!sessionMode && <div className="student-routine-start">
              <p>Revisá los ejercicios de este día y comenzá cuando estés listo.</p>
              <button type="button" className="student-routine-start__button" disabled={startingWorkout || !selectedDay} onClick={handleBeginWorkout}>
                {startingWorkout ? 'Iniciando…' : 'Comenzar rutina'}
              </button>
            </div>}

            {!sessionMode && <section className="student-routine-history student-routine-history--progress" aria-labelledby="workout-history-heading">
              <header className="student-routine-history__header">
                <div className="student-routine-history__title">
                  <History size={20} />
                  <h3 id="workout-history-heading">Tu progreso con esta rutina</h3>
                </div>
                <span>{routineWorkoutSummaries.length} {routineWorkoutSummaries.length === 1 ? 'entrenamiento' : 'entrenamientos'}</span>
              </header>
              <p className="student-routine-history__subtitle">Resumen de tus entrenamientos anteriores, con promedios de las series registradas.</p>
              {routineWorkoutSummaries.length === 0 ? (
                <p className="student-routine-history__empty">Todavía no hay entrenamientos registrados para esta rutina. Cuando termines uno, vas a poder consultar acá tu progreso.</p>
              ) : (
                <ul className="student-routine-history__list">
                  {routineWorkoutSummaries.map((workout) => (
                    <li key={workout.key} className="student-routine-history__item student-routine-history__item--workout">
                      <div className="student-routine-history__item-main">
                        <strong>{workout.day}</strong>
                        <time className="student-routine-history__date" dateTime={workout.recordedAt}>{new Date(workout.recordedAt).toLocaleDateString('es-AR')}</time>
                        <span className="student-routine-history__meta">{workout.logs.length} {workout.logs.length === 1 ? 'serie registrada' : 'series registradas'}</span>
                        <span className="student-routine-history__averages">
                          Promedios: {workout.averageReps === null ? 'repeticiones —' : `${workout.averageReps.toFixed(1)} reps`} · {workout.averageWeight === null ? 'carga —' : `${workout.averageWeight.toFixed(1)} kg`} · {workout.averageDuration === null ? 'duración —' : `${workout.averageDuration.toFixed(0)} s por serie`}<br />Duración total: {workout.totalDuration === null ? 'No disponible' : formatWorkoutDuration(workout.totalDuration)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>}
            {sessionMode && sessionId && <section className="student-routine-history student-routine-history--current" aria-labelledby="current-workout-history-heading">
              <header className="student-routine-history__header">
                <div className="student-routine-history__title"><History size={20} /><h3 id="current-workout-history-heading">Historial de este entrenamiento</h3></div>
                <span>{currentSessionLogs.length} {currentSessionLogs.length === 1 ? 'serie registrada' : 'series registradas'}</span>
              </header>
              <p className="student-routine-history__subtitle">Registros realizados durante esta sesión.</p>
              {currentSessionLogs.length === 0 ? (
                <p className="student-routine-history__empty">Todavía no registraste series en este entrenamiento.</p>
              ) : (
                <ul className="student-routine-history__list">
                  {currentSessionLogs.map((log) => (
                    <li key={log.id} className="student-routine-history__item">
                      <div className="student-routine-history__item-main">
                        <strong>{log.exercise_name}</strong>
                        <time className="student-routine-history__date" dateTime={log.recorded_at}>{new Date(log.recorded_at).toLocaleDateString('es-AR')}</time>
                        <span className="student-routine-history__meta">{log.day_name} · Serie {log.set_number} · {log.reps_completed} reps · {log.weight_kg === null || log.weight_kg === 0 ? 'Peso corporal (0 kg)' : `${log.weight_kg} kg`}</span>
                        {log.duration_seconds !== null && <span className="student-routine-history__meta">Duración de la serie: {formatWorkoutDuration(log.duration_seconds)}</span>}
                      </div>
                      <span className={`student-routine-exercise__modality-badge ${log.modality === 'HOME' ? 'student-routine-exercise__modality-badge--home' : 'student-routine-exercise__modality-badge--gym'}`}>{ROUTINE_MODALITIES[log.modality] ?? log.modality}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>}
            {sessionMode && <div className="student-routine-finish">
              <button type="button" className="student-routine-finish__button"
                disabled={!sessionId || Boolean(activeSet || finishedSet || savingExerciseId || finishingWorkout || autoFinishPending)}
                onClick={() => void handleFinishWorkout(false)}>
                {finishingWorkout ? 'Finalizando…' : 'Finalizar rutina'}
              </button>
            </div>}
          </>
        )}
        {showCelebration && <div className="workout-celebration" role="dialog" aria-modal="true" aria-labelledby="workout-celebration-title">
          <div className="workout-confetti" aria-hidden="true">{Array.from({ length: 28 }, (_, index) => <span key={index} className={`workout-confetti__piece workout-confetti__piece--${index % 6}`} style={{ left: `${(index * 37) % 100}%`, animationDelay: `${(index % 8) * 0.12}s` }} />)}</div>
          <div className="workout-celebration__card">
            <span className="workout-celebration__icon" aria-hidden="true">✦</span>
            <h2 id="workout-celebration-title">¡Felicitaciones!</h2>
            <p>Terminaste el entrenamiento del día. Momento de descansar.</p>
            <button type="button" onClick={() => navigate(ROUTES.studentRoutines + (sessionId ? '?session=' + encodeURIComponent(sessionId) : ''), { replace: true })}>Continuar</button>
          </div>
        </div>}
      </section>
    </main>
  );
}
