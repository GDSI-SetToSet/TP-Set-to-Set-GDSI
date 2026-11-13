import assert from 'node:assert/strict';
import test from 'node:test';
import {
  RPE_UNREPORTED_LABEL,
  findPendingRpeSession,
  sessionRpeStatusLabel,
  shouldPromptForRpe,
  syncSessionAfterRpe,
} from './sessionRpeState.mjs';

test('solicita RPE directamente cuando el resumen finalizado no tiene calificación', () => {
  assert.equal(shouldPromptForRpe(null), false);
  assert.equal(shouldPromptForRpe({ rpe: null }), true);
  assert.equal(shouldPromptForRpe({ rpe: undefined }), true);
  assert.equal(shouldPromptForRpe({ rpe: 8 }), false);
});

test('sincroniza workoutSessions inmediatamente al guardar RPE y limpia el recordatorio pendiente', () => {
  const initial = [
    { id: 's2', finished_at: '2026-11-12T11:00:00Z', rpe: null },
    { id: 's1', finished_at: '2026-11-10T11:00:00Z', rpe: 7 },
  ];
  assert.equal(findPendingRpeSession(initial, null)?.id, 's2');

  const updated = syncSessionAfterRpe(initial, { id: 's2', finished_at: '2026-11-12T11:00:00Z', rpe: 9 });
  assert.equal(updated[0].rpe, 9);
  assert.equal(updated[1].rpe, 7);
  assert.equal(findPendingRpeSession(updated, null), null);
});

test('no duplica ni altera sesiones cuando se inserta una sesión recién finalizada', () => {
  const initial = [{ id: 's1', finished_at: '2026-11-10T11:00:00Z', rpe: 7 }];
  const withFinished = syncSessionAfterRpe(initial, { id: 's2', finished_at: '2026-11-12T11:00:00Z', rpe: null });
  assert.deepEqual(withFinished.map((s) => s.id), ['s2', 's1']);
  assert.equal(findPendingRpeSession(withFinished, 's3')?.id, 's2');
  assert.equal(findPendingRpeSession(withFinished, 's2'), null);
});

test('muestra etiqueta unificada "Finalizada sin reporte" y distingue sesión en curso', () => {
  assert.equal(sessionRpeStatusLabel({ finished_at: null, rpe: null }), 'En curso');
  assert.equal(sessionRpeStatusLabel({ finished_at: '2026-11-12T11:00:00Z', rpe: null }), RPE_UNREPORTED_LABEL);
  assert.equal(sessionRpeStatusLabel({ finished_at: '2026-11-12T11:00:00Z', rpe: 6 }), 'Esfuerzo: 6/10');
});
