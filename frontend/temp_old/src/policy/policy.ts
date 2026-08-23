// Policy Interventions Controller - Binding slider inputs and toggles to states

export interface PolicyState {
  busCapacity: number;       // +0% to +100%
  metroFreq: number;         // +0% to +80%
  congestionPricing: number;  // ₹0 to ₹250
  wfhMandate: boolean;       // false (Off) or true (30% WFH)
}

export class PolicyController {
  public state: PolicyState = {
    busCapacity: 0,
    metroFreq: 0,
    congestionPricing: 0,
    wfhMandate: false
  };

  private onStateChangeCallback: (newState: PolicyState) => void = () => {};

  constructor(onStateChange: (newState: PolicyState) => void) {
    this.onStateChangeCallback = onStateChange;
    this.initListeners();
  }

  private initListeners() {
    // 1. Bus Capacity Slider
    const sliderBus = document.getElementById('slider-bus-cap') as HTMLInputElement;
    const valBus = document.getElementById('val-bus-cap');
    if (sliderBus && valBus) {
      sliderBus.addEventListener('input', (e) => {
        const val = parseInt((e.target as HTMLInputElement).value);
        this.state.busCapacity = val;
        valBus.textContent = `+${val}%`;
        this.triggerChange();
      });
    }

    // 2. Metro Frequency Slider
    const sliderMetro = document.getElementById('slider-metro-freq') as HTMLInputElement;
    const valMetro = document.getElementById('val-metro-freq');
    if (sliderMetro && valMetro) {
      sliderMetro.addEventListener('input', (e) => {
        const val = parseInt((e.target as HTMLInputElement).value);
        this.state.metroFreq = val;
        valMetro.textContent = `+${val}%`;
        this.triggerChange();
      });
    }

    // 3. Congestion Pricing Slider
    const sliderCong = document.getElementById('slider-congestion-pricing') as HTMLInputElement;
    const valCong = document.getElementById('val-congestion-pricing');
    if (sliderCong && valCong) {
      sliderCong.addEventListener('input', (e) => {
        const val = parseInt((e.target as HTMLInputElement).value);
        this.state.congestionPricing = val;
        valCong.textContent = `₹${val}`;
        this.triggerChange();
      });
    }

    // 4. WFH Mandate Toggles
    const btnWfhOff = document.getElementById('toggle-wfh-off');
    const btnWfhOn = document.getElementById('toggle-wfh-on');
    const valWfh = document.getElementById('val-wfh');
    
    if (btnWfhOff && btnWfhOn && valWfh) {
      btnWfhOff.addEventListener('click', () => {
        this.state.wfhMandate = false;
        valWfh.textContent = 'Off';
        btnWfhOff.classList.add('active');
        btnWfhOn.classList.remove('active');
        this.triggerChange();
      });

      btnWfhOn.addEventListener('click', () => {
        this.state.wfhMandate = true;
        valWfh.textContent = '30%';
        btnWfhOn.classList.add('active');
        btnWfhOff.classList.remove('active');
        this.triggerChange();
      });
    }
  }

  private triggerChange() {
    this.onStateChangeCallback({ ...this.state });
  }

  // Update controls programmatically if state is synced from backend
  public syncState(state: Partial<PolicyState>) {
    if (state.busCapacity !== undefined) {
      this.state.busCapacity = state.busCapacity;
      const el = document.getElementById('slider-bus-cap') as HTMLInputElement;
      if (el) el.value = state.busCapacity.toString();
      const val = document.getElementById('val-bus-cap');
      if (val) val.textContent = `+${state.busCapacity}%`;
    }

    if (state.metroFreq !== undefined) {
      this.state.metroFreq = state.metroFreq;
      const el = document.getElementById('slider-metro-freq') as HTMLInputElement;
      if (el) el.value = state.metroFreq.toString();
      const val = document.getElementById('val-metro-freq');
      if (val) val.textContent = `+${state.metroFreq}%`;
    }

    if (state.congestionPricing !== undefined) {
      this.state.congestionPricing = state.congestionPricing;
      const el = document.getElementById('slider-congestion-pricing') as HTMLInputElement;
      if (el) el.value = state.congestionPricing.toString();
      const val = document.getElementById('val-congestion-pricing');
      if (val) val.textContent = `₹${state.congestionPricing}`;
    }

    if (state.wfhMandate !== undefined) {
      this.state.wfhMandate = state.wfhMandate;
      const btnWfhOff = document.getElementById('toggle-wfh-off');
      const btnWfhOn = document.getElementById('toggle-wfh-on');
      const valWfh = document.getElementById('val-wfh');
      
      if (btnWfhOff && btnWfhOn && valWfh) {
        valWfh.textContent = state.wfhMandate ? '30%' : 'Off';
        if (state.wfhMandate) {
          btnWfhOn.classList.add('active');
          btnWfhOff.classList.remove('active');
        } else {
          btnWfhOff.classList.add('active');
          btnWfhOn.classList.remove('active');
        }
      }
    }
  }
}
