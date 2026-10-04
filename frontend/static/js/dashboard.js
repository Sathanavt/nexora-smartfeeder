/**
 * SmartFeeder EMS — Home Dashboard Controller
 * Fetches live telemetry data from backend, calculates visual gauges, and updates UI.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // DOM Elements
  const tsEl = document.getElementById('telemetryTimestamp');
  const refreshBtn = document.getElementById('refreshDataBtn');
  const errorBanner = document.getElementById('homeErrorBanner');
  const errorMsg = document.getElementById('homeErrorMessage');
  const retryBtn = document.getElementById('retryLoadBtn');

  // BUS-1 Elements
  const bus1Demand = document.getElementById('bus1Demand');
  const bus1Voltage = document.getElementById('bus1Voltage');
  const bus1Current = document.getElementById('bus1Current');
  const bus1Frequency = document.getElementById('bus1Frequency');
  const bus1SolarBadge = document.getElementById('bus1SolarBadge');
  const bus1SolarStatus = document.getElementById('bus1SolarStatus');
  const bus1BessBadge = document.getElementById('bus1BessBadge');
  const bus1BessStatus = document.getElementById('bus1BessStatus');

  // BUS-2 Elements
  const bus2Demand = document.getElementById('bus2Demand');
  const bus2Voltage = document.getElementById('bus2Voltage');
  const bus2Current = document.getElementById('bus2Current');
  const bus2Frequency = document.getElementById('bus2Frequency');
  const bus2SolarBadge = document.getElementById('bus2SolarBadge');
  const bus2SolarStatus = document.getElementById('bus2SolarStatus');
  const bus2BessBadge = document.getElementById('bus2BessBadge');
  const bus2BessStatus = document.getElementById('bus2BessStatus');

  // EMS Elements
  const emsOperatingMode = document.getElementById('emsOperatingMode');
  const emsPvSetpoint = document.getElementById('emsPvSetpoint');
  const emsBessSetpoint = document.getElementById('emsBessSetpoint');
  const emsGridImport = document.getElementById('emsGridImport');

  // Secondary Summary Metrics
  const totalFeederDemand = document.getElementById('totalFeederDemand');
  const totalSolarGen = document.getElementById('totalSolarGen');
  const totalGridImport = document.getElementById('totalGridImport');
  const bessASoc = document.getElementById('bessASoc');
  const bessAGaugeFill = document.getElementById('bessAGaugeFill');
  const bessBSoc = document.getElementById('bessBSoc');
  const bessBGaugeFill = document.getElementById('bessBGaugeFill');

  // System Strip Elements
  const stripSolarBadge = document.getElementById('stripSolarBadge');
  const stripSolarText = document.getElementById('stripSolarText');

  let isFetching = false;
  let pollInterval = null;

  // Number formatting helper
  function formatNum(val, decimals = 1) {
    if (val === null || val === undefined || isNaN(val)) return '--';
    return Number(val).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  // Calculate SOC window percentage fill (15% to 90% operating window)
  function calculateSocFill(soc) {
    const min = 15.0;
    const max = 90.0;
    if (soc <= min) return 0;
    if (soc >= max) return 100;
    return Math.round(((soc - min) / (max - min)) * 100);
  }

  // Set badge style for BESS
  function updateBessBadge(badgeEl, statusEl, status) {
    if (!badgeEl || !statusEl) return;
    const s = (status || 'IDLE').toUpperCase();
    statusEl.textContent = s;
    badgeEl.className = 'indicator-badge';
    if (s === 'CHARGING') {
      badgeEl.classList.add('charging');
    } else if (s === 'DISCHARGING') {
      badgeEl.classList.add('discharging');
    }
  }

  // Set badge style for Solar
  function updateSolarBadge(badgeEl, statusEl, status) {
    if (!badgeEl || !statusEl) return;
    const s = (status || 'INACTIVE').toUpperCase();
    statusEl.textContent = s;
    badgeEl.className = 'indicator-badge';
    if (s === 'ACTIVE') {
      badgeEl.classList.add('active');
    }
  }

  // Fetch live dashboard telemetry
  async function loadDashboardData() {
    if (isFetching) return;
    isFetching = true;

    if (refreshBtn) refreshBtn.style.animation = 'spin 800ms linear infinite';

    try {
      const response = await fetch('/api/dashboard/live', {
        headers: { 'Accept': 'application/json' }
      });

      if (!response.ok) {
        if (response.status === 401) {
          // Unauthenticated session - redirect to login
          window.location.href = '/login';
          return;
        }
        throw new Error('Unable to load dashboard data.');
      }

      const resJson = await response.json();
      if (!resJson.success || !resJson.data) {
        throw new Error(resJson.error || 'Dashboard data is currently unavailable.');
      }

      renderDashboard(resJson.data);
      if (errorBanner) errorBanner.style.display = 'none';

    } catch (err) {
      if (errorBanner && errorMsg) {
        errorMsg.textContent = err.message || 'Unable to load dashboard data.';
        errorBanner.style.display = 'flex';
      }
    } finally {
      isFetching = false;
      if (refreshBtn) refreshBtn.style.animation = '';
    }
  }

  // Populate UI with fetched data
  function renderDashboard(data) {
    const { timestamp_formatted, bus1, bus2, ems, summary, system_strip } = data;

    // Timestamp
    if (tsEl) tsEl.textContent = timestamp_formatted || 'Live Synchronized';

    // 1. BUS-1
    if (bus1) {
      if (bus1Demand) {
        bus1Demand.textContent = formatNum(bus1.demand_kw, 1);
        bus1Demand.classList.remove('skeleton-text');
      }
      if (bus1Voltage) {
        bus1Voltage.textContent = formatNum(bus1.voltage_kv, 2);
        bus1Voltage.classList.remove('skeleton-text');
      }
      if (bus1Current) {
        bus1Current.textContent = formatNum(bus1.current_a, 1);
        bus1Current.classList.remove('skeleton-text');
      }
      if (bus1Frequency) {
        bus1Frequency.textContent = formatNum(bus1.frequency_hz, 2);
        bus1Frequency.classList.remove('skeleton-text');
      }
      updateSolarBadge(bus1SolarBadge, bus1SolarStatus, bus1.solar_status);
      updateBessBadge(bus1BessBadge, bus1BessStatus, bus1.bess_status);
    }

    // 2. BUS-2
    if (bus2) {
      if (bus2Demand) {
        bus2Demand.textContent = formatNum(bus2.demand_kw, 1);
        bus2Demand.classList.remove('skeleton-text');
      }
      if (bus2Voltage) {
        bus2Voltage.textContent = formatNum(bus2.voltage_kv, 2);
        bus2Voltage.classList.remove('skeleton-text');
      }
      if (bus2Current) {
        bus2Current.textContent = formatNum(bus2.current_a, 1);
        bus2Current.classList.remove('skeleton-text');
      }
      if (bus2Frequency) {
        bus2Frequency.textContent = formatNum(bus2.frequency_hz, 2);
        bus2Frequency.classList.remove('skeleton-text');
      }
      updateSolarBadge(bus2SolarBadge, bus2SolarStatus, bus2.solar_status);
      updateBessBadge(bus2BessBadge, bus2BessStatus, bus2.bess_status);
    }

    // 3. EMS STATUS
    if (ems) {
      if (emsOperatingMode) {
        emsOperatingMode.textContent = ems.operating_mode || 'Grid Only';
        emsOperatingMode.classList.remove('skeleton-text');
      }
      if (emsPvSetpoint) {
        emsPvSetpoint.textContent = formatNum(ems.pv_setpoint_kw, 1);
        emsPvSetpoint.classList.remove('skeleton-text');
      }
      if (emsBessSetpoint) {
        emsBessSetpoint.textContent = formatNum(ems.bess_setpoint_kw, 1);
        emsBessSetpoint.classList.remove('skeleton-text');
      }
      if (emsGridImport) {
        emsGridImport.textContent = formatNum(ems.grid_import_kw, 1);
        emsGridImport.classList.remove('skeleton-text');
      }
    }

    // 4. SECONDARY METRICS
    if (summary) {
      if (totalFeederDemand) {
        totalFeederDemand.textContent = formatNum(summary.total_feeder_demand_kw, 1);
        totalFeederDemand.classList.remove('skeleton-text');
      }
      if (totalSolarGen) {
        totalSolarGen.textContent = formatNum(summary.total_solar_gen_kw, 1);
        totalSolarGen.classList.remove('skeleton-text');
      }
      if (totalGridImport) {
        totalGridImport.textContent = formatNum(summary.total_grid_import_kw, 1);
        totalGridImport.classList.remove('skeleton-text');
      }

      // BESS-A SOC & Window Gauge
      if (bessASoc) {
        bessASoc.textContent = formatNum(summary.bess_a_soc_pct, 1);
        bessASoc.classList.remove('skeleton-text');
      }
      if (bessAGaugeFill) {
        const fillA = calculateSocFill(summary.bess_a_soc_pct);
        bessAGaugeFill.style.width = `${fillA}%`;
      }

      // BESS-B SOC & Window Gauge
      if (bessBSoc) {
        bessBSoc.textContent = formatNum(summary.bess_b_soc_pct, 1);
        bessBSoc.classList.remove('skeleton-text');
      }
      if (bessBGaugeFill) {
        const fillB = calculateSocFill(summary.bess_b_soc_pct);
        bessBGaugeFill.style.width = `${fillB}%`;
      }
    }

    // 5. SYSTEM STATUS STRIP
    if (system_strip) {
      if (stripSolarBadge && stripSolarText) {
        stripSolarText.textContent = system_strip.solar || 'ACTIVE';
        stripSolarBadge.className = 'strip-badge';
        if (system_strip.solar === 'ACTIVE') {
          stripSolarBadge.classList.add('online');
        }
      }
    }
  }

  // Event Listeners
  refreshBtn?.addEventListener('click', loadDashboardData);
  retryBtn?.addEventListener('click', loadDashboardData);

  // Initial load
  loadDashboardData();

  // Automatic gentle polling every 30 seconds
  pollInterval = setInterval(loadDashboardData, 30000);

  window.addEventListener('beforeunload', () => {
    if (pollInterval) clearInterval(pollInterval);
  });
});
