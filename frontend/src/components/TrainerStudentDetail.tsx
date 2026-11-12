import { Activity, CalendarDays, ChevronUp, Dumbbell, Package, ShieldAlert, Target, UserRound } from 'lucide-react';
import type { TrainerStudentDetail as TrainerStudentDetailModel } from '../types/trainerStudent';
import { PainReportAnalysis } from './PainReportAnalysis';

interface TrainerStudentDetailProps {
  detail: TrainerStudentDetailModel;
  onClose: () => void;
}

function formatDate(value: string | null): string {
  if (!value) return 'Sin datos';
  return new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' }).format(new Date(value));
}

function translateProtectedZone(zone: string): string {
  const translations: Record<string, string> = {
    knee: 'Rodilla',
    elbow: 'Codo',
    'wrist and hand': 'Muñeca y mano',
  };
  return translations[zone.trim().toLowerCase()] ?? zone;
}

function translateStatus(status: string): string {
  return { PUBLISHED: 'Publicado', DRAFT: 'Borrador' }[status] ?? status;
}

export function TrainerStudentDetail({ detail, onClose }: TrainerStudentDetailProps) {
  const fullName = [detail.profile.first_name, detail.profile.last_name].filter(Boolean).join(' ') || 'Alumno';
  return (
    <section className="trainer-student-detail" aria-labelledby="trainer-student-detail-title">
      <div className="trainer-student-detail__heading">
        <div>
          <span>DETALLE DEL ALUMNO</span>
          <h2 id="trainer-student-detail-title">{fullName}</h2>
        </div>
        <button type="button" className="trainer-student-detail__close" onClick={onClose}>
          <ChevronUp size={17} aria-hidden="true" />
          Ocultar detalles
        </button>
        <p>Información del perfil, paquete contratado, objetivos, limitaciones, rutina y actividad.</p>
      </div>

      <div className="trainer-student-detail__grid">
        <article>
          <h3><UserRound size={18} aria-hidden="true" />Perfil</h3>
          <p>Estado: {translateStatus(detail.profile.status)}</p>
          <p><CalendarDays size={15} aria-hidden="true" /> Fecha de nacimiento: {formatDate(detail.profile.birth_date)}</p>
          <p>Contacto: {detail.profile.contact_phone || 'Sin datos'}</p>
          {detail.profile.bio && <p>{detail.profile.bio}</p>}
        </article>
        <article>
          <h3><Package size={18} aria-hidden="true" />Paquete contratado</h3>
          <p>{detail.relationship.package_title || 'Sin paquete informado'}</p>
          <p>{detail.relationship.agreed_monthly_price.toLocaleString('es-AR')} {detail.relationship.agreed_currency} por mes</p>
          <p><CalendarDays size={15} aria-hidden="true" /> Desde: {formatDate(detail.relationship.start_date)}</p>
        </article>
        <article>
          <h3><Target size={18} aria-hidden="true" />Objetivos</h3>
          {detail.goals.fitness_goals.length > 0
            ? <ul>{detail.goals.fitness_goals.map((goal) => <li key={goal}>{goal}</li>)}</ul>
            : <p>Sin objetivos cargados.</p>}
          {detail.goals.personal_motivation && <p>{detail.goals.personal_motivation}</p>}
        </article>
        <article>
          <h3><ShieldAlert size={18} aria-hidden="true" />Limitaciones</h3>
          {detail.limitations.protected_zones.length > 0
            ? <ul>{detail.limitations.protected_zones.map((zone) => <li key={zone}>{translateProtectedZone(zone)}</li>)}</ul>
            : <p>Sin zonas a proteger informadas.</p>}
        </article>
        <article>
          <h3><Dumbbell size={18} aria-hidden="true" />Rutina vigente</h3>
          <p>{detail.routine?.name || 'Sin rutina asignada.'}</p>
        </article>
        <article className="trainer-student-detail__metrics">
          <h3><Activity size={18} aria-hidden="true" />Métricas</h3>
          <div className="trainer-student-detail__metric-list">
            <div><strong>{detail.metrics.finished_sessions}</strong><span>Sesiones finalizadas</span></div>
            <div><strong>{detail.metrics.logged_sets}</strong><span>Series registradas</span></div>
            <div><strong>{detail.metrics.last_rpe ?? '—'}</strong><span>Último RPE</span></div>
          </div>
          <p>Última sesión: {formatDate(detail.metrics.last_session_at)}</p>
          <p>Tonelaje de la última sesión: {detail.metrics.last_tonnage_kg !== null ? `${detail.metrics.last_tonnage_kg} kg` : 'Sin datos'}</p>
        </article>
        <PainReportAnalysis studentId={detail.profile.id} />
      </div>
    </section>
  );
}
