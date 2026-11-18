import assert from 'node:assert/strict';
import test from 'node:test';
import { buildPlanFilterOptions, canFilterByPlan, filterStudentsByPlan } from './studentPlanFilter.mjs';
import { filterStudentsByName } from './studentSearch.mjs';

const basic = { id: 'plan-basic', title: 'Plan Básico', is_active: true };
const premium = { id: 'plan-premium', title: 'Plan Premium', is_active: true };
const archived = { id: 'plan-old', title: 'Plan Viejo', is_active: false };

const students = [
  { student_id: '1', student_name: 'Álvaro García', plan_id: 'plan-basic', plan_title: 'Plan Básico' },
  { student_id: '2', student_name: 'María López', plan_id: 'plan-premium', plan_title: 'Plan Premium' },
  { student_id: '3', student_name: 'Mario Pérez', plan_id: 'plan-basic', plan_title: 'Plan Básico' },
];

test('con un único paquete registrado no se habilita el filtro', () => {
  const singlePlanStudents = students.filter((student) => student.plan_id === 'plan-basic');
  const options = buildPlanFilterOptions(singlePlanStudents, [basic]);
  assert.equal(options.length, 1);
  assert.equal(canFilterByPlan(options), false);
});

test('con más de un paquete registrado se ofrece cada paquete con sus cupos ocupados', () => {
  const options = buildPlanFilterOptions(students, [premium, basic]);
  assert.equal(canFilterByPlan(options), true);
  assert.deepEqual(options, [
    { plan_id: 'plan-basic', title: 'Plan Básico', student_count: 2 },
    { plan_id: 'plan-premium', title: 'Plan Premium', student_count: 1 },
  ]);
});

test('un paquete registrado sin alumnos aparece con cero cupos ocupados', () => {
  const onlyBasicStudents = students.filter((student) => student.plan_id === 'plan-basic');
  const options = buildPlanFilterOptions(onlyBasicStudents, [basic, premium]);
  assert.deepEqual(options.map((option) => [option.plan_id, option.student_count]), [
    ['plan-basic', 2],
    ['plan-premium', 0],
  ]);
});

test('los paquetes archivados solo aparecen si un alumno activo los tiene contratados', () => {
  const withArchived = [...students, { student_id: '4', student_name: 'Lucía Díaz', plan_id: 'plan-old', plan_title: 'Plan Viejo' }];
  assert.deepEqual(buildPlanFilterOptions(students, [basic, premium, archived]).map((o) => o.plan_id), ['plan-basic', 'plan-premium']);
  assert.deepEqual(buildPlanFilterOptions(withArchived, [basic, premium, archived]).map((o) => o.plan_id), ['plan-basic', 'plan-premium', 'plan-old']);
});

test('sin la lista de paquetes se derivan las opciones de los alumnos activos', () => {
  assert.deepEqual(buildPlanFilterOptions(students).map((o) => o.title), ['Plan Básico', 'Plan Premium']);
});

test('filtrar por un paquete muestra solo los alumnos que lo contrataron', () => {
  assert.deepEqual(filterStudentsByPlan(students, 'plan-basic').map((s) => s.student_id), ['1', '3']);
  assert.deepEqual(filterStudentsByPlan(students, 'plan-premium').map((s) => s.student_id), ['2']);
});

test('sin paquete seleccionado se muestran todos los alumnos activos', () => {
  assert.deepEqual(filterStudentsByPlan(students, ''), students);
});

test('el filtro por paquete se combina con la búsqueda por nombre', () => {
  const visible = filterStudentsByName(filterStudentsByPlan(students, 'plan-basic'), 'mario');
  assert.deepEqual(visible.map((s) => s.student_id), ['3']);
});
