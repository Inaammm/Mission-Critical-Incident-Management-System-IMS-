import { useState } from 'react';
import { submitRCA } from '../services/api';

interface Props {
  incidentId: string;
  onSubmit: () => void;
}

const RCA_CATEGORIES = [
  'Infrastructure',
  'Configuration',
  'Code Defect',
  'Dependency Failure',
  'Capacity',
  'Network',
  'Human Error',
  'Unknown',
];

function RCAForm({ incidentId, onSubmit }: Props) {
  const [form, setForm] = useState({
    incident_start: '',
    incident_end: '',
    root_cause_category: '',
    root_cause_description: '',
    fix_applied: '',
    prevention_steps: '',
    created_by: 'engineer',
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!form.incident_start || !form.incident_end) {
      setError('Incident start and end times are required');
      return;
    }

    if (!form.root_cause_category || !form.root_cause_description || !form.fix_applied || !form.prevention_steps) {
      setError('All fields are required');
      return;
    }
    if (form.root_cause_description.length < 10 || form.fix_applied.length < 10 || form.prevention_steps.length < 10) {
      setError('Description fields must be at least 10 characters');
      return;
    }

    setSubmitting(true);
    try {
      await submitRCA(incidentId, {
        ...form,
        incident_start: form.incident_start + ':00',
        incident_end: form.incident_end + ':00',
      });
      onSubmit();
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join('; '));
      } else {
        setError(detail || e.message || 'Failed to submit RCA');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && <div style={{ color: 'var(--p0)', marginBottom: '1rem' }}>{error}</div>}

      <div className="detail-grid">
        <div className="form-group">
          <label>Incident Start</label>
          <input type="datetime-local" name="incident_start" value={form.incident_start} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Incident End</label>
          <input type="datetime-local" name="incident_end" value={form.incident_end} onChange={handleChange} required />
        </div>
      </div>

      <div className="form-group">
        <label>Root Cause Category</label>
        <select name="root_cause_category" value={form.root_cause_category} onChange={handleChange} required>
          <option value="">Select category...</option>
          {RCA_CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
        </select>
      </div>

      <div className="form-group">
        <label>Root Cause Description</label>
        <textarea name="root_cause_description" value={form.root_cause_description} onChange={handleChange} placeholder="Describe the root cause in detail..." required />
      </div>

      <div className="form-group">
        <label>Fix Applied</label>
        <textarea name="fix_applied" value={form.fix_applied} onChange={handleChange} placeholder="What fix was applied to resolve this incident?" required />
      </div>

      <div className="form-group">
        <label>Prevention Steps</label>
        <textarea name="prevention_steps" value={form.prevention_steps} onChange={handleChange} placeholder="What steps will prevent this from recurring?" required />
      </div>

      <div className="form-group">
        <label>Submitted By</label>
        <input type="text" name="created_by" value={form.created_by} onChange={handleChange} />
      </div>

      <button type="submit" className="btn btn-primary" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit RCA'}
      </button>
    </form>
  );
}

export default RCAForm;
