"""
FastAPI server for the interactive visualization.
Serves the HTML/JS frontend and provides API endpoints.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pandas as pd
from pathlib import Path
from typing import Optional, Union, List, Dict
import logging
from functools import lru_cache
import os

# ============================================================================
# Configuration Models
# ============================================================================

class ThresholdConfig(BaseModel):
    """Configuration for threshold zones."""
    green_upper: float = 20.0    # Green zone: 0% to this value
    amber_width: float = 10.0    # Amber zone width above green
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "green_upper": 20.0,
                "amber_width": 10.0
            }
        }
    }


class ColumnConfig(BaseModel):
    """Configuration for column name mapping."""
    # Common columns
    date_column: str = "dates"
    actual_column: str = "target_variable"
    
    # LSTM mode columns
    lstm_predicted_column: str = "Predicted"
    lstm_difference_column: str = "LSTM_Difference"
    
    # STD mode columns
    std_rolling_mean_column: str = "Rolling_Mean"
    std_rolling_std_column: str = "Rolling_STD"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "date_column": "dates",
                "actual_column": "target_variable",
                "lstm_predicted_column": "Predicted",
                "lstm_difference_column": "LSTM_Difference",
                "std_rolling_mean_column": "Rolling_Mean",
                "std_rolling_std_column": "Rolling_STD"
            }
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


class SheetColumnsResponse(BaseModel):
    """Response model for sheet columns endpoint."""
    sheet_columns: Dict[str, List[str]]


class SheetsResponse(BaseModel):
    """Response model for sheets endpoint."""
    sheets: List[str]


# ============================================================================
# App Initialization
# ============================================================================

app = FastAPI(
    title="Deviation Threshold Visualization API",
    description="API for interactive visualization of actual vs predicted values with configurable deviation bands",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add CORS middleware for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default data path - can be overridden via environment variable
DATA_PATH = Path(os.environ.get('VIZ_DATA_PATH', Path(__file__).parent.parent.parent / 'data' / 'extracted' / 'Bor_graph.xlsx'))
STATIC_DIR = Path(__file__).parent

# Global configuration (in production, use database or env vars)
current_config = ThresholdConfig()
column_config = ColumnConfig()

# ============================================================================
# SHEET COLUMN CONFIGURATION
# Edit this dictionary to define column names for each sheet
# 
# Supported formats:
# 1. List format: ["date_col", "actual_col", "lstm_predicted", "lstm_diff", "rolling_mean", "rolling_std"]
# 2. Dict format: {"cols": [...], "skip_first": 0, "trim_mode": "global"}
#
# trim_mode options:
#   - "global": Only drop leading incomplete rows globally (default)
#   - "quarter": Drop leading incomplete rows per quarter
#   - "none": No automatic trimming
#
# NOTE: Supports BOTH file formats:
#   - Old format (Bor_graph.xlsx): Actual, Predicted, Difference columns
#   - New format (extracted_sample.xlsx): LSTM_Predicted, LSTM_Relative_Error, STD_* columns
# ============================================================================
SHEET_COLUMN_CONFIG: Dict[str, Union[List[str], Dict]] = {
    # ---- New format (extracted_sample.xlsx) ----
    "Loans and other receivables": ["dates", "Loans and other receivables", "LSTM_Predicted", "LSTM_Relative_Error", "lag_Loans and other receivables", "STD_Loans and other receivables"],
    "Nonaccural loans": ["dates", "Nonaccrual loans", "LSTM_Predicted", "LSTM_Relative_Error", "lag_Nonaccrual loans", "STD_Nonaccrual loans"],
    
    # ---- Old format (Bor_graph.xlsx) ----
    # Borrowings sheet: dates, Actual, Predicted, Difference
    "Borrowings": ["dates", "Actual", "Predicted", "Difference", "Rolling_Mean", "Rolling_STD"],
    # Loans sheet: dates, loans, lag_loans, std_loans, LSTM_Predicted, LSTM_Relative_Error
    "Loans": ["dates", "loans", "LSTM_Predicted", "LSTM_Relative_Error", "lag_loans", "std_loans"],
    # Nonaccural sheet (check columns)
    "Nonaccural": ["dates", "Nonaccural", "LSTM_Predicted", "LSTM_Relative_Error", "lag_Nonaccural", "std_Nonaccural"],
    
    # Add more sheets here as needed
}


# ============================================================================
# Utility Functions
# ============================================================================

def validate_file_path(file_path: Path) -> Path:
    """
    Validate file path to prevent directory traversal attacks.
    
    Args:
        file_path: Path to validate
        
    Returns:
        Resolved absolute path
        
    Raises:
        HTTPException: If path is invalid or outside allowed directories
    """
    try:
        resolved_path = file_path.resolve()
        
        # Ensure file exists
        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Ensure it's a file, not a directory
        if not resolved_path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
        
        # Check file extension
        allowed_extensions = {'.xlsx', '.xls', '.csv'}
        if resolved_path.suffix.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        return resolved_path
        
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid file path: {str(e)}")


def get_sheet_columns(file_path: Path = None) -> dict:
    """
    Get column names for all sheets in an Excel file.
    
    Returns:
        dict: {sheet_name: [col1, col2, col3, ...], ...}
    """
    path = file_path or DATA_PATH
    
    if not path.exists():
        return {}
    
    result = {}
    try:
        xl = pd.ExcelFile(path)
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name=sheet_name, nrows=0)  # Only read headers
            df.columns = df.columns.astype(str).str.strip()
            result[sheet_name] = list(df.columns)
    except Exception as e:
        logger.error(f"Error reading sheet columns: {e}")
    
    return result


def parse_sheet_config(sheet_name: str) -> dict:
    """
    Parse sheet configuration from SHEET_COLUMN_CONFIG.
    Returns a normalized dict with 'cols', 'skip_first', and 'trim_mode'.
    """
    if sheet_name not in SHEET_COLUMN_CONFIG:
        return None
    
    cfg = SHEET_COLUMN_CONFIG[sheet_name]
    
    if isinstance(cfg, dict):
        return {
            'cols': cfg.get('cols', []),
            'skip_first': cfg.get('skip_first', 0),
            'trim_mode': cfg.get('trim_mode', 'global'),
        }
    elif isinstance(cfg, list):
        return {
            'cols': cfg,
            'skip_first': 0,
            'trim_mode': 'global',
        }
    else:
        return None


def infer_columns_from_df(df: pd.DataFrame, col_config: ColumnConfig) -> dict:
    """
    Infer sensible column names from a dataframe when a sheet-specific mapping
    isn't provided. Returns a dict with keys: date_col, actual_col, lstm_predicted_col,
    lstm_diff_col, std_mean_col, std_std_col.
    
    Supports both:
    - Old format: Actual, Predicted, Difference, Rolling_Mean, Rolling_STD
    - New format: LSTM_Predicted, LSTM_Relative_Error, lag_*, STD_*
    """
    columns = list(df.columns)
    columns_lower = [c.lower() for c in columns]
    
    # Helper to find matching column
    def find_column(keywords: list, default: str) -> str:
        for kw in keywords:
            for i, col_lower in enumerate(columns_lower):
                if kw in col_lower:
                    return columns[i]
        return default
    
    # Heuristics for date column
    date_col = find_column(['date', 'period', 'quarter', 'time'], 
                           columns[0] if columns else col_config.date_column)

    # Heuristics for actual column - prioritize exact matches
    actual_keywords = ['actual', 'target', 'value', 'amount', 'balance', 'total']
    actual_col = find_column(actual_keywords, col_config.actual_column)
    
    # If no match found, use first numeric column that's not date
    if actual_col == col_config.actual_column and actual_col not in columns:
        numeric_cols = [c for c in columns if c != date_col and pd.api.types.is_numeric_dtype(df[c])]
        actual_col = numeric_cols[0] if numeric_cols else (columns[1] if len(columns) > 1 else col_config.actual_column)

    # LSTM/Predicted columns - support both formats
    # Old format: "Predicted"
    # New format: "LSTM_Predicted"
    lstm_predicted_col = find_column(['lstm_predicted', 'predicted'], col_config.lstm_predicted_column)
    
    # Difference/Error columns - support both formats
    # Old format: "Difference"
    # New format: "LSTM_Relative_Error"
    lstm_diff_col = find_column(['lstm_relative_error', 'relative_error', 'lstm_diff', 'difference', 'error'], 
                                col_config.lstm_difference_column)
    
    # Rolling Mean columns - support both formats
    # Old format: "Rolling_Mean"
    # New format: "lag_*"
    std_mean_col = find_column(['rolling_mean', 'lag_', 'mean'], col_config.std_rolling_mean_column)
    
    # Rolling STD columns - support both formats
    # Old format: "Rolling_STD"
    # New format: "STD_*"
    std_std_col = find_column(['rolling_std', 'std_'], col_config.std_rolling_std_column)

    return {
        'date_col': date_col,
        'actual_col': actual_col,
        'lstm_predicted_col': lstm_predicted_col,
        'lstm_diff_col': lstm_diff_col,
        'std_mean_col': std_mean_col,
        'std_std_col': std_std_col,
    }


def get_column_mapping(df: pd.DataFrame, sheet: Optional[str], col_config: ColumnConfig) -> dict:
    """
    Get column mapping for a dataframe, using sheet config if available, otherwise inferring.
    Returns dict with all column names.
    """
    sheet_cfg = parse_sheet_config(sheet) if sheet else None
    
    if sheet_cfg and sheet_cfg['cols']:
        cols = sheet_cfg['cols']
        return {
            'date_col': cols[0] if len(cols) > 0 else col_config.date_column,
            'actual_col': cols[1] if len(cols) > 1 else col_config.actual_column,
            'lstm_predicted_col': cols[2] if len(cols) > 2 else col_config.lstm_predicted_column,
            'lstm_diff_col': cols[3] if len(cols) > 3 else col_config.lstm_difference_column,
            'std_mean_col': cols[4] if len(cols) > 4 else col_config.std_rolling_mean_column,
            'std_std_col': cols[5] if len(cols) > 5 else col_config.std_rolling_std_column,
            'skip_first': sheet_cfg.get('skip_first', 0),
            'trim_mode': sheet_cfg.get('trim_mode', 'global'),
        }
    else:
        inferred = infer_columns_from_df(df, col_config)
        inferred['skip_first'] = 0
        inferred['trim_mode'] = 'global'
        return inferred


def drop_leading_incomplete_rows(df: pd.DataFrame, actual_col: str, lstm_predicted_col: str, std_mean_col: str) -> pd.DataFrame:
    """
    Drop leading rows from the dataframe until a row with valid actual value is found.
    This ensures the chart starts with meaningful data points.
    
    Returns:
        Trimmed dataframe starting from first valid actual row
    """
    if df.empty:
        return df
    
    working = df.copy()
    first_valid_idx = None
    
    for idx in working.index:
        row = working.loc[idx]
        # Primary check: has actual value
        if pd.notna(row.get(actual_col)):
            first_valid_idx = idx
            break
    
    if first_valid_idx is None:
        # No valid actual found - try finding first row with any expected value
        for idx in working.index:
            row = working.loc[idx]
            has_lstm = lstm_predicted_col in working.columns and pd.notna(row.get(lstm_predicted_col))
            has_rolling = std_mean_col in working.columns and pd.notna(row.get(std_mean_col))
            if has_lstm or has_rolling:
                first_valid_idx = idx
                break
    
    if first_valid_idx is None:
        # No valid data at all
        return working.iloc[0:0]
    
    return working.loc[first_valid_idx:].reset_index(drop=True)


def trim_by_quarter(df: pd.DataFrame, date_col: str, actual_col: str, lstm_predicted_col: str, std_mean_col: str) -> pd.DataFrame:
    """
    For each quarter in the dataframe, drop leading rows until a valid actual row is found.
    This ensures each quarter starts with meaningful data.
    
    Returns:
        Trimmed dataframe with leading incomplete rows removed per quarter
    """
    if df.empty or date_col not in df.columns:
        return df

    working = df.copy()
    working[date_col] = pd.to_datetime(working[date_col], errors='coerce')
    working = working.sort_values(by=date_col).reset_index(drop=True)
    working['_quarter'] = working[date_col].dt.to_period('Q').astype(str)

    keep_indices = []
    
    for quarter, group in working.groupby('_quarter', sort=True):
        first_valid_idx = None
        
        for idx in group.index:
            row = group.loc[idx]
            # Has actual value - this is our starting point
            if pd.notna(row.get(actual_col)):
                first_valid_idx = idx
                break
        
        if first_valid_idx is None:
            # No actual found, try expected values
            for idx in group.index:
                row = group.loc[idx]
                has_lstm = lstm_predicted_col in working.columns and pd.notna(row.get(lstm_predicted_col))
                has_rolling = std_mean_col in working.columns and pd.notna(row.get(std_mean_col))
                if has_lstm or has_rolling:
                    first_valid_idx = idx
                    break
        
        if first_valid_idx is not None:
            keep_indices.extend(list(group.loc[first_valid_idx:].index))

    if not keep_indices:
        return working.drop(columns=['_quarter']).reset_index(drop=True)

    return working.loc[keep_indices].drop(columns=['_quarter']).reset_index(drop=True)


def apply_data_trimming(df: pd.DataFrame, col_mapping: dict) -> pd.DataFrame:
    """
    Apply appropriate trimming based on trim_mode configuration.
    
    trim_mode options:
        - 'global': Drop leading incomplete rows globally (default)
        - 'quarter': Drop leading incomplete rows per quarter
        - 'none': No automatic trimming
    
    Returns:
        Trimmed dataframe
    """
    trim_mode = col_mapping.get('trim_mode', 'global')
    skip_first = col_mapping.get('skip_first', 0)
    
    date_col = col_mapping['date_col']
    actual_col = col_mapping['actual_col']
    lstm_predicted_col = col_mapping['lstm_predicted_col']
    std_mean_col = col_mapping['std_mean_col']
    
    result = df.copy()
    
    # Apply skip_first if specified (before any other trimming)
    if skip_first > 0:
        result = result.iloc[skip_first:].reset_index(drop=True)
    
    # Apply trimming based on mode
    if trim_mode == 'none':
        pass  # No trimming
    elif trim_mode == 'quarter':
        result = trim_by_quarter(result, date_col, actual_col, lstm_predicted_col, std_mean_col)
    else:  # 'global' (default)
        result = drop_leading_incomplete_rows(result, actual_col, lstm_predicted_col, std_mean_col)
    
    return result


def is_blank_string(value) -> bool:
    """Helper: treat strings like '', '-', '--', or whitespace as missing."""
    return isinstance(value, str) and value.strip() in ('', '-', '--')


def build_data_records(df: pd.DataFrame, col_mapping: dict) -> list:
    """
    Convert dataframe rows to JSON-serializable records for the API response.
    Filtering rules:
    - Show records ONLY if predicted/expected values are present
    - If both actual and predicted are missing: DON'T show
    - If actual is present but predicted is missing: DON'T show
    - If actual is missing but predicted is present: SHOW
    - If both actual and predicted are present: SHOW
    
    Returns:
        List of record dictionaries
    """
    date_col = col_mapping['date_col']
    actual_col = col_mapping['actual_col']
    lstm_predicted_col = col_mapping['lstm_predicted_col']
    lstm_diff_col = col_mapping['lstm_diff_col']
    std_mean_col = col_mapping['std_mean_col']
    std_std_col = col_mapping['std_std_col']
    
    result = []
    last_valid_date = None
    
    for _, row in df.iterrows():
        # Check if row has predicted/expected values first
        has_lstm_predicted = lstm_predicted_col in df.columns and pd.notna(row.get(lstm_predicted_col))
        has_rolling_mean = std_mean_col in df.columns and pd.notna(row.get(std_mean_col))
        
        # Skip rows without predicted values
        if not has_lstm_predicted and not has_rolling_mean:
            continue
        
        # Check if row has actual value
        has_actual = pd.notna(row.get(actual_col))
        
        # Determine how to display the date
        raw_date = row.get(date_col)

        # Parse date if possible
        parsed_date = None
        if pd.notna(raw_date) and not is_blank_string(raw_date):
            try:
                parsed_date = pd.to_datetime(raw_date)
            except Exception:
                parsed_date = None

        # If actual is missing AND we have a predicted value, and the source date is blank/missing,
        # show a Future - Qn,YYYY label based on the last valid date. Otherwise show the parsed date.
        is_future = False
        if not has_actual and (has_lstm_predicted or has_rolling_mean) and (pd.isna(raw_date) or is_blank_string(raw_date) or parsed_date is None):
            if last_valid_date:
                next_date = last_valid_date + pd.DateOffset(months=3)
                quarter = (next_date.month - 1) // 3 + 1
                date_str = f'Future - Q{quarter},{next_date.year}'
                is_future = True
            else:
                date_str = 'Future'
                is_future = True
        else:
            if parsed_date is not None and pd.notna(parsed_date):
                date_str = parsed_date.strftime('%Y-%m-%d')
                last_valid_date = parsed_date
            else:
                # Fall back to original string (keeps any non-date text)
                date_str = str(raw_date) if raw_date is not None else 'Future'
        
        record = {
            'date': date_str,
            'actual': float(row[actual_col]) if has_actual else None,
            'is_future': is_future,
        }

        # LSTM mode fields
        if has_lstm_predicted:
            record['expected_lstm'] = float(row[lstm_predicted_col])
            record['expected'] = float(row[lstm_predicted_col])  # Default expected

        if lstm_diff_col in df.columns and pd.notna(row.get(lstm_diff_col)):
            record['lstm_difference'] = float(row[lstm_diff_col])

        # STD mode fields - use Rolling_Mean as expected value for STD mode
        if has_rolling_mean:
            record['rolling_mean'] = float(row[std_mean_col])
            record['expected_rolling'] = float(row[std_mean_col])

        if std_std_col in df.columns and pd.notna(row.get(std_std_col)):
            record['rolling_std'] = float(row[std_std_col])

        result.append(record)
    
    return result


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


@app.get("/api/columns", response_model=ColumnConfig)
async def get_column_config():
    """Get current column name configuration."""
    return column_config


@app.post("/api/columns", response_model=ColumnConfig)
async def update_column_config(config: ColumnConfig):
    """Update column name mapping. Applies to all sheets."""
    global column_config
    column_config = config
    return column_config


# ============================================================================
# Data Endpoints
# ============================================================================

@app.get("/api/sheet-columns", response_model=SheetColumnsResponse)
async def get_sheet_columns_endpoint(
    csv: Optional[str] = Query(None, description="Path to Excel file")
):
    """
    Return a dictionary mapping sheet names to their column names.
    """
    file_path = validate_file_path(Path(csv)) if csv else DATA_PATH
    
    return SheetColumnsResponse(sheet_columns=get_sheet_columns(file_path))


@app.get("/api/sheets", response_model=SheetsResponse)
async def get_sheets(
    csv: Optional[str] = Query(None, description="Path to Excel file")
):
    """Return list of sheet names from the Excel file."""
    file_path = validate_file_path(Path(csv)) if csv else DATA_PATH
    
    try:
        if str(file_path).endswith('.xlsx') or str(file_path).endswith('.xls'):
            xl = pd.ExcelFile(file_path)
            return SheetsResponse(sheets=xl.sheet_names)
        else:
            return SheetsResponse(sheets=["default"])
    except Exception as e:
        logger.error(f"Error reading sheets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data")
async def get_data(
    csv: Optional[str] = Query(None, description="Path to CSV/Excel file"),
    sheet: Optional[str] = Query(None, description="Sheet name for Excel files"),
    expected: str = Query("both", description="Expected type: rolling, lstm, or both"),
    skip_first: Optional[int] = Query(None, description="Override: number of initial rows to skip"),
    trim_mode: Optional[str] = Query(None, description="Override: 'global', 'quarter', or 'none'")
):
    """
    Return data as JSON for the Plotly chart.
    
    Args:
        csv: Optional path to CSV/Excel file
        sheet: Optional sheet name for Excel files
        expected: Which expected columns to include
        skip_first: Override number of rows to skip (overrides sheet config)
        trim_mode: Override trimming mode (overrides sheet config)
    
    Returns:
        JSON with data array and config
    """
    file_path = validate_file_path(Path(csv)) if csv else DATA_PATH
    logger.info(f"Loading data from {file_path}, sheet: {sheet}")
    
    try:
        # Load data based on file extension
        if str(file_path).endswith('.xlsx') or str(file_path).endswith('.xls'):
            df = pd.read_excel(file_path, sheet_name=sheet) if sheet else pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        # Clean column names
        df.columns = df.columns.astype(str).str.strip()
        
        # Get column mapping (from config or inferred)
        col_mapping = get_column_mapping(df, sheet, column_config)
        
        # Apply query parameter overrides
        if skip_first is not None:
            col_mapping['skip_first'] = max(0, int(skip_first))
        if trim_mode is not None and trim_mode in ('global', 'quarter', 'none'):
            col_mapping['trim_mode'] = trim_mode
        
        # Apply data trimming
        trimmed_df = apply_data_trimming(df, col_mapping)
        
        # Build response records
        result = build_data_records(trimmed_df, col_mapping)
        
        return {
            "data": result, 
            "config": {
                "green_upper": current_config.green_upper,
                "amber_width": current_config.amber_width
            },
            "meta": {
                "original_rows": len(df),
                "trimmed_rows": len(trimmed_df),
                "returned_rows": len(result),
                "columns": col_mapping,
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug-trim")
async def debug_trim(
    csv: Optional[str] = Query(None, description="Path to CSV/Excel file"),
    sheet: Optional[str] = Query(None, description="Sheet name for Excel files"),
    n: int = Query(10, description="Number of head rows to return"),
):
    """
    Debug endpoint to diagnose data trimming behavior.
    Returns first n rows at each stage of processing.
    """
    file_path = validate_file_path(Path(csv)) if csv else DATA_PATH
    logger.info(f"Debug trim for {file_path}, sheet: {sheet}")

    try:
        if str(file_path).endswith('.xlsx') or str(file_path).endswith('.xls'):
            df = pd.read_excel(file_path, sheet_name=sheet) if sheet else pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)

        df.columns = df.columns.astype(str).str.strip()
        col_mapping = get_column_mapping(df, sheet, column_config)

        def to_records(df_in):
            out = []
            for _, r in df_in.head(n).iterrows():
                rec = {}
                for c in df_in.columns:
                    v = r.get(c)
                    if pd.isna(v):
                        rec[c] = None
                    elif isinstance(v, pd.Timestamp):
                        rec[c] = v.strftime('%Y-%m-%d')
                    else:
                        try:
                            rec[c] = float(v) if isinstance(v, (int, float)) else str(v)
                        except Exception:
                            rec[c] = str(v)
                out.append(rec)
            return out

        # Global trim only
        global_trimmed = drop_leading_incomplete_rows(
            df, 
            col_mapping['actual_col'], 
            col_mapping['lstm_predicted_col'], 
            col_mapping['std_mean_col']
        )
        
        # Quarter trim (on original data)
        quarter_trimmed = trim_by_quarter(
            df,
            col_mapping['date_col'],
            col_mapping['actual_col'], 
            col_mapping['lstm_predicted_col'], 
            col_mapping['std_mean_col']
        )

        return JSONResponse({
            'counts': {
                'original': len(df),
                'global_trimmed': len(global_trimmed),
                'quarter_trimmed': len(quarter_trimmed),
            },
            'column_mapping': col_mapping,
            'original_head': to_records(df),
            'global_trimmed_head': to_records(global_trimmed),
            'quarter_trimmed_head': to_records(quarter_trimmed),
        })
    except Exception as e:
        logger.error(f"Error in debug trim: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    import uvicorn
    logger.info("="*60)
    logger.info("  VISUALIZATION SERVER (FastAPI)")
    logger.info("="*60)
    logger.info(f"  Data file: {DATA_PATH}")
    logger.info(f"  Open in browser: http://localhost:5001")
    logger.info(f"  API docs: http://localhost:5001/docs")
    logger.info("="*60)
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
