import { useState, useEffect, useRef, useMemo, useCallback } from "react";

import apiClient from "../api/client";

const AIRPORT_PRESETS = [
  { name: "London Heathrow (LHR)", lat: 51.4700, lon: -0.4543 },
  { name: "John F. Kennedy (JFK)", lat: 40.6413, lon: -73.7781 },
  { name: "Tokyo Haneda (HND)", lat: 35.5494, lon: 139.7798 },
  { name: "Frankfurt Airport (FRA)", lat: 50.0379, lon: 8.5622 },
  { name: "Dubai International (DXB)", lat: 25.2532, lon: 55.3657 },
  { name: "Sydney Airport (SYD)", lat: -33.9461, lon: 151.1772 }
];

export default function Dashboard() {
  const [alerts, setAlerts] = useState([]);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [filterText, setFilterText] = useState("");
  const [filterType, setFilterType] = useState("all");
  const ws = useRef(null);

  // Radar state
  const [flights, setFlights] = useState([]);
  const [activeGeofence, setActiveGeofence] = useState(false);
  const [geofenceCenter, setGeofenceCenter] = useState({ lat: 51.4700, lon: -0.4543 });
  const [geofenceRadius, setGeofenceRadius] = useState(100);
  const [selectedFlight, setSelectedFlight] = useState(null);

  // Pan / Zoom state
  const [zoom, setZoom] = useState(1.5);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const initialPanOffset = useRef({ x: 0, y: 0 });

  // WebSockets Alert connection
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

  // Poll flight locations from REST geofencing API every 5 seconds
  useEffect(() => {
    let timer;

    async function fetchFlights() {
      try {
        let url = "/flights/nearby/";
        if (activeGeofence) {
          url += `?lat=${geofenceCenter.lat}&lon=${geofenceCenter.lon}&radius=${geofenceRadius}`;
        }
        const res = await apiClient.get(url);
        setFlights(res.data || []);
      } catch (err) {
        console.error("Failed to fetch active flights:", err);
      }
    }

    fetchFlights();
    timer = setInterval(fetchFlights, 5000);

    return () => clearInterval(timer);
  }, [activeGeofence, geofenceCenter, geofenceRadius]);

  // Alert counters
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

  // Convert GPS Coordinates to Local Radar X/Y coordinates in pixels
  const centerLat = geofenceCenter.lat;
  const centerLon = geofenceCenter.lon;

  const radarOriginX = 300;
  const radarOriginY = 300;
  const kmToPixels = 2 * zoom;

  const getFlightCoordinates = useCallback((lat, lon) => {
    if (lat === undefined || lon === undefined) return { x: 0, y: 0, visible: false };

    const dy = (lat - centerLat) * 111.0;
    const dx = (lon - centerLon) * 111.0 * Math.cos((centerLat * Math.PI) / 180.0);

    const px = radarOriginX + dx * kmToPixels + panOffset.x;
    const py = radarOriginY - dy * kmToPixels + panOffset.y;

    const insideRadarBorder = Math.sqrt(Math.pow(px - radarOriginX, 2) + Math.pow(py - radarOriginY, 2)) < 290;

    return { x: px, y: py, visible: insideRadarBorder };
  }, [centerLat, centerLon, kmToPixels, panOffset]);

  // Mouse pan handlers
  const handleMouseDown = (e) => {
    setIsPanning(true);
    panStart.current = { x: e.clientX, y: e.clientY };
    initialPanOffset.current = { ...panOffset };
  };

  const handleMouseMove = (e) => {
    if (!isPanning) return;
    const dx = e.clientX - panStart.current.x;
    const dy = e.clientY - panStart.current.y;
    setPanOffset({
      x: initialPanOffset.current.x + dx,
      y: initialPanOffset.current.y + dy
    });
  };

  const handleMouseUpOrLeave = () => {
    setIsPanning(false);
  };

  const resetRadarView = () => {
    setZoom(1.5);
    setPanOffset({ x: 0, y: 0 });
  };

  const handlePresetSelect = (e) => {
    const idx = parseInt(e.target.value);
    if (!isNaN(idx) && AIRPORT_PRESETS[idx]) {
      const preset = AIRPORT_PRESETS[idx];
      setGeofenceCenter({ lat: preset.lat, lon: preset.lon });
    }
  };

  // Pre-calculate geofence ring size
  const geofenceRadiusPixels = geofenceRadius * kmToPixels;

  // Pre-calculate flight listings on radar
  const radarFlights = useMemo(() => {
    return flights.map(flight => {
      const coords = getFlightCoordinates(flight.latitude, flight.longitude);
      return { ...flight, coords };
    });
  }, [flights, getFlightCoordinates]);


  // Sync inspection hook when flights list is refreshed
  const inspectedFlightDetail = useMemo(() => {
    if (!selectedFlight) return null;
    const found = flights.find(f => f.icao24 === selectedFlight.icao24);
    return found || selectedFlight;
  }, [flights, selectedFlight]);

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

      <div className="command-grid-layout">
        {/* LEFT COLUMN: RADAR MAP & CONTROLLERS */}
        <div className="radar-map-column">
          <div className="radar-display-panel">
            <div className="radar-panel-header">
              <h2>📡 Tactical Airspace Radar</h2>
              <div className="radar-view-controls">
                <span className="zoom-text">ZOOM: {zoom.toFixed(1)}x</span>
                <input
                  type="range"
                  min="0.5"
                  max="4.0"
                  step="0.1"
                  value={zoom}
                  onChange={(e) => setZoom(parseFloat(e.target.value))}
                  className="radar-zoom-slider"
                />
                <button onClick={resetRadarView} className="radar-reset-btn">Reset</button>
              </div>
            </div>

            <div
              className={`radar-canvas-container ${isPanning ? "panning" : ""}`}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUpOrLeave}
              onMouseLeave={handleMouseUpOrLeave}
            >
              <svg viewBox="0 0 600 600" className="radar-svg">
                <defs>
                  <radialGradient id="radarGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="#0b3c20" stopOpacity="0.8" />
                    <stop offset="60%" stopColor="#051c0e" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#0b0c10" stopOpacity="1" />
                  </radialGradient>
                  <filter id="glowEffect">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                    <feMerge>
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                </defs>

                {/* Radar Grid Center Backing */}
                <circle cx="300" cy="300" r="290" fill="url(#radarGlow)" />

                {/* Tactical Sweep Animation */}
                <line x1="300" y1="300" x2="300" y2="10" className="radar-sweep-arm" />

                {/* Distance Concentric Circles */}
                <circle cx="300" cy="300" r="75" className="radar-grid-ring" />
                <circle cx="300" cy="300" r="150" className="radar-grid-ring" />
                <circle cx="300" cy="300" r="225" className="radar-grid-ring" />
                <circle cx="300" cy="300" r="290" className="radar-grid-outer-ring" />

                <text x="300" y="220" className="radar-grid-text">50 KM</text>
                <text x="300" y="145" className="radar-grid-text">100 KM</text>
                <text x="300" y="70" className="radar-grid-text">150 KM</text>

                {/* Compass Axes */}
                <line x1="300" y1="10" x2="300" y2="590" className="radar-axis" />
                <line x1="10" y1="300" x2="590" y2="300" className="radar-axis" />

                <text x="305" y="25" className="radar-cardinal-text">N 000°</text>
                <text x="545" y="315" className="radar-cardinal-text">E 090°</text>
                <text x="305" y="585" className="radar-cardinal-text">S 180°</text>
                <text x="15" y="315" className="radar-cardinal-text">W 270°</text>

                {/* Geofence Pulser Ring Overlay */}
                {activeGeofence && (
                  <circle
                    cx={radarOriginX + panOffset.x}
                    cy={radarOriginY + panOffset.y}
                    r={geofenceRadiusPixels}
                    className="radar-geofence-bound-circle"
                    filter="url(#glowEffect)"
                  />
                )}

                {/* Inspected Flight Target projection line */}
                {inspectedFlightDetail && inspectedFlightDetail.latitude !== undefined && (
                  (() => {
                    const coords = getFlightCoordinates(inspectedFlightDetail.latitude, inspectedFlightDetail.longitude);
                    return (
                      <line
                        x1={radarOriginX + panOffset.x}
                        y1={radarOriginY + panOffset.y}
                        x2={coords.x}
                        y2={coords.y}
                        className="radar-target-line"
                      />
                    );
                  })()
                )}

                {/* Active Radar Flights */}
                {radarFlights.map((flight) => {
                  if (!flight.coords.visible) return null;

                  const isInspected = inspectedFlightDetail && inspectedFlightDetail.icao24 === flight.icao24;
                  const squawkStr = flight.squawk ? String(flight.squawk).trim() : "";
                  const isAnomaly = ["7500", "7600", "7700"].includes(squawkStr) || Math.abs(flight.vertical_rate || 0) > 25;

                  return (
                    <g
                      key={flight.icao24}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFlight(flight);
                      }}
                      className={`radar-blip-group ${isInspected ? "inspected" : ""} ${isAnomaly ? "anomaly" : ""}`}
                    >
                      {/* Interactive Selection Highlight Ring */}
                      {isInspected && (
                        <circle cx={flight.coords.x} cy={flight.coords.y} r="20" className="radar-blip-select-ring" />
                      )}

                      {/* Radar Blip Dot */}
                      <circle cx={flight.coords.x} cy={flight.coords.y} r="4" className="radar-blip-dot" />

                      {/* Direction vector airplane icon */}
                      <path
                        d="M0 -12 L1 -4 L10 1 L10 3 L1 2 L0 8 L3 10 L3 11 L0 10 L-3 11 L-3 10 L0 8 L-1 2 L-10 3 L-10 1 L-1 -4 Z"
                        transform={`translate(${flight.coords.x}, ${flight.coords.y}) rotate(${flight.true_track || 0}) scale(${isInspected ? 1.2 : 0.95})`}
                        className="radar-blip-icon"
                      />

                      {/* Label metadata tag */}
                      <text x={flight.coords.x + 14} y={flight.coords.y - 6} className="radar-blip-label callsign">
                        {flight.callsign || "UNKN"}
                      </text>
                      <text x={flight.coords.x + 14} y={flight.coords.y + 6} className="radar-blip-label details">
                        {Math.round((flight.baro_altitude || 0) * 3.28084 / 100)}FL
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>

          {/* GEOFENCE RADIAL CONTROLS */}
          <div className="geofence-control-panel">
            <div className="panel-section-title">
              <h3>⭕ Geofence Proximity System</h3>
              <div className="geofence-toggle-container">
                <span className="toggle-label">GEOFENCE MODE</span>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={activeGeofence}
                    onChange={(e) => setActiveGeofence(e.target.checked)}
                  />
                  <span className="toggle-slider" />
                </label>
              </div>
            </div>

            <div className={`geofence-inputs-grid ${activeGeofence ? "active" : "disabled"}`}>
              <div className="input-group full">
                <label>Airport Location Presets</label>
                <select onChange={handlePresetSelect} className="presets-select" disabled={!activeGeofence}>
                  <option value="">-- Choose Preset Airport --</option>
                  {AIRPORT_PRESETS.map((preset, idx) => (
                    <option key={idx} value={idx}>{preset.name}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label>Center Latitude (°N)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={geofenceCenter.lat}
                  onChange={(e) => setGeofenceCenter((prev) => ({ ...prev, lat: parseFloat(e.target.value) || 0 }))}
                  disabled={!activeGeofence}
                  className="coord-input"
                />
              </div>

              <div className="input-group">
                <label>Center Longitude (°E)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={geofenceCenter.lon}
                  onChange={(e) => setGeofenceCenter((prev) => ({ ...prev, lon: parseFloat(e.target.value) || 0 }))}
                  disabled={!activeGeofence}
                  className="coord-input"
                />
              </div>

              <div className="input-group full">
                <div className="slider-header">
                  <label>Proximity Radius (KM)</label>
                  <span className="slider-value">{geofenceRadius} KM</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="500"
                  step="5"
                  value={geofenceRadius}
                  onChange={(e) => setGeofenceRadius(parseInt(e.target.value))}
                  disabled={!activeGeofence}
                  className="radius-range-slider"
                />
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: INTELLIGENCE METRIC BLOCKS & ALERTS */}
        <div className="intelligence-column">
          {/* FLIGHT INSPECTOR */}
          <div className="flight-inspector-card">
            <h3>📋 Telemetry Aircraft Inspector</h3>
            {inspectedFlightDetail ? (
              <div className="inspector-panel-details">
                <div className="inspector-identity-block">
                  <span className="inspector-callsign">{inspectedFlightDetail.callsign || "UNKNOWN"}</span>
                  <span className="inspector-icao">{inspectedFlightDetail.icao24}</span>
                </div>

                <div className="inspector-stats-grid">
                  <div className="inspector-stat-item">
                    <span className="lbl">ALTITUDE</span>
                    <span className="val">{Math.round((inspectedFlightDetail.baro_altitude || 0) * 3.28084).toLocaleString()} FT</span>
                    <span className="sub">{Math.round(inspectedFlightDetail.baro_altitude || 0).toLocaleString()} M</span>
                  </div>

                  <div className="inspector-stat-item">
                    <span className="lbl">GROUND SPEED</span>
                    <span className="val">{Math.round((inspectedFlightDetail.velocity || 0) * 1.94384)} KTS</span>
                    <span className="sub">{Math.round((inspectedFlightDetail.velocity || 0) * 3.6)} KM/H</span>
                  </div>

                  <div className="inspector-stat-item">
                    <span className="lbl">HEADING</span>
                    <span className="val">{Math.round(inspectedFlightDetail.true_track || 0)}°</span>
                    <span className="sub">HEADING TRACK</span>
                  </div>

                  <div className="inspector-stat-item">
                    <span className="lbl">VERTICAL RATE</span>
                    <span className={`val ${inspectedFlightDetail.vertical_rate < 0 ? "descending" : inspectedFlightDetail.vertical_rate > 0 ? "climbing" : ""}`}>
                      {inspectedFlightDetail.vertical_rate ? `${Math.round(inspectedFlightDetail.vertical_rate * 196.85)} FPM` : "0 FPM"}
                    </span>
                    <span className="sub">{inspectedFlightDetail.vertical_rate ? `${inspectedFlightDetail.vertical_rate.toFixed(1)} M/S` : "0.0 M/S"}</span>
                  </div>

                  <div className="inspector-stat-item full-width">
                    <span className="lbl">COORDINATE GPS LOCATION</span>
                    <span className="val-loc">
                      {inspectedFlightDetail.latitude?.toFixed(5)}° N, {inspectedFlightDetail.longitude?.toFixed(5)}° E
                    </span>
                  </div>

                  <div className="inspector-stat-item">
                    <span className="lbl">TRANSPONDER SQUAWK</span>
                    <span className={`val-mono ${["7500", "7600", "7700"].includes(String(inspectedFlightDetail.squawk).trim()) ? "danger" : ""}`}>
                      {inspectedFlightDetail.squawk || "—"}
                    </span>
                  </div>

                  <div className="inspector-stat-item">
                    <span className="lbl">ORIGIN COUNTRY</span>
                    <span className="val-text">{inspectedFlightDetail.origin_country || "Unknown Country"}</span>
                  </div>

                  {inspectedFlightDetail.distance_km !== undefined && (
                    <div className="inspector-stat-item full-width highlighted">
                      <span className="lbl">DISTANCE FROM GEOFENCE CENTER</span>
                      <span className="val">{inspectedFlightDetail.distance_km.toFixed(2)} KM</span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="inspector-empty-state">
                Select an aircraft on the Radar Map to inspect its spatial and speed metrics in real time.
              </div>
            )}
          </div>

          {/* ACTIVE ALERTS AND FEED */}
          <div className="alert-ticker-container">
            <div className="alert-ticker-header">
              <h2>📡 Emergency Alerts Stream</h2>
              <div className="control-bar-inline">
                <input
                  type="text"
                  placeholder="Filter alerts..."
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  className="search-input-inline"
                />
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="filter-select-inline"
                >
                  <option value="all">All</option>
                  <option value="squawk">Squawk</option>
                  <option value="vertical_rate">V-Rate</option>
                </select>
                <button onClick={clearAlerts} className="clear-btn-inline">
                  Clear
                </button>
              </div>
            </div>

            <div className="alerts-feed-wrapper">
              {filteredAlerts.length === 0 ? (
                <div className="empty-state">No real-time stream anomalies detected.</div>
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
        </div>
      </div>
    </div>
  );
}
