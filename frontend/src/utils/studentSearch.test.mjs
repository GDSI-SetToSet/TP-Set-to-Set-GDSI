import assert from 'node:assert/strict';
import test from 'node:test';
import { filterStudentsByName } from './studentSearch.mjs';

const activeStudents = [
  { student_id: '1', student_name: 'Álvaro García', routine_template_id: 'routine-1' },
  { student_id: '2', student_name: 'María López', routine_template_id: null },
];
const studentsIncludingInactive = [
  ...activeStudents,
  { student_id: '3', student_name: 'Álvaro García', routine_template_id: 'terminated-routine' },
];

test('encuentra un alumno por nombre, apellido o nombre completo', () => {
  assert.deepEqual(filterStudentsByName(activeStudents, 'álvaro').map((student) => student.student_id), ['1']);
  assert.deepEqual(filterStudentsByName(activeStudents, 'López').map((student) => student.student_id), ['2']);
  assert.deepEqual(filterStudentsByName(activeStudents, 'Álvaro García').map((student) => student.student_id), ['1']);
});

test('la búsqueda ignora mayúsculas y acentos', () => {
  assert.deepEqual(filterStudentsByName(activeStudents, 'ALVARO GARCIA').map((student) => student.student_id), ['1']);
});

test('una búsqueda inexistente no devuelve alumnos', () => {
  assert.deepEqual(filterStudentsByName(activeStudents, 'Pedro Ruiz'), []);
});

test('una búsqueda vacía devuelve todos los alumnos activos', () => {
  assert.deepEqual(filterStudentsByName(activeStudents, '   '), activeStudents);
});

test('el filtro solo opera sobre la colección de alumnos activos y conserva sus acciones', () => {
  const filtered = filterStudentsByName(activeStudents, 'María');
  assert.deepEqual(filtered, [{ student_id: '2', student_name: 'María López', routine_template_id: null }]);
});

test('no devuelve alumnos no activos cuando no forman parte de la colección cargada', () => {
  const activeOnly = studentsIncludingInactive.filter((student) => student.student_id !== '3');
  assert.deepEqual(filterStudentsByName(activeOnly, 'Álvaro'), [
    { student_id: '1', student_name: 'Álvaro García', routine_template_id: 'routine-1' },
  ]);
});
