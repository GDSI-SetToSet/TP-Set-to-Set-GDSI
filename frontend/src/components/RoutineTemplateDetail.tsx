import { EXERCISE_CATEGORIES } from '../types/exercise';
import type { RoutineTemplate } from '../types/routineTemplate';

interface RoutineTemplateDetailProps {
  template: RoutineTemplate;
}

export function RoutineTemplateDetail({ template }: RoutineTemplateDetailProps) {
  return (
    <div className="routine-detail">
      {template.days.map((day) => (
        <section key={day.id} className="routine-detail__day">
          <h4>{day.name}</h4>
          {day.blocks.map((block) => (
            <div key={block.id} className="routine-detail__block">
              <h5>{block.name}</h5>
              <ul>
                {block.exercises.map((item) => (
                  <li key={item.id}>
                    <strong>{item.exercise.name}</strong>
                    <span>{EXERCISE_CATEGORIES[item.exercise.category]} · {item.exercise.target_muscle_group}</span>
                    <span>{item.sets} series · Repeticiones: {item.reps} · {item.rest_seconds} s de descanso</span>
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
