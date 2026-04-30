import { useState, useEffect, useCallback } from 'react';
import { Incident, DashboardStats, getIncidents, getDashboardStats, simulateBurst } from './services/api';
import { useWebSocket } from './services/websocket';
import IncidentList from './components/IncidentList';
import IncidentDetail from './components/IncidentDetail';

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const { lastMessage, isConnected } = useWebSocket('/ws/incidents');

  const fetchIncidents = useCallback(async () => {
    try {
      const res = await getIncidents(true);
      setIncidents(res.data);
    } catch {}
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await getDashboardStats();
      setStats(res.data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchIncidents();
    fetchStats();
    const interval = setInterval(() => { fetchIncidents(); fetchStats(); }, 5000);
    return () => clearInterval(interval);
  }, [fetchIncidents, fetchStats]);

  // React to WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      fetchIncidents();
      fetchStats();
    }
  }, [lastMessage, fetchIncidents, fetchStats]);

  const handleSimulate = async () => {
    await simulateBurst(150);
    setTimeout(fetchIncidents, 2000);
  };

  const selected = incidents.find(i => i.id === selectedId) || null;

  return (
    <div className="app">
      <header className="header">
        <h1>IMS - Incident Management System</h1>
        <div className="stats-bar">
          <div className="stat">
            <span className="stat-value" style={{ color: 'var(--p0)' }}>{stats?.p0_count || 0}</span> P0
          </div>
          <div className="stat">
            <span className="stat-value" style={{ color: 'var(--p1)' }}>{stats?.p1_count || 0}</span> P1
          </div>
          <div className="stat">
            <span className="stat-value" style={{ color: 'var(--p2)' }}>{stats?.p2_count || 0}</span> P2
          </div>
          <div className="stat">
            <span className="stat-value">{stats?.signals_per_second?.toFixed(1) || '0.0'}</span> sig/s
          </div>
          <div className="stat">
            <span style={{ color: isConnected ? 'var(--p3)' : 'var(--p0)' }}>
              {isConnected ? 'LIVE' : 'DISCONNECTED'}
            </span>
          </div>
          <button className="btn btn-danger" onClick={handleSimulate} style={{ fontSize: '0.75rem' }}>
            Simulate Burst
          </button>
        </div>
      </header>
      <main className="main">
        <aside className="sidebar">
          <IncidentList
            incidents={incidents}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </aside>
        <section className="content">
          {selected ? (
            <IncidentDetail incident={selected} onUpdate={fetchIncidents} />
          ) : (
            <div className="empty-state">
              Select an incident to view details, or simulate a burst to generate incidents.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
