/**
 * SmartFeeder EMS — Supervisory Control & Dispatch Client Logic
 * Handles real-time telemetry updates, power balance visualization,
 * coordinated energy sources state, and setpoint tracking.
 */

'use strict';

(function () {
  // DOM Cache
  const elTimestamp = document.getElementById('emsLatestTimestamp');
  const elConditionTitle = document.getElementById('operatingConditionTitle');
  const elConditionDesc = document.getElementById('operatingConditionDesc');
  const elNodeGrid = document.getElementById('nodeGrid');
  const elNodeSolar = document.getElementById('nodeSolar');
  const elNodeBess = document.getElementById('nodeBess');

  // Control Summary — PV Inverter Setpoint
  const elPvSetpoint = document.getElementById('pvInverterSetpoint');
  const elPvSolarAPower = document.getElementById('pvSolarAPower');
  const elPvSolarBPower = document.getElementById('pvSolarBPower');

  // Control Summary — BESS PCS Setpoint
  const elBessSetpoint = document.getElementById('bessPcsSetpoint');
  const elBessMode = document.getElementById('bessPcsMode');
  const elBessAPcsCmd = document.getElementById('bessAPcsCmd');
  const elBessBPcsCmd = document.getElementById('bessBPcsCmd');

  // Control Summary — Utility Grid Import
  const elGridImportKw = document.getElementById('gridImportKw');
  const elGridBus1Import = document.getElementById('gridBus1Import');
  const elGridBus2Import = document.getElementById('gridBus2Import');

  // Control Summary — Total Feeder Demand
  const elTotalDemand = document.getElementById('totalFeederDemand');
  const elBus1Demand = document.getElementById('bus1Demand');
  const elBus2Demand = document.getElementById('bus2Demand');

  // Live Power Balance
  const elFlowSolar = document.getElementById('flowSolarVal');
  const elFlowBess = document.getElementById('flowBessVal');
  const elFlowGrid = document.getElementById('flowGridVal');
  const elFlowLoad = document.getElementById('flowLoadVal');
  const elEquationMath = document.getElementById('powerEquationMath');
  const elBalanceChip = document.getElementById('balanceVerifiedChip');

  // Solar Control
  const elSolarAStatus = document.getElementById('solarAStatus');
  const elSolarACurGen = document.getElementById('solarACurGen');
  const elSolarAAvail = document.getElementById('solarAAvail');
  const elSolarASetpoint = document.getElementById('solarASetpoint');
  const elSolarAUtil = document.getElementById('solarAUtil');
  const elSolarACurtail = document.getElementById('solarACurtail');

  const elSolarBStatus = document.getElementById('solarBStatus');
  const elSolarBCurGen = document.getElementById('solarBCurGen');
  const elSolarBAvail = document.getElementById('solarBAvail');
  const elSolarBSetpoint = document.getElementById('solarBSetpoint');
  const elSolarBUtil = document.getElementById('solarBUtil');
  const elSolarBCurtail = document.getElementById('solarBCurtail');

  // BESS Control
  const elBessAState = document.getElementById('bessAState');
  const elBessASoc = document.getElementById('bessASoc');
  const elBessASoh = document.getElementById('bessASoh');
  const elBessAEnergy = document.getElementById('bessAEnergy');
  const elBessAPower = document.getElementById('bessAPower');
  const elBessASetpoint = document.getElementById('bessASetpoint');
  const elBessAReserve = document.getElementById('bessAReserve');

  const elBessBState = document.getElementById('bessBState');
  const elBessBSoc = document.getElementById('bessBSoc');
  const elBessBSoh = document.getElementById('bessBSoh');
  const elBessBEnergy = document.getElementById('bessBEnergy');
  const elBessBPower = document.getElementById('bessBPower');
  const elBessBSetpoint = document.getElementById('bessBSetpoint');
  const elBessBReserve = document.getElementById('bessBReserve');

  // Dynamic Reserve
  const elReserveEnergy = document.getElementById('reserveEnergyVal');
  const elReserveSoc = document.getElementById('reserveSocVal');
  const elReserveAvail = document.getElementById('reserveAvailVal');

  // Active Commands Table
  const elTableCommands = document.getElementById('tableEmsCommands');

  // Outlook Table
  const elTableOutlook = document.getElementById('tableEmsOutlook');

  /**
   * Updates all DOM elements with fresh EMS telemetry payload.
   * @param {Object} data 
   */
  function renderEmsTelemetry(data) {
    if (!data) return;

    // 1. Timestamp
    if (elTimestamp && data.timestamp_formatted) {
      elTimestamp.textContent = data.timestamp_formatted;
    }

    // 2. Operating Condition & Coordinated Source Nodes
    if (elConditionTitle && data.operating_condition) {
      elConditionTitle.textContent = data.operating_condition;
      
      const isGridActive = data.operating_condition.includes('GRID');
      const isSolarActive = data.operating_condition.includes('SOLAR');
      const isBessActive = data.operating_condition.includes('BESS');

      if (elNodeGrid) {
        elNodeGrid.classList.toggle('active', isGridActive);
      }
      if (elNodeSolar) {
        elNodeSolar.classList.toggle('active', isSolarActive);
      }
      if (elNodeBess) {
        elNodeBess.classList.toggle('active', isBessActive);
      }
    }

    // 3. Control Summary
    const cs = data.control_summary;
    if (cs) {
      // PV Inverter Setpoint Card
      if (cs.pv_inverter && elPvSetpoint) {
        elPvSetpoint.textContent = Number(cs.pv_inverter.setpoint_kw).toFixed(1);
        if (elPvSolarAPower) elPvSolarAPower.textContent = `${Number(cs.pv_inverter.solar_a_kw).toFixed(1)} kW`;
        if (elPvSolarBPower) elPvSolarBPower.textContent = `${Number(cs.pv_inverter.solar_b_kw).toFixed(1)} kW`;
      }

      // BESS PCS Setpoint Card
      if (cs.bess_pcs && elBessSetpoint) {
        elBessSetpoint.textContent = Number(cs.bess_pcs.setpoint_kw).toFixed(1);
        if (elBessMode) {
          elBessMode.textContent = cs.bess_pcs.mode;
          elBessMode.className = `direction-badge ${cs.bess_pcs.mode === 'DISCHARGE' ? 'badge-amber' : (cs.bess_pcs.mode === 'CHARGE' ? 'badge-green' : 'badge-neutral')}`;
        }
        if (elBessAPcsCmd) {
          elBessAPcsCmd.textContent = `${Number(cs.bess_pcs.bess_a_setpoint_kw).toFixed(1)} kW (${cs.bess_pcs.bess_a_state})`;
        }
        if (elBessBPcsCmd) {
          elBessBPcsCmd.textContent = `${Number(cs.bess_pcs.bess_b_setpoint_kw).toFixed(1)} kW (${cs.bess_pcs.bess_b_state})`;
        }
      }

      // Utility Grid Import Card
      if (cs.grid_import && elGridImportKw) {
        elGridImportKw.textContent = Number(cs.grid_import.import_kw).toFixed(1);
        if (elGridBus1Import) elGridBus1Import.textContent = `${Number(cs.grid_import.bus1_grid_kw).toFixed(1)} kW`;
        if (elGridBus2Import) elGridBus2Import.textContent = `${Number(cs.grid_import.bus2_grid_kw).toFixed(1)} kW`;
      }

      // Total Feeder Demand Card
      if (cs.feeder_demand && elTotalDemand) {
        elTotalDemand.textContent = Number(cs.feeder_demand.total_kw).toFixed(1);
        if (elBus1Demand) elBus1Demand.textContent = `${Number(cs.feeder_demand.bus1_demand_kw).toFixed(1)} kW`;
        if (elBus2Demand) elBus2Demand.textContent = `${Number(cs.feeder_demand.bus2_demand_kw).toFixed(1)} kW`;
      }
    }

    // 4. Live Power Balance
    const pb = data.power_balance;
    if (pb) {
      if (elFlowSolar) elFlowSolar.textContent = Number(pb.solar_generation_kw).toFixed(1);
      if (elFlowBess) {
        const val = Number(pb.bess_power_kw);
        elFlowBess.textContent = (val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1));
      }
      if (elFlowGrid) elFlowGrid.textContent = Number(pb.grid_import_kw).toFixed(1);
      if (elFlowLoad) elFlowLoad.textContent = Number(pb.feeder_demand_kw).toFixed(1);
      if (elEquationMath) elEquationMath.textContent = pb.equation;
      if (elBalanceChip) {
        elBalanceChip.className = `balance-verified-chip ${pb.is_balanced ? 'chip-green' : 'chip-amber'}`;
      }
    }

    // 5. Solar Control
    const sc = data.solar_control;
    if (sc) {
      if (sc.solar_a && elSolarACurGen) {
        elSolarACurGen.textContent = `${Number(sc.solar_a.current_gen_kw).toFixed(1)} kW`;
        if (elSolarAAvail) elSolarAAvail.textContent = `${Number(sc.solar_a.available_kw).toFixed(1)} kW`;
        if (elSolarASetpoint) elSolarASetpoint.textContent = `${Number(sc.solar_a.setpoint_kw).toFixed(1)} kW`;
        if (elSolarAUtil) elSolarAUtil.textContent = `${Number(sc.solar_a.utilized_kw).toFixed(1)} kW`;
        if (elSolarACurtail) elSolarACurtail.textContent = `${Number(sc.solar_a.curtailment_kw).toFixed(1)} kW`;
        if (elSolarAStatus) {
          elSolarAStatus.textContent = sc.solar_a.status;
          elSolarAStatus.className = `status-chip ${sc.solar_a.status === 'ACTIVE' ? 'chip-green' : 'chip-neutral'}`;
        }
      }
      if (sc.solar_b && elSolarBCurGen) {
        elSolarBCurGen.textContent = `${Number(sc.solar_b.current_gen_kw).toFixed(1)} kW`;
        if (elSolarBAvail) elSolarBAvail.textContent = `${Number(sc.solar_b.available_kw).toFixed(1)} kW`;
        if (elSolarBSetpoint) elSolarBSetpoint.textContent = `${Number(sc.solar_b.setpoint_kw).toFixed(1)} kW`;
        if (elSolarBUtil) elSolarBUtil.textContent = `${Number(sc.solar_b.utilized_kw).toFixed(1)} kW`;
        if (elSolarBCurtail) elSolarBCurtail.textContent = `${Number(sc.solar_b.curtailment_kw).toFixed(1)} kW`;
        if (elSolarBStatus) {
          elSolarBStatus.textContent = sc.solar_b.status;
          elSolarBStatus.className = `status-chip ${sc.solar_b.status === 'ACTIVE' ? 'chip-green' : 'chip-neutral'}`;
        }
      }
    }

    // 6. BESS Control
    const bc = data.bess_control;
    if (bc) {
      if (bc.bess_a && elBessASoc) {
        elBessASoc.textContent = `${Number(bc.bess_a.soc_pct).toFixed(1)} %`;
        if (elBessASoh) elBessASoh.textContent = `${Number(bc.bess_a.soh_pct).toFixed(2)} %`;
        if (elBessAEnergy) elBessAEnergy.textContent = `${Number(bc.bess_a.stored_energy_kwh).toFixed(1)} kWh`;
        if (elBessAPower) {
          const val = Number(bc.bess_a.current_power_kw);
          elBessAPower.textContent = (val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1)) + ' kW';
        }
        if (elBessASetpoint) elBessASetpoint.textContent = `${Number(bc.bess_a.setpoint_kw).toFixed(1)} kW`;
        if (elBessAReserve) elBessAReserve.textContent = `${Number(bc.bess_a.discharge_reserve_kwh).toFixed(1)} kWh`;
        if (elBessAState) {
          elBessAState.textContent = bc.bess_a.state;
          elBessAState.className = `status-chip ${bc.bess_a.state === 'DISCHARGING' ? 'chip-amber' : (bc.bess_a.state === 'CHARGING' ? 'chip-green' : 'chip-neutral')}`;
        }
      }

      if (bc.bess_b && elBessBSoc) {
        elBessBSoc.textContent = `${Number(bc.bess_b.soc_pct).toFixed(1)} %`;
        if (elBessBSoh) elBessBSoh.textContent = `${Number(bc.bess_b.soh_pct).toFixed(2)} %`;
        if (elBessBEnergy) elBessBEnergy.textContent = `${Number(bc.bess_b.stored_energy_kwh).toFixed(1)} kWh`;
        if (elBessBPower) {
          const val = Number(bc.bess_b.current_power_kw);
          elBessBPower.textContent = (val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1)) + ' kW';
        }
        if (elBessBSetpoint) elBessBSetpoint.textContent = `${Number(bc.bess_b.setpoint_kw).toFixed(1)} kW`;
        if (elBessBReserve) elBessBReserve.textContent = `${Number(bc.bess_b.discharge_reserve_kwh).toFixed(1)} kWh`;
        if (elBessBState) {
          elBessBState.textContent = bc.bess_b.state;
          elBessBState.className = `status-chip ${bc.bess_b.state === 'DISCHARGING' ? 'chip-amber' : (bc.bess_b.state === 'CHARGING' ? 'chip-green' : 'chip-neutral')}`;
        }
      }

      if (bc.dynamic_reserve) {
        if (elReserveEnergy) elReserveEnergy.textContent = `${Number(bc.dynamic_reserve.reserve_energy_kwh).toFixed(1)} kWh`;
        if (elReserveSoc) elReserveSoc.textContent = `${Number(bc.dynamic_reserve.reserve_soc_pct).toFixed(1)} %`;
        if (elReserveAvail) elReserveAvail.textContent = `${Number(bc.dynamic_reserve.available_discharge_kwh).toFixed(1)} kWh`;
      }
    }
  }

  /**
   * Periodically polls `/api/ems/data` to refresh telemetry seamlessly.
   */
  async function fetchLiveEmsData() {
    try {
      const resp = await fetch('/api/ems/data');
      if (!resp.ok) return;
      const res = await resp.json();
      if (res.success && res.data) {
        renderEmsTelemetry(res.data);
      }
    } catch (err) {
      console.warn('[EMS] Telemetry sync notice:', err);
    }
  }

  // Initialization
  document.addEventListener('DOMContentLoaded', () => {
    // 1. Read initial embedded telemetry
    const elEmbedded = document.getElementById('initialEmsTelemetry');
    if (elEmbedded && elEmbedded.textContent.trim()) {
      try {
        const initialData = JSON.parse(elEmbedded.textContent);
        renderEmsTelemetry(initialData);
      } catch (err) {
        console.error('[EMS] Failed to parse initial telemetry:', err);
      }
    }

    // 2. Start subtle background polling every 30 seconds
    setInterval(fetchLiveEmsData, 30000);
  });
})();
