import { AlertTriangle, ArrowRight, Check, TrendingDown, TrendingUp, Trophy, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getTrainingEvolution } from '../services/trainerStudentService';
import type { EvolutionGrouping, EvolutionPeriod, TrafficLight, TrainingEvolution as Evolution } from '../types/trainerStudent';
import {
  EFFORT_MESSAGES,
  EVOLUTION_GROUPINGS,
  EVOLUTION_PERIODS,
  LIGHT_LABELS,
  REVIEW_HINT,
  STATUS_LABELS,
  TREND_LABELS,
  firstName,
  formatAgo,
  formatChange,
  formatNumber,
  formatRange,
  formatSet,
  recentRecordCount,
  sortByStatus,
  statusCounts,
} from '../utils/trainingEvolution.mjs';
import { AdherenceChart, ExerciseChart, Legend, RpeChart, SetsByGroupChart } from './EvolutionCharts';
import '../styles/training-evolution.css';

const ICON = { green: Check, yellow: AlertTriangle, red: X };
const STATUS_ICON = { progressing: TrendingUp, stalled: AlertTriangle, declined: TrendingDown, unchanged: ArrowRight };
const icon = { size: 16, 'aria-hidden': true, className: 'training-evolution__icon' } as const;

/** Alternativa textual de un gráfico: tooltips nativos no sirven con teclado ni táctil. */
function Values({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="training-evolution__values">
      <summary>Ver valores en tabla</summary>
      <div className="training-evolution__table-wrap">
        <table className="training-evolution__table">
          <thead><tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
          <tbody>{rows.map((row) => <tr key={row[0]}>{row.map((cell, i) => <td key={i}>{cell}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </details>
  );
}

function Card({ title, value, detail, light, target, onGo }: {
  title: string; value: string; detail: string; light: TrafficLight; target: string; onGo: (id: string) => void;
}) {
  const state = light ?? 'none';
  return (
    <button type="button" className={`training-evolution__card training-evolution__card--${state}`} onClick={() => onGo(target)}
      aria-label={`${title}: ${value}. ${detail}${light ? `. ${LIGHT_LABELS[light]}` : ''}. Ir a la sección`}>
      <span className="training-evolution__card-title">{title}</span>
      <strong>{light && (() => { const Icon = ICON[light]; return <Icon {...icon} />; })()}{value}</strong>
      <small>{detail}</small>
    </button>
  );
}

export function TrainingEvolution({ studentId, studentName }: { studentId: string; studentName: string }) {
  const [period, setPeriod] = useState<EvolutionPeriod>('12w');
  const [groupBy, setGroupBy] = useState<EvolutionGrouping>('week');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [data, setData] = useState<Evolution | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const root = useRef<HTMLElement>(null);
  const name = firstName(studentName);

  useEffect(() => {
    let active = true;
    setError(false);
    getTrainingEvolution(studentId, { period, groupBy, muscleGroup })
      .then((result) => { if (active) setData(result); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [studentId, period, groupBy, muscleGroup]);

  const go = (id: string) => root.current?.querySelector(`#${id}-${studentId}`)?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start',
  });

  if (error) return <section className="training-evolution" role="alert"><h3>Progreso de {name}</h3><p>No pudimos cargar el progreso de este alumno. Probá de nuevo más tarde.</p></section>;
  if (!data) return <section className="training-evolution" aria-busy="true"><h3>Progreso de {name}</h3><p>Cargando progreso…</p></section>;

  const { summary } = data;
  const range = data.period.start ? formatRange(data.period.start, data.period.end) : `hasta ${formatRange(data.period.end, data.period.end)}`;
  const exercises = sortByStatus(data.exercises);
  const current = exercises.find((item) => item.exercise_id === selected) ?? exercises.find((item) => item.metric !== 'none') ?? null;
  const counts = statusCounts(exercises);
  const records = recentRecordCount(exercises, data.period.end);
  const trend = summary.effort.trend ? TREND_LABELS[summary.effort.trend as keyof typeof TREND_LABELS] : null;
  const missed = data.adherence.filter((week) => !week.is_partial && week.completed === 0).length;
  const effortMessage = summary.effort.message_key ? EFFORT_MESSAGES[summary.effort.message_key] : null;

  const controls = (
    <div className="training-evolution__controls">
      <label>Período
        <select value={period} onChange={(event) => setPeriod(event.target.value as EvolutionPeriod)}>
          {Object.entries(EVOLUTION_PERIODS).map(([key, label]) => <option key={key} value={key}>{label as string}</option>)}
        </select>
        <small>{range}</small>
      </label>
      <label>Agrupar
        <select value={groupBy} onChange={(event) => setGroupBy(event.target.value as EvolutionGrouping)}>
          {Object.entries(EVOLUTION_GROUPINGS).map(([key, label]) => <option key={key} value={key}>{label as string}</option>)}
        </select>
      </label>
      <label>Grupo muscular
        <select value={muscleGroup} onChange={(event) => { setMuscleGroup(event.target.value); setSelected(null); }}>
          <option value="">Todos</option>
          {data.muscle_groups.map((group) => <option key={group} value={group}>{group}</option>)}
        </select>
      </label>
    </div>
  );

  if (!data.has_sessions) {
    return <section className="training-evolution"><h3>Progreso de {name}</h3>{controls}<p>{name} todavía no registró entrenamientos.</p></section>;
  }

  return (
    <section className="training-evolution" ref={root}>
      <h3>Progreso de {name}</h3>
      {controls}
      <div className="training-evolution__cards">
        <Card title="Progreso" value={`${summary.progress.improving} de ${summary.progress.with_data}`} detail="ejercicios mejorando"
          light={summary.progress.status} target="evo-progress" onGo={go} />
        <Card title="Adherencia" value={summary.adherence.pct === null ? '—' : `${summary.adherence.pct} %`}
          detail={`${summary.adherence.completed_sessions} de ${summary.adherence.scheduled_sessions} sesiones`} light={summary.adherence.status} target="evo-adherence" onGo={go} />
        <Card title="Esfuerzo" value={summary.effort.avg_rpe_last_4 === null ? '—' : `RPE ${formatNumber(summary.effort.avg_rpe_last_4)}`}
          detail={trend ? `tendencia ${trend}` : 'sin reportes'} light={summary.effort.status} target="evo-effort" onGo={go} />
        <Card title="Para revisar" value={String(summary.to_review.count)} detail={summary.to_review.count ? 'puntos' : 'nada pendiente'}
          light={summary.to_review.status} target="evo-review" onGo={go} />
      </div>

      <section id={`evo-progress-${studentId}`} aria-labelledby={`evo-progress-h-${studentId}`}>
        <h4 id={`evo-progress-h-${studentId}`}>¿Está progresando?</h4>
        {exercises.length === 0 ? <p>No hay ejercicios{muscleGroup ? ` de ${muscleGroup}` : ''} en este período.</p> : (
          <>
            <p>
              {counts.progressing} {counts.progressing === 1 ? 'ejercicio progresa' : 'ejercicios progresan'}, {counts.stalled} estancado{counts.stalled === 1 ? '' : 's'}, {counts.declined} {counts.declined === 1 ? 'bajó' : 'bajaron'}
              {records > 0 && <> · <Trophy {...icon} /> {records} récord{records === 1 ? '' : 's'} esta semana</>}.
            </p>
            <div className="training-evolution__table-wrap">
              <table className="training-evolution__table">
                <caption className="training-evolution__sr">Progreso por ejercicio, ordenado por lo que requiere atención</caption>
                <thead><tr><th>Ejercicio</th><th>Inicio</th><th>Actual</th><th>Cambio</th><th>Estado</th><th>Última mejora</th></tr></thead>
                <tbody>
                  {exercises.map((item) => (
                    <tr key={item.exercise_id} className={current?.exercise_id === item.exercise_id ? 'is-selected' : undefined}>
                      <th scope="row">
                        {item.metric === 'none' ? item.name : (
                          <button type="button" className="training-evolution__link" onClick={() => setSelected(item.exercise_id)}>{item.name}</button>
                        )}
                        <small>{item.muscle_group}</small>
                      </th>
                      <td>{formatSet(item.start)}</td><td>{formatSet(item.current)}</td><td>{formatChange(item.change_pct)}</td>
                      <td><span className={`training-evolution__badge training-evolution__badge--${item.status}`}>{(() => { const Icon = STATUS_ICON[item.status as keyof typeof STATUS_ICON]; return Icon ? <Icon {...icon} /> : null; })()}{STATUS_LABELS[item.status]}</span></td>
                      <td>{item.last_improvement ? <>{item.last_improvement.is_pr && <Trophy {...icon} aria-hidden={false} aria-label="Récord personal" role="img" />}{formatAgo(item.last_improvement.date, data.period.end)}</> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {current && current.points.length > 0 && (
              <figure>
                <figcaption>{current.name}: {current.metric === 'max_weight' ? 'mejor serie (kg)' : 'máximo de repeticiones'} por {groupBy === 'week' ? 'semana' : 'entrenamiento'}</figcaption>
                <ExerciseChart points={current.points} groupBy={groupBy} kind={current.metric as 'max_weight' | 'max_reps'}
                  ariaLabel={`${current.name}: de ${formatSet(current.start)} a ${formatSet(current.current)}, ${STATUS_LABELS[current.status]}`} />
                <Values head={['Fecha', 'Serie', 'Objetivo (kg)', 'RPE']} rows={current.points.map((p) => [formatRange(p.period_start, groupBy === 'session' ? p.period_start : p.period_end), current.metric === 'max_weight' ? formatSet({ weight: p.weight, reps: p.reps }) : `${p.reps} reps`, p.target_weight ?? '—', p.rpe ?? '—'])} />
                <Legend items={[
                  ['line', 'Mejor serie de cada período'], ['dot', 'Período completo'], ['dashed', 'Período en curso: todavía incompleto'],
                  ['dotted', 'Peso objetivo programado'], ['ring', 'Récord personal vigente'],
                ]} />
              </figure>
            )}
          </>
        )}
      </section>

      <section id={`evo-adherence-${studentId}`} aria-labelledby={`evo-adherence-h-${studentId}`}>
        <h4 id={`evo-adherence-h-${studentId}`}>¿Está entrenando lo que le programé?</h4>
        <p>
          {summary.adherence.pct === null ? 'Todavía no hay semanas completas para medir.' : `Hizo ${summary.adherence.completed_sessions} de ${summary.adherence.scheduled_sessions} sesiones (${summary.adherence.pct} %)`}
          {summary.adherence.sets_completion_pct !== null && ` · completó el ${summary.adherence.sets_completion_pct} % de las series programadas`}
          {missed > 0 && ` · ${missed} semana${missed === 1 ? '' : 's'} sin entrenar`}.
        </p>
        <figure>
          <figcaption>Sesiones por semana</figcaption>
          <AdherenceChart weeks={data.adherence} ariaLabel={`Adherencia: ${summary.adherence.completed_sessions} de ${summary.adherence.scheduled_sessions} sesiones programadas`} />
          <Values head={['Semana', 'Realizadas', 'Programadas']} rows={data.adherence.map((w) => [formatRange(w.period_start, w.period_end) + (w.is_partial ? ' (en curso)' : ''), w.completed, w.scheduled])} />
          <Legend items={[
            ['bar-blue', 'Sesiones realizadas'], ['bar-gray', 'Sesiones programadas'], ['bar-red', 'Semana sin entrenar'], ['bar-partial', 'Semana en curso'],
          ]} />
        </figure>
        {data.most_skipped.length > 0 && (
          <>
            <h5>Ejercicios más salteados</h5>
            <ul>{data.most_skipped.map((item) => (
              <li key={item.exercise_id}>{item.name}: {item.completion_pct} % de las series{item.main_reason === 'replacement_requested' ? ' · pidió reemplazo' : ''}</li>
            ))}</ul>
          </>
        )}
      </section>

      <section id={`evo-effort-${studentId}`} aria-labelledby={`evo-effort-h-${studentId}`}>
        <h4 id={`evo-effort-h-${studentId}`}>¿Cómo le está costando?</h4>
        <p>{effortMessage ?? (summary.effort.avg_rpe_last_4 === null ? 'Sin reportes de esfuerzo en este período.' : 'Esfuerzo dentro de lo esperado.')}</p>
        {data.rpe.length > 0 && (
          <figure>
            <figcaption>RPE por {groupBy === 'week' ? 'semana' : 'entrenamiento'}</figcaption>
            <RpeChart points={data.rpe} groupBy={groupBy} ariaLabel={`RPE promedio de las últimas sesiones: ${summary.effort.avg_rpe_last_4 ?? 'sin datos'}`} />
            <Values head={['Fecha', 'RPE', 'Devolución']} rows={data.rpe.map((p) => [formatRange(p.period_start, groupBy === 'session' ? p.period_start : p.period_end), p.has_report ? formatNumber(p.rpe as number) : 'sin reporte', p.trainer_feedback ?? '—'])} />
            <Legend items={[
              ['line', 'RPE (esfuerzo percibido)'], ['band', 'Zona recomendada: RPE 6–8'], ['cross', 'Sesión sin reporte'], ['hollow', 'Período en curso'],
            ]} />
          </figure>
        )}
      </section>

      <section id={`evo-review-${studentId}`} aria-labelledby={`evo-review-h-${studentId}`}>
        <h4 id={`evo-review-h-${studentId}`}>¿Qué tengo que ajustar?</h4>
        {data.to_review.length === 0 ? <p><Check {...icon} /> Nada para ajustar por ahora</p> : (
          <ul className="training-evolution__review">{data.to_review.map((item, index) => (
            <li key={`${item.type}-${item.exercise_id ?? index}-${index}`}><span className="training-evolution__badge">{REVIEW_HINT[item.type]}</span> {item.label}</li>
          ))}</ul>
        )}
        {data.sets_by_muscle_group.length > 0 && (
          <figure>
            <figcaption>Series por semana y grupo muscular (hechas / programadas)</figcaption>
            <SetsByGroupChart groups={data.sets_by_muscle_group} ariaLabel="Series semanales completadas contra programadas por grupo muscular" />
            <Legend items={[['bar-blue', 'Series hechas por semana (promedio)'], ['mark', 'Series programadas por semana']]} />
          </figure>
        )}
      </section>
    </section>
  );
}
