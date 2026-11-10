import React, { useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, RotateCw, X } from 'lucide-react';
import { BODY_AREAS, ZONES_ES } from '../constants/bodyAreas';
import type { IntensityLevel, ReportZoneInput } from '../types/bodyMapReport';
import '../styles/body-map.css';

interface Props {
  selectedZones: ReportZoneInput[];
  onChange: (zones: ReportZoneInput[]) => void;
  readOnly?: boolean;
}

const INTENSITY_CONFIG: Record<
  IntensityLevel,
  { label: string; shortDesc: string; className: string; icon: React.ReactNode }
> = {
  NORMAL: {
    label: 'Carga normal',
    shortDesc: 'Fatiga o trabajo muscular habitual',
    className: 'body-map-intensity--normal',
    icon: <CheckCircle size={15} aria-hidden="true" />,
  },
  DISCOMFORT: {
    label: 'Molestia',
    shortDesc: 'Tensión, tirón o sobrecarga leve',
    className: 'body-map-intensity--discomfort',
    icon: <AlertTriangle size={15} aria-hidden="true" />,
  },
  PAIN: {
    label: 'Dolor',
    shortDesc: 'Punzante, agudo o limitante (alerta)',
    className: 'body-map-intensity--pain',
    icon: <AlertCircle size={15} aria-hidden="true" />,
  },
};

// Mapeo anatómico para vistas Anterior y Posterior
const ANTERIOR_ZONES = [
  'Neck',
  'Shoulder',
  'Elbow',
  'Wrist and hand',
  'Hip',
  'Knee',
  'Ankle and foot',
] as const;

const POSTERIOR_ZONES = [
  'Neck',
  'Shoulder',
  'Upper back',
  'Lower back',
  'Hip',
  'Ankle and foot',
] as const;

