/**
 * Parses backend ISO timestamps, assuming UTC when no explicit timezone offset is present.
 *
 * @param {string} value
 * @returns {Date}
 */
export function parseUtcIsoTimestamp(value) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(normalized);
}

/**
 * Formats a notification timestamp in local `es-AR` time.
 *
 * @param {string} value
 * @returns {string}
 */
export function formatNotificationTime(value) {
  const date = parseUtcIsoTimestamp(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}
