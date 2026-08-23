// Analytics & Charts renderer - Custom light-weight high performance dashboard plots

export class ChartsManager {
  // Historical data buckets for sparklines/bars (limited to last 20 ticks)
  private historyLimit = 16;
  private delayHistory: number[] = [12, 14, 15, 16, 17, 18.5];
  private shareHistory: number[] = [28, 30, 31, 32, 33.5, 34.2];
  private gridlockHistory: number[] = [5, 6, 7, 9, 10, 12];
  private metroHistory: number[] = [0, 0, 0, 0, 0, 0];

  constructor() {
    this.renderAllCharts();
  }

  // Record a new state tick and update visualizations
  public recordTick(
    avgDelay: number, 
    transitShare: number, 
    gridlock: number, 
    metroStationsAtCap: number
  ) {
    // Shift & append records
    this.appendData(this.delayHistory, avgDelay);
    this.appendData(this.shareHistory, transitShare);
    this.appendData(this.gridlockHistory, gridlock);
    this.appendData(this.metroHistory, metroStationsAtCap);

    // Re-render UI widgets
    this.renderAllCharts();
  }

  private appendData(arr: number[], val: number) {
    arr.push(val);
    if (arr.length > this.historyLimit) {
      arr.shift();
    }
  }

  public renderAllCharts() {
    // Stat 1: Avg Delay
    this.updateCardMetrics(
      'stat-delay', 
      'stat-delay-delta', 
      `${this.getLast(this.delayHistory).toFixed(1)}m`, 
      this.getDeltaText(this.delayHistory, 'm')
    );
    this.renderBars('chart-delay-bars', this.delayHistory, 30, 'danger');

    // Stat 2: Transit Mode Share
    this.updateCardMetrics(
      'stat-share', 
      'stat-share-delta', 
      `${this.getLast(this.shareHistory).toFixed(1)}%`, 
      this.getDeltaText(this.shareHistory, '%'),
      true // inverse delta color (increased public transit share is positive/good!)
    );
    this.renderBars('chart-share-bars', this.shareHistory, 100, 'accent2');

    // Stat 3: Gridlock Index
    this.updateCardMetrics(
      'stat-gridlock', 
      'stat-gridlock-delta', 
      `${Math.round(this.getLast(this.gridlockHistory))}%`, 
      this.getDeltaText(this.gridlockHistory, '%')
    );
    this.renderBars('chart-gridlock-bars', this.gridlockHistory, 100, 'warn');

    // Stat 4: Metro Overcapacity Stations
    const activeMetroCap = Math.round(this.getLast(this.metroHistory));
    this.updateCardMetrics(
      'stat-metro', 
      'stat-metro-delta', 
      `${activeMetroCap} / 42`, 
      this.getDeltaText(this.metroHistory, '')
    );
    this.renderBars('chart-metro-bars', this.metroHistory, 42, 'danger');
  }

  private getLast(arr: number[]): number {
    return arr[arr.length - 1] || 0;
  }

  private getDeltaText(arr: number[], unit: string): { text: string; dir: 'up' | 'down' | 'stable' } {
    if (arr.length < 2) return { text: `0${unit}`, dir: 'stable' };
    const prev = arr[arr.length - 2];
    const curr = arr[arr.length - 1];
    const diff = curr - prev;
    
    if (Math.abs(diff) < 0.05) return { text: `0${unit}`, dir: 'stable' };
    const prefix = diff > 0 ? '+' : '';
    const dir = diff > 0 ? 'up' : 'down';
    return { text: `${prefix}${diff.toFixed(1)}${unit}`, dir };
  }

  private updateCardMetrics(
    valueId: string, 
    deltaId: string, 
    valueStr: string, 
    delta: { text: string; dir: 'up' | 'down' | 'stable' },
    inverseColor = false
  ) {
    const valEl = document.getElementById(valueId);
    const delEl = document.getElementById(deltaId);
    if (!valEl || !delEl) return;

    valEl.textContent = valueStr;
    delEl.textContent = delta.text;
    
    // Clear existing classes
    delEl.className = 'chart-delta';
    
    // Assign semantic styling matching directional meaning
    if (delta.dir === 'stable') {
      delEl.classList.add('stable');
    } else if (delta.dir === 'up') {
      delEl.classList.add(inverseColor ? 'down' : 'up');
    } else {
      delEl.classList.add(inverseColor ? 'up' : 'down');
    }
  }

  // Draw pure HTML bars without heavy SVG constructs
  private renderBars(containerId: string, data: number[], maxVal: number, fillClass: string) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear child elements
    container.innerHTML = '';
    
    // Pad array with zeros to match standard history length
    const padded = [...data];
    while (padded.length < this.historyLimit) {
      padded.unshift(0);
    }

    padded.forEach((val, idx) => {
      const percentage = maxVal > 0 ? Math.min(100, (val / maxVal) * 100) : 0;
      
      const barCol = document.createElement('div');
      barCol.className = 'chart-bar-col';
      
      const barFill = document.createElement('div');
      barFill.className = `chart-bar-fill ${fillClass}`;
      barFill.style.height = `${Math.max(4, percentage)}%`;
      
      const barLabel = document.createElement('div');
      barLabel.className = 'chart-bar-label';
      // Label every 4 steps
      if (idx % 4 === 0) {
        barLabel.textContent = `T${idx}`;
      } else {
        barLabel.textContent = '';
      }

      barCol.appendChild(barFill);
      barCol.appendChild(barLabel);
      container.appendChild(barCol);
    });
  }
}
