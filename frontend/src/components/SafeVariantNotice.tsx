import { useEffect, useState } from 'react';
import { resolveSafeVariant } from '../services/safeVariantService';
import type { SafeVariantResolution } from '../types/safeVariant';
import { getVideoEmbedUrl } from '../utils/videoUrl';

interface Props {
  exerciseId: string;
  onSkip: () => void;
}

/** US-53: muestra la variante segura del ejercicio, o avisa que no hay una y permite saltearlo. */
export function SafeVariantNotice({ exerciseId, onSkip }: Props) {
  const [result, setResult] = useState<SafeVariantResolution | null>(null);

  useEffect(() => {
    resolveSafeVariant(exerciseId).then(setResult).catch(() => setResult(null));
  }, [exerciseId]);

  if (!result || result.status === 'SAFE') return null;
  if (result.status === 'BLOCKED') {
    return (
      <div className="safe-variant safe-variant--blocked" role="status">
        <p><strong>Sin variante segura.</strong> {result.message}</p>
        {result.can_skip && <button className="plan-cancel" type="button" onClick={onSkip}>Saltear ejercicio</button>}
      </div>
    );
  }
  const variant = result.variant!;
  const embed = variant.video_url ? getVideoEmbedUrl(variant.video_url) : null;
  return (
    <div className="safe-variant safe-variant--ok" role="status">
      <p><strong>Variante segura para tus limitaciones: {variant.name}</strong></p>
      <p>{variant.description}</p>
      {embed && <iframe className="exercise-video" src={embed} title={`Video de ${variant.name}`} loading="lazy" allowFullScreen />}
    </div>
  );
}
