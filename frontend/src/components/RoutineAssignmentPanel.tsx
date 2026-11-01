import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { assignRoutineToStudent, getRoutineAssignments } from '../services/routineTemplateService';
import type { RoutineAssignmentStudent, RoutineTemplate } from '../types/routineTemplate';

interface RoutineAssignmentPanelProps {
  templates: RoutineTemplate[];
}

export function RoutineAssignmentPanel({ templates }: RoutineAssignmentPanelProps) {
  const [students, setStudents] = useState<RoutineAssignmentStudent[]>([]);
  const [selectedRoutines, setSelectedRoutines] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    getRoutineAssignments()
      .then((items) => {
        setStudents(items);
        setSelectedRoutines(Object.fromEntries(items.map((item) => [item.relationship_id, item.routine_template_id ?? ''])));
      })
      .catch(() => setError('No pudimos cargar tus alumnos activos. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  async function saveAssignment(student: RoutineAssignmentStudent) {
    setSavingId(student.relationship_id);
    setError('');
    setMessage('');
    setWarnings([]);
    try {
      const routineTemplateId = selectedRoutines[student.relationship_id] || null;
      const conflicts = await assignRoutineToStudent(student.relationship_id, routineTemplateId);
      setWarnings(conflicts);
      const routine = templates.find((item) => item.id === routineTemplateId);
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
                  {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                </select>
              </label>
              <button
                type="button"
                className="profile-save"
                onClick={() => void saveAssignment(student)}
                disabled={savingId === student.relationship_id}
              >
                {savingId === student.relationship_id ? 'Guardando…' : 'Guardar asignación'}
              </button>
              {student.routine_template_id && (
                <Link className="profile-save" to={ROUTES.trainerStudentRoutine.replace(':studentId', student.student_id)}>
                  Editar rutina
                </Link>
              )}
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
