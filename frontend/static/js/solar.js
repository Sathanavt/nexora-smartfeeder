/**
 * SmartFeeder EMS — Solar Detailed Analysis Controller
 * Master interactive controller for Solar-A (BUS-1, 495 kW) and Solar-B (BUS-2, 420 kW).
 * Manages THREE permanent independent analysis sections visible simultaneously:
 * 1. SOLAR GENERATION VS TIME (3 options)
 * 2. SOLAR GENERATION VS TEMPERATURE (3 options)
 * 3. SOLAR UTILIZATION (1 option)
 * 
 * Provides robust chart lifecycle management, data binding, and independent dropdown switching.
 */

document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const container = document.querySelector('.solar-analysis-container');
  if (!container) return;

  const solarId = container.dataset.solarId || 'a';
  const solarName = container.dataset.solarName || 'Solar-A';

  // Ensure Chart.js is available
  const ChartClass = window.Chart || (typeof Chart !== 'undefined' ? Chart : null);
  if (!ChartClass) {
    console.error('Chart.js library is not available in global scope.');
  }

  // DOM Elements - Controls
  const datePicker = document.getElementById('solarDatePicker');
  const dateBadge = document.getElementById('solarDateBadge');
  const downloadBtn = document.getElementById('btnDownloadExcel');

  // DOM Elements - Section 1: Time
  const selectTime = document.getElementById('selectTimeAnalysis');
  const canvasTime = document.getElementById('chartTime');
  const canvasWrapTime = document.getElementById('canvasWrapTime');
  const emptyStateTime = document.getElementById('emptyStateTime');
  const legendTime = document.getElementById('legendTime');
  const titleTime = document.getElementById('titleTimeChart');
  const subtitleTime = document.getElementById('subtitleTimeChart');

  // DOM Elements - Section 2: Temperature
  const selectTemp = document.getElementById('selectTempAnalysis');
  const canvasTemp = document.getElementById('chartTemp');
  const canvasWrapTemp = document.getElementById('canvasWrapTemp');
  const emptyStateTemp = document.getElementById('emptyStateTemp');
  const legendTemp = document.getElementById('legendTemp');
  const titleTemp = document.getElementById('titleTempChart');
  const subtitleTemp = document.getElementById('subtitleTempChart');

  // DOM Elements - Section 3: Solar Utilization
  const selectPower = document.getElementById('selectPowerAnalysis');
  const canvasPower = document.getElementById('chartPower');
  const canvasWrapPower = document.getElementById('canvasWrapPower');
  const emptyStatePower = document.getElementById('emptyStatePower');
  const legendPower = document.getElementById('legendPower');
  const titlePower = document.getElementById('titlePowerChart');
  const subtitlePower = document.getElementById('subtitlePowerChart');
  const legendPowerDot1 = document.getElementById('legendPowerDot1');
  const legendPowerText1 = document.getElementById('legendPowerText1');
  const legendPowerDot2 = document.getElementById('legendPowerDot2');
  const legendPowerText2 = document.getElementById('legendPowerText2');

  // DOM Elements - Telemetry Snapshot Strip
  const snapCurrentGen = document.getElementById('snapCurrentGen');
  const snapTemperature = document.getElementById('snapTemperature');
  const snapGridImport = document.getElementById('snapGridImport');
  const snapBessImport = document.getElementById('snapBessImport');
  const snapStatusBadge = document.getElementById('snapStatusBadge');
  const snapStatusText = document.getElementById('snapStatusText');

  // DOM Elements - Daily Summary KPI Cards
  const summaryPeakGen = document.getElementById('summaryPeakGen');
  const summaryPeakTime = document.getElementById('summaryPeakTime');
  const summaryDailyGen = document.getElementById('summaryDailyGen');
  const summaryDailyUtilized = document.getElementById('summaryDailyUtilized');
  const summaryUtilRate = document.getElementById('summaryUtilRate');
  const summaryAvgTemp = document.getElementById('summaryAvgTemp');
  const summaryMaxTemp = document.getElementById('summaryMaxTemp');

  // Active Chart Instances
  let chartTimeInstance = null;
  let chartTempInstance = null;
  let chartPowerInstance = null;

  // Active Telemetry State
  let currentTelemetryData = null;

  // Professional Palette (Schneider Electric MNC Standard)
  const COLOR_ACTUAL = '#00843D';      // Schneider Electric Green
  const COLOR_ACTUAL_BORDER = '#006E33';
  const COLOR_FORECAST = '#1D4ED8';    // Corporate Distribution Blue
  const COLOR_FORECAST_BORDER = '#1E40AF';
  const COLOR_UTILIZED = '#0284C7';    // Sky Cyan for Local Solar Utilization
  const COLOR_UTILIZED_BORDER = '#0369A1';

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
  async function fetchSolarData(dateStr) {
    try {
      const response = await fetch(`/api/solar/${solarId}/data?date=${encodeURIComponent(dateStr)}`);
      if (!response.ok) {
        throw new Error('Failed to load solar telemetry.');
      }
      const result = await response.json();
      if (!result || !result.success || !result.data) {
        throw new Error(result?.error || 'Invalid solar data response.');
      }
      return result.data;
    } catch (err) {
      console.error('Error fetching solar telemetry:', err);
      return {
        available: false,
        message: 'DATA NOT AVAILABLE',
        submessage: 'Unable to load solar data for selected date.',
        info: 'Historical solar data is available from 05-Aug-2026.'
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
      if (snapCurrentGen) snapCurrentGen.textContent = '--.-';
      if (snapTemperature) snapTemperature.textContent = '--.-';
      if (snapGridImport) snapGridImport.textContent = '--.-';
      if (snapBessImport) snapBessImport.textContent = '--.-';
      if (snapStatusBadge) snapStatusBadge.className = 'solar-status-pill inactive';
      if (snapStatusText) snapStatusText.textContent = 'INACTIVE';

      // Empty KPI values
      if (summaryPeakGen) summaryPeakGen.textContent = '--.--';
      if (summaryPeakTime) summaryPeakTime.textContent = '--:--';
      if (summaryDailyGen) summaryDailyGen.textContent = '--.-';
      if (summaryDailyUtilized) summaryDailyUtilized.textContent = '--.-';
      if (summaryUtilRate) summaryUtilRate.textContent = '--.-%';
      if (summaryAvgTemp) summaryAvgTemp.textContent = '--.-';
      if (summaryMaxTemp) summaryMaxTemp.textContent = '--.-°C';
      return;
    }

    const t = data.current_telemetry || {};
    const s = data.summary || {};

    // Telemetry Snapshot
    if (snapCurrentGen) snapCurrentGen.textContent = (t.generation_kw ?? 0).toFixed(1);
    if (snapTemperature) snapTemperature.textContent = (t.temperature_c ?? 0).toFixed(1);
    if (snapGridImport) snapGridImport.textContent = (t.grid_import_kw ?? 0).toFixed(1);
    if (snapBessImport) snapBessImport.textContent = (t.bess_import_kw ?? 0).toFixed(1);

    const isActive = (t.status || 'INACTIVE').toUpperCase() === 'ACTIVE';
    if (snapStatusBadge) {
      snapStatusBadge.className = `solar-status-pill ${isActive ? 'active' : 'inactive'}`;
    }
    if (snapStatusText) snapStatusText.textContent = isActive ? 'ACTIVE' : 'INACTIVE';

    // Daily KPI Cards
    if (summaryPeakGen) summaryPeakGen.textContent = (s.peak_generation_kw ?? 0).toFixed(2);
    if (summaryPeakTime) summaryPeakTime.textContent = s.peak_time || '--:--';
    if (summaryDailyGen) summaryDailyGen.textContent = (s.daily_generation_kwh ?? 0).toFixed(1);
    if (summaryDailyUtilized) summaryDailyUtilized.textContent = (s.daily_utilized_kwh ?? 0).toFixed(1);
    if (summaryUtilRate) summaryUtilRate.textContent = `${(s.utilization_rate_pct ?? 0).toFixed(1)}%`;
    if (summaryAvgTemp) summaryAvgTemp.textContent = (s.avg_temperature_c ?? 0).toFixed(1);
    if (summaryMaxTemp) summaryMaxTemp.textContent = `${(s.max_temperature_c ?? 0).toFixed(1)}°C`;
  }

  // ==========================================================
  // 3. SECTION 1: SOLAR GENERATION VS TIME RENDERER
  // ==========================================================
  function renderSectionTime() {
    if (chartTimeInstance) {
      chartTimeInstance.destroy();
      chartTimeInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapTime) canvasWrapTime.style.display = 'none';
      if (emptyStateTime) emptyStateTime.classList.add('visible');
      if (legendTime) legendTime.style.display = 'none';
      return;
    }

    if (emptyStateTime) emptyStateTime.classList.remove('visible');
    if (canvasWrapTime) canvasWrapTime.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectTime ? selectTime.value : 'actual';
    const labels = hourly.map(r => r.time);
    let yAxisTitle = 'Solar Generation (kW)';
    let datasets = [];

    if (mode === 'actual') {
      if (titleTime) titleTime.textContent = 'ACTUAL GENERATION VS TIME';
      if (subtitleTime) subtitleTime.textContent = `24-Hour Actual Solar Generation Profile for ${solarName} (kW)`;
      if (legendTime) legendTime.style.display = 'none';
      yAxisTitle = 'Solar Generation (kW)';
      datasets = [{
        label: 'Actual Generation',
        data: hourly.map(r => r.actual_generation_kw),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titleTime) titleTime.textContent = 'FORECASTED GENERATION VS TIME';
      if (subtitleTime) subtitleTime.textContent = `24-Hour Forecasted Solar Generation Profile for ${solarName} (kW)`;
      if (legendTime) legendTime.style.display = 'none';
      yAxisTitle = 'Forecasted Solar Generation (kW)';
      datasets = [{
        label: 'Forecasted Generation',
        data: hourly.map(r => r.forecast_generation_kw),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted Generation
      if (titleTime) titleTime.textContent = 'ACTUAL VS FORECASTED GENERATION';
      if (subtitleTime) subtitleTime.textContent = `Hourly Comparison: Actual vs Forecasted Solar Generation for ${solarName} (kW)`;
      if (legendTime) legendTime.style.display = 'flex';
      yAxisTitle = 'Generation (kW)';
      datasets = [
        {
          label: 'Actual Generation',
          data: hourly.map(r => r.actual_generation_kw),
          backgroundColor: COLOR_ACTUAL,
          borderColor: COLOR_ACTUAL_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted Generation',
          data: hourly.map(r => r.forecast_generation_kw),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasTime) {
      try {
        chartTimeInstance = new ChartClass(canvasTime, {
          type: 'bar',
          data: { labels, datasets },
          options: createBarChartOptions('Time (Hours)', yAxisTitle, hourly)
        });
      } catch (err) {
        console.error('Error mounting Section 1 chart:', err);
      }
    }
  }

  // ==========================================================
  // 4. SECTION 2: SOLAR GENERATION VS TEMPERATURE RENDERER
  // ==========================================================
  function renderSectionTemp() {
    if (chartTempInstance) {
      chartTempInstance.destroy();
      chartTempInstance = null;
    }

    if (!currentTelemetryData || !currentTelemetryData.available) {
      if (canvasWrapTemp) canvasWrapTemp.style.display = 'none';
      if (emptyStateTemp) emptyStateTemp.classList.add('visible');
      if (legendTemp) legendTemp.style.display = 'none';
      return;
    }

    if (emptyStateTemp) emptyStateTemp.classList.remove('visible');
    if (canvasWrapTemp) canvasWrapTemp.style.display = 'block';

    const hourly = currentTelemetryData.hourly || [];
    const mode = selectTemp ? selectTemp.value : 'actual';

    // Sort ascending by temperature for thermal progression
    const sorted = [...hourly].sort((a, b) => a.temperature_c - b.temperature_c);
    const labels = sorted.map(r => `${r.temperature_c.toFixed(1)}°C (${r.time})`);
    let yAxisTitle = 'Solar Generation (kW)';
    let datasets = [];

    if (mode === 'actual') {
      if (titleTemp) titleTemp.textContent = 'ACTUAL GENERATION VS TEMPERATURE';
      if (subtitleTemp) subtitleTemp.textContent = `Hourly Actual Solar Generation vs Temperature for ${solarName}`;
      if (legendTemp) legendTemp.style.display = 'none';
      yAxisTitle = 'Solar Generation (kW)';
      datasets = [{
        label: 'Actual Generation',
        data: sorted.map(r => r.actual_generation_kw),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else if (mode === 'forecast') {
      if (titleTemp) titleTemp.textContent = 'FORECASTED GENERATION VS TEMPERATURE';
      if (subtitleTemp) subtitleTemp.textContent = `Forecasted Solar Generation vs Temperature for ${solarName}`;
      if (legendTemp) legendTemp.style.display = 'none';
      yAxisTitle = 'Forecasted Solar Generation (kW)';
      datasets = [{
        label: 'Forecasted Generation',
        data: sorted.map(r => r.forecast_generation_kw),
        backgroundColor: COLOR_FORECAST,
        borderColor: COLOR_FORECAST_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.65
      }];
    } else {
      // Comparison: Actual vs Forecasted Generation vs Temperature
      if (titleTemp) titleTemp.textContent = 'ACTUAL VS FORECASTED GENERATION VS TEMPERATURE';
      if (subtitleTemp) subtitleTemp.textContent = `Hourly Comparison: Actual vs Forecasted Output with respect to Temperature`;
      if (legendTemp) legendTemp.style.display = 'flex';
      yAxisTitle = 'Generation (kW)';
      datasets = [
        {
          label: 'Actual Generation',
          data: sorted.map(r => r.actual_generation_kw),
          backgroundColor: COLOR_ACTUAL,
          borderColor: COLOR_ACTUAL_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        },
        {
          label: 'Forecasted Generation',
          data: sorted.map(r => r.forecast_generation_kw),
          backgroundColor: COLOR_FORECAST,
          borderColor: COLOR_FORECAST_BORDER,
          borderWidth: 1,
          borderRadius: 4,
          barPercentage: 0.75,
          categoryPercentage: 0.8
        }
      ];
    }

    if (ChartClass && canvasTemp) {
      try {
        chartTempInstance = new ChartClass(canvasTemp, {
          type: 'bar',
          data: { labels, datasets },
          options: createBarChartOptions('Temperature (°C)', yAxisTitle, sorted)
        });
      } catch (err) {
        console.error('Error mounting Section 2 chart:', err);
      }
    }
  }

  // ==========================================================
  // 5. SECTION 3: SOLAR UTILIZATION RENDERER
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
    const labels = hourly.map(r => r.time);

    if (legendPower) legendPower.style.display = 'flex';
    if (titlePower) titlePower.textContent = 'SOLAR GENERATED VS UTILIZED';
    if (subtitlePower) subtitlePower.textContent = `Hourly Comparison: Solar Generated vs Utilized for ${solarName} (kW)`;
    if (legendPowerText1) legendPowerText1.textContent = 'Solar Generated';
    if (legendPowerDot1) legendPowerDot1.style.backgroundColor = COLOR_ACTUAL;
    if (legendPowerText2) legendPowerText2.textContent = 'Solar Utilized';
    if (legendPowerDot2) legendPowerDot2.style.backgroundColor = COLOR_UTILIZED;

    const datasets = [
      {
        label: 'Solar Generated',
        data: hourly.map(r => r.actual_generation_kw),
        backgroundColor: COLOR_ACTUAL,
        borderColor: COLOR_ACTUAL_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.75,
        categoryPercentage: 0.8
      },
      {
        label: 'Solar Utilized',
        data: hourly.map(r => r.utilized_kw),
        backgroundColor: COLOR_UTILIZED,
        borderColor: COLOR_UTILIZED_BORDER,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.75,
        categoryPercentage: 0.8
      }
    ];

    if (ChartClass && canvasPower) {
      try {
        chartPowerInstance = new ChartClass(canvasPower, {
          type: 'bar',
          data: { labels, datasets },
          options: createBarChartOptions('Time (Hours)', 'Generation (kW)', hourly)
        });
      } catch (err) {
        console.error('Error mounting Section 3 chart:', err);
      }
    }
  }

  // ==========================================================
  // 6. Chart.js Shared Config Helper
  // ==========================================================
  function createBarChartOptions(xAxisTitle, yAxisTitle, records) {
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
              return ` ${context.dataset.label}: ${val} kW`;
            },
            afterLabel: function(context) {
              const idx = context.dataIndex;
              const rec = records ? records[idx] : null;
              if (rec && rec.temperature_c !== undefined) {
                return ` Temp: ${Number(rec.temperature_c).toFixed(1)}°C`;
              }
              return '';
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
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(15, 23, 42, 0.06)'
          },
          ticks: {
            color: '#64748B',
            font: { family: 'JetBrains Mono', size: 11 },
            callback: function(val) {
              return `${val} kW`;
            }
          },
          title: {
            display: true,
            text: yAxisTitle,
            color: '#475569',
            font: { family: 'Inter', size: 11, weight: '700' },
            padding: { bottom: 8 }
          }
        }
      }
    };
  }

  // ==========================================================
  // 7. Event Listeners
  // ==========================================================

  // Date selection change -> updates all 3 sections simultaneously
  datePicker?.addEventListener('change', async (e) => {
    const newDate = e.target.value;
    if (!newDate) return;
    const data = await fetchSolarData(newDate);
    updateTelemetryAndSummary(data);
    renderSectionTime();
    renderSectionTemp();
    renderSectionPower();
  });

  // Independent Section 1 dropdown change -> updates ONLY Section 1
  selectTime?.addEventListener('change', () => {
    renderSectionTime();
  });

  // Independent Section 2 dropdown change -> updates ONLY Section 2
  selectTemp?.addEventListener('change', () => {
    renderSectionTemp();
  });

  // Independent Section 3 dropdown change -> updates ONLY Section 3
  selectPower?.addEventListener('change', () => {
    renderSectionPower();
  });

  // Excel download button
  downloadBtn?.addEventListener('click', () => {
    const selectedDate = datePicker ? datePicker.value : '2026-09-29';
    window.location.href = `/api/solar/${solarId}/download?date=${encodeURIComponent(selectedDate)}`;
  });

  // ==========================================================
  // 8. Initial Page Load
  // ==========================================================
  (async function init() {
    let initialData = null;

    // Check embedded telemetry first for instant zero-lag rendering
    const embeddedElem = document.getElementById('initialSolarTelemetry');
    if (embeddedElem && embeddedElem.textContent) {
      try {
        const parsed = JSON.parse(embeddedElem.textContent.trim());
        if (parsed && parsed.available) {
          initialData = parsed;
        }
      } catch (err) {
        console.warn('Unable to parse embedded initial solar telemetry:', err);
      }
    }

    // Fall back to API fetch if embedded data was not available
    if (!initialData) {
      const initialDate = datePicker ? datePicker.value : '2026-09-29';
      initialData = await fetchSolarData(initialDate);
    }

    updateTelemetryAndSummary(initialData);
    renderSectionTime();
    renderSectionTemp();
    renderSectionPower();
  })();

});
