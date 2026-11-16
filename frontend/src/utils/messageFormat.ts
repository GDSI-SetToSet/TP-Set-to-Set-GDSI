/** Fechas de mensajes: el backend guarda UTC sin zona; se agrega "Z" si falta. */
function toDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`);
}

export function formatMessageTime(value: string): string {
  const date = toDate(value);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return time;
  return `${date.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' })} ${time}`;
}

export function queryContext(exercise: { name: string } | null, setNumber: number | null): string {
  if (!exercise) return 'Consulta técnica';
  return setNumber ? `${exercise.name} · serie ${setNumber}` : exercise.name;
}

export const MESSAGE_MAX_LENGTH = 2000;
export const POLL_INTERVAL_MS = 10_000;
