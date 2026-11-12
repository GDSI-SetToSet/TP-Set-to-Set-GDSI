import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RoutineAssignmentPanel } from '../components/RoutineAssignmentPanel';
import { TrainerStudentDetail } from '../components/TrainerStudentDetail';
import { ROUTES } from '../constants/routes';
import { getTrainerAIRoutines } from '../services/assignedRoutineService';
import { getRoutineTemplates } from '../services/routineTemplateService';
import { getTrainerStudentDetail } from '../services/trainerStudentService';
import type { TrainerStudentDetail as TrainerStudentDetailModel } from '../types/trainerStudent';
import type { TrainerAIRoutine } from '../types/assignedRoutine';
import type { RoutineTemplate } from '../types/routineTemplate';

export function TrainerStudentsPage() {
  const [searchParams] = useSearchParams();
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [aiRoutines, setAIRoutines] = useState<TrainerAIRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<TrainerStudentDetailModel | null>(null);
  const [detailStudentId, setDetailStudentId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const routineStatus = searchParams.get('routineStatus');

  useEffect(() => {
    Promise.all([getRoutineTemplates(), getTrainerAIRoutines()])
      .then(([loadedTemplates, loadedAIRoutines]) => {
        setTemplates(loadedTemplates);
        setAIRoutines(loadedAIRoutines);
      })
      .catch(() => setError('No pudimos cargar tus rutinas. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  function selectStudent(studentId: string) {
    if (selectedStudentId === studentId) {
      setSelectedStudentId(null);
      return;
    }
    setSelectedStudentId(studentId);
    if (detailStudentId === studentId && studentDetail) {
      setDetailError('');
      return;
    }
    setStudentDetail(null);
    setDetailError('');
    setDetailLoading(true);
    getTrainerStudentDetail(studentId)
      .then((detail) => {
        setStudentDetail(detail);
        setDetailStudentId(studentId);
      })
      .catch(() => setDetailError('No pudimos cargar el detalle de este alumno. Intentá nuevamente.'))
      .finally(() => setDetailLoading(false));
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando alumnos…</main>;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card routine-students-card">
        <div className="profile-heading">
          <span>ALUMNOS</span>
          <h1>Mis alumnos</h1>
          <p>Consultá tus alumnos activos, sus rutinas y su progreso.</p>
        </div>
        {routineStatus === 'missing' && (
          <p className="form-alert" role="status">Este alumno todavía no tiene una rutina asignada para revisar.</p>
        )}
        {routineStatus === 'unavailable' && (
          <p className="form-alert" role="status">No pudimos comprobar si este alumno tiene una rutina asignada. Revisá sus datos en esta sección.</p>
        )}
        {error && <p className="form-alert" role="alert">{error}</p>}
        {!error && (
          <RoutineAssignmentPanel
            templates={templates}
            aiRoutines={aiRoutines}
            initialStudentId={searchParams.get('studentId') ?? undefined}
            initialSessionId={searchParams.get('sessionId') ?? undefined}
            initialEventId={searchParams.get('eventId') ?? undefined}
            initialEventType={searchParams.get('eventType') ?? undefined}
            onStudentSelect={selectStudent}
            selectedStudentId={selectedStudentId}
          />
        )}
        {selectedStudentId && (
          <div id={`student-detail-${selectedStudentId}`} className="trainer-student-detail-container">
            {detailLoading && <p role="status">Cargando detalle del alumno…</p>}
            {detailError && <p className="form-alert" role="alert">{detailError}</p>}
            {studentDetail && <TrainerStudentDetail detail={studentDetail} onClose={() => setSelectedStudentId(null)} />}
          </div>
        )}
      </section>
    </main>
  );
}
