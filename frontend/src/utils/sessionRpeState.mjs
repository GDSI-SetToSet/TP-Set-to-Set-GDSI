export const RPE_UNREPORTED_LABEL = 'Finalizada sin reporte';

/** Al finalizar una sesión sin RPE registrado, se solicita la calificación directamente. */
export function shouldPromptForRpe(summary) {
  return Boolean(summary && (summary.rpe === null || summary.rpe === undefined));
}

/** Sincroniza una sesión actualizada o recién finalizada en el listado del componente padre. */
export function syncSessionAfterRpe(sessions, updatedSession) {
  if (!updatedSession?.id) return sessions;
  let found = false;
  const next = sessions.map((session) => {
    if (session.id !== updatedSession.id) return session;
    found = true;
    return { ...session, ...updatedSession };
  });
  return found ? next : [updatedSession, ...sessions];
}

/** Devuelve la última sesión finalizada sin reporte RPE pendiente de recordar. */
export function findPendingRpeSession(sessions, activeSessionId) {
  return sessions.find(
    (session) => Boolean(session.finished_at)
      && (session.rpe === null || session.rpe === undefined)
      && session.id !== activeSessionId,
  ) ?? null;
}

export function sessionRpeStatusLabel(session) {
  if (!session?.finished_at) return 'En curso';
  if (session.rpe !== null && session.rpe !== undefined) return `Esfuerzo: ${session.rpe}/10`;
  return RPE_UNREPORTED_LABEL;
}
