import { useState, useEffect, useRef, useMemo } from "react";

export default function Dashboard() {
  const [alerts, setAlerts] = useState([]);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [filterText, setFilterText] = useState("");
  const [filterType, setFilterType] = useState("all");
  const ws = useRef(null);

  useEffect(() => {
    let reconnectTimeout;

    function connect() {
      setWsStatus("connecting");
      const socketUrl = `ws://${window.location.hostname}:8000/ws/alerts/`;
      ws.current = new WebSocket(socketUrl);

      ws.current.onopen = () => {
        setWsStatus("connected");
      };

      ws.current.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setAlerts((prev) => [payload, ...prev].slice(0, 100));
        } catch (err) {
          console.error("Error parsing WebSocket alert message:", err);
        }
      };

      ws.current.onclose = () => {
        setWsStatus("disconnected");
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.current.onerror = (err) => {
        console.error("WebSocket error:", err);
        ws.current.close();
      };
    }

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const stats = useMemo(() => {
    let emergencies = 0;
    let radioFailures = 0;
    let severeRates = 0;

    alerts.forEach((item) => {
      const type = item.alert?.type;
      const code = item.alert?.code;
      if (type === "squawk") {
        if (code === "7700" || code === "7500") emergencies++;
        if (code === "7600") radioFailures++;
      } else if (type === "vertical_rate") {
        severeRates++;
      }
    });

    return { total: alerts.length, emergencies, radioFailures, severeRates };
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    return alerts.filter((item) => {
      const matchesSearch =
        (item.callsign || "").toLowerCase().includes(filterText.toLowerCase()) ||
        (item.icao24 || "").toLowerCase().includes(filterText.toLowerCase());

      const matchesType =
        filterType === "all" ||
        (filterType === "squawk" && item.alert?.type === "squawk") ||
        (filterType === "vertical_rate" && item.alert?.type === "vertical_rate");

      return matchesSearch && matchesType;
    });
  }, [alerts, filterText, filterType]);

  const clearAlerts = () => setAlerts([]);

  const formatTime = (ts) => {
    if (!ts) return "";
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-title">
          <h1>🛫 AeroTrack Mission Control</h1>
          <div className="status-indicator">
            <span className={`status-pulse ${wsStatus}`} />
            <span className="status-text">{wsStatus.toUpperCase()}</span>
          </div>
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">TOTAL ALERTS</span>
          <span className="stat-value">{stats.total}</span>
        </div>
        <div className="stat-card critical">
          <span className="stat-label">EMERGENCIES (7500 / 7700)</span>
          <span className="stat-value">{stats.emergencies}</span>
        </div>
        <div className="stat-card warning">
          <span className="stat-label">RADIO FAILURES (7600)</span>
          <span className="stat-value">{stats.radioFailures}</span>
        </div>
        <div className="stat-card rate">
          <span className="stat-label">SEVERE CLIMB/DESCENT</span>
          <span className="stat-value">{stats.severeRates}</span>
        </div>
      </div>

      <div className="control-bar">
        <input
          type="text"
          placeholder="Filter by Callsign or ICAO..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          className="search-input"
        />
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="filter-select"
        >
          <option value="all">All Alerts</option>
          <option value="squawk">Squawk Transponder</option>
          <option value="vertical_rate">Extreme Vertical Rate</option>
        </select>
        <button onClick={clearAlerts} className="clear-btn">
          Clear History
        </button>
      </div>

      <div className="main-content-layout">
        <div className="alerts-feed-section">
          <h2>📡 Real-Time Stream</h2>
          <div className="alerts-feed">
            {filteredAlerts.length === 0 ? (
              <div className="empty-state">No telemetry alerts active.</div>
            ) : (
              filteredAlerts.map((item, index) => {
                const isSquawkEmergency =
                  item.alert?.type === "squawk" &&
                  (item.alert?.code === "7700" || item.alert?.code === "7500");

                return (
                  <div
                    key={`${item.icao24}-${item.timestamp}-${index}`}
                    className={`alert-feed-item ${isSquawkEmergency ? "critical-alert" : ""}`}
                  >
                    <div className="alert-meta">
                      <span className="alert-badge">
                        {item.alert?.type === "squawk" ? `SQUAWK ${item.alert.code}` : "V-RATE"}
                      </span>
                      <span className="alert-timestamp">{formatTime(item.timestamp)}</span>
                    </div>
                    <div className="alert-body">
                      <h3>
                        {item.callsign || "UNKNOWN"} ({item.icao24})
                      </h3>
                      <p className="alert-desc">{item.alert?.description}</p>
                      <div className="alert-coords">
                        <span>LAT: {item.latitude?.toFixed(4) || "—"}</span>
                        <span>LON: {item.longitude?.toFixed(4) || "—"}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="alerts-table-section">
          <h2>📋 Historical Log</h2>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Ident</th>
                  <th>Callsign</th>
                  <th>Alert Type</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="table-empty">
                      No matching historical logs.
                    </td>
                  </tr>
                ) : (
                  filteredAlerts.map((item, index) => (
                    <tr key={`${item.icao24}-${item.timestamp}-${index}`}>
                      <td>{formatTime(item.timestamp)}</td>
                      <td className="mono">{item.icao24}</td>
                      <td>{item.callsign || "—"}</td>
                      <td>
                        <span className={`table-badge ${item.alert?.type}`}>
                          {item.alert?.type === "squawk" ? "Squawk" : "Vertical Rate"}
                        </span>
                      </td>
                      <td>{item.alert?.description}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
