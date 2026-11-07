import { ArrowLeft, Video, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getAssignedStudentRoutine } from '../services/routineTemplateService';
import type { RoutineTemplate } from '../types/routineTemplate';
import '../styles/student-daily-routine-layout.css';

export function StudentRoutinesPage() {
  const [routine, setRoutine] = useState<RoutineTemplate | null>(null);
  const [selectedDayId, setSelectedDayId] = useState('');
  const [openVideoExerciseId, setOpenVideoExerciseId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getAssignedStudentRoutine()
      .then((assigned) => {
        setRoutine(assigned);
        setSelectedDayId(assigned?.days[0]?.id ?? '');
      })
      .catch(() => setError('No pudimos cargar tu rutina. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando tu rutina…</main>;

  const selectedDay = routine?.days.find((day) => day.id === selectedDayId) ?? routine?.days[0];
  const totalDuration = selectedDay?.blocks.reduce((total, block) => total + (block.estimated_duration_minutes ?? 0), 0) ?? 0;

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card student-daily-routine">
        <div className="profile-heading">
          <span>ESPACIO DEL ALUMNO</span>
          <h1>Rutina del día</h1>
          <p>Consultá los ejercicios y tiempos de la rutina que te asignó tu entrenador.</p>
        </div>

        {error ? (
          <p className="form-alert" role="alert">{error}</p>
        ) : !routine ? (
          <div className="student-daily-routine__empty" role="status">
            <h2>No tenés una rutina asignada</h2>
            <p>Cuando tu entrenador te asigne una rutina, vas a poder consultarla acá.</p>
          </div>
        ) : (
          <>
            <div className="student-daily-routine__summary">
              <div>
                <span>Rutina asignada</span>
                <h2>{routine.name}</h2>
              </div>
              <label htmlFor="routine-day">Día de la rutina
                <select
                  id="routine-day"
                  className="exercise-select"
                  value={selectedDay?.id ?? ''}
                  onChange={(event) => {
                    setSelectedDayId(event.target.value);
                    setOpenVideoExerciseId(null);
                  }}
                >
                  {routine.days.map((day) => <option key={day.id} value={day.id}>{day.name}</option>)}
                </select>
              </label>
              <strong>Duración estimada: {selectedDay?.blocks.some((block) => block.estimated_duration_minutes === null) ? 'Parcial' : `${totalDuration} min`}</strong>
            </div>

            {selectedDay?.blocks.map((block) => (
              <section key={block.id} className="student-daily-routine__block">
                <header>
                  <h3>{block.name}</h3>
                  <span>{block.estimated_duration_minutes === null ? 'Duración sin configurar' : `${block.estimated_duration_minutes} min estimados`}</span>
                </header>
                <ol>
                  {block.exercises.map((item) => (
                    <li key={item.id}>
                      <div className="student-routine-exercise__summary">
                        <h4>{item.exercise.name}</h4>
                        <p>{item.exercise.description}</p>
                        <span className="student-routine-exercise__muscle">Músculo principal: {item.exercise.target_muscle_group}</span>
                      </div>
                      <p>{item.sets} series · {item.reps} repeticiones</p>
                      <p>{item.target_weight_kg === null ? 'Sin carga indicada' : `${item.target_weight_kg} kg`} · {item.rest_seconds} s de descanso</p>
                      {(item.exercise.technical_cues || item.exercise.breathing_cues) && (
                        <dl className="student-routine-exercise__cues">
                          {item.exercise.technical_cues && (
                            <>
                              <dt>Notas técnicas y de postura</dt>
                              <dd>{item.exercise.technical_cues}</dd>
                            </>
                          )}
                          {item.exercise.breathing_cues && (
                            <>
                              <dt>Claves de respiración</dt>
                              <dd>{item.exercise.breathing_cues}</dd>
                            </>
                          )}
                        </dl>
                      )}
                      {item.exercise.video_url && (
                        <div className="student-routine-exercise__media">
                          <button
                            className="student-routine-exercise__video-toggle"
                            type="button"
                            aria-expanded={openVideoExerciseId === item.id}
                            aria-controls={`exercise-video-${item.id}`}
                            onClick={() => setOpenVideoExerciseId((current) => current === item.id ? null : item.id)}
                          >
                            {openVideoExerciseId === item.id ? <X size={18} /> : <Video size={18} />}
                            {openVideoExerciseId === item.id ? 'Ocultar video' : 'Ver video técnico'}
                          </button>
                          {openVideoExerciseId === item.id && (
                            <iframe
                              id={`exercise-video-${item.id}`}
                              className="exercise-video"
                              src={item.exercise.video_url}
                              title={`Video técnico de ${item.exercise.name}`}
                              loading="lazy"
                              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                              allowFullScreen
                              referrerPolicy="strict-origin-when-cross-origin"
                            />
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </>
        )}
      </section>
    </main>
  );
}
