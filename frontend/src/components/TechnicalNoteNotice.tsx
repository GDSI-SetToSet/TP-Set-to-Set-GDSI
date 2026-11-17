import { Pin } from 'lucide-react';
import { useState } from 'react';
import type { TechnicalNoteView } from '../types/conversation';
import '../styles/messages.css';

interface TechnicalNoteNoticeProps {
  notes: TechnicalNoteView[];
  onAcknowledge: (noteId: string) => Promise<void>;
}

/** US-62 escenario 3: nota técnica fijada que el alumno confirma antes de iniciar el ejercicio. */
export function TechnicalNoteNotice({ notes, onAcknowledge }: TechnicalNoteNoticeProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (notes.length === 0) return null;

  async function acknowledgeAll() {
    setBusy(true);
    setError('');
    try {
      for (const note of notes) await onAcknowledge(note.id);
    } catch {
      setError('No pudimos registrar la confirmación. Intentá nuevamente.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="technical-note" role="alert" aria-live="assertive">
      <p className="technical-note__title">
        <Pin size={16} aria-hidden="true" /> Nota técnica de {notes[0].trainer_name}
      </p>
      {notes.map((note) => <p key={note.id} className="technical-note__body">{note.body}</p>)}
      <p className="technical-note__hint">Leela antes de empezar este ejercicio.</p>
      {error && <p className="field-error">{error}</p>}
      <button type="button" className="technical-note__ack" onClick={() => void acknowledgeAll()} disabled={busy}>
        {busy ? 'Guardando…' : 'Entendido'}
      </button>
    </div>
  );
}
