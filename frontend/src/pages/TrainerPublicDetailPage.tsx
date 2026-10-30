import { ArrowLeft, Award, Users, DollarSign } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getTrainerPublicDetail } from '../services/discoveryService';
import type { TrainerPublicDetail } from '../types/discovery';
import '../styles/discovery.css';

export function TrainerPublicDetailPage() {
  const { trainerId } = useParams<{ trainerId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<TrainerPublicDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!trainerId) return;
    setLoading(true);
    getTrainerPublicDetail(trainerId)
      .then(setDetail)
      .catch(() => setError('No se pudo cargar el perfil del entrenador.'))
      .finally(() => setLoading(false));
  }, [trainerId]);

  if (loading) return <main className="discovery-shell"><p className="discovery-loading">Cargando perfil…</p></main>;
  if (error || !detail) return <main className="discovery-shell"><p className="form-alert" role="alert">{error || 'Perfil no encontrado.'}</p></main>;

  return (
    <main className="discovery-shell">
      <header className="discovery-header">
        <Link to={ROUTES.trainerSearch} className="back-link"><ArrowLeft size={16} /> Volver a búsqueda</Link>
        <h1>{detail.full_name ?? 'Entrenador'}</h1>
      </header>

      <section className="trainer-detail">
        <div className="trainer-detail__info">
          {detail.specialty && <span className="trainer-detail__specialty"><Award size={14} /> {detail.specialty}</span>}
          <span className={`trainer-detail__quota ${detail.has_available_quota ? 'available' : 'full'}`}>
            <Users size={14} /> {detail.has_available_quota ? `${detail.available_slots} cupos disponibles` : 'Sin cupos disponibles'}
          </span>
        </div>

        {detail.bio && <div className="trainer-detail__section"><h2>Sobre mí</h2><p>{detail.bio}</p></div>}
        {detail.certifications && <div className="trainer-detail__section"><h2>Certificaciones</h2><p>{detail.certifications}</p></div>}

        <div className="trainer-detail__section">
          <h2>Paquetes de entrenamiento</h2>
          {detail.plans.length === 0 ? (
            <p className="discovery-empty">Este entrenador no tiene paquetes activos.</p>
          ) : (
            <div className="plan-grid">
              {detail.plans.map(plan => (
                <div key={plan.id} className="plan-public-card">
                  <h3>{plan.title}</h3>
                  {plan.description && <p className="plan-public-card__desc">{plan.description}</p>}
                  <span className="plan-public-card__price"><DollarSign size={14} /> ${plan.monthly_price.toLocaleString('es-AR')} {plan.currency}/mes</span>
                  <button
                    className="plan-public-card__cta"
                    disabled={!detail.has_available_quota}
                    onClick={() => navigate(`/entrenadores/${trainerId}/solicitar?plan=${plan.id}`)}
                  >
                    {detail.has_available_quota ? 'Solicitar este plan' : 'Sin cupos'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
