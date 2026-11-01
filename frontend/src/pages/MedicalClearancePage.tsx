import axios from 'axios';
import { ArrowLeft, CheckCircle2, Download, FileText, Upload } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import {
  downloadMedicalClearance,
  getOwnMedicalClearance,
  uploadMedicalClearance,
} from '../services/medicalClearanceService';
import { getOwnStudentProfile } from '../services/studentService';
import type { MedicalClearance } from '../types/student';

const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export function MedicalClearancePage() {
  const [clearance, setClearance] = useState<MedicalClearance | null>(null);
  const [studentProfileId, setStudentProfileId] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [issueDate, setIssueDate] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getOwnStudentProfile(), getOwnMedicalClearance()])
      .then(([profile, currentClearance]) => {
        setStudentProfileId(profile.id);
        setClearance(currentClearance);
      })
      .catch(() => setError('No pudimos cargar la información de tu apto médico.'))
      .finally(() => setLoading(false));
  }, []);

  function handleFileSelection(event: React.ChangeEvent<HTMLInputElement>) {
    setError('');
    setMessage('');
    const file = event.target.files?.[0];
    if (!file) {
      setSelectedFile(null);
      return;
    }

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError('Formato no soportado. Solo podés subir archivos PDF, JPG o PNG.');
      setSelectedFile(null);
      event.target.value = '';
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError('El archivo supera el tamaño máximo permitido de 10 MB.');
      setSelectedFile(null);
      event.target.value = '';
      return;
    }

    if (file.size === 0) {
      setError('El archivo seleccionado está vacío.');
      setSelectedFile(null);
      event.target.value = '';
      return;
    }

    setSelectedFile(file);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError('Por favor, seleccioná un archivo de certificado médico.');
      return;
    }
    if (!issueDate) {
      setError('Por favor, indicá la fecha de emisión del certificado.');
      return;
    }

    setSaving(true);
    setError('');
    setMessage('');

    try {
      const updated = await uploadMedicalClearance(selectedFile, issueDate);
      setClearance(updated);
      setSelectedFile(null);
      setIssueDate('');
      setMessage('Certificado de apto médico cargado exitosamente.');
      // reset file input element if present
      const fileInput = document.getElementById('medical-clearance-file') as HTMLInputElement | null;
      if (fileInput) fileInput.value = '';
    } catch (caught) {
      if (axios.isAxiosError(caught) && caught.response?.data?.detail) {
        setError(typeof caught.response.data.detail === 'string' ? caught.response.data.detail : 'No se pudo subir el certificado.');
      } else {
        setError('Ocurrió un error al subir el certificado. Intentá nuevamente.');
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload() {
    if (!studentProfileId || !clearance) return;
    setDownloading(true);
    try {
      await downloadMedicalClearance(studentProfileId, clearance.original_filename);
    } catch {
      setError('No pudimos descargar el archivo del certificado.');
    } finally {
      setDownloading(false);
    }
  }

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link className="profile-back" to={ROUTES.studentHome}>
          <ArrowLeft size={18} /> Volver al inicio
        </Link>
      </header>
      <section className="profile-card">
        <div className="profile-intro">
          <h1>Certificado de Apto Médico</h1>
          <p>
            Cargá tu certificado médico o apto físico en formato PDF o imagen. El archivo reside en
            almacenamiento protegido y solo podrá ser consultado por vos y tus entrenadores autorizados.
          </p>
        </div>

        {loading ? (
          <p>Cargando información del certificado…</p>
        ) : (
          <div className="profile-form">
            {clearance ? (
              <div className="medical-clearance-card">
                <div className="medical-clearance-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={22} color="#173a32" />
                    <strong>{clearance.original_filename}</strong>
                  </div>
                  <span className="medical-clearance-badge">
                    <CheckCircle2 size={16} /> Vigente
                  </span>
                </div>
                <div className="medical-clearance-details">
                  <p><strong>Fecha de emisión:</strong> {clearance.issue_date}</p>
                  <p><strong>Subido el:</strong> {new Date(clearance.created_at).toLocaleDateString('es-AR')}</p>
                  <p><strong>Tamaño:</strong> {(clearance.file_size_bytes / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  type="button"
                  className="medical-clearance-download-btn"
                  onClick={handleDownload}
                  disabled={downloading}
                >
                  <Download size={18} /> {downloading ? 'Descargando…' : 'Descargar certificado actual'}
                </button>
              </div>
            ) : (
              <p style={{ color: '#556c5e', margin: '0 0 16px' }}>
                Todavía no tenés un certificado de apto médico cargado.
              </p>
            )}

            <form onSubmit={handleSubmit} className="medical-clearance-upload-box">
              <h2 style={{ fontSize: '1.15rem', color: '#173a32', margin: '8px 0 4px' }}>
                {clearance ? 'Actualizar o subir nuevo certificado' : 'Subir certificado'}
              </h2>
              <p className="medical-clearance-notice">
                Formatos permitidos: PDF, JPG, PNG (máx. 10 MB).
                {clearance && ' Al subir uno nuevo, reemplazará al actual como vigente y el anterior se archivará.'}
              </p>

              <label htmlFor="medical-clearance-file">
                Archivo del certificado
                <input
                  id="medical-clearance-file"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="medical-clearance-file-input"
                  onChange={handleFileSelection}
                />
              </label>

              <label htmlFor="medical-clearance-date">
                Fecha de emisión
                <input
                  id="medical-clearance-date"
                  type="date"
                  value={issueDate}
                  onChange={(e) => { setError(''); setIssueDate(e.target.value); }}
                />
              </label>

              {error && <p className="form-alert" role="alert">{error}</p>}
              {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}

              <button className="profile-save" type="submit" disabled={saving || !selectedFile || !issueDate}>
                <Upload size={18} /> {saving ? 'Subiendo…' : 'Subir certificado'}
              </button>
            </form>
          </div>
        )}
      </section>
    </main>
  );
}
