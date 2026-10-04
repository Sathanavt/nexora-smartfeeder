/**
 * SmartFeeder EMS — BUS-2 Detailed Dashboard Controller
 * Fetches real-time telemetry from /api/bus/2/live and updates
 * Summary metrics, Feeders 5 to 8, Solar-B, and BESS-B.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // DOM Elements - Header & Summary
  const tsVal = document.getElementById('busTsVal');
  const refreshBtn = document.getElementById('btnRefreshBus2');
  const summaryDemand = document.getElementById('summaryDemand');
  const summaryVoltage = document.getElementById('summaryVoltage');
  const summaryCurrent = document.getElementById('summaryCurrent');
  const summaryFreq = document.getElementById('summaryFreq');
  const summarySolarStatus = document.getElementById('summarySolarStatus');
  const summaryBessStatus = document.getElementById('summaryBessStatus');

  // DOM Elements - Solar-B
  const solarBGenVal = document.getElementById('solarBGenVal');
  const solarBTempVal = document.getElementById('solarBTempVal');
  const solarBGridVal = document.getElementById('solarBGridVal');
  const solarBBessVal = document.getElementById('solarBBessVal');
  const solarBStatusBadge = document.getElementById('solarBStatusBadge');

  // DOM Elements - BESS-B
  const bessBSocVal = document.getElementById('bessBSocVal');
  const bessBSohVal = document.getElementById('bessBSohVal');
  const bessBPowerVal = document.getElementById('bessBPowerVal');
  const bessBReserveVal = document.getElementById('bessBReserveVal');
  const bessBSocBar = document.getElementById('bessBSocBar');
  const bessBStatusBadge = document.getElementById('bessBStatusBadge');
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

  async function fetchBus2Telemetry() {
    if (isFetching) return;
    isFetching = true;

    if (refreshBtn) refreshBtn.classList.add('spinning');

    try {
      const res = await window.DashboardApi.getBus2Live();
      if (res && res.success && res.data) {
        updateUI(res.data);
      }
    } catch (err) {
      console.warn('Error fetching BUS-2 telemetry:', err);
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

    // 3. Feeders 5 to 8
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

    // 4. Solar-B
    if (data.solar_b) {
      const sb = data.solar_b;
      if (solarBGenVal) solarBGenVal.textContent = formatNum(sb.generation_kw, 1);
      if (solarBTempVal) solarBTempVal.textContent = `${formatNum(sb.temperature_c, 1)} °C`;
      if (solarBGridVal) solarBGridVal.textContent = `${formatNum(sb.grid_import_kw, 1)} kW`;
      if (solarBBessVal) solarBBessVal.textContent = `${formatNum(sb.bess_import_kw, 1)} kW`;

      if (solarBStatusBadge) {
        solarBStatusBadge.innerHTML = `
          <span class="pulse-dot" aria-hidden="true"></span>
          <span>${sb.status}</span>
        `;
        solarBStatusBadge.className = 'bus-live-badge ' + (sb.status === 'ACTIVE' ? 'active' : 'inactive');
      }
    }

    // 5. BESS-B
    if (data.bess_b) {
      const bb = data.bess_b;
      if (bessBSocVal) bessBSocVal.textContent = formatNum(bb.soc_pct, 1);
      if (bessBSohVal) bessBSohVal.textContent = `${formatNum(bb.soh_pct, 1)} %`;

      if (bessBPowerVal) {
        const sign = bb.power_kw > 0 ? '+' : '';
        bessBPowerVal.textContent = `${sign}${formatNum(bb.power_kw, 1)} kW (${bb.status})`;
      }

      if (bessBReserveVal) {
        bessBReserveVal.textContent = `${formatNum(bb.dynamic_reserve_kwh, 1)} kWh (${formatNum(bb.dynamic_reserve_soc_pct, 1)}% SOC)`;
      }

      if (bessBSocBar) {
        const clampedSoc = Math.max(0, Math.min(100, bb.soc_pct));
        bessBSocBar.style.width = `${clampedSoc}%`;
      }

      if (socStatusText) {
        socStatusText.textContent = bb.soc_alert ? 'Alert: Outside Bounds' : 'Normal';
        socStatusText.style.color = bb.soc_alert ? '#DC2626' : '#00843D';
      }

      if (bessBStatusBadge) {
        bessBStatusBadge.innerHTML = `
          <span class="pulse-dot" aria-hidden="true"></span>
          <span>${bb.status}</span>
        `;
        bessBStatusBadge.className = 'bus-live-badge ' + bb.status.toLowerCase();
      }
    }
  }

  // Refresh Button Listener
  if (refreshBtn) {
    refreshBtn.addEventListener('click', (e) => {
      e.preventDefault();
      fetchBus2Telemetry();
    });
  }

  // Background Auto-Refresh every 30 seconds
  refreshTimer = setInterval(fetchBus2Telemetry, 30000);

  window.addEventListener('beforeunload', () => {
    if (refreshTimer) clearInterval(refreshTimer);
  });
});
