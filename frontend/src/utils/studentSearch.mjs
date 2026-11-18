function normalizeSearchText(value) {
  return value
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLocaleLowerCase('es-AR')
    .trim();
}

export function filterStudentsByName(students, search) {
  const normalizedSearch = normalizeSearchText(search);
  if (!normalizedSearch) return students;

  return students.filter((student) => normalizeSearchText(student.student_name).includes(normalizedSearch));
}
