import { ArrowLeft, Trophy } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { StreakCard } from '../components/StreakCard';
import { LoadChart, VolumeChart } from '../components/StudentProgressCharts';
import { ROUTES } from '../constants/routes';
import { getStudentProgress, getStudentStreak } from '../services/studentProgressService';
import type { ProgressFilters, StudentProgress, TrainingStreak } from '../types/studentProgress';
import { formatNumber } from '../utils/trainingEvolution.mjs';
import '../styles/training-evolution.css';

const dateTime = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium', timeZone: 'UTC' });

export function StudentProgressPage() {
  const [filters, setFilters] = useState<ProgressFilters>({});
  const [data, setData] = useState<StudentProgress | null>(null);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [streak, setStreak] = useState<TrainingStreak | null>(null);

  useEffect(() => {
    let active = true;
    getStudentStreak().then((loaded) => { if (active) setStreak(loaded); }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getStudentProgress(filters)
      .then((result) => {
        if (active) setData(result);
      })
      .catch(() => {
        if (active) setError('No pudimos cargar tu evolución. Revisá los filtros e intentá nuevamente.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters]);

  const set = (key: keyof ProgressFilters) => (value: string) =>
    setFilters((current) => ({ ...current, [key]: value || undefined }));
  const exercise = data?.exercises.find((item) => item.exercise_id === selected) ?? data?.exercises[0];
  const comparison = data?.week_comparison;

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>
      <section className="profile-card training-evolution">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Mi evolución</h1>
          <p>Mirá cómo avanzan tus cargas, tu volumen semanal y tus récords personales.</p>
        </div>
        {streak && <StreakCard streak={streak} />}

        <div className="training-evolution__controls">
          <label>Ejercicio
            <select value={filters.exercise_id ?? ''} onChange={(e) => set('exercise_id')(e.target.value)}>
              <option value="">Todos</option>
              {data?.exercises.map((item) => <option key={item.exercise_id} value={item.exercise_id}>{item.name}</option>)}
            </select>
          </label>
          <label>Grupo muscular
            <select value={filters.muscle_group ?? ''} onChange={(e) => set('muscle_group')(e.target.value)}>
              <option value="">Todos</option>
              {data?.muscle_groups.map((group) => <option key={group} value={group}>{group}</option>)}
            </select>
          </label>
          <label>Desde
            <input type="date" value={filters.from ?? ''} max={filters.to} onChange={(e) => set('from')(e.target.value)} />
          </label>
          <label>Hasta
            <input type="date" value={filters.to ?? ''} min={filters.from} onChange={(e) => set('to')(e.target.value)} />
          </label>
          <small>{data?.range.is_default ? 'Mostrando las últimas 12 semanas.' : ''}</small>
        </div>

        {loading && <p role="status">Cargando tu evolución…</p>}
        {error && <p role="alert" className="profile-error">{error}</p>}
        {!loading && !error && data && !data.has_data && (
          <p role="status">Todavía no hay series registradas para estos filtros. Entrená y registrá tus series para ver tu evolución.</p>
        )}

        {!loading && !error && data?.has_data && (
          <>
            <h4>Carga por ejercicio</h4>
            {data.exercises.length > 1 && (
              <label className="training-evolution__controls">
                <select aria-label="Ejercicio del gráfico" value={exercise?.exercise_id} onChange={(e) => setSelected(e.target.value)}>
                  {data.exercises.map((item) => <option key={item.exercise_id} value={item.exercise_id}>{item.name}</option>)}
                </select>
              </label>
            )}
            {exercise && (exercise.has_trend
              ? <figure><figcaption>{exercise.name} · carga máxima por día (kg)</figcaption><LoadChart exercise={exercise} /></figure>
              : <p role="status">Se requieren más sesiones de {exercise.name} para trazar la tendencia.</p>)}

            <h4>Volumen semanal</h4>
            <figure><figcaption>Kilaje total por semana (kg)</figcaption><VolumeChart weeks={data.weekly_volume} /></figure>
            {comparison && (
              <p>
                Esta semana: <strong>{formatNumber(comparison.current_volume_kg)} kg</strong> · semana anterior: {formatNumber(comparison.previous_volume_kg)} kg
                {comparison.delta_vs_previous_pct !== null && ` (${comparison.delta_vs_previous_pct > 0 ? '+' : ''}${formatNumber(comparison.delta_vs_previous_pct)} %)`}
                {' '}· promedio de las anteriores: {formatNumber(comparison.previous_avg_kg)} kg
              </p>
            )}

            <h4><Trophy size={18} aria-hidden="true" /> Récords personales</h4>
            {data.personal_records.length === 0
              ? <p>No lograste récords en este período.</p>
              : (
                <ol>
                  {data.personal_records.map((record) => (
                    <li key={`${record.exercise_id}-${record.achieved_at}`}>
                      {dateTime.format(new Date(record.achieved_at))} · <strong>{record.exercise_name}</strong>: {formatNumber(record.weight_kg)} kg × {record.reps}
                      {record.is_initial ? ' (primer registro)' : ` (antes ${formatNumber(record.previous_weight_kg ?? 0)} kg)`}
                    </li>
                  ))}
                </ol>
              )}
          </>
        )}
      </section>
    </main>
  );
}
