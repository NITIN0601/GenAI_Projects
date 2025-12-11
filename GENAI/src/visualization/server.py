"""
FastAPI server for the interactive visualization.
Serves the HTML/JS frontend and provides API endpoints.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration Models
# ============================================================================

class ThresholdConfig(BaseModel):
    """Configuration for threshold zones."""
    green_upper: float = 20.0    # Green zone: 0% to this value
    amber_width: float = 10.0    # Amber zone width above green
    
    class Config:
        schema_extra = {
            "example": {
                "green_upper": 20.0,
                "amber_width": 10.0
            }
        }


class DataResponse(BaseModel):
    """Response model for data endpoint."""
    data: list
    

class ConfigResponse(BaseModel):
    """Response model for config with calculated thresholds."""
    green_upper: float
    amber_width: float
    # Calculated values
    amber_lower: float
    amber_upper: float
    red_lower: float


# ============================================================================
# App Initialization
# ============================================================================

app = FastAPI(
    title="Deviation Threshold Visualization API",
    description="API for interactive visualization of actual vs predicted values with configurable deviation bands",
    version="1.0.0"
)

# Default data path
DATA_PATH = Path(__file__).parent.parent.parent / 'data' / 'extracted' / 'Bor_graph.xlsx'
STATIC_DIR = Path(__file__).parent

# Global configuration (in production, use database or env vars)
current_config = ThresholdConfig()


# ============================================================================
# Static File Routes
# ============================================================================

@app.get("/", response_class=FileResponse)
async def index():
    """Serve the main HTML page."""
    return FileResponse(STATIC_DIR / 'index.html')


@app.get("/app.js", response_class=FileResponse)
async def serve_js():
    """Serve the JavaScript file."""
    return FileResponse(STATIC_DIR / 'app.js')


# ============================================================================
# Configuration Endpoints
# ============================================================================

@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Get current threshold configuration with calculated values."""
    return ConfigResponse(
        green_upper=current_config.green_upper,
        amber_width=current_config.amber_width,
        amber_lower=current_config.green_upper,
        amber_upper=current_config.green_upper + current_config.amber_width,
        red_lower=current_config.green_upper + current_config.amber_width
    )


@app.post("/api/config", response_model=ConfigResponse)
async def update_config(config: ThresholdConfig):
    """Update threshold configuration."""
    global current_config
    current_config = config
    return ConfigResponse(
        green_upper=current_config.green_upper,
        amber_width=current_config.amber_width,
        amber_lower=current_config.green_upper,
        amber_upper=current_config.green_upper + current_config.amber_width,
        red_lower=current_config.green_upper + current_config.amber_width
    )


# ============================================================================
# Data Endpoint
# ============================================================================

@app.get("/api/data")
async def get_data(
    csv: Optional[str] = Query(None, description="Path to CSV/Excel file"),
    expected: str = Query("both", description="Expected type: rolling, lstm, or both")
):
    """
    Return data as JSON for the Plotly chart.
    
    Args:
        csv: Optional path to CSV/Excel file
        expected: Which expected columns to include
    
    Returns:
        JSON with data array
    """
    # Use provided path or default
    file_path = Path(csv) if csv else DATA_PATH
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        # Load data based on file extension
        if str(file_path).endswith('.xlsx') or str(file_path).endswith('.xls'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        # Standardize column mapping for Bor_graph.xlsx format
        result = []
        
        for _, row in df.iterrows():
            # Skip rows with no date
            if pd.isna(row.get('dates')):
                continue
            
            # Skip rows with no Predicted value - bands would go to 0
            if pd.isna(row.get('Predicted')):
                continue
                
            record = {
                'date': pd.to_datetime(row['dates']).strftime('%Y-%m-%d') if pd.notna(row.get('dates')) else None,
                'actual': float(row['Actual']) if pd.notna(row.get('Actual')) else None,
            }
            
            # Add predicted as expected values
            if pd.notna(row.get('Predicted')):
                record['expected_rolling'] = float(row['Predicted'])
                record['expected_lstm'] = float(row['Predicted'])
                record['expected'] = float(row['Predicted'])
            else:
                record['expected_rolling'] = None
                record['expected_lstm'] = None
                record['expected'] = None
            
            # Include difference if available
            if pd.notna(row.get('Difference')):
                record['difference'] = float(row['Difference'])
            
            # Only include records with actual values
            if record['actual'] is not None:
                result.append(record)
        
        return {"data": result, "config": {
            "green_upper": current_config.green_upper,
            "amber_width": current_config.amber_width
        }}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    import uvicorn
    print("\n" + "="*60)
    print("  VISUALIZATION SERVER (FastAPI)")
    print("="*60)
    print(f"  Data file: {DATA_PATH}")
    print(f"  Open in browser: http://localhost:5001")
    print(f"  API docs: http://localhost:5001/docs")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=5001)
