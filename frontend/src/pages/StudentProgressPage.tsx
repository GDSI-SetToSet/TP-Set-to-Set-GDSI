import { ArrowLeft } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AchievementCelebration } from '../components/AchievementCelebration';
import { AchievementsSection } from '../components/AchievementsSection';
import { StreakCard } from '../components/StreakCard';
import { ConsistencyChart, LoadChart, LoadChartLegend } from '../components/StudentProgressCharts';
import { ROUTES } from '../constants/routes';
import { getStudentAchievements } from '../services/achievementService';
import { getStudentProgress, getStudentStreak } from '../services/studentProgressService';
import type { AchievementsOverview } from '../types/achievement';
import type { ProgressPeriodKey, StudentProgress, TrainingStreak } from '../types/studentProgress';
import {
  PERIOD_LABELS, PROGRESS_HELP, consistencyLine, weeksText, exercisePhrase, formatMark, kg, markToBeat, recordLine, sortExercises, summaryCards,
} from '../utils/studentProgress.mjs';
import { formatDay } from '../utils/trainingEvolution.mjs';
import '../styles/training-evolution.css';

const goTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

export function StudentProgressPage() {
  const [period, setPeriod] = useState<ProgressPeriodKey>('12w');
  const [group, setGroup] = useState('');
  const [data, setData] = useState<StudentProgress | null>(null);
  const [groups, setGroups] = useState<string[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [streak, setStreak] = useState<TrainingStreak | null>(null);
  const [achievements, setAchievements] = useState<AchievementsOverview | null>(null);

  useEffect(() => {
    let active = true;
    getStudentStreak().then((loaded) => { if (active) setStreak(loaded); }).catch(() => undefined);
    getStudentAchievements().then((loaded) => { if (active) setAchievements(loaded); }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getStudentProgress({ period, muscle_group: group || undefined })
      .then((result) => {
        if (!active) return;
        setData(result);
        if (!group) setGroups(result.muscle_groups);
      })
      .catch(() => active && setError('No pudimos cargar tu evolución. Intentá nuevamente en un momento.'))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [period, group]);

  const changePeriod = (value: ProgressPeriodKey) => {
    setPeriod(value);
    setGroup('');
    setSelected('');
  };
  const exercises = data ? sortExercises(data.exercises) : [];
  const chosen = exercises.find((item) => item.exercise_id === selected);
  const next = data?.next_session;
  const consistency = data ? consistencyLine(data.consistency) : null;
  const toBeat = data && !data.records.length ? markToBeat(data.exercises) : null;

  return (
    <main className="profile-shell student-progress-page">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>
      <section className="profile-card training-evolution">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Mi evolución</h1>
        </div>
        {streak && <StreakCard streak={streak} />}
        {achievements && (
          <>
            <AchievementCelebration
              preloadedItems={achievements.unlocked}
              onDismissed={(celebratedIds) => {
                setAchievements((current) => (current ? {
                  ...current,
                  unlocked: current.unlocked.map((item) => (
                    celebratedIds.includes(item.id)
                      ? { ...item, pending_celebration: false }
                      : item
                  )),
                } : current));
              }}
            />
            <AchievementsSection overview={achievements} />
          </>
        )}

        <div className="training-evolution__controls">
          <label>Período
            <select value={period} onChange={(e) => changePeriod(e.target.value as ProgressPeriodKey)}>
              {Object.entries(PERIOD_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>
          {data?.period.start && <small>{formatDay(data.period.start)} – {formatDay(data.period.end)}</small>}
        </div>

        {loading && !data && <p role="status">Cargando tu evolución…</p>}
        {error && <p role="alert" className="profile-error">{error}</p>}

        {!error && data && !data.has_sessions && (
          <>
            <p role="status">Todavía no registraste entrenamientos. Cuando termines tu primera sesión, vas a ver tu progreso acá.</p>
            <Link className="student-evolution__cta" to={ROUTES.studentRoutines}>Ver rutina del día</Link>
          </>
        )}

        {!error && data?.has_sessions && (
          <div aria-busy={loading} style={{ opacity: loading ? 0.6 : 1 }}>
            <div className="training-evolution__cards">
              {summaryCards(data.summary).map((card) => (
                <button key={card.id} type="button" className="training-evolution__card" onClick={() => goTo(card.id)}>
                  <span className="training-evolution__card-title">{card.title}</span>
                  <strong>{card.text}</strong>
                </button>
              ))}
            </div>

            <h4 id="mejorando">¿Estoy mejorando?</h4>
            <div className="student-evolution__chips" role="group" aria-label="Grupo muscular">
              {['', ...groups].map((name) => (
                <button key={name || 'all'} type="button" aria-pressed={group === name} onClick={() => { setGroup(name); setSelected(''); }}>{name || 'Todos'}</button>
              ))}
            </div>
            {exercises.length === 0
              ? <p role="status">{group ? `No hiciste ejercicios de ${group} en este período` : 'No registraste ejercicios en este período'}</p>
              : (
                <ul className="student-evolution__list">
                  {exercises.map((item) => (
                    <li key={item.exercise_id}>
                      <button type="button" aria-pressed={item.exercise_id === chosen?.exercise_id} onClick={() => setSelected(item.exercise_id === selected ? '' : item.exercise_id)}>
                        <strong>{item.name}</strong>: {exercisePhrase(item)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            {chosen && (chosen.points.length > 1
              ? <figure><figcaption>{chosen.name} · {chosen.metric === 'max_weight' ? 'mejor peso de cada sesión' : 'mejores repeticiones de cada sesión'}</figcaption><div className="training-evolution__chart-scroll" role="region" aria-label={`Gráfico de evolución de ${chosen.name}`}><LoadChart exercise={chosen} /></div><LoadChartLegend exercise={chosen} /></figure>
              : <p role="status">Con la próxima sesión de {chosen.name} vas a ver tu gráfico.</p>)}
            <details>
              <summary>¿Cómo se mide el progreso?</summary>
              <p>{PROGRESS_HELP}</p>
            </details>

            <h4 id="constante">¿Estoy siendo constante?</h4>
            {data.consistency.length === 0
              ? <p>Todavía no tenés sesiones acordadas</p>
              : (
                <>
                  {consistency && <p><strong>{consistency}</strong></p>}
                  {data.summary.streak.best_weeks > 0 && <p>Racha actual: {weeksText(data.summary.streak.current_weeks)} · Tu mejor racha: {weeksText(data.summary.streak.best_weeks)}</p>}
                  <figure><figcaption>Sesiones por semana</figcaption><div className="training-evolution__chart-scroll" role="region" aria-label="Gráfico de sesiones por semana"><ConsistencyChart weeks={data.consistency} /></div><ul className="training-evolution__legend training-evolution__legend--student-chart" aria-label="Referencias del gráfico"><li><span className="training-evolution__chart-key training-evolution__chart-key--solid" aria-hidden="true" />Sesiones realizadas</li><li><span className="training-evolution__chart-key training-evolution__chart-key--planned" aria-hidden="true" />Sesiones acordadas</li><li><span className="training-evolution__chart-key training-evolution__chart-key--current" aria-hidden="true" />Semana en curso</li><li><span className="training-evolution__chart-key training-evolution__chart-key--check" aria-hidden="true">✓</span>Objetivo semanal cumplido</li></ul></figure>
                </>
              )}

            <h4 id="logros">¿Qué logré?</h4>
            {data.records.length > 0
              ? (
                <ol className="student-evolution__records">
                  {data.records.map((record) => (
                    <li key={`${record.exercise_id}-${record.date}`}>{formatDay(record.date)} · <strong>{record.name}</strong> · {recordLine(record)}</li>
                  ))}
                </ol>
              )
              : <p>Todavía no tenés récords en este período.{toBeat && ` Tu marca a superar en ${toBeat.name} es ${toBeat.mark}.`}</p>}
            {data.new_exercises.length > 0 && <p>Empezaste {data.new_exercises.length} {data.new_exercises.length === 1 ? 'ejercicio nuevo' : 'ejercicios nuevos'}: {data.new_exercises.map((n) => n.name).join(', ')}.</p>}

            <h4 id="ahora">¿Qué me toca ahora?</h4>
            {!next
              ? <p>No tenés sesiones programadas todavía. Tu entrenador te va a avisar cuando cargue tu próxima rutina.</p>
              : (
                <>
                  {next.trainer_feedback && <p role="note"><strong>Tu entrenador:</strong> {next.trainer_feedback}</p>}
                  <div className="training-evolution__table-wrap">
                    <table className="training-evolution__table training-evolution__table--student-next">
                      <caption>{next.day_name}</caption>
                      <thead><tr><th>Ejercicio</th><th>La última vez</th><th>Próxima sesión</th></tr></thead>
                      <tbody>
                        {next.exercises.map((e) => (
                          <tr key={e.exercise_id}>
                            <td data-label="Ejercicio">{e.name}{e.adjusted_by_trainer && <small>Ajustado por tu entrenador{e.trainer_note && `: ${e.trainer_note}`}</small>}</td>
                            <td data-label="La última vez">{e.last ? formatMark(e.last) : '— (primera vez)'}</td>
                            <td data-label="Próxima sesión"><strong>{e.target_weight ? `${kg(e.target_weight)} × ${e.reps}` : `${e.reps} repeticiones`}</strong> · {e.sets} series</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            <Link className="student-evolution__cta" to={ROUTES.studentRoutines}>Ver rutina del día</Link>
          </div>
        )}
      </section>
    </main>
  );
}
