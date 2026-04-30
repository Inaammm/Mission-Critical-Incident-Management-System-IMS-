import { Incident } from '../services/api';

interface Props {
  incidents: Incident[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function IncidentList({ incidents, selectedId, onSelect }: Props) {
  if (incidents.length === 0) {
    return <div className="empty-state" style={{ padding: '2rem' }}>No active incidents</div>;
  }

  return (
    <ul className="incident-list">
      {incidents.map(incident => (
        <li
          key={incident.id}
          className={`incident-item ${incident.id === selectedId ? 'active' : ''}`}
          onClick={() => onSelect(incident.id)}
        >
          <div className="incident-header">
            <span className={`severity-badge severity-${incident.severity}`}>
              {incident.severity}
            </span>
            <span className="status-badge">{incident.status}</span>
          </div>
          <div className="incident-title">{incident.title}</div>
          <div className="incident-meta">
            {incident.component_id} | {incident.signal_count} signals |{' '}
            {new Date(incident.created_at).toLocaleTimeString()}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default IncidentList;
