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
    // STD mode settings
    stdGreenUpper: 2,      // Green zone: ±X STD
    stdAmberUpper: 3       // Amber zone: ±X STD (red is above this)
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
        preview.textContent = `Green: 0-${CONFIG.greenUpperBase}%, Amber: ${CONFIG.greenUpperBase}-${amberUpper}%, Red: ${amberUpper}%+`;
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
    const params = new URLSearchParams();
    if (expected) params.set('expected', expected);
    if (csvPath) params.set('csv', csvPath);
    const url = '/api/data' + (params.toString() ? ('?' + params.toString()) : '');

    const res = await fetch(url);
    const payload = await res.json();

    if (payload.error) {
        alert('Error fetching data: ' + JSON.stringify(payload));
        return [];
    }

    // Update config from response if available
    if (payload.config) {
        CONFIG.greenUpperBase = payload.config.green_upper;
        CONFIG.amberWidth = payload.config.amber_width;
        updateConfigDisplay();
    }

    return payload.data;
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
 * @param {number} std - Standard deviation
 * @param {number} yRange - Y-axis upper limit
 * @param {number} yMin - Y-axis lower limit
 * @returns {Object} Band boundaries
 */
function calculateSTDBands(expecteds, std, yRange, yMin) {
    const greenStd = CONFIG.stdGreenUpper;   // e.g., 2
    const amberStd = CONFIG.stdAmberUpper;   // e.g., 3

    // Green band: ±greenStd STD
    const greenBandUpper = expecteds.map(e => e + greenStd * std);
    const greenBandLower = expecteds.map(e => e - greenStd * std);

    // Amber band: greenStd to amberStd STD
    const amberBandUpperTop = expecteds.map(e => e + amberStd * std);
    const amberBandUpperBottom = greenBandUpper;
    const amberBandLowerTop = greenBandLower;
    const amberBandLowerBottom = expecteds.map(e => e - amberStd * std);

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
        if (z <= greenStd) return 'green';    // Within ±greenStd STD
        if (z <= amberStd) return 'orange';   // Within ±amberStd STD
        return 'red';                          // Beyond ±amberStd STD
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
        if (pct <= thresholds.level1_upper) return 'green';
        if (pct <= thresholds.level2_upper) return 'orange';
        return 'red';
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
 */
function buildPlot(data, deviations, sliderValue, expectedKey, visualizationMode = 'lstm') {
    const x = data.map((d, i) => (d.date ? d.date : i));
    const actuals = data.map((d) => d.actual);
    const expecteds = data.map((d) => Number(d[expectedKey] !== undefined ? d[expectedKey] : d.expected));

    // Calculate y-axis range
    const allValues = [...actuals.filter(v => isFinite(v)), ...expecteds.filter(v => isFinite(v))];
    const maxVal = Math.max(...allValues);
    const minVal = Math.min(...allValues.filter(v => v > 0));
    const yRange = maxVal * 1.2;
    const yMin = Math.max(0, minVal * 0.8);

    let colors, bands, legendLabels, hoverText;

    if (visualizationMode === 'std') {
        // STD Mode: Use Z-scores and symmetric bands
        const { std, mean } = computeSTD(data, expectedKey);
        const zScores = computeZScores(data, expectedKey, std);
        colors = classifyPointsSTD(zScores);
        bands = calculateSTDBands(expecteds, std, yRange, yMin);
        legendLabels = {
            green: `Green Zone (±${CONFIG.stdGreenUpper}σ)`,
            amber: `Amber Zone (±${CONFIG.stdGreenUpper}-${CONFIG.stdAmberUpper}σ)`,
            red: `Red Zone (>±${CONFIG.stdAmberUpper}σ)`
        };
        hoverText = zScores.map((z) => (z !== null && isFinite(z) ? `Z: ${z.toFixed(2)}` : ''));

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
        bands = calculateBands(expecteds, thresholds, yRange, yMin);
        legendLabels = {
            green: `Green Zone (0-${Math.round(thresholds.level1_upper)}%)`,
            amber: `Amber Zone (${Math.round(thresholds.level2_lower)}-${Math.round(thresholds.level2_upper)}%)`,
            red: `Red Zone (>${Math.round(thresholds.level3_lower)}%)`
        };
        hoverText = pctDev.map((p) => (p !== null && isFinite(p) ? p.toFixed(2) + '%' : ''));

        // Hide STD info panel in LSTM mode
        const stdPanel = document.getElementById('std-info-panel');
        if (stdPanel) stdPanel.style.display = 'none';
    }

    // Calculate bands (continues in next section)

    // Create traces
    const traceExpected = {
        x: x,
        y: expecteds,
        mode: 'lines',
        name: 'Predicted',
        line: { color: '#6a0dad', dash: 'dash', width: 2, shape: 'linear' },
        marker: { size: 6 },
        hovertemplate: '%{x}<br>Predicted: %{y:.2f}<extra></extra>'
    };

    const traceGreenBand = {
        x: x.concat([...x].reverse()),
        y: bands.green.upper.concat([...bands.green.lower].reverse()),
        fill: 'toself',
        fillcolor: 'rgba(144,238,144,0.35)',
        line: { width: 1, color: 'rgba(34,139,34,0.8)', shape: 'linear' },
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
        fillcolor: 'rgba(255,200,100,0.4)',
        line: { width: 1, color: 'rgba(255,165,0,0.8)', shape: 'linear' },
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
        fillcolor: 'rgba(255,200,100,0.4)',
        line: { width: 1, color: 'rgba(255,165,0,0.8)', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false
    };

    const traceRedBandUpper = {
        x: x.concat([...x].reverse()),
        y: bands.red.upperTop.concat([...bands.red.upperBottom].reverse()),
        fill: 'toself',
        fillcolor: 'rgba(240,128,128,0.3)',
        line: { width: 1, color: 'rgba(220,20,60,0.8)', shape: 'linear' },
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
        fillcolor: 'rgba(240,128,128,0.3)',
        line: { width: 1, color: 'rgba(220,20,60,0.8)', shape: 'linear' },
        type: 'scatter',
        mode: 'lines',
        hoverinfo: 'skip',
        showlegend: false
    };

    const traceActual = {
        x: x,
        y: actuals,
        mode: 'markers+lines',
        name: 'Actual',
        marker: { color: colors, size: 10, line: { width: 1, color: '#222' } },
        line: { color: '#1f77b4', dash: 'solid' },
        text: hoverText,
        hovertemplate: '%{x}<br>Actual: %{y:.2f}<br>Deviation: %{text}<extra></extra>'
    };

    // Create vertical dotted connector lines from actual to predicted (deviation reference)
    const connectorLines = [];
    for (let i = 0; i < x.length; i++) {
        connectorLines.push({
            x: [x[i], x[i]],
            y: [actuals[i], expecteds[i]],
            mode: 'lines',
            line: { color: 'rgba(0, 0, 139, 0.7)', width: 2, dash: 'dot' },
            type: 'scatter',
            hoverinfo: 'skip',
            showlegend: i === 0,
            name: i === 0 ? 'Deviation Reference' : undefined
        });
    }

    const layout = {
        title: 'Actual vs Predicted Values with Deviation Bands',
        xaxis: { title: 'Date', type: 'date' },
        yaxis: {
            title: 'Value',
            range: [yMin, yRange],
            fixedrange: false
        },
        hovermode: 'closest',
        margin: { t: 60, b: 80 },
        dragmode: 'zoom'
    };

    const traces = [
        traceRedBandUpper, traceRedBandLower,
        traceAmberBandUpper, traceAmberBandLower,
        traceGreenBand,
        ...connectorLines,  // Deviation reference lines (behind points)
        traceExpected,
        traceActual
    ];

    Plotly.react('chart', traces, layout, { responsive: true });
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

    let expectedKey = 'expected';
    let visualizationMode = expectedChoice.value || 'lstm';  // 'std' or 'lstm'
    let rawData = await fetchData('both', null);  // Original unfiltered data
    let data = rawData;  // Filtered data for plotting

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
        buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);
    }

    // Set default expected key
    if (rawData && rawData.length > 0 && rawData[0].expected != null) expectedKey = 'expected';
    else if (rawData && rawData.length > 0 && rawData[0].expected_rolling != null) expectedKey = 'expected_rolling';

    let deviations = computeDeviations(data, expectedKey);
    buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);

    // Slider change handler
    thresholdInput.addEventListener('input', (e) => {
        const val = Number(e.target.value);
        thresholdValue.textContent = val;
        const deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, val, expectedKey, visualizationMode);
    });

    // Visualization mode change handler (STD vs LSTM)
    expectedChoice.addEventListener('change', async () => {
        visualizationMode = expectedChoice.value;  // 'std' or 'lstm'

        // Toggle config panels based on mode
        const lstmConfig = document.getElementById('lstm-config');
        const stdConfig = document.getElementById('std-config');
        if (lstmConfig && stdConfig) {
            lstmConfig.style.display = visualizationMode === 'lstm' ? 'flex' : 'none';
            stdConfig.style.display = visualizationMode === 'std' ? 'flex' : 'none';
        }

        deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);
    });

    // Load data button handler
    loadBtn.addEventListener('click', async () => {
        data = await fetchData('both', csvPathInput.value || null);
        if (data && data.length > 0 && data[0].expected != null) expectedKey = 'expected';
        else if (data && data.length > 0 && data[0].expected_rolling != null) expectedKey = 'expected_rolling';
        deviations = computeDeviations(data, expectedKey);
        buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);
    });

    // Apply config button handler
    if (applyConfigBtn) {
        applyConfigBtn.addEventListener('click', async () => {
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
            deviations = computeDeviations(data, expectedKey);
            buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);
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
                preview.textContent = `Green: 0-${greenUpper}%, Amber: ${greenUpper}-${amberUpper}%, Red: ${amberUpper}%+`;
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
            deviations = computeDeviations(data, expectedKey);
            buildPlot(data, deviations, Number(thresholdInput.value), expectedKey, visualizationMode);
        });

        // Live preview for STD config
        const updateStdPreview = () => {
            const greenStd = Number(stdGreenInput.value);
            const amberStd = Number(stdAmberInput.value);
            const preview = document.getElementById('std-threshold-preview');
            if (preview) {
                preview.textContent = `Green: ±${greenStd}σ, Amber: ±${greenStd}-${amberStd}σ, Red: >±${amberStd}σ`;
            }
        };
        stdGreenInput.addEventListener('input', updateStdPreview);
        stdAmberInput.addEventListener('input', updateStdPreview);
    }
});
