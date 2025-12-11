# Deviation Threshold Visualization

Interactive visualization for comparing actual vs predicted values with configurable deviation bands.

---

## Overview

This visualization displays:
- **Actual values** (data points with color-coded deviation)
- **Predicted values** (dashed line)
- **Deviation bands** (green/amber/red zones)

### Features
- ✅ Configurable threshold zones (green/amber/red)
- ✅ Dynamic slider for tolerance adjustment
- ✅ MAPE-aligned bands (bands match point classification)
- ✅ FastAPI backend with auto-generated API docs
- ✅ Modular JavaScript with reusable functions

---

## Quick Start

### 1. Install Dependencies
```bash
cd /Users/nitin/Desktop/Chatbot/Morgan/GENAI
source .venv/bin/activate
pip install fastapi uvicorn pandas openpyxl
```

### 2. Start Server
```bash
python3 src/visualization/server.py
```

### 3. Open in Browser
- **Main UI:** http://localhost:5001
- **API Docs:** http://localhost:5001/docs

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve main HTML page |
| `/app.js` | GET | Serve JavaScript |
| `/api/data` | GET | Get chart data |
| `/api/config` | GET | Get threshold configuration |
| `/api/config` | POST | Update threshold configuration |

### Example: Get Config
```bash
curl http://localhost:5001/api/config
```
```json
{
    "green_upper": 20.0,
    "amber_width": 10.0,
    "amber_lower": 20.0,
    "amber_upper": 30.0,
    "red_lower": 30.0
}
```

### Example: Update Config
```bash
curl -X POST http://localhost:5001/api/config \
  -H "Content-Type: application/json" \
  -d '{"green_upper": 25, "amber_width": 15}'
```

---

## File Structure

```
src/visualization/
├── server.py      # FastAPI backend
├── app.js         # Frontend JavaScript (modular)
├── index.html     # HTML with threshold controls
└── README.md      # This file
```

---

## Threshold Logic

### Configuration
- **Green Zone Upper:** Base threshold for acceptable deviation (default: 20%)
- **Amber Band Width:** Width of warning zone above green (default: 10%)

### Zones
- **Green:** 0% to `green_upper`
- **Amber:** `green_upper` to `green_upper + amber_width`
- **Red:** Above `green_upper + amber_width`

### Slider
The slider adds an **offset** to the base thresholds:
- Slider = 0 → Thresholds use base values
- Slider = 10 → Thresholds shift by +10%

---

## Deviation Formula (MAPE)

```
deviation = |actual - predicted| / actual × 100
```

### Band Calculation
To align bands with MAPE classification:
- **Upper band:** `predicted / (1 - T%)`
- **Lower band:** `predicted / (1 + T%)`

This creates asymmetric bands that correctly represent MAPE thresholds.

---

## Modular JavaScript Functions

| Function | Purpose |
|----------|---------|
| `loadConfig()` | Load threshold config from API |
| `saveConfig(green, amber)` | Save config to API |
| `fetchData(expected, csvPath)` | Fetch chart data |
| `computeDeviations(data, key)` | Calculate MAPE deviations |
| `calculateThresholds(slider)` | Calculate zone thresholds |
| `classifyPoints(devs, thresholds)` | Color-code points |
| `calculateBands(expecteds, thresholds, yRange, yMin)` | Calculate band boundaries |
| `buildPlot(data, devs, slider, key)` | Render Plotly chart |

---

## Converting to React / Angular

### React Implementation

#### 1. Create React App
```bash
npx create-react-app deviation-viz
cd deviation-viz
npm install plotly.js-dist-min axios
```

#### 2. Project Structure
```
src/
├── api/
│   └── configApi.js        # API calls
├── components/
│   ├── ThresholdConfig.jsx  # Config panel
│   ├── ToleranceSlider.jsx  # Slider control
│   ├── DeviationChart.jsx   # Plotly chart
│   └── Legend.jsx           # Legend
├── hooks/
│   ├── useConfig.js         # Config state hook
│   └── useChartData.js      # Data fetching hook
├── utils/
│   ├── deviations.js        # Deviation calculations
│   ├── thresholds.js        # Threshold logic
│   └── bands.js             # Band calculations
└── App.jsx
```

#### 3. Key Components

**configApi.js:**
```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:5001';

export const getConfig = () => axios.get(`${API_BASE}/api/config`);
export const updateConfig = (config) => axios.post(`${API_BASE}/api/config`, config);
export const getData = () => axios.get(`${API_BASE}/api/data`);
```

