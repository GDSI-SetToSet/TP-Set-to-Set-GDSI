import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RoutineAssignmentPanel } from '../components/RoutineAssignmentPanel';
import { ROUTES } from '../constants/routes';
import { getRoutineTemplates } from '../services/routineTemplateService';
import type { RoutineTemplate } from '../types/routineTemplate';

export function TrainerStudentsPage() {
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getRoutineTemplates()
      .then(setTemplates)
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
        {error && <p className="form-alert" role="alert">{error}</p>}
        {!error && <RoutineAssignmentPanel templates={templates} />}
      </section>
    </main>
  );
}
