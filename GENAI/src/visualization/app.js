// =============================================================================
// Deviation Threshold Visualization - Frontend
// =============================================================================
// Modular, configurable chart for visualizing actual vs predicted values
// with dynamic deviation bands (green/amber/red zones).

// =============================================================================
// CONFIGURATION
// =============================================================================

// Default configuration - will be loaded from API
let CONFIG = {
    // LSTM/MAPE mode settings
    greenUpperBase: 20,    // Base green zone upper bound (%)
    amberWidth: 10,        // Width of amber band above green (%)
    sliderMin: 0,
    sliderMax: 100,
    // STD mode settings (financial data defaults)
    stdGreenUpper: 2,      // Green zone: ±2 STD
    stdAmberUpper: 3       // Amber zone: ±3 STD (red is beyond this)
};

/**
 * Load configuration from the API.
 * @returns {Promise<Object>} Configuration object
 */
async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const config = await res.json();
        CONFIG.greenUpperBase = config.green_upper;
        CONFIG.amberWidth = config.amber_width;
        updateConfigDisplay();
        return config;
    } catch (e) {
        console.error('Failed to load config:', e);
        return CONFIG;
    }
}

/**
 * Save configuration to the API.
 * @param {number} greenUpper - Green zone upper bound
 * @param {number} amberWidth - Amber band width
 * @returns {Promise<Object>} Updated configuration
 */
async function saveConfig(greenUpper, amberWidth) {
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                green_upper: greenUpper,
                amber_width: amberWidth
            })
        });
        const config = await res.json();
        CONFIG.greenUpperBase = config.green_upper;
        CONFIG.amberWidth = config.amber_width;
        updateConfigDisplay();
        return config;
    } catch (e) {
        console.error('Failed to save config:', e);
        return null;
    }
}

/**
 * Update the config display in the UI.
 */
function updateConfigDisplay() {
    const greenInput = document.getElementById('green-upper');
    const amberInput = document.getElementById('amber-width');
    const preview = document.getElementById('threshold-preview');

    if (greenInput) greenInput.value = CONFIG.greenUpperBase;
    if (amberInput) amberInput.value = CONFIG.amberWidth;

    if (preview) {
        const amberUpper = CONFIG.greenUpperBase + CONFIG.amberWidth;
        preview.innerHTML = `<span class="color-green">Green: 0-${CONFIG.greenUpperBase}%</span>, <span class="color-amber">Amber: ${CONFIG.greenUpperBase}-${amberUpper}%</span>, <span class="color-red">Red: ${amberUpper}%+</span>`;
    }
}

// =============================================================================
// DATA FETCHING
// =============================================================================

/**
 * Fetch data from the API.
 * @param {string} expected - Expected type: 'rolling', 'lstm', or 'both'
 * @param {string|null} csvPath - Optional path to data file
 * @returns {Promise<Array>} Data array
 */
async function fetchData(expected = 'both', csvPath = null) {
    try {
        const params = new URLSearchParams();
        if (expected) params.set('expected', expected);
        if (csvPath) params.set('csv', csvPath);
        const url = '/api/data' + (params.toString() ? ('?' + params.toString()) : '');

        const res = await fetch(url);
        if (!res.ok) {
            console.error('API error:', res.status, res.statusText);
            alert(`Error fetching data: ${res.status} ${res.statusText}`);
            return [];
        }

        const payload = await res.json();

        if (payload.error || payload.detail) {
            console.error('API returned error:', payload.error || payload.detail);
            alert('Error fetching data: ' + (payload.error || payload.detail));
            return [];
        }

        // Update config from response if available
        if (payload.config) {
            CONFIG.greenUpperBase = payload.config.green_upper;
            CONFIG.amberWidth = payload.config.amber_width;
            updateConfigDisplay();
        }

        return payload.data || [];
    } catch (e) {
        console.error('Network error fetching data:', e);
        alert('Network error: Unable to fetch data. Please check if the server is running.');
        return [];
    }
}

/**
 * Fetch available sheets from the Excel file.
 * @param {string|null} csvPath - Optional path to Excel file
 * @returns {Promise<Array<string>>} Array of sheet names
 */
async function fetchSheets(csvPath = null) {
    const params = new URLSearchParams();
    if (csvPath) params.set('csv', csvPath);
    const url = '/api/sheets' + (params.toString() ? ('?' + params.toString()) : '');

    try {
        const res = await fetch(url);
        const payload = await res.json();
        return payload.sheets || [];
    } catch (e) {
        console.error('Failed to fetch sheets:', e);
        return [];
    }
}

/**
 * Fetch data from a specific sheet.
 * @param {string} sheet - Sheet name
 * @param {string|null} csvPath - Optional path to data file
 * @returns {Promise<Array>} Data array
 */
async function fetchDataFromSheet(sheet, csvPath = null) {
    try {
        const params = new URLSearchParams();
        params.set('expected', 'both');
        if (sheet) params.set('sheet', sheet);
        if (csvPath) params.set('csv', csvPath);
        const url = '/api/data?' + params.toString();

        const res = await fetch(url);
        if (!res.ok) {
            console.error('API error:', res.status, res.statusText);
            alert(`Error loading sheet "${sheet}": ${res.status} ${res.statusText}`);
            return [];
        }

        const payload = await res.json();

        if (payload.error || payload.detail) {
            console.error('Error fetching sheet data:', payload.error || payload.detail);
            alert(`Error loading sheet "${sheet}": ` + (payload.error || payload.detail));
            return [];
        }

        if (!payload.data || payload.data.length === 0) {
            console.warn(`Sheet "${sheet}" returned no data. Check column configuration.`);
        }

        return payload.data || [];
    } catch (e) {
        console.error('Network error fetching sheet:', e);
        alert(`Network error loading sheet "${sheet}". Please check if the server is running.`);
        return [];
    }
}

// =============================================================================
// DEVIATION CALCULATION
// =============================================================================

/**
 * Compute MAPE deviations for each data point.
 * Formula: |actual - expected| / |actual| * 100
 * @param {Array} data - Data array
 * @param {string} expectedKey - Key for expected value
 * @returns {Array} Percentage deviations
 */
function computeDeviations(data, expectedKey) {
    return data.map((d) => {
        const expected = Number(d[expectedKey] !== undefined ? d[expectedKey] : d.expected);
        const actual = Number(d.actual);
        if (!isFinite(actual) || actual === 0) {
            return expected === 0 ? 0 : 100;
        }
        return Math.abs((actual - expected) / actual) * 100;
    });
}

// =============================================================================
// DATE FILTERING
// =============================================================================

/**
 * Extract unique years from data.
 * @param {Array} data - Data array with date field
 * @returns {Array} Sorted array of unique years
 */
function getYearsFromData(data) {
    const years = new Set();
    data.forEach(d => {
        if (d.date) {
            const year = new Date(d.date).getFullYear();
            if (!isNaN(year)) years.add(year);
        }
    });
    return Array.from(years).sort((a, b) => b - a);  // Most recent first
}

