import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, CircleAlert, Pencil } from 'lucide-react';
import { ROUTES } from '../constants/routes';
import { EffortFeedbackForm } from './EffortFeedbackForm';
import { assignRoutineToStudent, getRoutineAssignments, getTrainerStudentWorkoutLogs, getTrainerStudentWorkoutSessions } from '../services/routineTemplateService';
import { getAllTrainerStudentBodyMapReports, getTrainerStudentZoneHistory } from '../services/bodyMapReportService';
import type { TrainerAIRoutine } from '../types/assignedRoutine';
import type { BodyMapReportResponse, BodyMapZoneHistoryItem } from '../types/bodyMapReport';
import type { RoutineAssignmentStudent, RoutineTemplate, WorkoutSession, WorkoutSetLog } from '../types/routineTemplate';
import '../styles/routine-assignment-progress.css';
import '../styles/body-map.css';

function localDateKey(value: string): string {
  const date = new Date(value);
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function reportsForSession(
  session: WorkoutSession,
  sessions: WorkoutSession[],
  reports: BodyMapZoneHistoryItem[],
): BodyMapZoneHistoryItem[] {
  return reports.filter((report) => {
    if (report.session_id) return report.session_id === session.id;
    if (!report.session_day_name || report.session_day_name !== session.day_name) return false;
    if (localDateKey(report.created_at) !== localDateKey(session.started_at)) return false;

    const matchingSessions = sessions
      .filter((candidate) => candidate.day_name === report.session_day_name
        && localDateKey(candidate.started_at) === localDateKey(report.created_at))
      .sort((left, right) => Math.abs(Date.parse(left.started_at) - Date.parse(report.created_at))
        - Math.abs(Date.parse(right.started_at) - Date.parse(report.created_at)));
    return matchingSessions[0]?.id === session.id;
  });
}

interface RoutineAssignmentPanelProps {
  templates: RoutineTemplate[];
  aiRoutines: TrainerAIRoutine[];
  initialStudentId?: string;
  initialSessionId?: string;
  initialEventId?: string;
  initialEventType?: string;
  onStudentSelect?: (studentId: string) => void;
  selectedStudentId?: string | null;
}

export function RoutineAssignmentPanel({
  templates,
  aiRoutines,
  initialStudentId,
  initialSessionId,
  initialEventId,
  initialEventType,
  onStudentSelect,
  selectedStudentId,
}: RoutineAssignmentPanelProps) {
  const [students, setStudents] = useState<RoutineAssignmentStudent[]>([]);
  const [selectedRoutines, setSelectedRoutines] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [attentionLoaded, setAttentionLoaded] = useState(false);
  const [attentionError, setAttentionError] = useState('');
  const [sessionAvailabilityByRelationship, setSessionAvailabilityByRelationship] = useState<Record<string, boolean>>({});
  const [reportAvailabilityByStudent, setReportAvailabilityByStudent] = useState<Record<string, boolean>>({});
  const [savingId, setSavingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [openProgressFor, setOpenProgressFor] = useState<string | null>(null);
  const [progressByRelationship, setProgressByRelationship] = useState<Record<string, WorkoutSetLog[]>>({});
  const [sessionsByRelationship, setSessionsByRelationship] = useState<Record<string, WorkoutSession[]>>({});
  const [reportsByStudent, setReportsByStudent] = useState<Record<string, BodyMapReportResponse[]>>({});
  const [zoneReportsByStudent, setZoneReportsByStudent] = useState<Record<string, BodyMapZoneHistoryItem[]>>({});
  const [expandedSessionDetails, setExpandedSessionDetails] = useState<Record<string, boolean>>({});
  const [highlightedSessionId, setHighlightedSessionId] = useState<string | null>(null);
  const [highlightedEventId, setHighlightedEventId] = useState<string | null>(null);
  const [notificationContextMessage, setNotificationContextMessage] = useState('');
  const [progressLoadingFor, setProgressLoadingFor] = useState<string | null>(null);
  const [progressErrorFor, setProgressErrorFor] = useState<string | null>(null);
  const openedFromNotification = useRef(false);

  useEffect(() => {
    getRoutineAssignments()
      .then((items) => {
        setStudents(items);
        setSelectedRoutines(Object.fromEntries(items.map((item) => [item.relationship_id, item.routine_template_id ?? ''])));
      })
      .catch(() => setError('No pudimos cargar tus alumnos activos. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (loading) return undefined;
    let cancelled = false;
    setAttentionLoaded(false);
    setAttentionError('');

    Promise.all(students.map(async (student) => {
      const [sessionsResult, reportsResult] = await Promise.allSettled([
        getTrainerStudentWorkoutSessions(student.relationship_id),
        getAllTrainerStudentBodyMapReports(student.student_id),
      ]);
      return { student, sessionsResult, reportsResult };
    })).then((results) => {
      if (cancelled) return;
      const nextSessions: Record<string, WorkoutSession[]> = {};
      const nextReports: Record<string, BodyMapReportResponse[]> = {};
      const nextSessionAvailability: Record<string, boolean> = {};
      const nextReportAvailability: Record<string, boolean> = {};
      let failed = false;
      results.forEach(({ student, sessionsResult, reportsResult }) => {
        if (sessionsResult.status === 'fulfilled') {
          nextSessions[student.relationship_id] = sessionsResult.value;
          nextSessionAvailability[student.relationship_id] = true;
        } else {
          nextSessionAvailability[student.relationship_id] = false;
          failed = true;
        }
        if (reportsResult.status === 'fulfilled') {
          nextReports[student.student_id] = reportsResult.value;
          nextReportAvailability[student.student_id] = true;
        } else {
          nextReportAvailability[student.student_id] = false;
          failed = true;
        }
      });
      setSessionsByRelationship((current) => ({ ...current, ...nextSessions }));
      setReportsByStudent(nextReports);
      setSessionAvailabilityByRelationship(nextSessionAvailability);
      setReportAvailabilityByStudent(nextReportAvailability);
      setAttentionLoaded(true);
      if (failed) setAttentionError('No pudimos actualizar todos los indicadores de atención.');
    });

    return () => {
      cancelled = true;
    };
  }, [loading, students]);

  useEffect(() => {
    if (!initialStudentId || loading || openedFromNotification.current) return;
    const student = students.find((item) => item.student_id === initialStudentId);
    openedFromNotification.current = true;
    if (!student) {
      setNotificationContextMessage('No encontramos este alumno entre tus vínculos activos. Puede que ya no esté disponible.');
      return;
    }
    setOpenProgressFor(student.relationship_id);
    if (initialEventId) setHighlightedEventId(initialEventId);
    if (initialSessionId) {
      setExpandedSessionDetails((current) => ({ ...current, [initialSessionId]: true }));
      setHighlightedSessionId(initialSessionId);
    }
  }, [initialStudentId, initialSessionId, initialEventId, loading, students]);

  useEffect(() => {
    if (!initialStudentId || loading || !openedFromNotification.current) return;
    const student = students.find((item) => item.student_id === initialStudentId);
    if (!student) return;

    const sessionsAvailable = sessionAvailabilityByRelationship[student.relationship_id];
    if (attentionLoaded && sessionsAvailable === false) {
      setNotificationContextMessage('No pudimos cargar las sesiones de este alumno. Revisá su progreso desde esta sección.');
      return;
    }

    if (initialSessionId && attentionLoaded && sessionsAvailable) {
      const sessionExists = (sessionsByRelationship[student.relationship_id] ?? [])
        .some((session) => session.id === initialSessionId);
      if (!sessionExists) {
        setNotificationContextMessage('La sesión de esta notificación ya no está disponible. Podés consultar el progreso actual del alumno.');
      }
    }

    if (!initialEventId) return;
    if (initialEventType === 'PAIN_ALERT') {
      if (!attentionLoaded || reportAvailabilityByStudent[student.student_id] === undefined) return;
      if (!reportAvailabilityByStudent[student.student_id]) {
        setNotificationContextMessage('No pudimos comprobar el reporte asociado a esta notificación. Podés consultar los reportes disponibles del alumno.');
        return;
      }
      const report = (reportsByStudent[student.student_id] ?? [])
        .find((item) => item.id === initialEventId);
      if (!report) {
        setNotificationContextMessage('El reporte asociado a esta notificación ya no está disponible. Podés consultar los reportes actuales del alumno.');
        return;
      }
      const sessionId = report.session_id ?? initialSessionId;
      if (sessionId) {
        setHighlightedSessionId(sessionId);
        setExpandedSessionDetails((current) => ({ ...current, [sessionId]: true }));
      } else {
        setNotificationContextMessage('Este reporte no tiene una sesión disponible para destacar. Podés consultar los reportes actuales del alumno.');
      }
    } else if (initialEventType === 'PERSONAL_RECORD') {
      if (!Object.prototype.hasOwnProperty.call(progressByRelationship, student.relationship_id)) {
        if (progressErrorFor === student.relationship_id && progressLoadingFor !== student.relationship_id) {
          setNotificationContextMessage('No pudimos comprobar el récord asociado a esta notificación. Podés consultar el progreso actual del alumno.');
        }
        return;
      }
      const log = (progressByRelationship[student.relationship_id] ?? [])
        .find((item) => item.id === initialEventId);
      if (!log) {
        setNotificationContextMessage('La serie asociada a este récord ya no está disponible. Podés consultar el progreso actual del alumno.');
        return;
      }
      const sessionId = log.session_id ?? initialSessionId;
      if (sessionId) {
        setHighlightedSessionId(sessionId);
        setExpandedSessionDetails((current) => ({ ...current, [sessionId]: true }));
      } else {
        setNotificationContextMessage('Este récord no tiene una sesión disponible para destacar. Podés consultar el progreso actual del alumno.');
      }
    }
  }, [
    attentionLoaded,
    initialEventId,
    initialEventType,
    initialSessionId,
    initialStudentId,
    loading,
    progressByRelationship,
    progressErrorFor,
    progressLoadingFor,
    reportAvailabilityByStudent,
    reportsByStudent,
    sessionAvailabilityByRelationship,
    sessionsByRelationship,
    students,
  ]);

  useEffect(() => {
    if (!highlightedSessionId || !openProgressFor) return;
    const frame = window.requestAnimationFrame(() => {
      const target = document.getElementById(highlightedEventId
        ? `routine-event-${highlightedEventId}`
        : `routine-session-${highlightedSessionId}`)
        ?? document.getElementById(`routine-session-${highlightedSessionId}`);
      target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [highlightedEventId, highlightedSessionId, openProgressFor, progressByRelationship, sessionsByRelationship, zoneReportsByStudent]);

  const approvedAIRoutines = (studentId: string) => aiRoutines.filter((item) => item.student_id === studentId && item.status === 'APPROVED');

  useEffect(() => {
    if (!openProgressFor) return undefined;
    let cancelled = false;
    let inFlight = false;
    const relationshipId = openProgressFor;
    const refreshProgress = async () => {
      if (inFlight) return;
      inFlight = true;
      setProgressLoadingFor(relationshipId);
      try {
        const studentObj = students.find((s) => s.relationship_id === relationshipId);
        const [logs, sessions, zoneReports] = await Promise.all([
          getTrainerStudentWorkoutLogs(relationshipId),
          getTrainerStudentWorkoutSessions(relationshipId).catch(() => []),
          studentObj ? getTrainerStudentZoneHistory(studentObj.student_id).catch(() => []) : Promise.resolve([]),
        ]);
        if (!cancelled) {
          setProgressByRelationship((current) => ({ ...current, [relationshipId]: logs }));
          setSessionsByRelationship((current) => ({ ...current, [relationshipId]: sessions }));
          if (studentObj) {
            setZoneReportsByStudent((current) => ({ ...current, [studentObj.student_id]: zoneReports }));
          }
          setProgressErrorFor(null);
        }
      } catch {
        if (!cancelled) setProgressErrorFor(relationshipId);
      } finally {
        inFlight = false;
        if (!cancelled) setProgressLoadingFor(null);
      }
    };
    void refreshProgress();
    const interval = window.setInterval(() => void refreshProgress(), 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [openProgressFor]);

  // La rutina vigente puede ser una copia cuyo origen ya no existe: se muestra, pero no se reasigna.
  const isDetachedCopy = (student: RoutineAssignmentStudent) => Boolean(student.routine_template_id)
    && !templates.some((item) => item.id === student.routine_template_id)
    && !approvedAIRoutines(student.student_id).some((item) => item.id === student.routine_template_id);

  async function saveAssignment(student: RoutineAssignmentStudent) {
    setSavingId(student.relationship_id);
    setError('');
    setMessage('');
    setWarnings([]);
    try {
      const routineTemplateId = selectedRoutines[student.relationship_id] || null;
      const conflicts = await assignRoutineToStudent(student.relationship_id, routineTemplateId);
      setWarnings(conflicts);
      const routine = [...templates, ...aiRoutines].find((item) => item.id === routineTemplateId);
      setStudents((current) => current.map((item) => item.relationship_id === student.relationship_id
        ? { ...item, routine_template_id: routineTemplateId, routine_name: routine?.name ?? null }
        : item));
      setMessage(`Rutina actualizada para ${student.student_name}.`);
    } catch {
      setError('No pudimos guardar la asignación. Intentá nuevamente.');
    } finally {
      setSavingId('');
    }
  }

  function focusStudentEvent(student: RoutineAssignmentStudent, sessionId?: string | null) {
    setOpenProgressFor(student.relationship_id);
    setHighlightedEventId(null);
    if (!sessionId) {
      setHighlightedSessionId(null);
      return;
    }
    setHighlightedSessionId(sessionId);
    setExpandedSessionDetails((current) => ({ ...current, [sessionId]: true }));
  }

  function reportsWithDiscomfort(studentId: string): BodyMapReportResponse[] {
    return (reportsByStudent[studentId] ?? []).filter((report) =>
      report.zones.some((zone) => zone.intensity === 'PAIN' || zone.intensity === 'DISCOMFORT'),
    );
  }

  function pendingFeedbackSessions(relationshipId: string): WorkoutSession[] {
    return (sessionsByRelationship[relationshipId] ?? []).filter((session) =>
      session.rpe !== null && session.rpe !== undefined && !session.effort_feedback,
    );
  }

  function visibleSessionsFor(relationshipId: string): WorkoutSession[] {
    const sessions = sessionsByRelationship[relationshipId] ?? [];
    const recentSessions = sessions.slice(0, 5);
    const focusedSession = sessions.find((session) => session.id === highlightedSessionId);
    return focusedSession && !recentSessions.some((session) => session.id === focusedSession.id)
      ? [...recentSessions, focusedSession]
      : recentSessions;
  }

  return (
    <section className="routine-assignment">
      <div className="profile-heading">
        <span>ALUMNOS ACTIVOS</span>
        <h2>Asignar rutinas</h2>
        <p>Elegí qué rutina puede consultar cada alumno en “Rutina del día”.</p>
      </div>

      {loading ? (
        <p role="status">Cargando alumnos…</p>
      ) : error && students.length === 0 ? (
        <p className="form-alert" role="alert">{error}</p>
      ) : students.length === 0 ? (
        <p className="plan-empty">No tenés alumnos con un vínculo activo.</p>
      ) : (
        <div className="routine-assignment__list">
          {students.map((student) => (
            <div className="routine-assignment__row" key={student.relationship_id}>
              <div className="routine-assignment__student">
                <button
                  type="button"
                  className="routine-assignment__student-link"
                  aria-expanded={selectedStudentId === student.student_id}
                  aria-controls={`student-detail-${student.student_id}`}
                  onClick={() => onStudentSelect?.(student.student_id)}
                >
                  {student.student_name}
                </button>
                {attentionLoaded && reportsWithDiscomfort(student.student_id).length > 0 && (
                  <button
                    type="button"
                    className="routine-assignment__attention routine-assignment__attention--report"
                    title="Indicador informativo: no hay un estado de revisión persistido para estos reportes."
                    onClick={() => focusStudentEvent(
                      student,
                      reportsWithDiscomfort(student.student_id)[0]?.session_id,
                    )}
                  >
                    Molestias reportadas
                  </button>
                )}
                {attentionLoaded && pendingFeedbackSessions(student.relationship_id).length > 0 && (
                  <button
                    type="button"
                    className="routine-assignment__attention routine-assignment__attention--feedback"
                    onClick={() => focusStudentEvent(
                      student,
                      pendingFeedbackSessions(student.relationship_id)[0]?.id,
                    )}
                  >
                    Devolución pendiente
                  </button>
                )}
              </div>
              <label htmlFor={`routine-${student.relationship_id}`}>Rutina
                <select
                  id={`routine-${student.relationship_id}`}
                  className="exercise-select"
                  value={selectedRoutines[student.relationship_id] ?? ''}
                  onChange={(event) => setSelectedRoutines((current) => ({
                    ...current,
                    [student.relationship_id]: event.target.value,
                  }))}
                >
                  <option value="">Sin rutina asignada</option>
                  {isDetachedCopy(student) && <option value={student.routine_template_id ?? ''}>{student.routine_name} (actual)</option>}
                  {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                  {approvedAIRoutines(student.student_id).map((routine) => <option key={routine.id} value={routine.id}>{routine.name} (IA)</option>)}
                </select>
              </label>
              <button
                type="button"
                className="profile-save"
                onClick={() => void saveAssignment(student)}
                disabled={savingId === student.relationship_id || (isDetachedCopy(student) && selectedRoutines[student.relationship_id] === student.routine_template_id)}
              >
                {savingId === student.relationship_id ? 'Guardando…' : 'Guardar asignación'}
              </button>
              <div className="routine-assignment__actions">
                <span className="routine-assignment__actions-label">Acciones del alumno</span>
                <div className="routine-assignment__actions-buttons">
                  {student.routine_template_id && (
                    <Link
                      className={`profile-save routine-assignment__action-link${student.conflict_count > 0 ? ' routine-assignment__action-link--conflict' : ''}`}
                      to={ROUTES.trainerStudentRoutine.replace(':studentId', student.student_id)}
                      aria-label={student.conflict_count > 0
                        ? `Editar rutina de ${student.student_name}. Esta rutina tiene ejercicios que requieren revisión.`
                        : undefined}
                      title={student.conflict_count > 0 ? 'Esta rutina tiene ejercicios que requieren revisión' : undefined}
                      data-tooltip={student.conflict_count > 0 ? 'Esta rutina tiene ejercicios que requieren revisión' : undefined}
                    >
                      <Pencil size={15} aria-hidden="true" />
                      Editar rutina
                      {student.conflict_count > 0 && <CircleAlert size={18} aria-hidden="true" />}
                    </Link>
                  )}
                  <button
                    type="button"
                    className="profile-save routine-assignment__progress-toggle"
                    aria-expanded={openProgressFor === student.relationship_id}
                    onClick={() => {
                      setHighlightedSessionId(null);
                      setOpenProgressFor((current) => current === student.relationship_id ? null : student.relationship_id);
                    }}
                  >
                    {openProgressFor === student.relationship_id ? 'Ocultar progreso' : 'Ver progreso del alumno'}
                    <ChevronDown size={16} aria-hidden="true" />
                  </button>
                </div>
              </div>
              {openProgressFor === student.relationship_id && <div className="routine-assignment__progress" aria-label={`Progreso de ${student.student_name}`}>
                <div className="routine-assignment__progress-heading">
                  <strong>Sesiones y Esfuerzo (RPE)</strong>
                  <span>{progressLoadingFor === student.relationship_id ? 'Actualizando…' : 'Actualización automática'}</span>
                </div>
                {(sessionsByRelationship[student.relationship_id] ?? []).length === 0 ? (
                  <p className="plan-empty routine-assignment__empty">Todavía no hay sesiones finalizadas.</p>
                ) : (
                  <ul className="routine-assignment__sessions-list">
                    {visibleSessionsFor(student.relationship_id).map((session) => {
                      const sessions = sessionsByRelationship[student.relationship_id] ?? [];
                      const sessionLogs = (progressByRelationship[student.relationship_id] ?? [])
                        .filter((log) => log.session_id === session.id)
                        .sort((left, right) => left.recorded_at.localeCompare(right.recorded_at));
                      const sessionReports = reportsForSession(
                        session,
                        sessions,
                        zoneReportsByStudent[student.student_id] ?? [],
                      );
                      const highlightedReportIndex = highlightedEventId
                        ? sessionReports.findIndex((report) => report.report_id === highlightedEventId)
                        : -1;
                      const detailExpanded = Boolean(expandedSessionDetails[session.id]);

                      return (
                        <li
                          key={session.id}
                          id={`routine-session-${session.id}`}
                          className={`routine-assignment__session-item${session.id === highlightedSessionId ? ' routine-assignment__session-item--highlighted' : ''}`}
                        >
                            <div className="routine-assignment__session-summary">
                              <strong>{session.day_name}</strong>
                              <time dateTime={session.started_at}>{new Date(session.started_at).toLocaleDateString('es-AR')}</time>
                              {session.rpe !== null && session.rpe !== undefined ? (
                                <span className="routine-assignment__rpe-badge routine-assignment__rpe-badge--reported">
                                  Esfuerzo: {session.rpe}/10
                                </span>
                              ) : (
                                <span className="routine-assignment__rpe-badge routine-assignment__rpe-badge--unreported">
                                  Sin calificación
                                </span>
                              )}
                            </div>
                            {session.rpe !== null && session.rpe !== undefined && (
                              <EffortFeedbackForm
                                key={`${session.id}:${session.effort_feedback?.updated_at ?? ''}`}
                                relationshipId={student.relationship_id}
                                session={session}
                                onSaved={(feedback) => setSessionsByRelationship((current) => ({
                                  ...current,
                                  [student.relationship_id]: (current[student.relationship_id] ?? []).map((item) => (
                                    item.id === session.id ? { ...item, effort_feedback: feedback } : item
                                  )),
                                }))}
                              />
                            )}
                            {sessionReports.length > 0 && (
                              <div className="routine-assignment__session-reports" aria-label="Reportes de molestias de este entrenamiento">
                                {sessionReports.map((report, index) => (
                                  <div
                                    className={`routine-assignment__session-report${index === highlightedReportIndex ? ' routine-assignment__session-report--highlighted' : ''}`}
                                    id={index === highlightedReportIndex ? `routine-event-${highlightedEventId}` : undefined}
                                    key={report.id}
                                  >
                                    <strong>{report.zone_display || report.zone}</strong>
                                    <span className={`body-map-history-badge body-map-history-badge--${report.intensity.toLowerCase()}`}>
                                      {report.intensity === 'PAIN' ? 'Dolor' : report.intensity === 'DISCOMFORT' ? 'Molestia' : 'Carga normal'}
                                    </span>
                                    <time dateTime={report.created_at}>{new Date(report.created_at).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}</time>
                                    <span className="routine-assignment__session-report-exercise">
                                      {report.context === 'IN_EXERCISE' ? 'Durante ejercicio' : 'Fin del entrenamiento'}
                                      {report.exercise_name ? ` · ${report.exercise_name}` : ''}
                                      {report.action_taken === 'VARIANT_ACCEPTED' ? ' · Variante aceptada' : report.action_taken === 'EXERCISE_SKIPPED' ? ' · Ejercicio salteado' : ''}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            )}
                            <button
                              type="button"
                              className="routine-assignment__detail-toggle"
                              aria-expanded={detailExpanded}
                              aria-controls={`session-set-details-${session.id}`}
                              onClick={() => setExpandedSessionDetails((current) => ({ ...current, [session.id]: !current[session.id] }))}
                            >
                              {detailExpanded ? 'Ocultar detalle del entrenamiento' : 'Mostrar detalle del entrenamiento'}
                              <ChevronDown size={16} aria-hidden="true" />
                            </button>
                            {detailExpanded && (
                              <ul id={`session-set-details-${session.id}`} className="routine-assignment__set-list">
                                {sessionLogs.length === 0 ? (
                                  <li className="routine-assignment__set-empty">No hay series registradas en este entrenamiento.</li>
                                ) : sessionLogs.map((log) => (
                                  <li
                                    key={log.id}
                                    id={log.id === highlightedEventId ? `routine-event-${highlightedEventId}` : undefined}
                                    className={`routine-assignment__set-item${log.id === highlightedEventId ? ' routine-assignment__set-item--highlighted' : ''}`}
                                  >
                                    <strong>{log.exercise_name}</strong>
                                    <span>Serie {log.set_number}</span>
                                    <span>{log.reps_completed} reps</span>
                                    <span>{log.weight_kg === null || log.weight_kg === 0 ? 'Peso corporal' : `${log.weight_kg} kg`}</span>
                                    {log.duration_seconds !== null && <span>{log.duration_seconds} s</span>}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </li>
                        );
                    })}
                    </ul>
                  )}
                  {progressErrorFor === student.relationship_id ? (
                    <p className="form-alert" role="alert">No pudimos cargar el progreso. Seguiremos intentando actualizarlo.</p>
                  ) : null}
              </div>}
            </div>
          ))}
        </div>
      )}
      {error && students.length > 0 && <p className="form-alert" role="alert">{error}</p>}
      {attentionError && <p className="form-alert" role="alert">{attentionError}</p>}
      {notificationContextMessage && (
        <p className="form-alert" role="status">{notificationContextMessage}</p>
      )}
      {message && <p className="profile-success" role="status">{message}</p>}
      {warnings.length > 0 && (
        <div className="rt-alert" role="alert">
          <div>
            <strong>Atención: la rutina asignada tiene ejercicios que no son compatibles con las limitaciones del alumno</strong>
            <ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            <p>El alumno ya puede verla. Usá “Editar rutina” para reemplazar esos ejercicios y confirmar.</p>
          </div>
        </div>
      )}
    </section>
  );
}
