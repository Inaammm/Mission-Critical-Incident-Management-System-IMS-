import { useState, useEffect } from 'react';

interface Props {
  slaRemainingSeconds: number | null | undefined;
}

function SLATimer({ slaRemainingSeconds }: Props) {
  const [remaining, setRemaining] = useState(slaRemainingSeconds || 0);

  useEffect(() => {
    setRemaining(slaRemainingSeconds || 0);
  }, [slaRemainingSeconds]);

  useEffect(() => {
    if (remaining <= 0) return;
    const timer = setInterval(() => {
      setRemaining(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [remaining > 0]);

  if (!slaRemainingSeconds) return <span style={{ color: 'var(--text-secondary)' }}>N/A</span>;

  const hours = Math.floor(remaining / 3600);
  const mins = Math.floor((remaining % 3600) / 60);
  const secs = Math.floor(remaining % 60);

  let colorClass = 'sla-green';
  if (remaining < 300) colorClass = 'sla-red';
  else if (remaining < 900) colorClass = 'sla-yellow';

  return (
    <span className={`sla-timer ${colorClass}`}>
      {hours > 0 && `${hours}h `}{mins}m {secs}s
    </span>
  );
}

export default SLATimer;
