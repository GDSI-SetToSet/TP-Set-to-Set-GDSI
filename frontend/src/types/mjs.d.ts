declare module '*.mjs' {
  export function filterStudentsByName<T extends { student_name: string }>(
    students: T[],
    search: string,
  ): T[];
}