/**
 * Filter data by years (supports multiple years).
 * @param {Array} data - Data array
 * @param {Array<number>} years - Array of years to filter by
 * @returns {Array} Filtered data
 */
function filterDataByYears(data, years) {
    if (!years || years.length === 0) return data;
    return data.filter(d => {
        if (!d.date) return false;
        return years.includes(new Date(d.date).getFullYear());
    });
}

/**
 * Filter data by quarter numbers (1-4).
 * @param {Array} data - Data array
 * @param {Array<number>} quarters - Array of quarter numbers (1-4)
 * @returns {Array} Filtered data
 */
function filterDataByQuarterNumbers(data, quarters) {
    if (!quarters || quarters.length === 0) return data;
    return data.filter(d => {
        if (!d.date) return false;
        const month = new Date(d.date).getMonth();
        const q = Math.floor(month / 3) + 1;  // 1-4
        return quarters.includes(q);
    });
}

/**
 * Apply date filter based on current filter settings.
 * @param {Array} data - Original data array
 * @param {string} filterType - 'all', 'year', or 'quarters'
 * @param {Array<number>} years - Array of years if filterType is 'year'
 * @param {Array<number>} quarters - Array of quarter numbers (1-4) if filterType is 'quarters'
 * @returns {Array} Filtered data
 */
function applyDateFilter(data, filterType, years, quarters) {
    if (filterType === 'year' && years && years.length > 0) {
        return filterDataByYears(data, years);
    } else if (filterType === 'quarters' && quarters && quarters.length > 0) {
        return filterDataByQuarterNumbers(data, quarters);
    }
    return data;  // 'all' or no filter
}

/**
 * Compute Standard Deviation of residuals (actual - expected).
 * @param {Array} data - Data array
 * @param {string} expectedKey - Key for expected value
 * @returns {Object} { mean, std, residuals }
 */
function computeSTD(data, expectedKey) {
    const residuals = data.map((d) => {
        const expected = Number(d[expectedKey] !== undefined ? d[expectedKey] : d.expected);
        const actual = Number(d.actual);
        return actual - expected;
    }).filter(r => isFinite(r));

    const n = residuals.length;
    if (n === 0) return { mean: 0, std: 1, residuals: [] };

    const mean = residuals.reduce((a, b) => a + b, 0) / n;
    const variance = residuals.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / n;
    const std = Math.sqrt(variance);

    return { mean, std: std || 1, residuals };
}

/**
 * Compute Z-scores for each data point.
 * Z-score = (actual - expected) / STD
 * @param {Array} data - Data array
 * @param {string} expectedKey - Key for expected value
 * @param {number} std - Standard deviation
 * @returns {Array} Z-scores (absolute values)
 */
function computeZScores(data, expectedKey, std) {
    return data.map((d) => {
        const expected = Number(d[expectedKey] !== undefined ? d[expectedKey] : d.expected);
        const actual = Number(d.actual);
        if (!isFinite(actual) || !isFinite(expected)) return null;
        return Math.abs((actual - expected) / std);
    });
}

/**
 * Calculate STD-based band boundaries.
 * @param {Array} expecteds - Expected values
 * @param {Array|number} stds - Standard deviation(s) (array or scalar)
 * @param {number} yRange - Y-axis upper limit
 * @param {number} yMin - Y-axis lower limit
 * @returns {Object} Band boundaries
 */
function calculateSTDBands(expecteds, stds, yRange, yMin) {
    const greenStd = CONFIG.stdGreenUpper;   // e.g., 2
    const amberStd = CONFIG.stdAmberUpper;   // e.g., 3

    // Helper to get STD for current index
    const getStd = (i) => Array.isArray(stds) ? (stds[i] || 0) : stds;

    // Green band: ±greenStd STD
    const greenBandUpper = expecteds.map((e, i) => e + greenStd * getStd(i));
    const greenBandLower = expecteds.map((e, i) => e - greenStd * getStd(i));

    // Amber band: greenStd to amberStd STD
    const amberBandUpperTop = expecteds.map((e, i) => e + amberStd * getStd(i));
    const amberBandUpperBottom = greenBandUpper;
    const amberBandLowerTop = greenBandLower;
    const amberBandLowerBottom = expecteds.map((e, i) => e - amberStd * getStd(i));

    // Red band: beyond amberStd STD to graph edges
    const redBandUpperTop = expecteds.map(() => yRange);
    const redBandUpperBottom = amberBandUpperTop;
    const redBandLowerTop = amberBandLowerBottom;
    const redBandLowerBottom = expecteds.map(() => Math.max(0, yMin));

    return {
        green: { upper: greenBandUpper, lower: greenBandLower },
        amber: {
            upperTop: amberBandUpperTop, upperBottom: amberBandUpperBottom,
            lowerTop: amberBandLowerTop, lowerBottom: amberBandLowerBottom
        },
        red: {
            upperTop: redBandUpperTop, upperBottom: redBandUpperBottom,
            lowerTop: redBandLowerTop, lowerBottom: redBandLowerBottom
        }
    };
}

/**
 * Classify points into zones based on Z-score (STD mode).
 * @param {Array} zScores - Z-scores (absolute values)
 * @returns {Array} Colors for each point
 */
function classifyPointsSTD(zScores) {
    const greenStd = CONFIG.stdGreenUpper;
    const amberStd = CONFIG.stdAmberUpper;
    return zScores.map((z) => {
        if (z === null || !isFinite(z)) return '#888';
        if (z <= greenStd) return '#107A1B';    // Within ±greenStd STD
        if (z <= amberStd) return '#BB831B';   // Within ±amberStd STD
        return '#C00C00';                       // Beyond ±amberStd STD
    });
}

// =============================================================================
// THRESHOLD CALCULATION
// =============================================================================

/**
 * Calculate threshold levels based on slider value and config.
 * @param {number} sliderValue - Current slider value (0-100)
 * @returns {Object} Threshold levels
 */
function calculateThresholds(sliderValue) {
    // Slider adds offset to base green zone
    const tolerance = sliderValue + CONFIG.greenUpperBase;

    return {
        level1_upper: tolerance,                           // Green zone: 0 to tolerance
        level2_lower: tolerance,                           // Amber starts at tolerance
        level2_upper: tolerance + CONFIG.amberWidth,       // Amber ends at tolerance + width
        level3_lower: tolerance + CONFIG.amberWidth,       // Red starts above amber
        level3_upper: Math.max(tolerance + 50, 100)        // Red upper (for visualization)
    };
}

// =============================================================================
// POINT CLASSIFICATION
// =============================================================================

/**
 * Classify points into zones based on deviation and thresholds.
 * @param {Array} deviations - Percentage deviations
 * @param {Object} thresholds - Threshold levels
 * @returns {Array} Colors for each point
 */
