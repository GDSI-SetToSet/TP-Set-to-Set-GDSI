import { Search, ArrowLeft, ArrowRight, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { searchTrainers } from '../services/discoveryService';
import type { TrainerSearchResult, TrainerSearchFilters } from '../types/discovery';
import '../styles/discovery.css';
import '../styles/trainer-search.css';

export function TrainerSearchPage() {
  const [results, setResults] = useState<TrainerSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [onlyAvailable, setOnlyAvailable] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  async function doSearch(p: number = page) {
    setLoading(true);
    setError('');
    try {
      const filters: TrainerSearchFilters = { page: p, page_size: pageSize, only_available: onlyAvailable };
      if (name.trim()) filters.name = name.trim();
      if (specialty.trim()) filters.specialty = specialty.trim();
      if (maxPrice.trim()) filters.max_price = Number(maxPrice);
      const data = await searchTrainers(filters);
      setResults(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch {
      setError('Error al buscar entrenadores.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { doSearch(1); }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    doSearch(1);
  }

  const totalPages = Math.ceil(total / pageSize);

  function formatPrice(value: number | null) {
    if (value === null) return '—';
    return `$${value.toLocaleString('es-AR')}`;
  }

  return (
    <main className="profile-shell trainer-search-page">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <div className="trainer-search-content">
        <div className="trainer-search-heading">
          <span>ENTRENADORES</span>
          <h1><Search size={30} aria-hidden="true" /> Buscar entrenadores</h1>
          <p>Encontrá un entrenador por nombre, especialidad o precio.</p>
        </div>

        <form className="trainer-search-filters" onSubmit={handleSubmit}>
          <label className="trainer-search-field">
            Nombre
            <input
              type="search"
              value={name}
              onChange={event => setName(event.target.value)}
              className="trainer-search-input"
              placeholder="Ej. Juan Pérez"
              aria-label="Buscar entrenador por nombre"
            />
          </label>
          <label className="trainer-search-field">
            Especialidad
            <input
              type="text"
              value={specialty}
              onChange={event => setSpecialty(event.target.value)}
              className="trainer-search-input"
              placeholder="Ej. Fuerza"
              aria-label="Filtrar por especialidad"
            />
          </label>
          <label className="trainer-search-field">
            Precio máximo
            <input
              type="number"
              value={maxPrice}
              onChange={event => setMaxPrice(event.target.value)}
              className="trainer-search-input"
              min={0}
              placeholder="Sin límite"
              aria-label="Precio máximo"
            />
          </label>
          <label className="trainer-search-checkbox">
            <input type="checkbox" checked={onlyAvailable} onChange={event => setOnlyAvailable(event.target.checked)} />
            Solo con cupos
          </label>
          <button type="submit" className="profile-save trainer-search-submit">
            <Search size={18} /> Buscar
          </button>
        </form>

        {error && <p className="form-alert" role="alert">{error}</p>}

        {loading ? (
          <p className="discovery-loading">Buscando entrenadores…</p>
        ) : results.length === 0 ? (
          <p className="discovery-empty trainer-search-empty">No encontramos entrenadores con esos filtros.</p>
        ) : (
          <>
            <div className="trainer-grid">
              {results.map(trainer => (
                <article key={trainer.id} className="trainer-card">
                  <h3 className="trainer-card__name">{trainer.full_name ?? 'Entrenador'}</h3>
                  {trainer.specialty && <span className="trainer-card__specialty">{trainer.specialty}</span>}
                  {trainer.bio_preview && <p className="trainer-card__bio">{trainer.bio_preview}</p>}
                  <div className="trainer-card__meta">
                    <span className="trainer-card__price">{formatPrice(trainer.min_price)}{trainer.max_price !== trainer.min_price ? ` – ${formatPrice(trainer.max_price)}` : ''}</span>
                    <span className={`trainer-card__quota ${trainer.has_available_quota ? 'available' : 'full'}`}>
                      <Users size={14} /> {trainer.has_available_quota ? `${trainer.available_slots} cupos` : 'Sin cupos'}
                    </span>
                  </div>
                  <Link to={`/entrenadores/${trainer.id}`} className="filter-btn trainer-card__cta">Ver perfil</Link>
                </article>
              ))}
            </div>

            {totalPages > 1 && (
              <nav className="pagination" aria-label="Paginación de entrenadores">
                <button type="button" disabled={page <= 1} onClick={() => doSearch(page - 1)} className="pagination-btn"><ArrowLeft size={14} /> Anterior</button>
                <span className="pagination-info">Página {page} de {totalPages}</span>
                <button type="button" disabled={page >= totalPages} onClick={() => doSearch(page + 1)} className="pagination-btn">Siguiente <ArrowRight size={14} /></button>
              </nav>
            )}
          </>
        )}
      </div>
    </main>
  );
}
