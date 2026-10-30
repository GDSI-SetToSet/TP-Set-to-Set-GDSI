import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { RoutineTemplateCard } from '../components/RoutineTemplateCard';
import { ROUTES } from '../constants/routes';
import { getStudentRoutineTemplates } from '../services/routineTemplateService';
import type { RoutineTemplate } from '../types/routineTemplate';

export function StudentRoutinesPage() {
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getStudentRoutineTemplates()
      .then(setTemplates)
      .catch(() => setError('No pudimos cargar las rutinas. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando rutinas…</main>;

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Rutinas de tus entrenadores</h1>
          <p>Consultá las rutinas genéricas de los entrenadores con los que tenés un vínculo activo.</p>
        </div>
        {error && <p className="form-alert" role="alert">{error}</p>}
      </section>

      <section className="plan-list" aria-label="Rutinas disponibles">
        {templates.length === 0 && !error
          ? <p className="plan-empty">Todavía no hay rutinas disponibles.</p>
          : templates.map((template) => <RoutineTemplateCard key={template.id} template={template} />)}
      </section>
    </main>
  );
}