function classifyPoints(deviations, thresholds) {
    return deviations.map((pct) => {
        if (pct === null || !isFinite(pct)) return '#888';
        if (pct <= thresholds.level1_upper) return '#107A1B';
        if (pct <= thresholds.level2_upper) return '#BB831B';
        return '#C00C00';
    });
}

// =============================================================================
// BAND CALCULATION
// =============================================================================

/**
 * Calculate band boundaries using MAPE formula.
 * @param {Array} expecteds - Expected values
 * @param {Object} thresholds - Threshold levels
 * @param {number} yRange - Y-axis upper limit
 * @param {number} yMin - Y-axis lower limit
 * @returns {Object} Band boundaries
 */
function calculateBands(expecteds, thresholds, yRange, yMin) {
    const capT = (t) => Math.min(t, 80);  // Cap at 80% to prevent extreme scaling

    // Green band: 0 to level1_upper% MAPE
    const greenBandUpper = expecteds.map(e => e / (1 - capT(thresholds.level1_upper) / 100));
    const greenBandLower = expecteds.map(e => e / (1 + thresholds.level1_upper / 100));

    // Amber band: level1_upper% to level2_upper% MAPE
    const amberBandUpperTop = expecteds.map(e => e / (1 - capT(thresholds.level2_upper) / 100));
    const amberBandUpperBottom = greenBandUpper;
    const amberBandLowerTop = greenBandLower;
    const amberBandLowerBottom = expecteds.map(e => e / (1 + thresholds.level2_upper / 100));

    // Red band: from amber boundary to graph edges
    const redBandUpperTop = expecteds.map(() => yRange);
    const redBandUpperBottom = amberBandUpperTop;
    const redBandLowerTop = amberBandLowerBottom;
    const redBandLowerBottom = expecteds.map(() => Math.max(0, yMin));

    return {
        green: { upper: greenBandUpper, lower: greenBandLower },
        amber: {
            upperTop: amberBandUpperTop, upperBottom: amberBandUpperBottom,
            lowerTop: amberBandLowerTop, lowerBottom: amberBandLowerBottom
        },
        red: {
            upperTop: redBandUpperTop, upperBottom: redBandUpperBottom,
            lowerTop: redBandLowerTop, lowerBottom: redBandLowerBottom
        }
    };
}

// =============================================================================
// PLOT BUILDING
// =============================================================================

/**
 * Build and render the Plotly chart.
 * @param {Array} data - Data array
 * @param {Array} deviations - Percentage deviations (or null for STD mode)
 * @param {number} sliderValue - Current slider value
 * @param {string} expectedKey - Key for expected value
 * @param {string} visualizationMode - 'std' or 'lstm'
 * @param {string} sheetName - Current sheet name for title
 */
