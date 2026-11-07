import { EXERCISE_CATEGORIES, type Exercise } from '../types/exercise';

// Forma común a rutinas genéricas y generadas con IA.
interface DetailBlock {
  id: string;
  name: string;
  estimated_duration_minutes?: number | null;
  exercises: {
    id: string;
    sets: number;
    reps: string;
    rest_seconds: number;
    target_weight_kg?: number | null;
    exercise: Exercise;
  }[];
}

interface RoutineTemplateDetailProps {
  template: { days: { id: string; name: string; blocks: DetailBlock[] }[] };
}

export function RoutineTemplateDetail({ template }: RoutineTemplateDetailProps) {
  return (
    <div className="routine-detail">
      {template.days.map((day) => (
        <section key={day.id} className="routine-detail__day">
          <h4>{day.name}</h4>
          {day.blocks.map((block) => (
            <div key={block.id} className="routine-detail__block">
              <h5>{block.name} · {block.estimated_duration_minutes == null ? 'Duración sin configurar' : `${block.estimated_duration_minutes} min`}</h5>
              <ul>
                {block.exercises.map((item) => (
                  <li key={item.id}>
                    <strong>{item.exercise.name}</strong>
                    <span>{EXERCISE_CATEGORIES[item.exercise.category]} · {item.exercise.target_muscle_group}</span>
                    <span>{item.sets} series · Repeticiones: {item.reps} · {item.rest_seconds} s de descanso</span>
                    <span>Peso objetivo: {item.target_weight_kg == null ? 'Sin carga indicada' : `${item.target_weight_kg} kg`}</span>
                    {item.exercise.video_url && (
                      <iframe
                        className="exercise-video"
                        src={item.exercise.video_url}
                        title={`Video demostrativo de ${item.exercise.name}`}
                        loading="lazy"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowFullScreen
                      />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
