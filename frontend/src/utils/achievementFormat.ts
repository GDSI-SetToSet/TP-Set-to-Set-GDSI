/** Fecha de un logro ("2026-11-17T10:00:00" → "17/11/2026"), sin correr el día por la zona horaria. */
export function formatAchievementDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-');
  return `${day}/${month}/${year}`;
}
