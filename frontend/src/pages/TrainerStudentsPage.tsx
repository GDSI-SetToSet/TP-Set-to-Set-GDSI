import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RoutineAssignmentPanel } from '../components/RoutineAssignmentPanel';
import { ROUTES } from '../constants/routes';
import { getTrainerAIRoutines } from '../services/assignedRoutineService';
import { getRoutineTemplates } from '../services/routineTemplateService';
import type { TrainerAIRoutine } from '../types/assignedRoutine';
import type { RoutineTemplate } from '../types/routineTemplate';

export function TrainerStudentsPage() {
  const [searchParams] = useSearchParams();
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [aiRoutines, setAIRoutines] = useState<TrainerAIRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
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
          <p>Consultá tus vínculos activos y asigná a cada alumno la rutina que va a ver en “Rutina del día”.</p>
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
          />
        )}
      </section>
    </main>
  );
}
