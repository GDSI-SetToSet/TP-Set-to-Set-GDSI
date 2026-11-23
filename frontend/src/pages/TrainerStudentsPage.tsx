import { ArrowLeft } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { RoutineAssignmentPanel } from '../components/RoutineAssignmentPanel';
import { TrainerStudentDetail } from '../components/TrainerStudentDetail';
import { ROUTES } from '../constants/routes';
import { getTrainerAIRoutines } from '../services/assignedRoutineService';
import { getRoutineTemplates } from '../services/routineTemplateService';
import { getTrainerStudentDetail } from '../services/trainerStudentService';
import { createScopedRequestTracker, executeStudentDetailRequest } from '../utils/safetyAlerts.mjs';
import type { TrainerStudentDetail as TrainerStudentDetailModel } from '../types/trainerStudent';
import type { TrainerAIRoutine } from '../types/assignedRoutine';
import type { RoutineTemplate } from '../types/routineTemplate';

export function TrainerStudentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  // US-35: tras una baja se vuelve a montar el panel para recargar la lista de alumnos activos.
  const [listVersion, setListVersion] = useState(0);
  const [terminationNotice, setTerminationNotice] = useState('');
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [aiRoutines, setAIRoutines] = useState<TrainerAIRoutine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [studentDetail, setStudentDetail] = useState<TrainerStudentDetailModel | null>(null);
  const [detailStudentId, setDetailStudentId] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [safetyRefreshKey, setSafetyRefreshKey] = useState(0);
  const selectedStudentIdRef = useRef<string | null>(selectedStudentId);
  selectedStudentIdRef.current = selectedStudentId;
  const detailTrackerRef = useRef(createScopedRequestTracker());
  const handledDetailNavKeyRef = useRef('');
  const routineStatus = searchParams.get('routineStatus');
  const notificationStudentId = searchParams.get('studentId');
  const notificationView = searchParams.get('view');

  useEffect(() => {
    const initialTracker = createScopedRequestTracker();
    detailTrackerRef.current = createScopedRequestTracker();
    const req = initialTracker.begin('initial');

    Promise.all([getRoutineTemplates(), getTrainerAIRoutines()])
      .then(([loadedTemplates, loadedAIRoutines]) => {
        if (!req.isCurrent()) return;
        setTemplates(loadedTemplates);
        setAIRoutines(loadedAIRoutines);
      })
      .catch(() => {
        if (!req.isCurrent()) return;
        setError('No pudimos cargar tus rutinas. Intentá nuevamente.');
      })
      .finally(() => {
        if (!req.isCurrent()) return;
        setLoading(false);
      });

    return () => {
      initialTracker.dispose();
      detailTrackerRef.current.dispose();
    };
  }, []);

  const loadStudentDetail = useCallback((studentId: string, options?: { silentError?: boolean }) => {
    return executeStudentDetailRequest({
      studentId,
      tracker: detailTrackerRef.current,
      isSelectedStudent: (id) => selectedStudentIdRef.current === id,
      fetchDetail: getTrainerStudentDetail,
      onSuccess: (detail) => {
        setStudentDetail(detail);
        setDetailStudentId(studentId);
        setDetailError('');
      },
      onError: options?.silentError
        ? undefined
        : () => setDetailError('No pudimos cargar el detalle de este alumno. Intentá nuevamente.'),
      onFinally: options?.silentError
        ? undefined
        : () => setDetailLoading(false),
    });
  }, []);

  function handleSafetyAlertReviewed(studentId: string) {
    setSafetyRefreshKey((current) => current + 1);
    if (selectedStudentIdRef.current === studentId) {
      void loadStudentDetail(studentId, { silentError: true });
    }
  }

  function selectStudent(studentId: string) {
    if (selectedStudentId === studentId) {
      selectedStudentIdRef.current = null;
      detailTrackerRef.current.invalidate('detail');
      setSelectedStudentId(null);
      setDetailLoading(false);
      return;
    }
    selectedStudentIdRef.current = studentId;
    setSelectedStudentId(studentId);
    if (detailStudentId === studentId && studentDetail) {
      detailTrackerRef.current.invalidate('detail');
      setDetailError('');
      setDetailLoading(false);
      return;
    }
    setStudentDetail(null);
    setDetailStudentId(null);
    setDetailError('');
    setDetailLoading(true);
    void loadStudentDetail(studentId);
  }

  function retryStudentDetail(studentId: string) {
    setDetailError('');
    setDetailLoading(true);
    void loadStudentDetail(studentId);
  }

  const detailNavKey = notificationStudentId && notificationView === 'detail'
    ? `${notificationStudentId}|${notificationView}`
    : '';
  useEffect(() => {
    if (loading || !detailNavKey || handledDetailNavKeyRef.current === detailNavKey || !notificationStudentId) return;
    handledDetailNavKeyRef.current = detailNavKey;
    selectedStudentIdRef.current = notificationStudentId;
    setSelectedStudentId(notificationStudentId);
    if (detailStudentId !== notificationStudentId || !studentDetail) {
      setStudentDetail(null);
      setDetailStudentId(null);
      setDetailError('');
      setDetailLoading(true);
      void loadStudentDetail(notificationStudentId);
    }
  }, [loading, detailNavKey, notificationStudentId, detailStudentId, studentDetail, loadStudentDetail]);

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
        {terminationNotice && <p className="form-alert form-alert--success" role="status">{terminationNotice}</p>}
        {!error && (
          <RoutineAssignmentPanel
            key={listVersion}
            templates={templates}
            aiRoutines={aiRoutines}
            initialStudentId={notificationStudentId ?? undefined}
            initialSessionId={searchParams.get('sessionId') ?? undefined}
            initialEventId={searchParams.get('eventId') ?? undefined}
            initialEventType={searchParams.get('eventType') ?? undefined}
            initialView={notificationView ?? undefined}
            onStudentSelect={selectStudent}
            selectedStudentId={selectedStudentId}
            safetyRefreshKey={safetyRefreshKey}
            onSafetyAlertReviewed={handleSafetyAlertReviewed}
            renderStudentDetail={(studentId) => (
              <>
                {detailLoading && <p role="status">Cargando detalle del alumno…</p>}
                {detailError && (
                  <div className="form-alert" role="alert">
                    <p>{detailError}</p>
                    <button
                      type="button"
                      className="profile-save"
                      onClick={() => retryStudentDetail(studentId)}
                    >
                      Reintentar
                    </button>
                  </div>
                )}
                {studentDetail && studentDetail.profile.id === studentId && (
                  <TrainerStudentDetail
                    key={studentDetail.profile.id}
                    detail={studentDetail}
                    onClose={() => {
                      selectedStudentIdRef.current = null;
                      detailTrackerRef.current.invalidate('detail');
                      setSelectedStudentId(null);
                      setDetailLoading(false);
                    }}
                    safetyRefreshKey={safetyRefreshKey}
                    onSafetyAlertReviewed={handleSafetyAlertReviewed}
                    onTerminated={(result, studentName) => {
                      selectedStudentIdRef.current = null;
                      detailTrackerRef.current.invalidate('detail');
                      setSelectedStudentId(null);
                      setStudentDetail(null);
                      setDetailLoading(false);
                      setSearchParams({});
                      setTerminationNotice(
                        `${studentName} fue dado de baja. Se liberó un cupo: tenés ${result.available_slots} ${result.available_slots === 1 ? 'cupo disponible' : 'cupos disponibles'}.`,
                      );
                      setListVersion((value) => value + 1);
                    }}
                  />
                )}
              </>
            )}
          />
        )}
      </section>
    </main>
  );
}
