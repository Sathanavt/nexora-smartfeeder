/**
 * SmartFeeder EMS — Feeder Detailed Demand Analysis Controller
 * Master interactive controller for Feeder 1 through Feeder 8.
 * Controls date selection, analysis modes, Chart.js rendering,
 * data availability states, and Excel downloads.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  const container = document.querySelector('.feeder-analysis-container');
  if (!container) return;

  const feederId = container.getAttribute('data-feeder-id') || '1';
  const feederName = container.getAttribute('data-feeder-name') || 'FEEDER-1';

  // DOM Elements - Controls
  const datePicker = document.getElementById('feederDatePicker');
  const dateBadge = document.getElementById('feederDateBadge');
  const analysisSelect = document.getElementById('analysisSelect');
  const btnDownloadExcel = document.getElementById('btnDownloadExcel');

  // DOM Elements - Chart & State
  const chartCanvas = document.getElementById('feederDemandChart');
  const chartCanvasWrapper = document.getElementById('chartCanvasWrapper');
  const emptyState = document.getElementById('feederEmptyState');
  const emptyStateTitle = document.getElementById('emptyStateTitle');
  const emptyStateSub = document.getElementById('emptyStateSub');
  const emptyStateInfo = document.getElementById('emptyStateInfo');
  const chartMainTitle = document.getElementById('chartMainTitle');
  const chartSubtitle = document.getElementById('chartSubtitle');
  const chartDateChip = document.getElementById('chartDateChip');
  const chartSeriesLegend = document.getElementById('chartSeriesLegend');

  // DOM Elements - Summary KPIs
  const summaryPeakDemand = document.getElementById('summaryPeakDemand');
  const summaryPeakTime = document.getElementById('summaryPeakTime');
  const summaryPeakDuration = document.getElementById('summaryPeakDuration');
  const summaryPeakThreshold = document.getElementById('summaryPeakThreshold');
  const summaryDailyEnergy = document.getElementById('summaryDailyEnergy');

  let currentTelemetry = null;
  let chartInstance = null;

  /**
   * Formats ISO date string YYYY-MM-DD into DD-Mon-YYYY (e.g. 29-Sep-2026)
   */
  function formatDateDisplay(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    const year = parts[0];
    const monthIndex = parseInt(parts[1], 10) - 1;
    const day = parts[2];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${day}-${months[monthIndex] || parts[1]}-${year}`;
  }

  /**
   * Fetches telemetry for the selected feeder and date from backend API
   */
  async function loadFeederTelemetry(dateStr) {
    if (!dateStr) return;

    dateBadge.textContent = formatDateDisplay(dateStr);
    chartDateChip.textContent = formatDateDisplay(dateStr);

    try {
      const response = await fetch(`/api/feeder/${feederId}/data?date=${encodeURIComponent(dateStr)}`);
      const result = await response.json();

      if (result && result.success && result.data) {
        currentTelemetry = result.data;
        updateView();
      } else {
        showEmptyState(
          'DATA NOT AVAILABLE',
          `Unable to load ${feederName} telemetry for ${formatDateDisplay(dateStr)}.`,
          'Please verify the data source or select an active date.'
        );
      }
    } catch (err) {
      console.error('Error fetching feeder telemetry:', err);
      showEmptyState(
        'DATA NOT AVAILABLE',
        `Unable to load ${feederName} telemetry for ${formatDateDisplay(dateStr)}.`,
        'Connection error while fetching feeder data.'
      );
    }
  }

  /**
   * Displays the professional empty-state container
   */
  function showEmptyState(title, subtitle, info) {
    if (chartInstance) {
      chartInstance.destroy();
      chartInstance = null;
    }
    chartCanvasWrapper.style.display = 'none';
    emptyState.classList.add('active');

    emptyStateTitle.textContent = title || 'DATA NOT AVAILABLE';
    emptyStateSub.textContent = subtitle || `No actual ${feederName} data is available.`;
    emptyStateInfo.textContent = info || 'Actual feeder data is available from 05-Aug-2026 onwards.';

    chartSeriesLegend.style.display = 'none';

    // Reset summary KPIs to placeholders
    summaryPeakDemand.textContent = '--.--';
    summaryPeakTime.textContent = '--:--';
    summaryPeakDuration.textContent = '--';
    summaryPeakThreshold.textContent = '--.--';
    summaryDailyEnergy.textContent = '--.-';
  }

  /**
   * Updates view when data is available
   */
  function updateView() {
    if (!currentTelemetry || !currentTelemetry.available) {
      showEmptyState(
        currentTelemetry?.message || 'DATA NOT AVAILABLE',
        currentTelemetry?.submessage || `No actual ${feederName} data is available for selected date.`,
        currentTelemetry?.info || 'Actual feeder data is available from 05-Aug-2026 onwards.'
      );
      return;
    }

    // Hide empty state, reveal chart
    emptyState.classList.remove('active');
    chartCanvasWrapper.style.display = 'block';

    // Update Summary KPI Cards
    const summary = currentTelemetry.summary;
    if (summary) {
      summaryPeakDemand.textContent = summary.peak_demand_kw?.toFixed(2) || '--';
      summaryPeakTime.textContent = summary.peak_time || '--:--';
      summaryPeakDuration.textContent = summary.peak_duration_text || '--';
      summaryPeakThreshold.textContent = summary.peak_threshold_kw?.toFixed(2) || '--';
      summaryDailyEnergy.textContent = summary.daily_energy_kwh?.toFixed(1) || '--';
    }

    renderChart();
  }

  /**
   * Renders Bar Chart using Chart.js based on selected analysis mode
   */
  function renderChart() {
    if (!currentTelemetry || !currentTelemetry.hourly || !chartCanvas) return;

    const mode = analysisSelect.value || 'actual';
    const hourly = currentTelemetry.hourly;
    const labels = hourly.map(h => h.time);

    // Update Headings based on mode
    if (mode === 'actual') {
      chartMainTitle.textContent = 'Actual Demand vs Time';
      chartSubtitle.textContent = `24-Hour Actual Profile for ${feederName} (kW)`;
      chartSeriesLegend.style.display = 'none';
    } else if (mode === 'forecast') {
      chartMainTitle.textContent = 'Forecasted Demand vs Time';
      chartSubtitle.textContent = `24-Hour Forecast Profile for ${feederName} (kW)`;
      chartSeriesLegend.style.display = 'none';
    } else if (mode === 'comparison') {
      chartMainTitle.textContent = 'Actual vs Forecasted Demand';
      chartSubtitle.textContent = `Side-by-Side Comparison for ${feederName} (kW)`;
      chartSeriesLegend.style.display = 'flex';
    }

    // Prepare Datasets
    let datasets = [];

    if (mode === 'actual') {
      datasets = [{
        label: 'Actual Demand (kW)',
        data: hourly.map(h => h.actual_demand_kw),
        backgroundColor: '#00843D',
        borderColor: '#006E33',
        borderWidth: 1,
        borderRadius: 4,
        maxBarThickness: 34
      }];
    } else if (mode === 'forecast') {
      datasets = [{
        label: 'Forecasted Demand (kW)',
        data: hourly.map(h => h.forecast_demand_kw),
        backgroundColor: '#1D4ED8',
        borderColor: '#1E40AF',
        borderWidth: 1,
        borderRadius: 4,
        maxBarThickness: 34
      }];
    } else if (mode === 'comparison') {
      datasets = [
        {
          label: 'Actual Demand (kW)',
          data: hourly.map(h => h.actual_demand_kw),
          backgroundColor: '#00843D',
          borderColor: '#006E33',
          borderWidth: 1,
          borderRadius: 3,
          maxBarThickness: 22
        },
        {
          label: 'Forecasted Demand (kW)',
          data: hourly.map(h => h.forecast_demand_kw),
          backgroundColor: '#1D4ED8',
          borderColor: '#1E40AF',
          borderWidth: 1,
          borderRadius: 3,
          maxBarThickness: 22
        }
      ];
    }

    // Destroy prior chart instance before re-creating
    if (chartInstance) {
      chartInstance.destroy();
    }

    // Ensure Chart.js is loaded
    if (typeof Chart === 'undefined') {
      console.error('Chart.js library is not loaded.');
      return;
    }

    chartInstance = new Chart(chartCanvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 350
        },
        plugins: {
          legend: {
            display: false // Using our custom styled legend bar
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleColor: '#FFFFFF',
            bodyColor: '#E2E8F0',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 10,
            cornerRadius: 6,
            titleFont: { family: 'Inter', size: 12, weight: '700' },
            bodyFont: { family: 'JetBrains Mono', size: 12, weight: '500' },
            callbacks: {
              title: (items) => `Time: ${items[0].label}`,
              label: (item) => ` ${item.dataset.label}: ${Number(item.raw).toFixed(2)} kW`
            }
          }
        },
        scales: {
          x: {
            grid: {
              color: 'rgba(15, 23, 42, 0.05)',
              drawBorder: false
            },
            ticks: {
              font: { family: 'JetBrains Mono', size: 11 },
              color: '#64748B'
            },
            title: {
              display: true,
              text: 'TIME',
              font: { family: 'Inter', size: 11, weight: '700' },
              color: '#475569',
              padding: { top: 10 }
            }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: 'rgba(15, 23, 42, 0.06)',
              drawBorder: false
            },
            ticks: {
              font: { family: 'JetBrains Mono', size: 11 },
              color: '#64748B',
              callback: (val) => `${val} kW`
            },
            title: {
              display: true,
              text: 'DEMAND (kW)',
              font: { family: 'Inter', size: 11, weight: '700' },
              color: '#475569',
              padding: { bottom: 8 }
            }
          }
        }
      }
    });
  }

  // ==========================================================
  // Event Listeners
  // ==========================================================

  // 1. Calendar Date Change
  datePicker?.addEventListener('change', (e) => {
    const newDate = e.target.value;
    if (newDate) {
      loadFeederTelemetry(newDate);
    }
  });

  // 2. Analysis Dropdown Change
  analysisSelect?.addEventListener('change', () => {
    if (currentTelemetry && currentTelemetry.available) {
      renderChart();
    }
  });

  // 3. Download Excel Report
  btnDownloadExcel?.addEventListener('click', () => {
    const selectedDate = datePicker.value || '2026-09-29';
    window.location.href = `/api/feeder/${feederId}/download?date=${encodeURIComponent(selectedDate)}`;
  });

  // Initialize with default date
  const initialDate = datePicker.value || '2026-09-29';
  loadFeederTelemetry(initialDate);
});
