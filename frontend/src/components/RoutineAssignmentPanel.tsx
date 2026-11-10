import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { EffortFeedbackForm } from './EffortFeedbackForm';
import { assignRoutineToStudent, getRoutineAssignments, getTrainerStudentWorkoutLogs, getTrainerStudentWorkoutSessions } from '../services/routineTemplateService';
import type { TrainerAIRoutine } from '../types/assignedRoutine';
import type { RoutineAssignmentStudent, RoutineTemplate, WorkoutSession, WorkoutSetLog } from '../types/routineTemplate';
import '../styles/routine-assignment-progress.css';

interface RoutineAssignmentPanelProps {
  templates: RoutineTemplate[];
  aiRoutines: TrainerAIRoutine[];
}

export function RoutineAssignmentPanel({ templates, aiRoutines }: RoutineAssignmentPanelProps) {
  const [students, setStudents] = useState<RoutineAssignmentStudent[]>([]);
  const [selectedRoutines, setSelectedRoutines] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [openProgressFor, setOpenProgressFor] = useState<string | null>(null);
  const [progressByRelationship, setProgressByRelationship] = useState<Record<string, WorkoutSetLog[]>>({});
  const [sessionsByRelationship, setSessionsByRelationship] = useState<Record<string, WorkoutSession[]>>({});
  const [progressLoadingFor, setProgressLoadingFor] = useState<string | null>(null);
  const [progressErrorFor, setProgressErrorFor] = useState<string | null>(null);

  useEffect(() => {
    getRoutineAssignments()
      .then((items) => {
        setStudents(items);
        setSelectedRoutines(Object.fromEntries(items.map((item) => [item.relationship_id, item.routine_template_id ?? ''])));
      })
      .catch(() => setError('No pudimos cargar tus alumnos activos. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

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
        const [logs, sessions] = await Promise.all([
          getTrainerStudentWorkoutLogs(relationshipId),
          getTrainerStudentWorkoutSessions(relationshipId).catch(() => []),
        ]);
        if (!cancelled) {
          setProgressByRelationship((current) => ({ ...current, [relationshipId]: logs }));
          setSessionsByRelationship((current) => ({ ...current, [relationshipId]: sessions }));
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
              <strong>{student.student_name}</strong>
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
              {student.routine_template_id && (
                <Link className="profile-save" to={ROUTES.trainerStudentRoutine.replace(':studentId', student.student_id)}>
                  Editar rutina
                </Link>
              )}
              {student.routine_template_id && <>
                <button
                  type="button"
                  className="profile-save routine-assignment__progress-toggle"
                  aria-expanded={openProgressFor === student.relationship_id}
                  onClick={() => setOpenProgressFor((current) => current === student.relationship_id ? null : student.relationship_id)}
                >
                  {openProgressFor === student.relationship_id ? 'Ocultar progreso' : 'Ver progreso del alumno'}
                </button>
                {openProgressFor === student.relationship_id && <div className="routine-assignment__progress" aria-label={`Progreso de ${student.student_name}`}>
                  <div className="routine-assignment__progress-heading">
                    <strong>Sesiones y Esfuerzo (RPE)</strong>
                    <span>{progressLoadingFor === student.relationship_id ? 'Actualizando…' : 'Actualización automática'}</span>
                  </div>
                  {(sessionsByRelationship[student.relationship_id] ?? []).length === 0 ? (
                    <p className="plan-empty" style={{ margin: '0 0 16px' }}>Todavía no hay sesiones finalizadas.</p>
                  ) : (
                    <ul className="routine-assignment__sessions-list" style={{ margin: '0 0 16px' }}>
                      {(sessionsByRelationship[student.relationship_id] ?? []).slice(0, 5).map((session) => (
                        <li key={session.id} className="routine-assignment__session-item">
                          <strong>{session.day_name}</strong>
                          <time dateTime={session.started_at}>{new Date(session.started_at).toLocaleDateString('es-AR')}</time>
                          {session.rpe !== null && session.rpe !== undefined ? (
                            <span className="routine-assignment__rpe-badge routine-assignment__rpe-badge--reported">
                              RPE: {session.rpe}/10
                            </span>
                          ) : (
                            <span className="routine-assignment__rpe-badge routine-assignment__rpe-badge--unreported">
                              Sin reporte de RPE
                            </span>
                          )}
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
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="routine-assignment__progress-heading">
                    <strong>Series registradas</strong>
                  </div>
                  {progressErrorFor === student.relationship_id ? (
                    <p className="form-alert" role="alert">No pudimos cargar el progreso. Seguiremos intentando actualizarlo.</p>
                  ) : (progressByRelationship[student.relationship_id] ?? []).length === 0 ? (
                    <p className="plan-empty">Todavía no hay series registradas para esta rutina.</p>
                  ) : (
                    <ul>
                      {(progressByRelationship[student.relationship_id] ?? []).slice(0, 12).map((log) => (
                        <li key={log.id}>
                          <strong>{log.exercise_name}</strong>
                          <time dateTime={log.recorded_at}>{new Date(log.recorded_at).toLocaleDateString('es-AR')}</time>
                          <span>{log.day_name} · Serie {log.set_number} · {log.reps_completed} reps · {log.weight_kg === null || log.weight_kg === 0 ? 'Peso corporal (0 kg)' : `${log.weight_kg} kg`}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>}
              </>}
            </div>
          ))}
        </div>
      )}
      {error && students.length > 0 && <p className="form-alert" role="alert">{error}</p>}
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
