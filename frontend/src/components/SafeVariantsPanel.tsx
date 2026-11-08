import { useCallback, useEffect, useState } from 'react';
import { BODY_AREAS, ZONES_ES } from '../constants/bodyAreas';
import { getApiErrorInfo } from '../services/errorMessage';
import { addSafeVariant, getSafeVariants, removeSafeVariant } from '../services/safeVariantService';
import type { Exercise } from '../types/exercise';
import type { SafeVariant } from '../types/safeVariant';

const zoneLabel = (zone: string) => {
  const area = BODY_AREAS.find((item) => item.toLowerCase() === zone.toLowerCase());
  return area ? ZONES_ES[area] : zone;
};

interface Props {
  exercise: Exercise;
  library: Exercise[];
}

/** Variantes seguras (US-53): el entrenador vincula otro ejercicio de su biblioteca para las zonas de riesgo. */
export function SafeVariantsPanel({ exercise, library }: Props) {
  const [variants, setVariants] = useState<SafeVariant[]>([]);
  const [variantId, setVariantId] = useState('');
  const [zones, setZones] = useState<string[]>([]);
  const [error, setError] = useState('');
  const riskZones = exercise.contraindicated_zones ?? [];

  const load = useCallback(() => {
    getSafeVariants(exercise.id).then(setVariants).catch(() => setError('No pudimos cargar las variantes.'));
  }, [exercise.id]);
  useEffect(load, [load]);

  async function handleAdd() {
    setError('');
    try {
      await addSafeVariant(exercise.id, { variant_exercise_id: variantId, covered_zones: zones });
      setVariantId('');
      setZones([]);
      load();
    } catch (caught) {
      setError(getApiErrorInfo(caught, 'No pudimos guardar la variante.').message);
    }
  }

  async function handleRemove(id: string) {
    setError('');
    try {
      await removeSafeVariant(exercise.id, id);
      load();
    } catch (caught) {
      setError(getApiErrorInfo(caught, 'No pudimos quitar la variante.').message);
    }
  }

  if (riskZones.length === 0) return null;
  return (
    <fieldset className="zone-checks">
      <legend>Variantes seguras</legend>
      <p>Ejercicio que ve el alumno con esas zonas protegidas en lugar de este. Tiene que cubrir todas sus zonas en conflicto.</p>
      {error && <p className="form-alert" role="alert">{error}</p>}
      <ul className="safe-variants-list">
        {variants.map((item) => (
          <li key={item.id}>
            <span>{item.variant_name} · {item.covered_zones.map(zoneLabel).join(', ')}</span>
            <button className="plan-cancel" type="button" onClick={() => handleRemove(item.id)} aria-label={`Quitar variante ${item.variant_name}`}>Quitar</button>
          </li>
        ))}
        {variants.length === 0 && <li>Todavía no hay variantes seguras para este ejercicio.</li>}
      </ul>
      <label>Ejercicio variante
        <select className="exercise-select" value={variantId} onChange={(event) => setVariantId(event.target.value)}>
          <option value="">Elegí un ejercicio</option>
          {library.filter((item) => item.id !== exercise.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <div className="zone-checks__grid">
        {riskZones.map((zone) => (
          <label key={zone} className="exercise-check zone-checks__item">
            <input
              type="checkbox"
              checked={zones.includes(zone)}
              onChange={(event) => setZones((current) => (event.target.checked ? [...current, zone] : current.filter((z) => z !== zone)))}
            />
            {zoneLabel(zone)}
          </label>
        ))}
      </div>
      <button className="profile-save" type="button" onClick={handleAdd} disabled={!variantId || zones.length === 0} aria-describedby="safe-variant-hint">Agregar variante</button>
      <small id="safe-variant-hint" className="safe-variants-hint">Elegí el ejercicio variante y al menos una zona que cubre.</small>
    </fieldset>
  );
}
