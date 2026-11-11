import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import {
  approveAssignedRoutine,
  generateAIRoutine,
  getActiveStudents,
  getAssignedRoutine,
  getTrainerAIRoutines,
  updateAssignedRoutine,
} from '../services/assignedRoutineService';
import { getApiErrorInfo } from '../services/errorMessage';
import { getExercises } from '../services/exerciseService';
import { getRoutineTemplates } from '../services/routineTemplateService';
import type {
  ActiveStudent,
  AssignedRoutine,
  AssignedRoutineExerciseUpdate,
  AssignedRoutineUpdatePayload,
} from '../types/assignedRoutine';
import type { Exercise } from '../types/exercise';
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
  const state = location.state as { from?: string; editRoutineId?: string } | null;
  const cameFromRoutines = state?.from === 'routines';
  const initialEditRoutineId = state?.editRoutineId;

  const [students, setStudents] = useState<ActiveStudent[]>([]);
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);

  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState<number | undefined>(undefined);
  const [canFallbackHeuristic, setCanFallbackHeuristic] = useState(false);
  const [proposal, setProposal] = useState<AssignedRoutine | null>(null);
  const [savedRoutines, setSavedRoutines] = useState<AssignedRoutine[]>([]);
  const [approvedSuccess, setApprovedSuccess] = useState(false);

  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<AssignedRoutineUpdatePayload | null>(null);
  const [editSuccess, setEditSuccess] = useState('');
  const [editError, setEditError] = useState('');

  function initEditForm(routine: AssignedRoutine) {
    setEditForm({
      name: routine.name,
      duration_weeks: routine.duration_weeks,
      intensity: routine.intensity,
      has_no_materials_alternative: routine.has_no_materials_alternative,
      days: routine.days.map((day) => ({
        name: day.name,
        blocks: day.blocks.map((block) => ({
          name: block.name,
          estimated_duration_minutes: block.estimated_duration_minutes ?? null,
          exercises: block.exercises.map((item) => ({
            exercise_id: item.exercise.id,
            sets: item.sets,
            reps: item.reps,
            rest_seconds: item.rest_seconds,
            adaptation_notes: item.adaptation_notes ?? '',
            target_weight_kg: item.target_weight_kg ?? null,
          })),
        })),
      })),
    });
    setIsEditing(true);
    setEditError('');
    setEditSuccess('');
  }

  useEffect(() => {
    Promise.all([getActiveStudents(), getRoutineTemplates(), getTrainerAIRoutines(), getExercises()])
      .then(([studentsData, templatesData, savedData, exercisesData]) => {
        setStudents(studentsData);
        setTemplates(templatesData);
        setSavedRoutines(savedData);
        setLibrary(exercisesData);
        if (studentsData.length > 0) setSelectedStudentId(studentsData[0].student_id);
        if (templatesData.length > 0) setSelectedTemplateId(templatesData[0].id);

        if (initialEditRoutineId) {
          const found = savedData.find((r) => r.id === initialEditRoutineId);
          if (found) {
            setProposal(found);
            setSelectedStudentId(found.student_id);
            if (found.template_id) setSelectedTemplateId(found.template_id);
            initEditForm(found);
          } else {
            getAssignedRoutine(initialEditRoutineId)
              .then((routine) => {
                setProposal(routine);
                setSelectedStudentId(routine.student_id);
                if (routine.template_id) setSelectedTemplateId(routine.template_id);
                initEditForm(routine);
              })
              .catch(() => setError('No pudimos cargar la rutina para editar.'));
          }
        }
      })
      .catch(() => {
        setError('No pudimos cargar los alumnos o rutinas. Intentá nuevamente.');
        setErrorStatus(undefined);
        setCanFallbackHeuristic(false);
      })
      .finally(() => setLoadingInitial(false));
  }, [initialEditRoutineId]);

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
    setIsEditing(false);
    setEditSuccess('');
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
    setIsEditing(false);
    setEditForm(null);
    setEditSuccess('');
    setEditError('');
  }

  function handleCancelEdit() {
    setIsEditing(false);
    setEditError('');
  }

  function updateExercise(
    dayIdx: number,
    blockIdx: number,
    exIdx: number,
    field: keyof AssignedRoutineExerciseUpdate,
    value: string | number | null,
  ) {
    setEditForm((current) => {
      if (!current) return current;
      const nextDays = [...current.days];
      const targetDay = { ...nextDays[dayIdx] };
      const nextBlocks = [...targetDay.blocks];
      const targetBlock = { ...nextBlocks[blockIdx] };
      const nextExercises = [...targetBlock.exercises];
      nextExercises[exIdx] = {
        ...nextExercises[exIdx],
        [field]: value,
      };
      targetBlock.exercises = nextExercises;
      nextBlocks[blockIdx] = targetBlock;
      targetDay.blocks = nextBlocks;
      nextDays[dayIdx] = targetDay;
      return { ...current, days: nextDays };
    });
  }

  function addExerciseToBlock(dayIdx: number, blockIdx: number) {
    if (!editForm || library.length === 0) return;
    const defaultExercise = library[0];
    setEditForm((current) => {
      if (!current) return current;
      const nextDays = [...current.days];
      const targetDay = { ...nextDays[dayIdx] };
      const nextBlocks = [...targetDay.blocks];
      const targetBlock = { ...nextBlocks[blockIdx] };
      targetBlock.exercises = [
        ...targetBlock.exercises,
        {
          exercise_id: defaultExercise.id,
          sets: 3,
          reps: '10',
          rest_seconds: 60,
          target_weight_kg: null,
          adaptation_notes: '',
        },
      ];
      nextBlocks[blockIdx] = targetBlock;
      targetDay.blocks = nextBlocks;
      nextDays[dayIdx] = targetDay;
      return { ...current, days: nextDays };
    });
  }

  function removeExerciseFromBlock(dayIdx: number, blockIdx: number, exIdx: number) {
    setEditForm((current) => {
      if (!current) return current;
      const nextDays = [...current.days];
      const targetDay = { ...nextDays[dayIdx] };
      const nextBlocks = [...targetDay.blocks];
      const targetBlock = { ...nextBlocks[blockIdx] };
      targetBlock.exercises = targetBlock.exercises.filter((_, idx) => idx !== exIdx);
      nextBlocks[blockIdx] = targetBlock;
      targetDay.blocks = nextBlocks;
      nextDays[dayIdx] = targetDay;
      return { ...current, days: nextDays };
    });
  }

  async function handleSaveEdit() {
    if (!proposal || !editForm || savingEdit) return;
    setSavingEdit(true);
    setEditError('');
    setEditSuccess('');
    try {
      const updated = await updateAssignedRoutine(proposal.id, editForm);
      setProposal(updated);
      setSavedRoutines((current) => current.map((r) => (r.id === updated.id ? updated : r)));
      setIsEditing(false);
      setEditSuccess('¡Rutina actualizada correctamente!');
    } catch (err: unknown) {
      const info = getApiErrorInfo(err, 'No se pudieron guardar las modificaciones.');
      setEditError(info.message);
    } finally {
      setSavingEdit(false);
    }
  }

  if (loadingInitial) {
    return (
      <main className="loading-screen">
        <span className="loading-mark" /> Cargando datos de entrenamiento…
      </main>
    );
  }

  return (
    <main className="profile-shell profile-shell--trainer">
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
            alumno usando IA. Como entrenador, tenés la supervisión y edición final obligatoria.
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

        {editSuccess && (
          <div className="ai-success-banner" role="status">
            <CheckCircle2 size={24} />
            <div>
              <strong>{editSuccess}</strong>
              <p>Las modificaciones manuales fueron guardadas y no consumieron cuotas de IA.</p>
            </div>
          </div>
        )}

        {editError && (
          <div className="form-alert ai-error-panel" role="alert">
            <div className="ai-error-header">
              <AlertTriangle size={20} />
              <strong>No se pudieron guardar los cambios</strong>
            </div>
            <p style={{ margin: '6px 0 0' }}>{editError}</p>
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

            <div className="ai-generate-actions">
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
            <div className="ai-proposal-toolbar">
              <div className="ai-proposal-status">
                <span className="ai-proposal-badge">
                  <Sparkles size={15} /> Generada mediante IA
                </span>
                <span className={`ai-proposal-badge ${proposal.status === 'APPROVED' ? 'ai-proposal-badge--approved' : 'ai-proposal-badge--review'}`}>
                  {proposal.status === 'APPROVED' ? (
                    <>
                      <CheckCircle2 size={16} /> Rutina Aprobada y Asignada
                    </>
                  ) : (
                    <>
                      <Clock size={16} /> Propuesta en Revisión (Supervisión Humana)
                    </>
                  )}
                </span>
              </div>
              <div className="ai-proposal-actions">
                {!isEditing && (
                  <button
                    type="button"
                    className="plan-action-btn"
                    onClick={() => initEditForm(proposal)}
                    disabled={approving}
                  >
                    <Pencil size={16} /> Editar rutina
                  </button>
                )}
                <button
                  type="button"
                  className="plan-action-btn"
                  onClick={handleReset}
                  disabled={approving || savingEdit}
                >
                  Generar otra rutina
                </button>
              </div>
            </div>

            {isEditing && editForm ? (
              <div className="ai-edit-form">
                <h3>Editar rutina manualmente</h3>
                <p className="ai-edit-description">
                  Ajustá series, repeticiones (ej. "8-12", "30s"), descansos, pesos o intercambiá ejercicios. Guardar cambios no invoca la IA.
                </p>

                <div className="ai-edit-settings">
                  <label className="ai-edit-field">
                    Nombre de la rutina
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      maxLength={150}
                    />
                  </label>
                  <label className="ai-edit-field">
                    Duración (semanas)
                    <input
                      type="number"
                      min={1}
                      max={52}
                      value={editForm.duration_weeks}
                      onChange={(e) => setEditForm({ ...editForm, duration_weeks: Number(e.target.value) || 1 })}
                    />
                  </label>
                  <label className="ai-edit-field">
                    Intensidad
                    <select
                      value={editForm.intensity}
                      onChange={(e) => setEditForm({ ...editForm, intensity: e.target.value })}
                    >
                      <option value="BAJA">BAJA</option>
                      <option value="MEDIA">MEDIA</option>
                      <option value="ALTA">ALTA</option>
                    </select>
                  </label>
                </div>

                <div className="ai-edit-days">
                  {editForm.days.map((day, dayIdx) => (
                    <div key={`day-${dayIdx}`} className="ai-edit-day">
                      <div className="ai-edit-day-heading">
                        <label className="ai-edit-day-name">
                          Día {dayIdx + 1}:
                          <input
                            type="text"
                            value={day.name}
                            onChange={(e) => {
                              const nextDays = [...editForm.days];
                              nextDays[dayIdx] = { ...nextDays[dayIdx], name: e.target.value };
                              setEditForm({ ...editForm, days: nextDays });
                            }}
                          />
                        </label>
                      </div>

                      {day.blocks.map((block, blockIdx) => (
                        <div key={`block-${dayIdx}-${blockIdx}`} className="ai-edit-block">
                          <label className="ai-edit-block-name">
                            Bloque:
                            <input
                              type="text"
                              value={block.name}
                              onChange={(e) => {
                                const nextDays = [...editForm.days];
                                const targetDay = { ...nextDays[dayIdx] };
                                const nextBlocks = [...targetDay.blocks];
                                nextBlocks[blockIdx] = { ...nextBlocks[blockIdx], name: e.target.value };
                                targetDay.blocks = nextBlocks;
                                nextDays[dayIdx] = targetDay;
                                setEditForm({ ...editForm, days: nextDays });
                              }}
                            />
                          </label>

                          <div className="ai-edit-exercises">
                            {block.exercises.map((item, exIdx) => (
                              <div key={`ex-${dayIdx}-${blockIdx}-${exIdx}`} className="ai-edit-exercise-row">
                                <label>
                                  Ejercicio
                                  <select
                                    value={item.exercise_id}
                                    onChange={(e) => updateExercise(dayIdx, blockIdx, exIdx, 'exercise_id', e.target.value)}
                                  >
                                    {library.map((ex) => (
                                      <option key={ex.id} value={ex.id}>
                                        {ex.name} ({ex.target_muscle_group})
                                      </option>
                                    ))}
                                  </select>
                                </label>
                                <label>
                                  Series
                                  <input
                                    type="number"
                                    min={1}
                                    max={20}
                                    value={item.sets}
                                    onChange={(e) => updateExercise(dayIdx, blockIdx, exIdx, 'sets', Number(e.target.value) || 1)}
                                  />
                                </label>
                                <label>
                                  Repeticiones
                                  <input
                                    type="text"
                                    value={item.reps}
                                    placeholder="8-12, 30s"
                                    onChange={(e) => updateExercise(dayIdx, blockIdx, exIdx, 'reps', e.target.value)}
                                  />
                                </label>
                                <label>
                                  Descanso (s)
                                  <input
                                    type="number"
                                    min={0}
                                    max={600}
                                    value={item.rest_seconds}
                                    onChange={(e) => updateExercise(dayIdx, blockIdx, exIdx, 'rest_seconds', Number(e.target.value) || 0)}
                                  />
                                </label>
                                <label>
                                  Peso (kg)
                                  <input
                                    type="number"
                                    step="0.5"
                                    min={0}
                                    placeholder="Opcional"
                                    value={item.target_weight_kg ?? ''}
                                    onChange={(e) => {
                                      const val = e.target.value.trim();
                                      updateExercise(dayIdx, blockIdx, exIdx, 'target_weight_kg', val === '' ? null : Number(val));
                                    }}
                                  />
                                </label>
                                <label>
                                  Notas de adaptación
                                  <input
                                    type="text"
                                    placeholder="Opcional"
                                    value={item.adaptation_notes ?? ''}
                                    onChange={(e) => updateExercise(dayIdx, blockIdx, exIdx, 'adaptation_notes', e.target.value)}
                                  />
                                </label>
                                {block.exercises.length > 1 && (
                                  <button
                                    type="button"
                                    className="ai-edit-exercise-remove"
                                    title="Quitar ejercicio"
                                    onClick={() => removeExerciseFromBlock(dayIdx, blockIdx, exIdx)}
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>

                          <div className="ai-edit-add-exercise">
                            <button
                              type="button"
                              className="plan-action-btn"
                              onClick={() => addExerciseToBlock(dayIdx, blockIdx)}
                            >
                              <Plus size={14} /> Agregar ejercicio al bloque
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>

                <div className="ai-edit-actions">
                  <button
                    type="button"
                    className="ai-approve-btn"
                    onClick={handleSaveEdit}
                    disabled={savingEdit}
                  >
                    <Save size={18} /> {savingEdit ? 'Guardando modificaciones…' : 'Guardar cambios'}
                  </button>
                  <button
                    type="button"
                    className="plan-action-btn"
                    onClick={handleCancelEdit}
                    disabled={savingEdit}
                  >
                    <X size={18} /> Cancelar edición
                  </button>
                </div>
              </div>
            ) : (
              <>
                <h2>{proposal.name}</h2>
                <div className="ai-proposal-metrics">
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
                  <div className="ai-summary-section">
                    <h3 className="ai-summary-title">
                      Resumen de adaptaciones y decisiones biomecánicas de la IA:
                    </h3>
                    <div className="ai-summary-box">{proposal.adaptation_summary}</div>
                  </div>
                )}

                <div className="ai-routine-preview">
                  <h3 className="ai-routine-preview-heading">Estructura de la rutina</h3>
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
                                {item.target_weight_kg != null && (
                                  <span>
                                    <strong>Peso objetivo:</strong> {item.target_weight_kg} kg
                                  </span>
                                )}
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
              </>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
