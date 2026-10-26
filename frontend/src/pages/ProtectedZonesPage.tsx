import axios from 'axios';
import { ArrowLeft, CheckCircle2, Plus, Save, Trash2 } from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnProtectedZones, updateOwnProtectedZones } from '../services/studentService';

const BODY_AREAS = [
  'Neck',
  'Shoulder',
  'Elbow',
  'Wrist and hand',
  'Upper back',
  'Lower back',
  'Hip',
  'Knee',
  'Ankle and foot',
  'Other',
] as const;

const ZONES_ES: Record<string, string> = {
  'Neck': 'Cuello',
  'Shoulder': 'Hombro',
  'Elbow': 'Codo',
  'Wrist and hand': 'Muñeca y mano',
  'Upper back': 'Espalda alta',
  'Lower back': 'Espalda baja',
  'Hip': 'Cadera',
  'Knee': 'Rodilla',
  'Ankle and foot': 'Tobillo y pie',
  'Other': 'Otra',
};

const OTHER_OPTION = 'Other';

export function ProtectedZonesPage() {
  const navigate = useNavigate();
  const redirectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [zones, setZones] = useState<string[]>([]);
  const [selectedArea, setSelectedArea] = useState('');
  const [customArea, setCustomArea] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getOwnProtectedZones()
      .then((data) => setZones(data.zones.map((zone) => zone.body_area)))
      .catch(() => setError('No pudimos cargar tus zonas a proteger. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => () => {
    if (redirectTimeout.current !== null) clearTimeout(redirectTimeout.current);
  }, []);

  const areaToAdd = selectedArea === OTHER_OPTION ? customArea.trim() : selectedArea;
  const canAdd = zones.length < 20
    && Boolean(areaToAdd)
    && !zones.some((zone) => zone.toLocaleLowerCase() === areaToAdd.toLocaleLowerCase());

  function addZone() {
    if (!canAdd) return;
    setZones((current) => [...current, areaToAdd]);
    setSelectedArea('');
    setCustomArea('');
    setError('');
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    try {
      const updated = await updateOwnProtectedZones(zones);
      setZones(updated.zones.map((zone) => zone.body_area));
      setIsSubmitting(false);
      setIsSuccess(true);
      redirectTimeout.current = setTimeout(() => {
        navigate(ROUTES.studentHome);
        redirectTimeout.current = null;
      }, 1000);
    } catch (caught) {
      setError(
        axios.isAxiosError(caught)
          ? 'Revisá las zonas ingresadas e intentá nuevamente.'
          : 'No pudimos guardar tus zonas a proteger. Intentá nuevamente.',
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando zonas a proteger…</main>;

  return (
    <>
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back">
          <ArrowLeft size={18} /> Volver al inicio
        </Link>
      </header>
      <section className="profile-card">
        <div className="profile-heading">
          <span>SALUD Y SEGURIDAD</span>
          <h1>Zonas a proteger</h1>
          <p>Indicá lesiones previas, molestias o zonas que requieren cuidado para tenerlas en cuenta al planificar tu entrenamiento.</p>
        </div>
        <form className="profile-form" onSubmit={handleSubmit}>
          <div className="protected-zone-add">
            <label htmlFor="protected-zone-select">Zona corporal</label>
            <div className="protected-zone-add__controls">
              <select
                id="protected-zone-select"
                value={selectedArea}
                onChange={(event) => setSelectedArea(event.target.value)}
              >
                <option value="">Seleccioná una zona</option>
                {BODY_AREAS.map((area) => <option key={area} value={area}>{ZONES_ES[area]}</option>)}
              </select>
              {selectedArea === OTHER_OPTION && (
                <input
                  value={customArea}
                  onChange={(event) => setCustomArea(event.target.value)}
                  maxLength={80}
                  placeholder="Escribí otra zona corporal"
                  aria-label="Otra zona corporal"
                />
              )}
              <button className="profile-save protected-zone-add__button" type="button" onClick={addZone} disabled={!canAdd}>
                <Plus size={18} /> Agregar
              </button>
            </div>
          </div>

          {zones.length > 0 ? (
            <ul className="protected-zone-list" aria-label="Zonas registradas">
              {zones.map((zone) => (
                <li key={zone} className="protected-zone-item">
                  <span>{ZONES_ES[zone] || zone}</span>
                  <button
                    type="button"
                    className="protected-zone-remove"
                    onClick={() => setZones((current) => current.filter((item) => item !== zone))}
                    aria-label={`Eliminar ${zone}`}
                  >
                    <Trash2 size={17} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="protected-zone-empty">Todavía no registraste zonas a proteger.</p>
          )}

          {error && <p className="form-alert" role="alert">{error}</p>}
          <button className="profile-save" type="submit" disabled={isSubmitting}>
            <Save size={18} /> {isSubmitting ? 'Guardando...' : 'Guardar zonas'}
          </button>
        </form>
      </section>
    </main>
    {(isSubmitting || isSuccess) && (
      <div className="success-overlay" role="status" aria-live="polite" aria-atomic="true">
        <div className="success-overlay__card">
          {isSuccess ? (
            <>
              <span className="success-overlay__icon"><CheckCircle2 size={32} aria-hidden="true" /></span>
              <h2>¡Guardado con éxito!</h2>
              <p>Redirigiendo...</p>
            </>
          ) : (
            <>
              <span className="success-overlay__spinner" aria-hidden="true" />
              <h2>Guardando...</h2>
            </>
          )}
        </div>
      </div>
    )}
    </>
  );
}
