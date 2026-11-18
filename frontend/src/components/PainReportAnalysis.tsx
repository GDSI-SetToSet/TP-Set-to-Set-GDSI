import { HeartPulse } from 'lucide-react';
import { useEffect, useState } from 'react';
import { getAllTrainerStudentZoneHistory } from '../services/bodyMapReportService';
import type { BodyMapZoneHistoryItem } from '../types/bodyMapReport';
import { PAIN_GROUPINGS, aggregatePain, groupByReport } from '../utils/painReportAnalysis.mjs';
import type { PainGrouping } from '../utils/painReportAnalysis.mjs';
import '../styles/pain-report-analysis.css';

const INTENSITY_LABELS = { DISCOMFORT: 'Molestia', PAIN: 'Dolor', NORMAL: 'Normal' } as const;
const CONTEXT_LABELS = { IN_EXERCISE: 'Durante el ejercicio', POST_SESSION: 'Post-sesión' } as const;
const VISIBLE_REPORTS = 10;

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

/** US-28: reportes de molestia/dolor del alumno y su distribución por zona, grupo muscular, ejercicio o día. */
export function PainReportAnalysis({ studentId }: { studentId: string }) {
  const [items, setItems] = useState<BodyMapZoneHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [grouping, setGrouping] = useState<PainGrouping>('zone');
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    getAllTrainerStudentZoneHistory(studentId)
      .then((loaded) => { if (!cancelled) setItems(loaded); })
      .catch(() => { if (!cancelled) setError('No pudimos cargar los reportes de molestias de este alumno.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [studentId]);

  const reports = groupByReport(items);
  const groups = aggregatePain(items, grouping);
  const maxTotal = Math.max(1, ...groups.map((group) => group.total));
  const visibleReports = showAll ? reports : reports.slice(0, VISIBLE_REPORTS);

  return (
    <article className="pain-analysis" aria-labelledby={`pain-analysis-${studentId}`}>
      <h3 id={`pain-analysis-${studentId}`}><HeartPulse size={18} aria-hidden="true" />Molestias y dolor reportados</h3>

      {loading ? (
        <p role="status">Cargando reportes…</p>
      ) : error ? (
        <p className="form-alert" role="alert">{error}</p>
      ) : reports.length === 0 ? (
        <p>El alumno no reportó molestias ni dolor.</p>
      ) : (
        <>
          <div className="pain-analysis__chart">
            <div className="pain-analysis__chart-header">
              <label htmlFor={`pain-grouping-${studentId}`}>Agrupar por</label>
              <select
                id={`pain-grouping-${studentId}`}
                value={grouping}
                onChange={(event) => setGrouping(event.target.value as PainGrouping)}
              >
                {(Object.keys(PAIN_GROUPINGS) as PainGrouping[]).map((key) => (
                  <option key={key} value={key}>{PAIN_GROUPINGS[key]}</option>
                ))}
              </select>
              <span className="pain-analysis__legend" aria-hidden="true">
                <span><i className="is-pain" />Dolor</span>
                <span><i className="is-discomfort" />Molestia</span>
              </span>
            </div>
            <ul className="pain-analysis__bars" aria-label={`Reportes por ${PAIN_GROUPINGS[grouping].toLowerCase()}`}>
              {groups.map((group) => (
                <li key={group.label}>
                  <span className="pain-analysis__bar-label">{group.label}</span>
                  <span
                    className="pain-analysis__bar-track"
                    role="img"
                    aria-label={`${group.label}: ${group.pain} con dolor y ${group.discomfort} con molestia`}
                  >
                    <span className="pain-analysis__bar is-pain" style={{ width: `${(group.pain / maxTotal) * 100}%` }} />
                    <span className="pain-analysis__bar is-discomfort" style={{ width: `${(group.discomfort / maxTotal) * 100}%` }} />
                  </span>
                  <span className="pain-analysis__bar-count">{group.total}</span>
                </li>
              ))}
            </ul>
          </div>

          <h4 className="pain-analysis__subtitle">Reportes ({reports.length})</h4>
          <ul className="pain-analysis__reports">
            {visibleReports.map((report) => (
              <li key={report.report_id}>
                <div className="pain-analysis__report-meta">
                  <time dateTime={report.created_at}>{formatDateTime(report.created_at)}</time>
                  <span>{CONTEXT_LABELS[report.context]}</span>
                </div>
                <p className="pain-analysis__report-source">
                  {report.exercise_name ?? 'Reporte de la sesión'}
                  {report.exercise_muscle_group && ` · ${report.exercise_muscle_group}`}
                  {report.session_day_name && ` · ${report.session_day_name}`}
                </p>
                <ul className="pain-analysis__zones">
                  {report.zones.map((zone) => (
                    <li key={zone.zone} className={zone.intensity === 'PAIN' ? 'is-pain' : 'is-discomfort'}>
                      {zone.zone_display}: {INTENSITY_LABELS[zone.intensity]}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
          {reports.length > VISIBLE_REPORTS && (
            <button type="button" className="pain-analysis__more" onClick={() => setShowAll((value) => !value)}>
              {showAll ? 'Ver menos' : `Ver los ${reports.length} reportes`}
            </button>
          )}
        </>
      )}
    </article>
  );
}
