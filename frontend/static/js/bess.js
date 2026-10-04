/**
 * SmartFeeder EMS — BESS Detailed Energy Storage Analysis Controller
 * Master interactive controller for BESS-A (BUS-1, 2 MWh) and BESS-B (BUS-2, 2 MWh).
 * Manages FOUR permanent independent analysis sections visible simultaneously:
 * 1. BESS STATE OF CHARGE (SOC) (3 options)
 * 2. BESS STATE OF HEALTH (SOH) (3 options)
 * 3. BESS ENERGY ANALYSIS (3 options)
 * 4. BESS POWER ANALYSIS (3 options)
 * 
 * Provides robust chart lifecycle management, mathematical consistency, and independent dropdown switching.
 */

document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const container = document.querySelector('.bess-analysis-container');
  if (!container) return;

  const bessId = container.dataset.bessId || 'a';
  const bessName = container.dataset.bessName || 'BESS-A';

  // Ensure Chart.js is available
  const ChartClass = window.Chart || (typeof Chart !== 'undefined' ? Chart : null);
  if (!ChartClass) {
    console.error('Chart.js library is not available in global scope.');
  }

  // DOM Elements - Controls
  const datePicker = document.getElementById('bessDatePicker');
  const dateBadge = document.getElementById('bessDateBadge');
  const downloadBtn = document.getElementById('btnDownloadExcel');

  // DOM Elements - Section 1: SOC
  const selectSoc = document.getElementById('selectSocAnalysis');
  const canvasSoc = document.getElementById('chartSoc');
  const canvasWrapSoc = document.getElementById('canvasWrapSoc');
  const emptyStateSoc = document.getElementById('emptyStateSoc');
  const legendSoc = document.getElementById('legendSoc');
  const titleSoc = document.getElementById('titleSocChart');
  const subtitleSoc = document.getElementById('subtitleSocChart');

  // DOM Elements - Section 2: SOH
  const selectSoh = document.getElementById('selectSohAnalysis');
  const canvasSoh = document.getElementById('chartSoh');
  const canvasWrapSoh = document.getElementById('canvasWrapSoh');
  const emptyStateSoh = document.getElementById('emptyStateSoh');
  const legendSoh = document.getElementById('legendSoh');
  const titleSoh = document.getElementById('titleSohChart');
  const subtitleSoh = document.getElementById('subtitleSohChart');

  // DOM Elements - Section 3: Energy
  const selectEnergy = document.getElementById('selectEnergyAnalysis');
  const canvasEnergy = document.getElementById('chartEnergy');
  const canvasWrapEnergy = document.getElementById('canvasWrapEnergy');
  const emptyStateEnergy = document.getElementById('emptyStateEnergy');
  const legendEnergy = document.getElementById('legendEnergy');
  const titleEnergy = document.getElementById('titleEnergyChart');
  const subtitleEnergy = document.getElementById('subtitleEnergyChart');

  // DOM Elements - Section 4: Power
  const selectPower = document.getElementById('selectPowerAnalysis');
  const canvasPower = document.getElementById('chartPower');
  const canvasWrapPower = document.getElementById('canvasWrapPower');
  const emptyStatePower = document.getElementById('emptyStatePower');
  const legendPower = document.getElementById('legendPower');
  const titlePower = document.getElementById('titlePowerChart');
  const subtitlePower = document.getElementById('subtitlePowerChart');
  const legendPowerForecastItem = document.getElementById('legendPowerForecastItem');

  // DOM Elements - Telemetry Snapshot Strip
  const snapCurrentSoc = document.getElementById('snapCurrentSoc');
  const snapCurrentSoh = document.getElementById('snapCurrentSoh');
  const snapStoredEnergy = document.getElementById('snapStoredEnergy');
  const snapCurrentPower = document.getElementById('snapCurrentPower');
  const snapStatusBadge = document.getElementById('snapStatusBadge');
  const snapStatusText = document.getElementById('snapStatusText');
  const snapDynamicReserve = document.getElementById('snapDynamicReserve');
  const snapDischReserve = document.getElementById('snapDischReserve');
  const snapChargeHeadroom = document.getElementById('snapChargeHeadroom');
  const headerStatusText = document.getElementById('headerStatusText');
  const headerStatusPulse = document.getElementById('headerStatusPulse');

  // DOM Elements - Daily Summary KPI Cards
  const summaryMinSoc = document.getElementById('summaryMinSoc');
  const summaryMaxSoc = document.getElementById('summaryMaxSoc');
  const summaryAvgSoc = document.getElementById('summaryAvgSoc');
  const summaryDailyCharged = document.getElementById('summaryDailyCharged');
  const summaryDailyDischarged = document.getElementById('summaryDailyDischarged');
  const summaryDailyCycles = document.getElementById('summaryDailyCycles');
  const summaryAvgSoh = document.getElementById('summaryAvgSoh');

  // Active Chart Instances
  let chartSocInstance = null;
  let chartSohInstance = null;
  let chartEnergyInstance = null;
  let chartPowerInstance = null;

  // Active Telemetry State
  let currentTelemetryData = null;

  // Professional Palette (Schneider Electric MNC Standard)
  const COLOR_ACTUAL = '#00843D';          // Schneider Green
  const COLOR_ACTUAL_BORDER = '#006E33';
  const COLOR_FORECAST = '#1D4ED8';        // Corporate Distribution Blue
  const COLOR_FORECAST_BORDER = '#1E40AF';
  const COLOR_DISCHARGE = '#D97706';       // Amber for Discharging
  const COLOR_DISCHARGE_BORDER = '#B45309';
  const COLOR_CHARGE = '#00843D';          // Green for Charging
  const COLOR_CHARGE_BORDER = '#006E33';

  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function formatDateDisplay(dateStr) {
    if (!dateStr) return '';
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const year = parts[0];
        const month = MONTHS[parseInt(parts[1], 10) - 1];
        const day = parts[2].padStart(2, '0');
        return `${day} ${month} ${year}`;
      }
    } catch (e) {
      return dateStr;
    }
    return dateStr;
  }

  // ==========================================================
  // 1. Data Fetching
  // ==========================================================
  async function fetchBessData(dateStr) {
    try {
      const response = await fetch(`/api/bess/${bessId}/data?date=${encodeURIComponent(dateStr)}`);
      if (!response.ok) {
        throw new Error('Failed to load BESS telemetry.');
      }
      const result = await response.json();
      if (!result || !result.success || !result.data) {
        throw new Error(result?.error || 'Invalid BESS data response.');
      }
      return result.data;
    } catch (err) {
      console.error('Error fetching BESS telemetry:', err);
      return {
        available: false,
        message: 'DATA NOT AVAILABLE',
        submessage: 'Unable to load BESS telemetry for selected date.',
        info: 'Historical BESS telemetry is available from 05-Aug-2026 onwards.'
      };
    }
  }

  // ==========================================================
  // 2. Telemetry Snapshot & Daily Summary KPI Cards
  // ==========================================================
  function updateTelemetryAndSummary(data) {
    currentTelemetryData = data;
    const dateStr = datePicker ? datePicker.value : '2026-09-29';
    const dateDisplay = formatDateDisplay(dateStr);

    if (dateBadge) dateBadge.textContent = dateDisplay;

    if (!data || !data.available) {
      // Empty snapshot values
      if (snapCurrentSoc) snapCurrentSoc.textContent = '--.-';
      if (snapCurrentSoh) snapCurrentSoh.textContent = '--.--';
      if (snapStoredEnergy) snapStoredEnergy.textContent = '--.-';
      if (snapCurrentPower) snapCurrentPower.textContent = '--.-';
      if (snapStatusBadge) snapStatusBadge.className = 'bess-status-pill idle';
      if (snapStatusText) snapStatusText.textContent = 'IDLE';
      if (snapDynamicReserve) snapDynamicReserve.textContent = '--.-';
      if (snapDischReserve) snapDischReserve.textContent = '--';
      if (snapChargeHeadroom) snapChargeHeadroom.textContent = '--';
      if (headerStatusText) headerStatusText.textContent = 'IDLE';
      if (headerStatusPulse) headerStatusPulse.style.backgroundColor = '#94A3B8';

      // Empty KPI values
      if (summaryMinSoc) summaryMinSoc.textContent = '--.-';
      if (summaryMaxSoc) summaryMaxSoc.textContent = '--.-';
      if (summaryAvgSoc) summaryAvgSoc.textContent = '--.-%';
      if (summaryDailyCharged) summaryDailyCharged.textContent = '--.-';
      if (summaryDailyDischarged) summaryDailyDischarged.textContent = '--.-';
      if (summaryDailyCycles) summaryDailyCycles.textContent = '--.--';
      if (summaryAvgSoh) summaryAvgSoh.textContent = '--.--%';
      return;
    }

    const t = data.current_telemetry || {};
    const s = data.summary || {};

    // Telemetry Snapshot
    if (snapCurrentSoc) snapCurrentSoc.textContent = (t.actual_soc_pct ?? 50.0).toFixed(1);
    if (snapCurrentSoh) snapCurrentSoh.textContent = (t.actual_soh_pct ?? 99.17).toFixed(2);
    if (snapStoredEnergy) snapStoredEnergy.textContent = (t.actual_energy_kwh ?? 1000.0).toFixed(1);
    if (snapCurrentPower) snapCurrentPower.textContent = (t.actual_power_kw ?? 0.0).toFixed(1);

    const st = (t.status || 'IDLE').toUpperCase();
    if (snapStatusBadge) {
      snapStatusBadge.className = `bess-status-pill ${st.toLowerCase()}`;
    }
    if (snapStatusText) snapStatusText.textContent = st;
    if (headerStatusText) headerStatusText.textContent = st;
    if (headerStatusPulse) {
      headerStatusPulse.style.backgroundColor = (st === 'CHARGING' || st === 'DISCHARGING') ? '#00843D' : '#94A3B8';
    }

    if (snapDynamicReserve) snapDynamicReserve.textContent = (t.reserve_discharge_kwh ?? 0.0).toFixed(1);
    if (snapDischReserve) snapDischReserve.textContent = (t.reserve_discharge_kwh ?? 0.0).toFixed(0);
    if (snapChargeHeadroom) snapChargeHeadroom.textContent = (t.headroom_charge_kwh ?? 0.0).toFixed(0);

    // Daily KPI Cards
    if (summaryMinSoc) summaryMinSoc.textContent = (s.min_soc_pct ?? 15.0).toFixed(1);
    if (summaryMaxSoc) summaryMaxSoc.textContent = (s.max_soc_pct ?? 90.0).toFixed(1);
    if (summaryAvgSoc) summaryAvgSoc.textContent = `${(s.avg_soc_pct ?? 50.0).toFixed(1)}%`;
    if (summaryDailyCharged) summaryDailyCharged.textContent = (s.daily_charged_kwh ?? 0.0).toFixed(1);
    if (summaryDailyDischarged) summaryDailyDischarged.textContent = (s.daily_discharged_kwh ?? 0.0).toFixed(1);
    if (summaryDailyCycles) summaryDailyCycles.textContent = (s.daily_cycles ?? 0.0).toFixed(2);
    if (summaryAvgSoh) summaryAvgSoh.textContent = `${(s.avg_soh_pct ?? 99.17).toFixed(2)}%`;
  }

  // ==========================================================
  // 3. SECTION 1: BESS STATE OF CHARGE (SOC) RENDERER
  // ==========================================================
  function renderSectionSoc() {
    if (chartSocInstance) {
      chartSocInstance.destroy();
      chartSocInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapSoc) canvasWrapSoc.style.display = 'none';
      if (emptyStateSoc) emptyStateSoc.classList.add('visible');
      if (legendSoc) legendSoc.style.display = 'none';
      return;
    }

    if (emptyStateSoc) emptyStateSoc.classList.remove('visible');
    if (canvasWrapSoc) canvasWrapSoc.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectSoc ? selectSoc.value : 'actual';
    const labels = hourly.map(r => r.time);
    let yAxisTitle = 'SOC (%)';
    let datasets = [];

    if (mode === 'actual') {
      if (titleSoc) titleSoc.textContent = 'ACTUAL SOC VS TIME';
      if (subtitleSoc) subtitleSoc.textContent = `24-Hour Actual State of Charge Profile for ${bessName} (15% Min &ndash; 90% Max Operating Window)`;
      if (legendSoc) legendSoc.style.display = 'none';
      yAxisTitle = 'SOC (%)';
      datasets = [{
        label: 'Actual SOC',
        data: hourly.map(r => r.actual_soc_pct),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titleSoc) titleSoc.textContent = 'FORECASTED SOC VS TIME';
      if (subtitleSoc) subtitleSoc.textContent = `24-Hour Forecasted State of Charge Trajectory for ${bessName} (%)`;
      if (legendSoc) legendSoc.style.display = 'none';
      yAxisTitle = 'Forecasted SOC (%)';
      datasets = [{
        label: 'Forecasted SOC',
        data: hourly.map(r => r.forecast_soc_pct),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted SOC
      if (titleSoc) titleSoc.textContent = 'ACTUAL VS FORECASTED SOC';
      if (subtitleSoc) subtitleSoc.textContent = `Hourly Comparison: Actual vs Forecasted State of Charge for ${bessName} (%)`;
      if (legendSoc) legendSoc.style.display = 'flex';
      yAxisTitle = 'SOC (%)';
      datasets = [
        {
          label: 'Actual SOC',
          data: hourly.map(r => r.actual_soc_pct),
          backgroundColor: COLOR_ACTUAL,
          borderColor: COLOR_ACTUAL_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted SOC',
          data: hourly.map(r => r.forecast_soc_pct),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasSoc) {
      try {
        chartSocInstance = new ChartClass(canvasSoc, {
          type: 'bar',
          data: { labels, datasets },
          options: createBessChartOptions('Time (Hours)', yAxisTitle, '%', 0, 100)
        });
      } catch (err) {
        console.error('Error mounting Section 1 chart:', err);
      }
    }
  }

  // ==========================================================
  // 4. SECTION 2: BESS STATE OF HEALTH (SOH) RENDERER
  // ==========================================================
  function renderSectionSoh() {
    if (chartSohInstance) {
      chartSohInstance.destroy();
      chartSohInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapSoh) canvasWrapSoh.style.display = 'none';
      if (emptyStateSoh) emptyStateSoh.classList.add('visible');
      if (legendSoh) legendSoh.style.display = 'none';
      return;
    }

    if (emptyStateSoh) emptyStateSoh.classList.remove('visible');
    if (canvasWrapSoh) canvasWrapSoh.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectSoh ? selectSoh.value : 'actual';
    const labels = hourly.map(r => r.time);
    let yAxisTitle = 'SOH (%)';
    let datasets = [];

    if (mode === 'actual') {
      if (titleSoh) titleSoh.textContent = 'ACTUAL SOH VS TIME';
      if (subtitleSoh) subtitleSoh.textContent = `Battery Health Index and Capacity Retention for ${bessName} (%)`;
      if (legendSoh) legendSoh.style.display = 'none';
      yAxisTitle = 'SOH (%)';
      datasets = [{
        label: 'Actual SOH',
        data: hourly.map(r => r.actual_soh_pct),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titleSoh) titleSoh.textContent = 'FORECASTED SOH VS TIME';
      if (subtitleSoh) subtitleSoh.textContent = `Projected SOH Degradation Trajectory for ${bessName} (%)`;
      if (legendSoh) legendSoh.style.display = 'none';
      yAxisTitle = 'Forecasted SOH (%)';
      datasets = [{
        label: 'Forecasted SOH',
        data: hourly.map(r => r.forecast_soh_pct),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted SOH
      if (titleSoh) titleSoh.textContent = 'ACTUAL VS FORECASTED SOH';
      if (subtitleSoh) subtitleSoh.textContent = `Comparison: Actual vs Forecasted Battery Health for ${bessName} (%)`;
      if (legendSoh) legendSoh.style.display = 'flex';
      yAxisTitle = 'SOH (%)';
      datasets = [
        {
          label: 'Actual SOH',
          data: hourly.map(r => r.actual_soh_pct),
          backgroundColor: COLOR_ACTUAL,
          borderColor: COLOR_ACTUAL_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted SOH',
          data: hourly.map(r => r.forecast_soh_pct),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasSoh) {
      try {
        chartSohInstance = new ChartClass(canvasSoh, {
          type: 'bar',
          data: { labels, datasets },
          options: createBessChartOptions('Time (Hours)', yAxisTitle, '%', 95, 100)
        });
      } catch (err) {
        console.error('Error mounting Section 2 chart:', err);
      }
    }
  }

  // ==========================================================
  // 5. SECTION 3: BESS ENERGY ANALYSIS RENDERER
  // ==========================================================
  function renderSectionEnergy() {
    if (chartEnergyInstance) {
      chartEnergyInstance.destroy();
      chartEnergyInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapEnergy) canvasWrapEnergy.style.display = 'none';
      if (emptyStateEnergy) emptyStateEnergy.classList.add('visible');
      if (legendEnergy) legendEnergy.style.display = 'none';
      return;
    }

    if (emptyStateEnergy) emptyStateEnergy.classList.remove('visible');
    if (canvasWrapEnergy) canvasWrapEnergy.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectEnergy ? selectEnergy.value : 'actual';
    const labels = hourly.map(r => r.time);
    let yAxisTitle = 'Stored Energy (kWh)';
    let datasets = [];

    if (mode === 'actual') {
      if (titleEnergy) titleEnergy.textContent = 'ACTUAL ENERGY VS TIME';
      if (subtitleEnergy) subtitleEnergy.textContent = `24-Hour Stored Energy Profile for ${bessName} (kWh, based on 2000 kWh Capacity)`;
      if (legendEnergy) legendEnergy.style.display = 'none';
      yAxisTitle = 'Stored Energy (kWh)';
      datasets = [{
        label: 'Actual Stored Energy',
        data: hourly.map(r => r.actual_energy_kwh),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titleEnergy) titleEnergy.textContent = 'FORECASTED ENERGY VS TIME';
      if (subtitleEnergy) subtitleEnergy.textContent = `24-Hour Forecasted Stored Energy for ${bessName} (kWh)`;
      if (legendEnergy) legendEnergy.style.display = 'none';
      yAxisTitle = 'Forecasted Stored Energy (kWh)';
      datasets = [{
        label: 'Forecasted Stored Energy',
        data: hourly.map(r => r.forecast_energy_kwh),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted Energy
      if (titleEnergy) titleEnergy.textContent = 'ACTUAL VS FORECASTED ENERGY';
      if (subtitleEnergy) subtitleEnergy.textContent = `Hourly Comparison: Actual vs Forecasted Energy for ${bessName} (kWh)`;
      if (legendEnergy) legendEnergy.style.display = 'flex';
      yAxisTitle = 'Stored Energy (kWh)';
      datasets = [
        {
          label: 'Actual Energy',
          data: hourly.map(r => r.actual_energy_kwh),
          backgroundColor: COLOR_ACTUAL,
          borderColor: COLOR_ACTUAL_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted Energy',
          data: hourly.map(r => r.forecast_energy_kwh),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasEnergy) {
      try {
        chartEnergyInstance = new ChartClass(canvasEnergy, {
          type: 'bar',
          data: { labels, datasets },
          options: createBessChartOptions('Time (Hours)', yAxisTitle, 'kWh', 0, 2000)
        });
      } catch (err) {
        console.error('Error mounting Section 3 chart:', err);
      }
    }
  }

  // ==========================================================
  // 6. SECTION 4: BESS POWER ANALYSIS RENDERER
  // ==========================================================
  function renderSectionPower() {
    if (chartPowerInstance) {
      chartPowerInstance.destroy();
      chartPowerInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapPower) canvasWrapPower.style.display = 'none';
      if (emptyStatePower) emptyStatePower.classList.add('visible');
      if (legendPower) legendPower.style.display = 'none';
      return;
    }

    if (emptyStatePower) emptyStatePower.classList.remove('visible');
    if (canvasWrapPower) canvasWrapPower.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectPower ? selectPower.value : 'actual';
    const labels = hourly.map(r => r.time);
    let yAxisTitle = 'BESS Power (kW)';
    let datasets = [];

    if (mode === 'actual') {
      if (titlePower) titlePower.textContent = 'ACTUAL POWER VS TIME';
      if (subtitlePower) subtitlePower.textContent = `24-Hour Power Dispatch for ${bessName} ((+) Discharging / (-) Charging in kW)`;
      if (legendPower) legendPower.style.display = 'flex';
      if (legendPowerForecastItem) legendPowerForecastItem.style.display = 'none';
      yAxisTitle = 'BESS Power (kW)';

      // Color positive power (discharging) Amber, negative power (charging) Green
      const bgColors = hourly.map(r => r.actual_power_kw >= 0 ? COLOR_DISCHARGE : COLOR_CHARGE);
      const borderColors = hourly.map(r => r.actual_power_kw >= 0 ? COLOR_DISCHARGE_BORDER : COLOR_CHARGE_BORDER);

      datasets = [{
        label: 'Actual Power',
        data: hourly.map(r => r.actual_power_kw),
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titlePower) titlePower.textContent = 'FORECASTED POWER VS TIME';
      if (subtitlePower) subtitlePower.textContent = `24-Hour Forecasted Active Power Dispatch for ${bessName} (kW)`;
      if (legendPower) legendPower.style.display = 'none';
      yAxisTitle = 'Forecasted Power (kW)';
      datasets = [{
        label: 'Forecasted Power',
        data: hourly.map(r => r.forecast_power_kw),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted Power
      if (titlePower) titlePower.textContent = 'ACTUAL VS FORECASTED POWER';
      if (subtitlePower) subtitlePower.textContent = `Hourly Comparison: Actual vs Forecasted Power Dispatch for ${bessName} (kW)`;
      if (legendPower) legendPower.style.display = 'flex';
      if (legendPowerForecastItem) legendPowerForecastItem.style.display = 'inline-flex';
      yAxisTitle = 'BESS Power (kW)';

      const bgColors = hourly.map(r => r.actual_power_kw >= 0 ? COLOR_DISCHARGE : COLOR_CHARGE);

      datasets = [
        {
          label: 'Actual Power',
          data: hourly.map(r => r.actual_power_kw),
          backgroundColor: bgColors,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted Power',
          data: hourly.map(r => r.forecast_power_kw),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasPower) {
      try {
        chartPowerInstance = new ChartClass(canvasPower, {
          type: 'bar',
          data: { labels, datasets },
          options: createBessChartOptions('Time (Hours)', yAxisTitle, 'kW', null, null)
        });
      } catch (err) {
        console.error('Error mounting Section 4 chart:', err);
      }
    }
  }

  // ==========================================================
  // 7. Chart.js Shared Config Helper
  // ==========================================================
  function createBessChartOptions(xAxisTitle, yAxisTitle, unit, yMin = null, yMax = null) {
    const scalesY = {
      grid: {
        color: 'rgba(15, 23, 42, 0.06)'
      },
      ticks: {
        color: '#64748B',
        font: { family: 'JetBrains Mono', size: 11 },
        callback: function(val) {
          return `${val} ${unit}`;
        }
      },
      title: {
        display: true,
        text: yAxisTitle,
        color: '#475569',
        font: { family: 'Inter', size: 11, weight: '700' },
        padding: { bottom: 8 }
      }
    };

    if (yMin !== null) scalesY.min = yMin;
    if (yMax !== null) scalesY.max = yMax;

    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 250
      },
      plugins: {
        legend: {
          display: false // We use our custom headers for cleaner enterprise styling
        },
        tooltip: {
          enabled: true,
          backgroundColor: '#0F172A',
          titleColor: '#FFFFFF',
          bodyColor: '#E2E8F0',
          borderColor: 'rgba(255, 255, 255, 0.12)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 6,
          titleFont: { family: 'Inter', size: 12, weight: '700' },
          bodyFont: { family: 'JetBrains Mono', size: 11, weight: '500' },
          callbacks: {
            title: function(items) {
              return items && items.length > 0 ? items[0].label : '';
            },
            label: function(context) {
              const val = context.parsed.y !== null && context.parsed.y !== undefined
                ? Number(context.parsed.y).toFixed(2)
                : '0.00';
              return ` ${context.dataset.label}: ${val} ${unit}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            display: false
          },
          ticks: {
            color: '#64748B',
            font: { family: 'JetBrains Mono', size: 11 },
            maxRotation: 45,
            minRotation: 0
          },
          title: {
            display: true,
            text: xAxisTitle,
            color: '#475569',
            font: { family: 'Inter', size: 11, weight: '700' },
            padding: { top: 8 }
          }
        },
        y: scalesY
      }
    };
  }

  // ==========================================================
  // 8. Event Listeners
  // ==========================================================

  // Date selection change -> updates all 4 sections simultaneously
  datePicker?.addEventListener('change', async (e) => {
    const newDate = e.target.value;
    if (!newDate) return;
    const data = await fetchBessData(newDate);
    updateTelemetryAndSummary(data);
    renderSectionSoc();
    renderSectionSoh();
    renderSectionEnergy();
    renderSectionPower();
  });

  // Independent Section 1 dropdown change -> updates ONLY Section 1
  selectSoc?.addEventListener('change', () => {
    renderSectionSoc();
  });

  // Independent Section 2 dropdown change -> updates ONLY Section 2
  selectSoh?.addEventListener('change', () => {
    renderSectionSoh();
  });

  // Independent Section 3 dropdown change -> updates ONLY Section 3
  selectEnergy?.addEventListener('change', () => {
    renderSectionEnergy();
  });

  // Independent Section 4 dropdown change -> updates ONLY Section 4
  selectPower?.addEventListener('change', () => {
    renderSectionPower();
  });

  // Excel download button
  downloadBtn?.addEventListener('click', () => {
    const selectedDate = datePicker ? datePicker.value : '2026-09-29';
    window.location.href = `/api/bess/${bessId}/download?date=${encodeURIComponent(selectedDate)}`;
  });

  // ==========================================================
  // 9. Initial Page Load (renders all 4 sections immediately)
  // ==========================================================
  (async function init() {
    let initialData = null;

    // Check embedded telemetry first for instant zero-lag rendering
    const embeddedElem = document.getElementById('initialBessTelemetry');
    if (embeddedElem && embeddedElem.textContent) {
      try {
        const parsed = JSON.parse(embeddedElem.textContent.trim());
        if (parsed && parsed.available) {
          initialData = parsed;
        }
      } catch (err) {
        console.warn('Unable to parse embedded initial BESS telemetry:', err);
      }
    }

    // Fall back to API fetch if embedded data was not available
    if (!initialData) {
      const initialDate = datePicker ? datePicker.value : '2026-09-29';
      initialData = await fetchBessData(initialDate);
    }

    updateTelemetryAndSummary(initialData);
    renderSectionSoc();
    renderSectionSoh();
    renderSectionEnergy();
    renderSectionPower();
  })();

});