**ThresholdConfig.jsx:**
```jsx
import { useState } from 'react';
import { updateConfig } from '../api/configApi';

export function ThresholdConfig({ config, onConfigUpdate }) {
  const [greenUpper, setGreenUpper] = useState(config.green_upper);
  const [amberWidth, setAmberWidth] = useState(config.amber_width);

  const handleApply = async () => {
    const newConfig = await updateConfig({ green_upper: greenUpper, amber_width: amberWidth });
    onConfigUpdate(newConfig.data);
  };

  return (
    <div className="config-panel">
      <input type="number" value={greenUpper} onChange={e => setGreenUpper(+e.target.value)} />
      <input type="number" value={amberWidth} onChange={e => setAmberWidth(+e.target.value)} />
      <button onClick={handleApply}>Apply</button>
    </div>
  );
}
```

**DeviationChart.jsx:**
```jsx
import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import { buildTraces, buildLayout } from '../utils/chartBuilder';

export function DeviationChart({ data, config, sliderValue }) {
  const chartRef = useRef(null);

  useEffect(() => {
    const traces = buildTraces(data, config, sliderValue);
    const layout = buildLayout();
    Plotly.react(chartRef.current, traces, layout, { responsive: true });
  }, [data, config, sliderValue]);

  return <div ref={chartRef} id="chart" />;
}
```

#### 4. State Management
```jsx
// App.jsx
import { useState, useEffect } from 'react';
import { getConfig, getData } from './api/configApi';

function App() {
  const [config, setConfig] = useState(null);
  const [data, setData] = useState([]);
  const [sliderValue, setSliderValue] = useState(0);

  useEffect(() => {
    getConfig().then(res => setConfig(res.data));
    getData().then(res => setData(res.data.data));
  }, []);

  if (!config) return <div>Loading...</div>;

  return (
    <div>
      <ThresholdConfig config={config} onConfigUpdate={setConfig} />
      <ToleranceSlider value={sliderValue} onChange={setSliderValue} />
      <DeviationChart data={data} config={config} sliderValue={sliderValue} />
    </div>
  );
}
```

---

### Angular Implementation

#### 1. Create Angular App
```bash
ng new deviation-viz
cd deviation-viz
npm install plotly.js-dist-min
```

#### 2. Project Structure
```
src/app/
├── services/
│   ├── config.service.ts     # API calls
│   └── data.service.ts
├── components/
│   ├── threshold-config/
│   ├── tolerance-slider/
│   ├── deviation-chart/
│   └── legend/
├── models/
│   └── config.model.ts
├── utils/
│   ├── deviations.ts
│   ├── thresholds.ts
│   └── bands.ts
└── app.component.ts
```

#### 3. Key Components

**config.service.ts:**
```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ThresholdConfig {
  green_upper: number;
  amber_width: number;
  amber_lower: number;
  amber_upper: number;
  red_lower: number;
}

@Injectable({ providedIn: 'root' })
export class ConfigService {
  private apiUrl = 'http://localhost:5001';

  constructor(private http: HttpClient) {}

  getConfig(): Observable<ThresholdConfig> {
    return this.http.get<ThresholdConfig>(`${this.apiUrl}/api/config`);
  }

  updateConfig(config: Partial<ThresholdConfig>): Observable<ThresholdConfig> {
    return this.http.post<ThresholdConfig>(`${this.apiUrl}/api/config`, config);
  }
}
```

**deviation-chart.component.ts:**
```typescript
import { Component, Input, OnChanges, ElementRef, ViewChild } from '@angular/core';
import * as Plotly from 'plotly.js-dist-min';

@Component({
  selector: 'app-deviation-chart',
  template: '<div #chart></div>'
})
export class DeviationChartComponent implements OnChanges {
  @ViewChild('chart') chartEl!: ElementRef;
  @Input() data: any[] = [];
  @Input() config: any;
  @Input() sliderValue = 0;

  ngOnChanges() {
    if (this.data.length && this.config) {
      this.updateChart();
    }
  }

  updateChart() {
    const traces = this.buildTraces();
    const layout = this.buildLayout();
    Plotly.react(this.chartEl.nativeElement, traces, layout, { responsive: true });
  }
  
  // ... buildTraces, buildLayout methods
}
```

#### 4. CORS Configuration
Add CORS middleware to FastAPI backend:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4200"],  # React, Angular
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Best Practices for Framework Migration

1. **Keep Backend Unchanged** - The FastAPI backend works with any frontend
2. **Reuse Calculation Logic** - Port the utility functions (deviations, thresholds, bands)
3. **Use TypeScript** - Add type definitions for better IDE support
4. **State Management** - Use React Context or Angular Services for config state
5. **Testing** - Write unit tests for calculation functions
6. **CORS** - Configure backend to allow frontend origin
