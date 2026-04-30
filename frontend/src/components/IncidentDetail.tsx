import { useState, useEffect } from 'react';
import {
  Incident, Signal, getIncidentSignals, getIncidentAudit,
  transitionIncident, getRCA, RCA
} from '../services/api';
import RCAForm from './RCAForm';
import SLATimer from './SLATimer';

interface Props {
  incident: Incident;
  onUpdate: () => void;
}

function IncidentDetail({ incident, onUpdate }: Props) {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [rca, setRca] = useState<RCA | null>(null);
  const [showRCAForm, setShowRCAForm] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDetails();
  }, [incident.id]);

  const loadDetails = async () => {
    try {
      const [sigRes, auditRes] = await Promise.all([
        getIncidentSignals(incident.id),
        getIncidentAudit(incident.id),
      ]);
      setSignals(sigRes.data);
      setAudit(auditRes.data);
    } catch {}
    try {
      const rcaRes = await getRCA(incident.id);
      setRca(rcaRes.data);
    } catch {
      setRca(null);
    }
  };

  const handleTransition = async (newStatus: string) => {
    setError('');
    try {
      await transitionIncident(incident.id, newStatus);
      onUpdate();
      loadDetails();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Transition failed');
    }
  };

  const getNextActions = () => {
    switch (incident.status) {
      case 'OPEN': return [{ label: 'Start Investigation', status: 'INVESTIGATING', cls: 'btn-primary' }];
      case 'INVESTIGATING': return [
        { label: 'Mark Resolved', status: 'RESOLVED', cls: 'btn-success' },
        { label: 'Reopen', status: 'OPEN', cls: 'btn-danger' },
      ];
      case 'RESOLVED': return [{ label: 'Close Incident', status: 'CLOSED', cls: 'btn-success' }];
      default: return [];
    }
  };

  return (
    <div className="detail-panel">
      <h2>{incident.title}</h2>

      {error && <div style={{ color: 'var(--p0)', marginBottom: '1rem', padding: '0.5rem', background: 'rgba(239,68,68,0.1)', borderRadius: '4px' }}>{error}</div>}

      {/* Status & Actions */}
      <div className="detail-section">
        <h3>Status & Actions</h3>
        <div className="detail-grid">
          <div className="detail-field">
            <label>Current Status</label>
            <span className={`severity-badge severity-${incident.severity}`} style={{ marginRight: '0.5rem' }}>{incident.severity}</span>
            <span className="status-badge">{incident.status}</span>
          </div>
          <div className="detail-field">
            <label>SLA Remaining</label>
            <SLATimer slaRemainingSeconds={incident.sla_remaining_seconds} />
          </div>
          <div className="detail-field">
            <label>Signal Count</label>
            <span>{incident.signal_count}</span>
          </div>
          <div className="detail-field">
            <label>MTTR</label>
            <span>{incident.mttr_seconds ? `${(incident.mttr_seconds / 60).toFixed(1)} min` : 'N/A'}</span>
          </div>
        </div>
        <div className="btn-group">
          {getNextActions().map(action => (
            <button key={action.status} className={`btn ${action.cls}`} onClick={() => handleTransition(action.status)}>
              {action.label}
            </button>
          ))}
          {(incident.status === 'RESOLVED' || incident.status === 'INVESTIGATING') && !rca && (
            <button className="btn btn-primary" onClick={() => setShowRCAForm(true)}>
              Submit RCA
            </button>
          )}
        </div>
      </div>

      {/* RCA */}
      {showRCAForm && !rca && (
        <div className="detail-section">
          <h3>Root Cause Analysis</h3>
          <RCAForm incidentId={incident.id} onSubmit={() => { setShowRCAForm(false); loadDetails(); onUpdate(); }} />
        </div>
      )}
      {rca && (
        <div className="detail-section">
          <h3>Root Cause Analysis (Submitted)</h3>
          <div className="detail-grid">
            <div className="detail-field"><label>Category</label><span>{rca.root_cause_category}</span></div>
            <div className="detail-field"><label>Submitted By</label><span>{rca.created_by}</span></div>
            <div className="detail-field"><label>Root Cause</label><span>{rca.root_cause_description}</span></div>
            <div className="detail-field"><label>Fix Applied</label><span>{rca.fix_applied}</span></div>
          </div>
        </div>
      )}

      {/* Signals */}
      <div className="detail-section">
        <h3>Raw Signals ({signals.length})</h3>
        <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
          <table className="signals-table">
            <thead>
              <tr><th>Time</th><th>Error Code</th><th>Message</th><th>Latency</th></tr>
            </thead>
            <tbody>
              {signals.map((sig, i) => (
                <tr key={i}>
                  <td>{new Date(sig.timestamp).toLocaleTimeString()}</td>
                  <td>{sig.error_code}</td>
                  <td>{sig.error_message?.substring(0, 50)}</td>
                  <td>{sig.latency_ms?.toFixed(0)}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Trail */}
      <div className="detail-section">
        <h3>Audit Trail</h3>
        {audit.map((entry, i) => (
          <div key={i} style={{ marginBottom: '0.5rem', fontSize: '0.8rem', borderLeft: '2px solid var(--accent)', paddingLeft: '0.75rem' }}>
            <strong>{entry.action}</strong> — {entry.new_value || entry.old_value}
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
              {entry.performed_by} | {entry.created_at && new Date(entry.created_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default IncidentDetail;
