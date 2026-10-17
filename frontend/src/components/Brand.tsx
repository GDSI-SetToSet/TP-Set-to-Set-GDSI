import { Dumbbell } from 'lucide-react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className={`brand${compact ? ' brand--compact' : ''}`} to={ROUTES.root} aria-label="Set to Set, inicio">
      <span className="brand__icon"><Dumbbell size={20} strokeWidth={2.3} /></span>
      <span>set<span className="brand__accent">to</span>set</span>
    </Link>
  );
}