function buildPlot(data, deviations, sliderValue, expectedKey, visualizationMode = 'lstm', sheetName = '') {
    // Format x-axis as Q1 2024 format
    const x = data.map((d, i) => (d.date ? d.date : i));
    const xLabels = data.map(d => formatDateAsQuarter(d.date));
    const actuals = data.map((d) => d.actual);
    const expecteds = data.map((d) => Number(d[expectedKey] !== undefined ? d[expectedKey] : d.expected));

    // Calculate y-axis range
    const allValues = [...actuals.filter(v => isFinite(v)), ...expecteds.filter(v => isFinite(v))];
    const maxVal = Math.max(...allValues);
    const minVal = Math.min(...allValues);

    // Calculate y-axis range with 10% padding above max and below min
    const range = maxVal - minVal;
    const padding = range * 0.1;  // 10% of the data range
    const yMax = maxVal + padding;
    const yMin = Math.max(0, minVal - padding);  // Don't go below 0

    let colors, bands, legendLabels, hoverText, rawDeviations;

    // Show/hide sigma note based on mode
    const sigmaNoteEl = document.getElementById('sigma-note');
    if (sigmaNoteEl) {
        sigmaNoteEl.style.display = visualizationMode === 'std' ? 'block' : 'none';
    }

    if (visualizationMode === 'std') {
        // STD Mode: Use Rolling_STD from data or calculate if not available
        // Use rolling_mean as expected value for STD mode
        const stdModeExpected = data.map(d => d.rolling_mean || d[expectedKey] || d.expected);

        // Get average rolling_std from data, or calculate if not available
        const rollingStdValues = data.map(d => d.rolling_std).filter(v => isFinite(v));
        let std, mean;

        if (rollingStdValues.length > 0) {
            // Use rolling_std from data (average of all values)
            std = rollingStdValues.reduce((a, b) => a + b, 0) / rollingStdValues.length;
            mean = stdModeExpected.filter(v => isFinite(v)).reduce((a, b) => a + b, 0) / stdModeExpected.length;
        } else {
            // Fallback: calculate STD from residuals
            const computed = computeSTD(data, expectedKey);
            std = computed.std;
            mean = computed.mean;
        }

        // Compute Z-scores using: |actual - rolling_mean| / rolling_std
        const zScores = data.map((d, i) => {
            const actual = d.actual;
            const expected = d.rolling_mean || stdModeExpected[i];
            const pointStd = d.rolling_std || std;
            if (!isFinite(actual) || !isFinite(expected) || pointStd === 0) return null;
            return Math.abs(actual - expected) / pointStd;
        });

        // Prepare rolling STD array for band calculation (use specific point STD or fallback to global std)
        const stdArray = data.map(d => d.rolling_std || std);

        colors = classifyPointsSTD(zScores);
        bands = calculateSTDBands(stdModeExpected, stdArray, yMax, yMin);
        legendLabels = {
            green: `Green Zone (±${CONFIG.stdGreenUpper}σ)`,
            amber: `Amber Zone (±${CONFIG.stdGreenUpper}-${CONFIG.stdAmberUpper}σ)`,
            red: `Red Zone (>±${CONFIG.stdAmberUpper}σ)`
        };
        // Format hover text with descriptive labels for STD mode
        hoverText = zScores.map((z) => {
            if (z === null || !isFinite(z)) return '';
            if (z <= CONFIG.stdGreenUpper) return 'Not Anomaly';
            if (z <= CONFIG.stdAmberUpper) return 'Level 2';
            return 'Level 3';
        });
        rawDeviations = zScores;  // Store raw z-scores for table

        // Show STD info panel and update stats
        const stdPanel = document.getElementById('std-info-panel');
        if (stdPanel) {
            stdPanel.style.display = 'block';
            document.getElementById('std-value').textContent = std.toFixed(2);
            document.getElementById('mean-value').textContent = mean.toFixed(2);
            document.getElementById('range-2std').textContent = `±${(2 * std).toFixed(2)}`;
        }
    } else {
        // LSTM/MAPE Mode: Use percentage deviations and MAPE-aligned bands
        const pctDev = (deviations && deviations.length === data.length) ? deviations : computeDeviations(data, expectedKey);
        const thresholds = calculateThresholds(sliderValue);
        colors = classifyPoints(pctDev, thresholds);
        bands = calculateBands(expecteds, thresholds, yMax, yMin);
        legendLabels = {
            green: `Green Zone (0-${Math.round(thresholds.level1_upper)}%)`,
            amber: `Amber Zone (${Math.round(thresholds.level2_lower)}-${Math.round(thresholds.level2_upper)}%)`,
            red: `Red Zone (>${Math.round(thresholds.level3_lower)}%)`
        };
        hoverText = pctDev.map((p) => (p !== null && isFinite(p) ? p.toFixed(2) + '%' : ''));
        rawDeviations = pctDev;  // Store raw percentage values for table

        // Hide STD info panel in LSTM mode
        const stdPanel = document.getElementById('std-info-panel');
        if (stdPanel) stdPanel.style.display = 'none';
    }

    // Create traces
    // Prepare marker sizes and colors for future points on the Predicted line
    // Detect future: actual is null/missing but predicted exists
    const predictedMarkerSizes = data.map(d => {
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;
        return isFuture ? 12 : 0;  // Only show markers for future points
    });
    const predictedMarkerColors = data.map((d, i) => {
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;
        if (isFuture) {
            // Future points: white fill for hollow appearance
            return '#FFFFFF';
        }
        return 'rgba(0,0,0,0)';  // Invisible for non-future
    });
    const predictedMarkerBorders = data.map((d, i) => {
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;
        if (isFuture) {
            if (visualizationMode === 'std') {
                return '#888888';  // Gray for STD mode
            } else {
                // LSTM mode: trend-based color
                if (i > 0 && data[i - 1].actual != null && expecteds[i] != null) {
                    const prevActual = data[i - 1].actual;
                    return expecteds[i] > prevActual ? '#107A1B' : '#C00C00';
                }
                return '#888888';
            }
        }
        return '#6a0dad';  // Purple border for non-future (matches line)
    });

    const traceExpected = {
        x: x,
        y: expecteds,
        mode: 'lines+markers',  // Changed to include markers for future points
        name: 'Predicted',
        line: { color: '#6a0dad', dash: 'dash', width: 2, shape: 'linear' },
        marker: {
            size: predictedMarkerSizes,
            color: predictedMarkerColors,
            symbol: 'circle',
            line: { width: 2, color: predictedMarkerBorders }
        },
        text: xLabels,
        // Format values with commas for tooltip display
        customdata: expecteds.map(e => e != null && isFinite(e) ? e.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-'),
        hovertemplate: '%{text}<br>Predicted: $%{customdata} M<extra></extra>'
    };

    const traceGreenBand = {
        x: x.concat([...x].reverse()),
        y: bands.green.upper.concat([...bands.green.lower].reverse()),
        fill: 'toself',
        fillcolor: '#F1F7F1',
        line: { width: 1, color: '#107A1B', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        name: legendLabels.green,
        hoverinfo: 'skip',
        showlegend: true
    };

    const traceAmberBandUpper = {
        x: x.concat([...x].reverse()),
        y: bands.amber.upperTop.concat([...bands.amber.upperBottom].reverse()),
        fill: 'toself',
        fillcolor: '#FBF8F1',
        line: { width: 1, color: '#BB831B', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        name: legendLabels.amber,
        hoverinfo: 'skip',
        showlegend: true
    };

    const traceAmberBandLower = {
        x: x.concat([...x].reverse()),
        y: bands.amber.lowerTop.concat([...bands.amber.lowerBottom].reverse()),
        fill: 'toself',
        fillcolor: '#FBF8F1',
        line: { width: 1, color: '#BB831B', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false
    };

    const traceRedBandUpper = {
        x: x.concat([...x].reverse()),
        y: bands.red.upperTop.concat([...bands.red.upperBottom].reverse()),
        fill: 'toself',
        fillcolor: '#FCF0F0',
        line: { width: 1, color: '#C00C00', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        name: legendLabels.red,
        hoverinfo: 'skip',
        showlegend: true
    };

    const traceRedBandLower = {
        x: x.concat([...x].reverse()),
        y: bands.red.lowerTop.concat([...bands.red.lowerBottom].reverse()),
        fill: 'toself',
        fillcolor: '#FCF0F0',
        line: { width: 1, color: '#C00C00', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false
    };

    // Prepare marker colors and border colors for future vs non-future points
    // Detect future: actual is null/missing but predicted exists  
    const markerFillColors = data.map((d, i) => {
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;
        return isFuture ? '#FFFFFF' : colors[i];  // White fill for future points
    });

    const markerBorderColors = data.map((d, i) => {
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;
        if (isFuture) {
            // For future points, border color depends on visualization mode
            if (visualizationMode === 'std') {
                // STD mode: neutral gray border (can't determine direction without deviation)
                return '#888888';
            } else {
                // LSTM mode: trend-based border color
                if (i > 0 && data[i - 1].actual != null && expecteds[i] != null) {
                    const prevActual = data[i - 1].actual;
                    return expecteds[i] > prevActual ? '#107A1B' : '#C00C00';  // Green if up, Red if down
                }
                return '#888888';  // Gray if no trend available
            }
        }
        return '#242424';  // Default black border for non-future points
    });

    const traceActual = {
        x: x,
        y: actuals,
        mode: 'markers+lines',
        name: 'Actual',
        showlegend: false,  // Hide main trace from legend
        marker: {
            color: markerFillColors,
            size: 10,
            symbol: 'circle',
            line: { width: 2, color: markerBorderColors }
        },
        line: { color: '#242424', dash: 'solid' },
        text: xLabels,
        // Format values with commas for tooltip display
        customdata: actuals.map((a, i) => [
            a != null && isFinite(a) ? a.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-',
            expecteds[i] != null && isFinite(expecteds[i]) ? expecteds[i].toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-',
            hoverText[i]
        ]),
        hovertemplate: '%{text}<br>Actual: $%{customdata[0]} M<br>Predicted: $%{customdata[1]} M<br>Deviation: %{customdata[2]}<extra></extra>'
    };

    // Count points in each zone
    let greenCount = 0, amberCount = 0, redCount = 0;
    colors.forEach(c => {
        if (c === '#107A1B') greenCount++;
        else if (c === '#BB831B') amberCount++;
        else if (c === '#C00C00') redCount++;
    });

    // Legend-only traces for colored actual points with dynamic counts
    const legendActualGreen = {
        x: [null], y: [null],
        mode: 'markers+lines',
        name: `Actual (Green Zone) - ${greenCount}`,
        marker: { color: '#107A1B', size: 10, symbol: 'circle', line: { width: 2, color: '#242424' } },
        line: { color: '#242424', dash: 'solid' },
        showlegend: true,
        hoverinfo: 'skip'
    };

    const legendActualAmber = {
        x: [null], y: [null],
        mode: 'markers+lines',
        name: `Actual (Amber Zone) - ${amberCount}`,
        marker: { color: '#BB831B', size: 10, symbol: 'circle', line: { width: 2, color: '#242424' } },
        line: { color: '#242424', dash: 'solid' },
        showlegend: true,
        hoverinfo: 'skip'
    };

    const legendActualRed = {
        x: [null], y: [null],
        mode: 'markers+lines',
        name: `Actual (Red Zone) - ${redCount}`,
        marker: { color: '#C00C00', size: 10, symbol: 'circle', line: { width: 2, color: '#242424' } },
        line: { color: '#242424', dash: 'solid' },
        showlegend: true,
        hoverinfo: 'skip'
    };

    // Create vertical dotted connector lines from actual to predicted (deviation reference)
    const connectorLines = [];
    for (let i = 0; i < x.length; i++) {
        connectorLines.push({
            x: [x[i], x[i]],
            y: [actuals[i], expecteds[i]],
            mode: 'lines',
            line: { color: '#666666', width: 2, dash: 'dot' },
            type: 'scatter',
            hoverinfo: 'skip',
            showlegend: i === 0,
            name: i === 0 ? 'Deviation Reference' : undefined
        });
    }

    // Dynamic title with sheet name
    const chartTitle = sheetName
        ? `Actual vs Predicted Anomaly Detection: ${sheetName}`
        : 'Actual vs Predicted Anomaly Detection';

    const layout = {
        title: {
            text: chartTitle,
            font: { family: 'Arial', color: '#242424', size: 16 }
        },
        xaxis: {
            title: { text: 'Quarter / Year', font: { family: 'Arial', color: '#242424' } },
            type: 'category',
            ticktext: xLabels,
            tickvals: x,
            automargin: true,
            tickfont: { family: 'Arial', color: '#242424' }
        },
        yaxis: {
            title: { text: 'in million(s) (USD)', font: { family: 'Arial', color: '#242424' } },
            range: [yMin, yMax],
            fixedrange: false,
            automargin: true,
            tickfont: { family: 'Arial', color: '#242424' }
        },
        legend: {
            orientation: 'h',
            yanchor: 'top',
            y: -0.15,
            xanchor: 'center',
            x: 0.5,
            font: { size: 10 },
            bgcolor: 'rgba(255,255,255,0.9)',
            bordercolor: '#DDD',
            borderwidth: 1
        },
        hovermode: 'closest',
        hoverlabel: {
            bgcolor: '#FFF',
            font: { color: '#000', family: 'Arial', size: 12 },
            bordercolor: '#DDD'
        },
        margin: { t: 60, b: 160, l: 80, r: 40 },
        dragmode: 'zoom',
        paper_bgcolor: '#FFF',
        plot_bgcolor: '#FFF',
        font: { family: 'Arial' }
    };

    const traces = [
        traceRedBandUpper, traceRedBandLower,
        traceAmberBandUpper, traceAmberBandLower,
        traceGreenBand,
        ...connectorLines,  // Deviation reference lines (behind points)
        traceExpected,
        traceActual,
        legendActualRed, legendActualAmber, legendActualGreen
    ];

    Plotly.react('chart', traces, layout, { responsive: true });

    // Add chart click handler to highlight table row
    const chartDiv = document.getElementById('chart');
    chartDiv.removeAllListeners && chartDiv.removeAllListeners('plotly_click');

    // Find the index of traceActual in the traces array
    const actualTraceIndex = traces.findIndex(t => t.name === 'Actual');

    chartDiv.on('plotly_click', function (eventData) {
        if (eventData.points && eventData.points.length > 0) {
            const point = eventData.points[0];
            // Only respond to clicks on the Actual trace
            if (point.curveNumber === actualTraceIndex) {
                const pointIndex = point.pointIndex;
                highlightTableRow(pointIndex);
                highlightChartPoint(pointIndex, data.length);
            }
        }
    });

    // Update data table with colors and raw deviations
    renderDataTable(data, colors, rawDeviations, visualizationMode);
}

/**
 * Highlight a specific row in the data table.
 * @param {number} pointIndex - Index of point to highlight
 */
function highlightTableRow(pointIndex) {
    const tableContainer = document.getElementById('data-table');
    if (!tableContainer) return;

    // Remove previous selection
    tableContainer.querySelectorAll('tr.selected').forEach(r => r.classList.remove('selected'));

    // Find and highlight the row
    const row = tableContainer.querySelector(`tr[data-index="${pointIndex}"]`);
    if (row) {
        row.classList.add('selected');
        // Scroll row into view
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// =============================================================================
// DATA TABLE RENDERING
// =============================================================================

/**
 * Format date as Q1, YYYY format
 * @param {string} dateStr - Date string
 * @returns {string} Formatted date
 */
function formatDateAsQuarter(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const month = date.getMonth();
    const quarter = Math.floor(month / 3) + 1;
    const year = date.getFullYear();
    return `Q${quarter}, ${year}`;
}

/**
 * Format value as currency ($X.XXM)
 * @param {number} value - Numeric value
 * @returns {string} Formatted currency string
 */
function formatCurrency(value) {
    if (value == null || !isFinite(value)) return '-';
    // Format with commas for thousands separators
    return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} M`;
}

/**
 * Render the data table with zone colors matching chart.
 * Columns displayed depend on visualization mode:
 * - STD mode:  Actual, Predicted (Rolling Mean), Deviation Range (Level 3, Level 2, Not Anomaly)
 * - LSTM mode: Actual, Predicted (LSTM), Deviation (%)
 * 
 * @param {Array} data - Data array
 * @param {Array} colors - Array of color values per point
 * @param {Array} deviations - Array of deviation percentages or Z-scores per point
 * @param {string} visualizationMode - 'lstm' or 'std'
 */
function renderDataTable(data, colors, deviations, visualizationMode) {
    const tableContainer = document.getElementById('data-table');
    if (!tableContainer) return;

    // Toggle Legend Sections based on mode
    const stdLegend = document.getElementById('legend-section-std');
    const mlLegend = document.getElementById('legend-section-ml');

    if (stdLegend && mlLegend) {
        if (visualizationMode === 'std') {
            stdLegend.style.display = 'block';
            mlLegend.style.display = 'none';
        } else {
            stdLegend.style.display = 'none';
            mlLegend.style.display = 'block';
        }
    }

    // Count zones for legend
    let greenCount = 0, amberCount = 0, redCount = 0;
    colors.forEach(c => {
        if (c === '#107A1B') greenCount++;
        else if (c === '#BB831B') amberCount++;
        else if (c === '#C00C00') redCount++;
    });

    // Determine which legend to update based on mode
    const prefix = visualizationMode === 'std' ? 'std' : 'ml';
    const otherPrefix = visualizationMode === 'std' ? 'ml' : 'std';

    // Helper to update count visibility and text
    const updateCount = (type, count) => {
        // Update active legend
        const el = document.getElementById(`${prefix}-${type}-count`);
        if (el) {
            el.textContent = `(${count})`;
            el.style.display = 'inline-block';
        }
        // Hide inactive legend counts (to avoid confusion)
        const otherEl = document.getElementById(`${otherPrefix}-${type}-count`);
        if (otherEl) {
            otherEl.style.display = 'none';
        }
    };

    updateCount('green', greenCount);
    updateCount('amber', amberCount);
    updateCount('red', redCount);

    // Determine headers based on mode
    let lastColHeader = 'Deviation (%)';
    if (visualizationMode === 'std') {
        lastColHeader = 'Deviation Range';
    }

    let html = `
        <table>
            <thead>
                <tr>
                    <th style="width: 20%">Dates</th>
                    <th style="width: 25%">Actual</th>
                    <th style="width: 25%">Predicted</th>
                    <th style="width: 30%">${lastColHeader}</th>
                </tr>
            </thead>
            <tbody>
    `;

    data.forEach((d, i) => {
        // Detect future row: actual is null/missing but predicted exists
        const hasPredicted = d.expected != null || d.expected_lstm != null || d.expected_rolling != null;
        const isFuture = (d.actual == null || d.actual === '-') && hasPredicted;

        let zoneClass = '';
        if (isFuture) {
            zoneClass = 'zone-future';  // White background for future rows
            console.log('[DEBUG] Future row detected:', d.date, 'actual:', d.actual, 'predicted:', d.expected);
        } else {
            if (colors[i] === '#107A1B') zoneClass = 'zone-green';
            else if (colors[i] === '#BB831B') zoneClass = 'zone-amber';
            else if (colors[i] === '#C00C00') zoneClass = 'zone-red';
        }

        const dateStr = d.date ? formatDateAsQuarter(d.date) : `Point ${i + 1}`;
        const actual = d.actual != null ? d.actual.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-';

        // Expected value logic
        let expectedVal = '-';
        let rawExpected;

        if (visualizationMode === 'std') {
            // Prioritize rolling mean for STD
            rawExpected = d.rolling_mean || d.expected_rolling || d.expected;
        } else {
            // Prioritize LSTM for LSTM mode
            rawExpected = d.expected_lstm || d.expected;
        }

        if (rawExpected != null && isFinite(rawExpected)) {
            expectedVal = rawExpected.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        // Deviation column logic
        let deviationContent = '-';
        const val = deviations ? deviations[i] : null;

        if (isFuture) {
            // Future row logic - mode specific
            if (visualizationMode === 'std') {
                // STD mode: no deviation for future rows (can't calculate Z-score without actual)
                deviationContent = '--';
            } else {
                // LSTM mode: show percentage with green/red arrow based on prediction trend
                // Compare current predicted with previous actual (if available)
                if (i > 0 && data[i - 1].actual != null && rawExpected != null) {
                    const prevActual = data[i - 1].actual;
                    const percentChange = Math.abs((rawExpected - prevActual) / prevActual * 100);

                    if (rawExpected > prevActual) {
                        deviationContent = `<span style="color: #107A1B; font-size: 18px;">▲</span> ${percentChange.toFixed(2)}%`;
                    } else if (rawExpected < prevActual) {
                        deviationContent = `<span style="color: #C00C00; font-size: 18px;">▼</span> ${percentChange.toFixed(2)}%`;
                    } else {
                        deviationContent = '<span style="color: #888; font-size: 18px;">→</span> 0.00%';
                    }
                } else {
                    deviationContent = '--';
                }
            }
        } else if (val !== null && isFinite(val)) {
            if (visualizationMode === 'std') {
                // STD Mode: Show Level based on Z-score
                // Green: < 2, Amber: 2-3, Red: > 3
                // Using exact thresholds from CONFIG if valid, else defaults
                const greenThresh = CONFIG.stdGreenUpper || 2;
                const amberThresh = CONFIG.stdAmberUpper || 3;

                if (val <= greenThresh) {
                    deviationContent = 'Not Anomaly';
                } else if (val <= amberThresh) {
                    deviationContent = 'Level 2';
                } else {
                    deviationContent = 'Level 3';
                }
            } else {
                // LSTM Mode: Show Percentage
                deviationContent = val.toFixed(2) + '%';
            }
        }

        html += `
            <tr class="${zoneClass}" data-index="${i}">
                <td>${dateStr}</td>
                <td>${actual}</td>
                <td>${expectedVal}</td>
                <td>${deviationContent}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    tableContainer.innerHTML = html;

    // Track selected row
    let selectedRow = null;

    // Add click handlers for row highlighting
    tableContainer.querySelectorAll('tr[data-index]').forEach(row => {
        row.addEventListener('click', (e) => {
            e.stopPropagation();
            const idx = parseInt(row.getAttribute('data-index'));
            highlightChartPoint(idx, data.length);

            // Remove previous selection
            if (selectedRow) {
                selectedRow.classList.remove('selected');
            }
            // Add selection to this row
            row.classList.add('selected');
            selectedRow = row;
        });
    });

    // Click outside to deselect
    document.addEventListener('click', (e) => {
        if (!tableContainer.contains(e.target)) {
            if (selectedRow) {
                selectedRow.classList.remove('selected');
                selectedRow = null;
                // Reset chart point sizes
                resetChartPointSizes(data.length);
            }
        }
    });
}

/**
 * Reset all chart point sizes to default
 * @param {number} totalPoints - Total number of points
 */
function resetChartPointSizes(totalPoints) {
    const sizes = Array(totalPoints).fill(10);
    const chartDiv = document.getElementById('chart');
    if (chartDiv && chartDiv.data) {
        const actualTraceIndex = chartDiv.data.findIndex(t => t.name === 'Actual');
        if (actualTraceIndex !== -1) {
            Plotly.restyle('chart', { 'marker.size': [sizes] }, [actualTraceIndex]);
        }
    }
}

/**
 * Highlight a specific point on the chart.
 * @param {number} pointIndex - Index of point to highlight
 * @param {number} totalPoints - Total number of points
 */
function highlightChartPoint(pointIndex, totalPoints) {
    // Create array of sizes - larger for highlighted point
    const sizes = Array(totalPoints).fill(10);
    sizes[pointIndex] = 20;  // Make highlighted point bigger

    // Update the Actual trace - find it by name
    const chartDiv = document.getElementById('chart');
    if (chartDiv && chartDiv.data) {
        const actualTraceIndex = chartDiv.data.findIndex(t => t.name === 'Actual');
        if (actualTraceIndex !== -1) {
            Plotly.restyle('chart', { 'marker.size': [sizes] }, [actualTraceIndex]);
        }
    }
}

// =============================================================================
// EVENT HANDLERS
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Load config first
    await loadConfig();

    // Get UI elements
    const thresholdInput = document.getElementById('threshold');
    const thresholdValue = document.getElementById('threshold-value');
    const expectedChoice = document.getElementById('expected');
    const csvPathInput = document.getElementById('csv');
    const loadBtn = document.getElementById('load-data');
    const greenUpperInput = document.getElementById('green-upper');
    const amberWidthInput = document.getElementById('amber-width');
    const applyConfigBtn = document.getElementById('apply-config');
    const datasetSelect = document.getElementById('dataset-select');
    const tableSelect = document.getElementById('table-select');

    let expectedKey = 'expected';
    let visualizationMode = expectedChoice.value || 'lstm';  // 'std' or 'lstm'
    let currentSheet = null;  // Current selected sheet
    let rawData = await fetchData('both', null);  // Original unfiltered data
    let data = rawData;  // Filtered data for plotting
    let currentColors = [];  // Track colors for data table

    // Populate dataset dropdown from sheets
    async function populateDatasetDropdown() {
        const sheets = await fetchSheets();
        datasetSelect.innerHTML = '';  // Clear existing options
        sheets.forEach(sheet => {
            const option = document.createElement('option');
            option.value = sheet;
            option.textContent = sheet;
            datasetSelect.appendChild(option);
        });
        // Auto-select first sheet
        if (sheets.length > 0) {
            datasetSelect.value = sheets[0];
            currentSheet = sheets[0];
        }
    }
    await populateDatasetDropdown();

    // Dataset selection change handler
    if (datasetSelect) {
        console.log('Attaching change listener to dataset-select');
        datasetSelect.addEventListener('change', async () => {
            try {
                currentSheet = datasetSelect.value;
                console.log('Sheet selected:', currentSheet);
                if (currentSheet) {
                    rawData = await fetchDataFromSheet(currentSheet);
                    console.log('Data loaded:', rawData?.length, 'rows');
                    data = rawData;
                    populateYearCheckboxes();
                    rebuildWithFilter();
                    console.log('Chart rebuilt for sheet:', currentSheet);
                }
            } catch (err) {
                console.error('Error loading sheet:', err);
            }
        });
    } else {
        console.error('datasetSelect element not found!');
    }

    // Table selection change handler (future scalability)
    if (tableSelect) {
        tableSelect.addEventListener('change', () => {
            const selectedTable = tableSelect.value;
            console.log('Table selected:', selectedTable);
            // Future: Load different data file or configuration based on table selection
            // For now, only one table is supported (contract_fair_value)
        });
    }

    // Date filter dropdown elements
    const yearDropdown = document.getElementById('year-dropdown');
    const yearHeader = document.getElementById('year-header');
    const yearCheckboxes = document.getElementById('year-checkboxes');
    const quarterDropdown = document.getElementById('quarter-dropdown');
    const quarterHeader = document.getElementById('quarter-header');
    const quarterCheckboxes = document.getElementById('quarter-checkboxes');

    // Toggle dropdown on header click
    function setupDropdown(dropdown, header) {
        header.addEventListener('click', (e) => {
            e.stopPropagation();
            // Close other dropdowns
            document.querySelectorAll('.dropdown-checkbox.open').forEach(d => {
                if (d !== dropdown) d.classList.remove('open');
            });
            dropdown.classList.toggle('open');
        });
    }
    setupDropdown(yearDropdown, yearHeader);
    setupDropdown(quarterDropdown, quarterHeader);

    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.dropdown-checkbox.open').forEach(d => d.classList.remove('open'));
    });

    // Prevent dropdown from closing when clicking inside
    [yearDropdown, quarterDropdown].forEach(d => {
        d.addEventListener('click', e => e.stopPropagation());
    });

    // Graph size control
    const graphSizeSelect = document.getElementById('graph-size');
    const chartElement = document.getElementById('chart');
    if (graphSizeSelect && chartElement) {
        graphSizeSelect.addEventListener('change', () => {
            const size = graphSizeSelect.value;
            // Remove all size classes
            chartElement.classList.remove('chart-small', 'chart-medium', 'chart-large');
            // Add selected size class
            chartElement.classList.add(`chart-${size}`);
            // Trigger Plotly resize
            if (window.Plotly) {
                window.Plotly.Plots.resize(chartElement);
            }
        });
        // Set initial size
        chartElement.classList.add('chart-large');
    }

    // Populate year checkboxes from data
    function populateYearCheckboxes() {
        const years = getYearsFromData(rawData);
        yearCheckboxes.innerHTML =
            `<label class="checkbox-item select-all"><input type="checkbox" value="all"> Select All</label>` +
            years.map(y =>
                `<label class="checkbox-item"><input type="checkbox" value="${y}"> ${y}</label>`
            ).join('');
        // Add change listeners
        setupSelectAll(yearCheckboxes);
    }
    populateYearCheckboxes();

    // Setup Select All functionality for a dropdown
    function setupSelectAll(container) {
        const allCheckboxes = container.querySelectorAll('input');
        const selectAllCb = container.querySelector('input[value="all"]');

        allCheckboxes.forEach(cb => {
            cb.addEventListener('change', (e) => {
                if (cb.value === 'all') {
                    // Toggle all other checkboxes
                    const isChecked = cb.checked;
                    container.querySelectorAll('input:not([value="all"])').forEach(c => c.checked = isChecked);
                } else {
                    // Update Select All based on other checkboxes
                    const others = container.querySelectorAll('input:not([value="all"])');
                    const allChecked = Array.from(others).every(c => c.checked);
                    selectAllCb.checked = allChecked;
                }
                updateHeaderText();
                rebuildWithFilter();
            });
        });
    }

    // Setup Select All for quarter checkboxes
    setupSelectAll(quarterCheckboxes);

    // Update header text to show selected items
    function updateHeaderText() {
        const selectedYears = getCheckedValues(yearCheckboxes);
        const selectedQuarters = getCheckedValues(quarterCheckboxes);

        yearHeader.textContent = selectedYears.length > 0
            ? selectedYears.join(', ')
            : 'Select Years...';

        quarterHeader.textContent = selectedQuarters.length > 0
            ? selectedQuarters.map(q => `Q${q}`).join(', ')
            : 'Select Quarters...';
    }

    // Helper function to get checked values from checkbox group (excludes Select All)
    function getCheckedValues(container) {
        return Array.from(container.querySelectorAll('input:checked:not([value="all"])')).map(cb => Number(cb.value));
    }

    // Helper function to apply filter and rebuild plot
    function rebuildWithFilter() {
        const selectedYears = getCheckedValues(yearCheckboxes);
        const selectedQuarters = getCheckedValues(quarterCheckboxes);

        // Apply combined filter (years AND quarters)
        let filtered = rawData;
        if (selectedYears.length > 0) {
            filtered = filterDataByYears(filtered, selectedYears);
        }
        if (selectedQuarters.length > 0) {
            filtered = filterDataByQuarterNumbers(filtered, selectedQuarters);
        }
        data = filtered;

        if (data.length === 0) {
            alert('No data for selected filter. Showing all data.');
            data = rawData;
            // Uncheck all
            yearCheckboxes.querySelectorAll('input').forEach(cb => cb.checked = false);
            quarterCheckboxes.querySelectorAll('input').forEach(cb => cb.checked = false);
            updateHeaderText();
        }

        deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);
    }

    // Set default expected key
    // Set default expected key based on mode and availability
    if (visualizationMode === 'lstm') {
        expectedKey = 'expected';
    } else {
        // For STD, prefer expected_rolling
        if (rawData && rawData.length > 0 && rawData[0].expected_rolling != null) {
            expectedKey = 'expected_rolling';
        } else {
            expectedKey = 'expected';
        }
    }

    let deviations = computeDeviations(data, expectedKey);
    buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);

    // Slider change handler
    thresholdInput.addEventListener('input', (e) => {
        const val = Number(e.target.value);
        thresholdValue.textContent = val;
        const deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, val, expectedKey, visualizationMode, currentSheet);
    });

    // Visualization mode change handler (STD vs LSTM)
    expectedChoice.addEventListener('change', async () => {
        visualizationMode = expectedChoice.value;  // 'std' or 'lstm'

        // Determine correct expected key for this mode
        if (visualizationMode === 'std') {
            // For STD, we primarily rely on expected_rolling if available
            if (data && data.length > 0 && data[0].expected_rolling != null) expectedKey = 'expected_rolling';
        } else {
            // For LSTM, force use of LSTM prediction
            expectedKey = 'expected';
        }

        // Toggle config panels based on mode
        const lstmConfig = document.getElementById('lstm-config');
        const stdConfig = document.getElementById('std-config');
        const sliderContainer = document.getElementById('slider-container');

        if (lstmConfig && stdConfig) {
            lstmConfig.style.display = visualizationMode === 'lstm' ? 'flex' : 'none';
            stdConfig.style.display = visualizationMode === 'std' ? 'flex' : 'none';
        }

        // Hide slider in STD mode (not used)
        if (sliderContainer) {
            sliderContainer.style.display = visualizationMode === 'lstm' ? 'flex' : 'none';
        }

        deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);
    });

    // Load data button handler (if button exists - may be hidden)
    if (loadBtn) {
        loadBtn.addEventListener('click', async () => {
            data = await fetchData('both', csvPathInput.value || null);
            if (data && data.length > 0 && data[0].expected != null) expectedKey = 'expected';
            else if (data && data.length > 0 && data[0].expected_rolling != null) expectedKey = 'expected_rolling';
            deviations = computeDeviations(data, expectedKey);
            buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);
        });
    }

    // Apply config button handler
    if (applyConfigBtn) {
        applyConfigBtn.addEventListener('click', async () => {
            console.log('LSTM Apply clicked');
            const greenUpper = Number(greenUpperInput.value);
            const amberWidth = Number(amberWidthInput.value);

            if (isNaN(greenUpper) || greenUpper < 0 || greenUpper > 100) {
                alert('Green upper must be between 0 and 100');
                return;
            }
            if (isNaN(amberWidth) || amberWidth < 0 || amberWidth > 50) {
                alert('Amber width must be between 0 and 50');
                return;
            }

            await saveConfig(greenUpper, amberWidth);

            // Update the preview text
            const amberUpper = greenUpper + amberWidth;
            const preview = document.getElementById('threshold-preview');
            if (preview) {
                preview.innerHTML = `<span class="color-green">Green: 0-${greenUpper}%</span>, <span class="color-amber">Amber: ${greenUpper}-${amberUpper}%</span>, <span class="color-red">Red: ${amberUpper}%+</span>`;
            }

            // Show visual feedback on button
            applyConfigBtn.textContent = 'Applied!';
            applyConfigBtn.style.background = '#107A1B';
            setTimeout(() => {
                applyConfigBtn.textContent = 'Apply';
            }, 1500);

            deviations = computeDeviations(data, expectedKey);
            buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);
            console.log('LSTM Plot rebuilt with new config');
        });
    }

    // Live preview of LSTM config changes
    if (greenUpperInput && amberWidthInput) {
        const updatePreview = () => {
            const greenUpper = Number(greenUpperInput.value);
            const amberWidth = Number(amberWidthInput.value);
            const preview = document.getElementById('threshold-preview');
            if (preview) {
                const amberUpper = greenUpper + amberWidth;
                preview.innerHTML = `<span class="color-green">Green: 0-${greenUpper}%</span>, <span class="color-amber">Amber: ${greenUpper}-${amberUpper}%</span>, <span class="color-red">Red: ${amberUpper}%+</span>`;
            }
        };
        greenUpperInput.addEventListener('input', updatePreview);
        amberWidthInput.addEventListener('input', updatePreview);
    }

    // STD config apply button handler
    const applyStdConfigBtn = document.getElementById('apply-std-config');
    const stdGreenInput = document.getElementById('std-green-upper');
    const stdAmberInput = document.getElementById('std-amber-upper');

    if (applyStdConfigBtn && stdGreenInput && stdAmberInput) {
        applyStdConfigBtn.addEventListener('click', () => {
            console.log('STD Apply clicked');
            const greenStd = Number(stdGreenInput.value);
            const amberStd = Number(stdAmberInput.value);

            if (isNaN(greenStd) || greenStd < 0.5 || greenStd > 5) {
                alert('Green STD must be between 0.5 and 5');
                return;
            }
            if (isNaN(amberStd) || amberStd <= greenStd || amberStd > 6) {
                alert('Amber STD must be greater than Green STD and max 6');
                return;
            }

            CONFIG.stdGreenUpper = greenStd;
            CONFIG.stdAmberUpper = amberStd;
            console.log('CONFIG updated:', CONFIG.stdGreenUpper, CONFIG.stdAmberUpper);

            // Update the preview text
            const preview = document.getElementById('std-threshold-preview');
            if (preview) {
                preview.innerHTML = `<span class="color-green">Green: ±${greenStd}σ</span>, <span class="color-amber">Amber: ±${greenStd}-${amberStd}σ</span>, <span class="color-red">Red: >±${amberStd}σ</span>`;
            }

            // Show visual feedback on button
            applyStdConfigBtn.textContent = 'Applied!';
            applyStdConfigBtn.style.background = '#107A1B';
            setTimeout(() => {
                applyStdConfigBtn.textContent = 'Apply';
            }, 1500);

            deviations = computeDeviations(data, expectedKey);
            buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode, currentSheet);
            console.log('Plot rebuilt');
        });

        // Live preview for STD config
        const updateStdPreview = () => {
            const greenStd = Number(stdGreenInput.value);
            const amberStd = Number(stdAmberInput.value);
            const preview = document.getElementById('std-threshold-preview');
            if (preview) {
                preview.innerHTML = `<span class="color-green">Green: ±${greenStd}σ</span>, <span class="color-amber">Amber: ±${greenStd}-${amberStd}σ</span>, <span class="color-red">Red: >±${amberStd}σ</span>`;
            }
        };
        stdGreenInput.addEventListener('input', updateStdPreview);
        stdAmberInput.addEventListener('input', updateStdPreview);
    }

    // Note: Column configuration is now managed in server.py SHEET_COLUMN_CONFIG dictionary
});
