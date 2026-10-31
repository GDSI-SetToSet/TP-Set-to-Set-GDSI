import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  Dumbbell,
  FileText,
  Inbox,
  LogOut,
  Package,
  Search,
  Shield,
  Sparkles,
  UserRound,
  Users,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { USER_ROLES } from '../constants/auth';
import { useAuth } from '../context/AuthContext';
import { homePath, ROUTES } from '../constants/routes';
import { getActivePlans, getTrainerRequests } from '../services/discoveryService';
import { getRoutineAssignments } from '../services/routineTemplateService';
import type { ActivePlansResponse, NotificationItem } from '../types/discovery';
import { NotificationBell } from '../components/NotificationBell';
import { getOwnHealthQuestionnaire } from '../services/studentHealthService';
import '../styles/health-questionnaire.css';

export function HomePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [pendingRequestsCount, setPendingRequestsCount] = useState<number>(0);
  const [activeStudentsCount, setActiveStudentsCount] = useState<number>(0);
  const [activePlans, setActivePlans] = useState<ActivePlansResponse>([]);
  const [healthQuestionnaireCompleted, setHealthQuestionnaireCompleted] = useState<boolean | null>(null);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const isTrainer = user?.role === USER_ROLES.trainer;
  const profilePath = isTrainer ? ROUTES.trainerProfile : ROUTES.studentProfile;
  const activeLinksCount = activePlans.filter((plan) => plan.status === 'ACTIVE').length;
  const greeting = isTrainer ? 'Tu espacio de entrenador' : 'Tu espacio de entrenamiento';
  const homeActions: Array<{ label: string; description: string; to: string; icon: ReactNode; count?: number; countLabel?: string; featured?: boolean; warning?: boolean }> = isTrainer
    ? [
        { label: 'Mis rutinas', description: 'Diseñá y organizá rutinas para tus alumnos.', to: ROUTES.trainerRoutines, icon: <Dumbbell size={20} /> },
        { label: 'Mis alumnos', description: 'Consultá tus alumnos activos y asignales rutinas.', to: ROUTES.trainerStudents, icon: <Users size={20} />, count: activeStudentsCount, countLabel: 'alumnos activos' },
        { label: 'Mis ejercicios', description: 'Administrá los ejercicios de tu biblioteca.', to: ROUTES.trainerExercises, icon: <Activity size={20} /> },
        { label: 'Mis paquetes', description: 'Gestioná tus propuestas de entrenamiento.', to: ROUTES.trainerPlans, icon: <Package size={20} /> },
        { label: 'Solicitudes', description: 'Revisá las solicitudes para entrenar con vos.', to: ROUTES.trainerRequests, icon: <Inbox size={20} />, count: pendingRequestsCount, countLabel: 'solicitudes pendientes' },
      ]
    : [
        { label: 'Rutina del día', description: 'Consultá los ejercicios y bloques asignados.', to: ROUTES.studentRoutines, icon: <Dumbbell size={20} />, featured: true },
        { label: 'Mis entrenadores', description: 'Revisá tus vínculos de entrenamiento.', to: ROUTES.studentActivePlans, icon: <Users size={20} />, count: activeLinksCount, countLabel: 'entrenadores activos' },
        { label: 'Buscar entrenadores', description: 'Encontrá un entrenador para empezar.', to: ROUTES.trainerSearch, icon: <Search size={20} /> },
        { label: 'Cuestionario de salud', description: healthQuestionnaireCompleted === false ? 'Es necesario completarlo para que tu entrenador diseñe una rutina segura.' : 'Actualizá la información de salud.', to: ROUTES.studentHealth, icon: <ClipboardList size={20} />, warning: healthQuestionnaireCompleted === false },
        { label: 'Zonas a proteger', description: 'Indicá las zonas que requieren cuidado.', to: ROUTES.studentProtectedZones, icon: <Shield size={20} /> },
        { label: 'Apto médico', description: 'Consultá el estado de tu apto médico.', to: ROUTES.studentMedical, icon: <FileText size={20} /> },
      ];

  useEffect(() => {
    let active = true;
    setError('');
    if (user?.role === USER_ROLES.trainer) {
      getTrainerRequests('PENDING')
        .then((requests) => {
          if (active) setPendingRequestsCount(requests.length);
        })
        .catch(() => {
          if (active) {
            setPendingRequestsCount(0);
            setError('No pudimos cargar tus solicitudes pendientes. Intentá nuevamente.');
          }
        });
      getRoutineAssignments()
        .then((students) => {
          if (active) setActiveStudentsCount(students.length);
        })
        .catch(() => {
          if (active) {
            setActiveStudentsCount(0);
            setError('No pudimos cargar tus alumnos activos. Intentá nuevamente.');
          }
        });
    } else if (user?.role === USER_ROLES.student) {
      getOwnHealthQuestionnaire()
        .then((questionnaire) => {
          if (active) setHealthQuestionnaireCompleted(Boolean(questionnaire));
        })
        .catch(() => {
          if (active) setHealthQuestionnaireCompleted(null);
        });
      getActivePlans()
        .then((plans) => {
          if (active) {
            setActivePlans(plans);
          }
        })
        .catch(() => {
          if (active) {
            setActivePlans([]);
            setError('No pudimos cargar tus vínculos activos. Intentá nuevamente.');
          }
        });
    }
    return () => {
      active = false;
    };
  }, [user?.role]);

  useEffect(() => {
    function closeProfileMenu(event: MouseEvent) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false);
      }
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setProfileMenuOpen(false);
    }
    document.addEventListener('mousedown', closeProfileMenu);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', closeProfileMenu);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } catch {
      setError('No pudimos cerrar la sesión en el servidor. Tu sesión local se cerró.');
    }
  }

  function handleNotificationClick(_notification: NotificationItem) {
    if (user?.role === USER_ROLES.student) {
      navigate(ROUTES.studentActivePlans);
    } else if (user?.role === USER_ROLES.trainer) {
      navigate(ROUTES.trainerRequests);
    }
  }

  return (
    <main className={`home-shell${user?.role === USER_ROLES.trainer ? ' home-shell--trainer' : ''}`}>
      <header className="home-header">
        <Link className="brand" to={homePath(user?.role ?? USER_ROLES.student)}><span className="brand__icon"><Sparkles size={19} /></span><span>set<span className="brand__accent">to</span>set</span></Link>
        <div className="home-header__actions">
          {(user?.role === USER_ROLES.student || user?.role === USER_ROLES.trainer) && (
            <NotificationBell onNotificationClick={handleNotificationClick} />
          )}
          <div className="profile-menu" ref={profileMenuRef}>
            <button
              type="button"
              className="profile-menu__trigger"
              aria-label="Abrir menú de perfil"
              aria-expanded={profileMenuOpen}
              aria-haspopup="menu"
              onClick={() => setProfileMenuOpen((open) => !open)}
            >
              <UserRound size={19} />
            </button>
            {profileMenuOpen && (
              <div className="profile-menu__dropdown" role="menu">
                <div className="profile-menu__identity">
                  <strong>{isTrainer ? 'Entrenador/a' : 'Alumno/a'}</strong>
                  <span>{user?.email}</span>
                </div>
                <Link role="menuitem" to={profilePath} onClick={() => setProfileMenuOpen(false)}>
                  <UserRound size={17} /> Mi perfil <ArrowRight size={15} />
                </Link>
                <button
                  type="button"
                  role="menuitem"
                  className="profile-menu__logout"
                  onClick={() => { setProfileMenuOpen(false); void handleLogout(); }}
                >
                  <LogOut size={17} /> Cerrar sesión
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
      <section className="welcome-card">
        <span className="welcome-kicker">CUENTA ACTIVA <span className="online-dot" /></span>
        <h1>{greeting}</h1>
        <p>Ingresaste como <strong>{user?.email}</strong>.</p>
        <div className="role-badge">{isTrainer ? 'Entrenador/a' : 'Alumno/a'}</div>
        <section className="home-actions" aria-labelledby="home-actions-title">
          <div className="home-actions__heading">
            <h2 id="home-actions-title">Accesos rápidos</h2>
            <span>¿Qué querés hacer hoy?</span>
          </div>
          <nav className="home-actions__grid" aria-label="Secciones principales">
            {homeActions.map((action) => (
              <Link
                key={action.label}
                className={`home-action${action.featured ? ' home-action--featured' : ''}`}
                to={action.to}
              >
                <span className="home-action__icon">{action.icon}</span>
                <span className="home-action__copy">
                  <strong>
                    {action.label}
                    {action.warning && (
                      <span className="home-action__warning" role="img" aria-label="Pendiente: es necesario completar el cuestionario">
                        <AlertTriangle size={15} aria-hidden="true" />
                      </span>
                    )}
                  </strong>
                  <span>{action.description}</span>
                </span>
                {typeof action.count === 'number' && action.count > 0 && (
                  <span className="home-action__count" aria-label={`${action.count} ${action.countLabel ?? 'elementos'}`}>{action.count}</span>
                )}
                <ArrowRight className="home-action__arrow" size={17} aria-hidden="true" />
              </Link>
            ))}
          </nav>
        </section>
        {error && <p className="form-alert" role="alert">{error}</p>}
        {user?.role === USER_ROLES.student && (
          <p className="home-active-plans-summary">
            {activeLinksCount === 0
              ? 'No tenés vínculos activos.'
              : `Tenés ${activeLinksCount} vínculo${activeLinksCount === 1 ? '' : 's'} activo${activeLinksCount === 1 ? '' : 's'}.`}
          </p>
        )}
        <div className="welcome-next"><span>Este es el primer paso de Set to Set.</span><Dumbbell size={18} /></div>
      </section>
    </main>
  );
}
