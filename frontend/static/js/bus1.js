/**
 * SmartFeeder EMS — BUS-1 Detailed Dashboard Controller
 * Fetches real-time telemetry from /api/bus/1/live and updates
 * Summary metrics, Feeders 1 to 4, Solar-A, and BESS-A.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // DOM Elements - Header & Summary
  const tsVal = document.getElementById('busTsVal');
  const refreshBtn = document.getElementById('btnRefreshBus1');
  const summaryDemand = document.getElementById('summaryDemand');
  const summaryVoltage = document.getElementById('summaryVoltage');
  const summaryCurrent = document.getElementById('summaryCurrent');
  const summaryFreq = document.getElementById('summaryFreq');
  const summarySolarStatus = document.getElementById('summarySolarStatus');
  const summaryBessStatus = document.getElementById('summaryBessStatus');

  // DOM Elements - Solar-A
  const solarAGenVal = document.getElementById('solarAGenVal');
  const solarATempVal = document.getElementById('solarATempVal');
  const solarAGridVal = document.getElementById('solarAGridVal');
  const solarABessVal = document.getElementById('solarABessVal');
  const solarAStatusBadge = document.getElementById('solarAStatusBadge');

  // DOM Elements - BESS-A
  const bessASocVal = document.getElementById('bessASocVal');
  const bessASohVal = document.getElementById('bessASohVal');
  const bessAPowerVal = document.getElementById('bessAPowerVal');
  const bessAReserveVal = document.getElementById('bessAReserveVal');
  const bessASocBar = document.getElementById('bessASocBar');
  const bessAStatusBadge = document.getElementById('bessAStatusBadge');
  const socStatusText = document.getElementById('socStatusText');

  let isFetching = false;
  let refreshTimer = null;

  function formatNum(val, decimals = 1) {
    if (val === null || val === undefined || isNaN(val)) return '--';
    return Number(val).toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  async function fetchBus1Telemetry() {
    if (isFetching) return;
    isFetching = true;

    if (refreshBtn) refreshBtn.classList.add('spinning');

    try {
      const res = await window.DashboardApi.getBus1Live();
      if (res && res.success && res.data) {
        updateUI(res.data);
      }
    } catch (err) {
      console.warn('Error fetching BUS-1 telemetry:', err);
    } finally {
      isFetching = false;
      if (refreshBtn) refreshBtn.classList.remove('spinning');
    }
  }

  function updateUI(data) {
    if (!data) return;

    // 1. Timestamp
    if (tsVal && data.timestamp_formatted) {
      tsVal.textContent = data.timestamp_formatted;
    }

    // 2. Summary Card
    if (data.summary) {
      const s = data.summary;
      if (summaryDemand) summaryDemand.textContent = formatNum(s.demand_kw, 1);
      if (summaryVoltage) summaryVoltage.textContent = formatNum(s.voltage_kv, 2);
      if (summaryCurrent) summaryCurrent.textContent = formatNum(s.current_a, 1);
      if (summaryFreq) summaryFreq.textContent = formatNum(s.frequency_hz, 2);

      if (summarySolarStatus) {
        summarySolarStatus.textContent = s.solar_status || 'INACTIVE';
        summarySolarStatus.className = 'cell-status-chip ' + (s.solar_status === 'ACTIVE' ? 'active' : 'inactive');
      }

      if (summaryBessStatus) {
        const bStatus = (s.bess_status || 'IDLE').toLowerCase();
        summaryBessStatus.textContent = s.bess_status || 'IDLE';
        summaryBessStatus.className = 'cell-status-chip ' + bStatus;
      }
    }

    // 3. Feeders 1 to 4
    if (data.feeders && Array.isArray(data.feeders)) {
      data.feeders.forEach(f => {
        const id = f.id;
        const dEl = document.getElementById(`feederDemand${id}`);
        const vEl = document.getElementById(`feederVoltage${id}`);
        const fEl = document.getElementById(`feederFreq${id}`);
        const pfEl = document.getElementById(`feederPf${id}`);

        if (dEl) dEl.textContent = formatNum(f.demand_kw, 2);
        if (vEl) vEl.textContent = `${formatNum(f.voltage_kv, 2)} kV`;
        if (fEl) fEl.textContent = `${formatNum(f.frequency_hz, 2)} Hz`;
        if (pfEl) pfEl.textContent = formatNum(f.power_factor, 2);
      });
    }

    // 4. Solar-A
    if (data.solar_a) {
      const sa = data.solar_a;
      if (solarAGenVal) solarAGenVal.textContent = formatNum(sa.generation_kw, 1);
      if (solarATempVal) solarATempVal.textContent = `${formatNum(sa.temperature_c, 1)} °C`;
      if (solarAGridVal) solarAGridVal.textContent = `${formatNum(sa.grid_import_kw, 1)} kW`;
      if (solarABessVal) solarABessVal.textContent = `${formatNum(sa.bess_import_kw, 1)} kW`;

      if (solarAStatusBadge) {
        solarAStatusBadge.innerHTML = `
          <span class="pulse-dot" aria-hidden="true"></span>
          <span>${sa.status}</span>
        `;
        solarAStatusBadge.className = 'bus-live-badge ' + (sa.status === 'ACTIVE' ? 'active' : 'inactive');
      }
    }

    // 5. BESS-A
    if (data.bess_a) {
      const ba = data.bess_a;
      if (bessASocVal) bessASocVal.textContent = formatNum(ba.soc_pct, 1);
      if (bessASohVal) bessASohVal.textContent = `${formatNum(ba.soh_pct, 1)} %`;

      if (bessAPowerVal) {
        const sign = ba.power_kw > 0 ? '+' : '';
        bessAPowerVal.textContent = `${sign}${formatNum(ba.power_kw, 1)} kW (${ba.status})`;
      }

      if (bessAReserveVal) {
        bessAReserveVal.textContent = `${formatNum(ba.dynamic_reserve_kwh, 1)} kWh (${formatNum(ba.dynamic_reserve_soc_pct, 1)}% SOC)`;
      }

      if (bessASocBar) {
        const clampedSoc = Math.max(0, Math.min(100, ba.soc_pct));
        bessASocBar.style.width = `${clampedSoc}%`;
      }

      if (socStatusText) {
        socStatusText.textContent = ba.soc_alert ? 'Alert: Outside Bounds' : 'Normal';
        socStatusText.style.color = ba.soc_alert ? '#DC2626' : '#00843D';
      }

      if (bessAStatusBadge) {
        bessAStatusBadge.innerHTML = `
          <span class="pulse-dot" aria-hidden="true"></span>
          <span>${ba.status}</span>
        `;
        bessAStatusBadge.className = 'bus-live-badge ' + ba.status.toLowerCase();
      }
    }
  }

  // Event Listeners
  if (refreshBtn) {
    refreshBtn.addEventListener('click', (e) => {
      e.preventDefault();
      fetchBus1Telemetry();
    });
  }

  // Periodic Telemetry Refresh (every 30 seconds)
  refreshTimer = setInterval(fetchBus1Telemetry, 30000);

  // Initial fetch on mount to sync dynamic values smoothly
  fetchBus1Telemetry();
});
