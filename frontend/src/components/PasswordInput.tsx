import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../constants/auth';

export function PasswordInput({ id, name = id, label = 'Contraseña', value, onChange, autoComplete, error, showHint = true }: {
  id: string;
  name?: string;
  label?: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  error?: string;
  showHint?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className={`input-wrap${error ? ' input-wrap--error' : ''}`}>
        <input id={id} name={name} type={visible ? 'text' : 'password'} value={value} onChange={(event) => onChange(event.target.value)} autoComplete={autoComplete} maxLength={PASSWORD_MAX_LENGTH} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : showHint ? `${id}-hint` : undefined} required />
        <button className="visibility-button" type="button" onClick={() => setVisible((current) => !current)} aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      {error ? <span id={`${id}-error`} className="field-error">{error}</span> : showHint ? <span id={`${id}-hint`} className="field-hint">Entre {PASSWORD_MIN_LENGTH} y {PASSWORD_MAX_LENGTH} caracteres, con mayúscula, minúscula y número.</span> : null}
    </div>
  );
}
