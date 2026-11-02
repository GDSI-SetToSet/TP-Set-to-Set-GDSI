import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import {
  approveAssignedRoutine,
  generateAIRoutine,
  getActiveStudents,
  getTrainerAIRoutines,
} from '../services/assignedRoutineService';
import { getApiErrorInfo } from '../services/errorMessage';
import { getRoutineTemplates } from '../services/routineTemplateService';
import type {
  ActiveStudent,
  AssignedRoutine,
} from '../types/assignedRoutine';
import type { RoutineTemplate } from '../types/routineTemplate';

function getErrorHeading(status?: number, message?: string): string {
  const lower = (message ?? '').toLowerCase();
  if (status === 503 || lower.includes('no está configurado') || lower.includes('gemini_api_key')) {
    return 'Google Gemini no está configurado';
  }
  if (status === 429 || lower.includes('cuota')) {
    return 'Cuota gratuita de Google Gemini agotada';
  }
  if (status === 504 || lower.includes('tiempo de espera')) {
    return 'Tiempo de espera agotado al consultar Google Gemini';
  }
  return 'No se pudo generar la propuesta con IA';
}

export function GenerateAIRoutinePage() {
  const location = useLocation();
  const cameFromRoutines = (location.state as { from?: string } | null)?.from === 'routines';
  const [students, setStudents] = useState<ActiveStudent[]>([]);
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);

  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState<number | undefined>(undefined);
  const [canFallbackHeuristic, setCanFallbackHeuristic] = useState(false);
  const [proposal, setProposal] = useState<AssignedRoutine | null>(null);
  const [savedRoutines, setSavedRoutines] = useState<AssignedRoutine[]>([]);
  const [approvedSuccess, setApprovedSuccess] = useState(false);

  useEffect(() => {
    Promise.all([getActiveStudents(), getRoutineTemplates(), getTrainerAIRoutines()])
      .then(([studentsData, templatesData, savedData]) => {
        setStudents(studentsData);
        setTemplates(templatesData);
        setSavedRoutines(savedData);
        if (studentsData.length > 0) setSelectedStudentId(studentsData[0].student_id);
        if (templatesData.length > 0) setSelectedTemplateId(templatesData[0].id);
      })
      .catch(() => {
        setError('No pudimos cargar los alumnos o rutinas. Intentá nuevamente.');
        setErrorStatus(undefined);
        setCanFallbackHeuristic(false);
      })
      .finally(() => setLoadingInitial(false));
  }, []);

  const selectedStudent = students.find((s) => s.student_id === selectedStudentId);
  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);
  // El listado viene de la más reciente a la más antigua.
  const savedForSelection = savedRoutines.find(
    (r) => r.student_id === selectedStudentId && r.template_id === selectedTemplateId,
  );

  async function handleGenerateProposal(providerOverride?: 'gemini' | 'heuristic') {
    if (!selectedStudentId || !selectedTemplateId || generating) return;
    setGenerating(true);
    setError('');
    setErrorStatus(undefined);
    setCanFallbackHeuristic(false);
    setApprovedSuccess(false);
    try {
      const result = await generateAIRoutine({
        student_id: selectedStudentId,
        template_id: selectedTemplateId,
        ...(providerOverride ? { provider: providerOverride } : {}),
      });
      setProposal(result);
      setSavedRoutines((current) => [result, ...current]);
    } catch (err: unknown) {
      const info = getApiErrorInfo(err, 'Error al generar la propuesta con IA.');
      setError(info.message);
      setErrorStatus(info.status);
      setCanFallbackHeuristic(providerOverride !== 'heuristic');
    } finally {
      setGenerating(false);
    }
  }

  async function handleApprove() {
    if (!proposal || approving) return;
    setApproving(true);
    setError('');
    setErrorStatus(undefined);
    setCanFallbackHeuristic(false);
    try {
      const updated = await approveAssignedRoutine(proposal.id);
      setProposal(updated);
      setSavedRoutines((current) => current.map((r) => (r.id === updated.id ? updated : r)));
      setApprovedSuccess(true);
    } catch (err: unknown) {
      const info = getApiErrorInfo(err, 'Error al aprobar la rutina.');
      setError(info.message);
      setErrorStatus(info.status);
    } finally {
      setApproving(false);
    }
  }

  function handleReset() {
    setProposal(null);
    setApprovedSuccess(false);
    setError('');
    setErrorStatus(undefined);
    setCanFallbackHeuristic(false);
  }

  if (loadingInitial) {
    return (
      <main className="loading-screen">
        <span className="loading-mark" /> Cargando datos de entrenamiento…
      </main>
    );
  }

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={cameFromRoutines ? ROUTES.trainerRoutines : ROUTES.trainerHome} className="profile-back">
          <ArrowLeft size={18} /> {cameFromRoutines ? 'Volver a mis rutinas' : 'Volver al inicio'}
        </Link>
      </header>

      <section className="profile-card ai-routine-container">
        <div className="profile-heading">
          <h1>Generar rutina particular para un alumno</h1>
          <p>
            Adaptá una de tus rutinas genéricas a los objetivos y limitaciones específicas de tu
            alumno usando IA. Como entrenador, tenés la supervisión y aprobación final obligatoria.
          </p>
        </div>

        {error && (
          <div className="form-alert ai-error-panel" role="alert">
            <div className="ai-error-header">
              <AlertTriangle size={20} />
              <strong>{getErrorHeading(errorStatus, error)}</strong>
            </div>
            <p style={{ margin: '6px 0 0' }}>{error}</p>
            {canFallbackHeuristic && !proposal && (
              <div className="ai-error-actions">
                <button
                  type="button"
                  className="plan-action-btn"
                  onClick={() => handleGenerateProposal()}
                  disabled={generating}
                >
                  <RefreshCw size={16} /> Reintentar con proveedor configurado
                </button>
                <button
                  type="button"
                  className="plan-action-btn ai-fallback-btn"
                  onClick={() => handleGenerateProposal('heuristic')}
                  disabled={generating}
                >
                  <Sparkles size={16} /> Usar adaptador heurístico explícitamente
                </button>
              </div>
            )}
          </div>
        )}

        {approvedSuccess && (
          <div className="ai-success-banner" role="status">
            <CheckCircle2 size={24} />
            <div>
              <strong>¡Rutina aprobada y asignada exitosamente!</strong>
              <p>
                Tu alumno ya tiene disponible su rutina personalizada en su espacio de entrenamiento.
                También quedó guardada en <Link to={ROUTES.trainerRoutines}>Mis rutinas</Link>.
              </p>
            </div>
          </div>
        )}

        {!proposal ? (
          <div>
            <div className="ai-routine-selector-grid">
              <div className="ai-routine-selector-card">
                <label htmlFor="student-selector">1. Seleccioná el alumno activo</label>
                {students.length === 0 ? (
                  <p className="ai-student-meta">No tenés alumnos con vínculo activo actualmente.</p>
                ) : (
                  <>
                    <select
                      id="student-selector"
                      value={selectedStudentId}
                      onChange={(e) => setSelectedStudentId(e.target.value)}
                      disabled={generating}
                    >
                      {students.map((st) => (
                        <option key={st.student_id} value={st.student_id}>
                          {st.full_name} {st.age ? `(${st.age} años)` : ''}
                        </option>
                      ))}
                    </select>
                    {selectedStudent && (
                      <div className="ai-student-meta">
                        <div>
                          <strong>Objetivos:</strong>{' '}
                          {selectedStudent.fitness_goals.length > 0
                            ? selectedStudent.fitness_goals.join(', ')
                            : 'Generales'}
                        </div>
                        {selectedStudent.protected_zones_count > 0 && (
                          <div style={{ color: '#b45309', fontWeight: 600 }}>
                            ⚠️ {selectedStudent.protected_zones_count} zona(s) a proteger registrada(s)
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="ai-routine-selector-card">
                <label htmlFor="template-selector">2. Seleccioná la rutina base de tu biblioteca</label>
                {templates.length === 0 ? (
                  <p className="ai-student-meta">No tenés rutinas genéricas creadas en tu biblioteca.</p>
                ) : (
                  <>
                    <select
                      id="template-selector"
                      value={selectedTemplateId}
                      onChange={(e) => setSelectedTemplateId(e.target.value)}
                      disabled={generating}
                    >
                      {templates.map((tpl) => (
                        <option key={tpl.id} value={tpl.id}>
                          {tpl.name} ({tpl.intensity} - {tpl.duration_weeks} sem.)
                        </option>
                      ))}
                    </select>
                    {selectedTemplate && (
                      <div className="ai-student-meta">
                        <div>
                          <strong>Intensidad base:</strong> {selectedTemplate.intensity}
                        </div>
                        <div>
                          <strong>Ejercicios totales:</strong> {selectedTemplate.exercise_count}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {savedForSelection && (
              <div className="ai-saved-notice" role="status">
                <p>
                  Ya generaste <strong>{savedForSelection.name}</strong> para este alumno con esta rutina base.
                </p>
                <button
                  type="button"
                  className="plan-action-btn"
                  onClick={() => setProposal(savedForSelection)}
                  disabled={generating}
                >
                  Abrir la rutina guardada
                </button>
              </div>
            )}

            <div style={{ marginTop: '24px' }}>
              <button
                type="button"
                className="profile-cta"
                onClick={() => handleGenerateProposal()}
                disabled={generating || students.length === 0 || templates.length === 0}
              >
                {generating ? (
                  <>
                    <RefreshCw size={18} className="spin-icon" /> Analizando perfil y generando propuesta con IA…
                  </>
                ) : (
                  <>
                    <Sparkles size={18} /> Generar propuesta de rutina con IA
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="ai-proposal-banner">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="ai-proposal-badge">
                  <Sparkles size={15} /> Generada mediante IA
                </span>
                <span className="ai-proposal-badge" style={{ background: proposal.status === 'APPROVED' ? '#16a34a' : '#4f46e5' }}>
                  {proposal.status === 'APPROVED' ? (
                    <>
                      <CheckCircle2 size={16} /> Rutina Aprobada y Asignada
                    </>
                  ) : (
                    <>
                      <Clock size={16} /> Propuesta en Revisión (Human-in-the-Loop)
                    </>
                  )}
                </span>
              </div>
              <button
                type="button"
                className="plan-action-btn"
                onClick={handleReset}
                disabled={approving}
              >
                Generar otra rutina
              </button>
            </div>

            <h2>{proposal.name}</h2>
            <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: 'var(--pf-body)', flexWrap: 'wrap' }}>
              <span>
                <strong>Intensidad:</strong> {proposal.intensity}
              </span>
              <span>
                <strong>Duración:</strong> {proposal.duration_weeks} semanas
              </span>
              <span>
                <strong>Ejercicios:</strong> {proposal.exercise_count}
              </span>
            </div>

            {proposal.adaptation_summary && (
              <div style={{ marginTop: '12px' }}>
                <h3 style={{ fontSize: '14px', margin: '0 0 6px', color: 'var(--pf-ink)' }}>
                  Resumen de adaptaciones y decisiones biomecánicas de la IA:
                </h3>
                <div className="ai-summary-box">{proposal.adaptation_summary}</div>
              </div>
            )}

            <div className="ai-routine-preview" style={{ marginTop: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '15px' }}>Estructura adaptada de la rutina</h3>
              {proposal.days.map((day) => (
                <div key={day.id} className="ai-day-card">
                  <h3>{day.name}</h3>
                  {day.blocks.map((block) => (
                    <div key={block.id} className="ai-block-card">
                      <h4>{block.name}</h4>
                      {block.exercises.map((item) => (
                        <div key={item.id} className="ai-exercise-item">
                          <div className="ai-exercise-header">
                            <strong>{item.exercise.name}</strong>
                            <div className="ai-exercise-tags">
                              <span className="ai-tag">{item.exercise.category}</span>
                              <span className="ai-tag">{item.exercise.target_muscle_group}</span>
                            </div>
                          </div>
                          <div className="ai-exercise-params">
                            <span>
                              <strong>Series:</strong> {item.sets}
                            </span>
                            <span>
                              <strong>Repeticiones:</strong> {item.reps}
                            </span>
                            <span>
                              <strong>Descanso:</strong> {item.rest_seconds}s
                            </span>
                          </div>
                          {item.adaptation_notes && (
                            <div className="ai-exercise-adaptation-note">
                              ℹ️ {item.adaptation_notes}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {proposal.status !== 'APPROVED' && (
              <div className="ai-approval-actions">
                <button
                  type="button"
                  className="ai-approve-btn"
                  onClick={handleApprove}
                  disabled={approving}
                >
                  <CheckCircle2 size={18} />
                  {approving ? 'Aprobando y asignando…' : 'Aprobar y asignar rutina al alumno'}
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