export function BodyMapSelector({ selectedZones, onChange, readOnly = false }: Props) {
  const [activeView, setActiveView] = useState<'anterior' | 'posterior'>('anterior');
  const [editingZone, setEditingZone] = useState<string | null>(null);

  const zoneMap = new Map<string, IntensityLevel>(
    selectedZones.map((item) => [item.zone, item.intensity])
  );

  const handleToggleZone = (zone: string) => {
    if (readOnly) return;
    if (zoneMap.has(zone)) {
      // Si ya está seleccionada y estamos editándola, la quitamos
      const updated = selectedZones.filter((item) => item.zone !== zone);
      onChange(updated);
      if (editingZone === zone) setEditingZone(null);
    } else {
      // Por defecto entra como Molestia o Carga normal y abre el selector de intensidad
      const updated = [...selectedZones, { zone, intensity: 'DISCOMFORT' as IntensityLevel }];
      onChange(updated);
      setEditingZone(zone);
    }
  };

  const handleChangeIntensity = (zone: string, intensity: IntensityLevel) => {
    if (readOnly) return;
    const updated = selectedZones.map((item) =>
      item.zone === zone ? { ...item, intensity } : item
    );
    onChange(updated);
    setEditingZone(null);
  };

  const handleRemoveZone = (zone: string) => {
    if (readOnly) return;
    onChange(selectedZones.filter((item) => item.zone !== zone));
    if (editingZone === zone) setEditingZone(null);
  };

  const currentViewZones = activeView === 'anterior' ? ANTERIOR_ZONES : POSTERIOR_ZONES;

  return (
    <div className="body-map-selector" role="region" aria-label="Mapa corporal interactivo">
      <div className="body-map-selector__header">
        <div>
          <h4 className="body-map-selector__title">Mapa de sensaciones y dolor</h4>
          <p className="body-map-selector__subtitle">
            Tocá una o más zonas para marcar sensaciones de carga, molestia o dolor.
          </p>
        </div>
        <div className="body-map-selector__view-tabs" role="tablist" aria-label="Vista anatómica">
          <button
            type="button"
            role="tab"
            aria-selected={activeView === 'anterior'}
            className={`body-map-selector__tab ${activeView === 'anterior' ? 'body-map-selector__tab--active' : ''}`}
            onClick={() => setActiveView('anterior')}
          >
            Frente (Anterior)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeView === 'posterior'}
            className={`body-map-selector__tab ${activeView === 'posterior' ? 'body-map-selector__tab--active' : ''}`}
            onClick={() => setActiveView('posterior')}
          >
            Espalda (Posterior)
          </button>
        </div>
      </div>

      <div className="body-map-selector__main">
        {/* Visual Silhouette & Zone Buttons */}
        <div className="body-map-canvas-container">
          <div className="body-map-silhouette-wrapper">
            <svg
              className="body-map-silhouette"
              viewBox="0 0 200 380"
              aria-hidden="true"
              focusable="false"
            >
              {/* Contorno anatómico estilizado */}
              <circle cx="100" cy="35" r="22" className="body-map-svg-outline" />
              <rect x="92" y="57" width="16" height="15" rx="4" className="body-map-svg-outline" />
              {activeView === 'anterior' ? (
                // Vista Frontal (Pecho y torso)
                <path
                  d="M60 72 Q100 80 140 72 L132 170 Q100 175 68 170 Z"
                  className="body-map-svg-outline"
                />
              ) : (
                // Vista Espalda
                <path
                  d="M60 72 Q100 75 140 72 L130 170 Q100 175 70 170 Z"
                  className="body-map-svg-outline"
                />
              )}
              {/* Brazos */}
              <path d="M60 72 L38 140 L28 200" strokeWidth="14" strokeLinecap="round" className="body-map-svg-limb" />
              <path d="M140 72 L162 140 L172 200" strokeWidth="14" strokeLinecap="round" className="body-map-svg-limb" />
              {/* Cadera y Piernas */}
              <path
                d="M68 170 Q100 175 132 170 L126 210 Q100 215 74 210 Z"
                className="body-map-svg-outline"
              />
              <path d="M82 210 L78 285 L74 360" strokeWidth="16" strokeLinecap="round" className="body-map-svg-limb" />
              <path d="M118 210 L122 285 L126 360" strokeWidth="16" strokeLinecap="round" className="body-map-svg-limb" />
            </svg>

            {/* Hotspots interactivos sobre la silueta */}
            <div className="body-map-hotspots" aria-label={`Zonas de la vista ${activeView}`}>
              {currentViewZones.map((zone) => {
                const isSelected = zoneMap.has(zone);
                const intensity = zoneMap.get(zone);
                const intensityStyle = intensity ? INTENSITY_CONFIG[intensity].className : '';
                return (
                  <button
                    key={zone}
                    type="button"
                    aria-pressed={isSelected}
                    className={`body-map-hotspot body-map-hotspot--${zone.toLowerCase().replace(/\s+/g, '-')} ${
                      isSelected ? `body-map-hotspot--selected ${intensityStyle}` : ''
                    }`}
                    onClick={() => handleToggleZone(zone)}
                    disabled={readOnly}
                    title={`${ZONES_ES[zone] ?? zone}${intensity ? ` (${INTENSITY_CONFIG[intensity].label})` : ''}`}
                  >
                    <span className="body-map-hotspot__label">{ZONES_ES[zone] ?? zone}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Panel lateral: Catálogo de botones accesibles y Clasificador de intensidad */}
        <div className="body-map-controls">
          <div className="body-map-controls__section">
            <span className="body-map-controls__label">
              Zonas ({activeView === 'anterior' ? 'Vista frontal' : 'Vista dorsal'}):
            </span>
            <div className="body-map-zone-buttons" role="group">
              {currentViewZones.map((zone) => {
                const isSelected = zoneMap.has(zone);
                const intensity = zoneMap.get(zone);
                return (
                  <button
                    key={zone}
                    type="button"
                    aria-pressed={isSelected}
                    className={`body-map-zone-btn ${
                      isSelected ? `body-map-zone-btn--selected ${intensity ? INTENSITY_CONFIG[intensity].className : ''}` : ''
                    }`}
                    onClick={() => handleToggleZone(zone)}
                    disabled={readOnly}
                  >
                    <span>{ZONES_ES[zone] ?? zone}</span>
                    {isSelected && intensity && (
                      <span className="body-map-zone-btn__badge">
                        {INTENSITY_CONFIG[intensity].icon}
                        {INTENSITY_CONFIG[intensity].label}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Diálogo emergente de asignación de intensidad para la zona en edición */}
          {editingZone && zoneMap.has(editingZone) && (
            <div className="body-map-intensity-picker" role="dialog" aria-label={`Clasificar sensación en ${ZONES_ES[editingZone] ?? editingZone}`}>
              <div className="body-map-intensity-picker__header">
                <strong>¿Qué sentís en {ZONES_ES[editingZone] ?? editingZone}?</strong>
                <button
                  type="button"
                  className="body-map-intensity-picker__close"
                  onClick={() => setEditingZone(null)}
                  aria-label="Cerrar selector de sensación"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="body-map-intensity-picker__options">
                {(['NORMAL', 'DISCOMFORT', 'PAIN'] as IntensityLevel[]).map((level) => {
                  const cfg = INTENSITY_CONFIG[level];
                  const isCurrent = zoneMap.get(editingZone) === level;
                  return (
                    <button
                      key={level}
                      type="button"
                      className={`body-map-intensity-btn ${cfg.className} ${
                        isCurrent ? 'body-map-intensity-btn--active' : ''
                      }`}
                      onClick={() => handleChangeIntensity(editingZone, level)}
                    >
                      <span className="body-map-intensity-btn__icon">{cfg.icon}</span>
                      <div className="body-map-intensity-btn__text">
                        <strong>{cfg.label}</strong>
                        <span>{cfg.shortDesc}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Resumen de selecciones */}
          <div className="body-map-summary">
            <div className="body-map-summary__title-row">
              <strong>Zonas reportadas ({selectedZones.length}):</strong>
              {selectedZones.length > 0 && !readOnly && (
                <button
                  type="button"
                  className="body-map-summary__clear-btn"
                  onClick={() => onChange([])}
                >
                  Limpiar todas
                </button>
              )}
            </div>
            {selectedZones.length === 0 ? (
              <p className="body-map-summary__empty">No marcaste ninguna zona corporal aún.</p>
            ) : (
              <ul className="body-map-summary__chips">
                {selectedZones.map((item) => {
                  const cfg = INTENSITY_CONFIG[item.intensity];
                  return (
                    <li key={item.zone} className={`body-map-chip ${cfg.className}`}>
                      <span className="body-map-chip__icon">{cfg.icon}</span>
                      <span className="body-map-chip__name">{ZONES_ES[item.zone] ?? item.zone}:</span>
                      <span className="body-map-chip__intensity">{cfg.label}</span>
                      {!readOnly && (
                        <div className="body-map-chip__actions">
                          <button
                            type="button"
                            className="body-map-chip__edit"
                            onClick={() => setEditingZone(item.zone)}
                            title="Cambiar sensación"
                            aria-label={`Cambiar sensación de ${ZONES_ES[item.zone] ?? item.zone}`}
                          >
                            <RotateCw size={12} />
                          </button>
                          <button
                            type="button"
                            className="body-map-chip__remove"
                            onClick={() => handleRemoveZone(item.zone)}
                            title="Quitar zona"
                            aria-label={`Quitar ${ZONES_ES[item.zone] ?? item.zone}`}
                          >
                            <X size={14} />
                          </button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
