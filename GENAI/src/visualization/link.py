"""
Visualization Module for Anomaly Detection in 10-Q Financial Data

Author: dundaymo_msid
Version: 1.0.0
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path
import warnings
import argparse
import json
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# ============================================================================
# CONFIGURATION CLASS
# ============================================================================

class AnomalyDetectionConfig:
    """Configuration class for dynamic column mapping and settings"""
    
    def __init__(self, config_dict: Optional[Dict] = None):
        """Initialize configuration with defaults or custom mapping"""
        
        # Default column mappings
        self.columns = {
            'date': 'dates',
            'actual_value': 'Nonaccrual loans', # Example: 'Borrowings' or 'Loans and other receivables'
            'lstm_predicted': 'LSTM_Predicted',
            'lstm_reconstruction_error': 'LSTM_Reconstruction_Error',
            'lstm_relative_error': 'LSTM_Relative_Error',
            'lstm_anomaly': 'LSTM_Anomaly_Detection',
            'manual_anomaly': 'Anomaly Detection',
            'rolling_mean': 'RollingMean_Nonaccrual loans',  # Example: 'RollingMean_Borrowings' or 'RollingMean_Loans and other receivables'
            'std_minus_1': 'STD-1',
            'std_plus_1': 'STD+1',
            'std_minus_2': 'STD-2',
            'std_plus_2': 'STD+2'
        }
        
        # Plot settings
        self.plot_settings = {
            'figsize_single': (24, 13),
            'figsize_double': (24, 16),
            'dpi': 300,
            'marker_sizes': {
                'extreme': 500,
                'level2': 400,
                'other': 350,
                'normal': 60
            },
            'colors': {
                'manual': 'darkorange',
                'lstm': 'green',
                'both': 'red',
                'std_extreme': 'darkred',
                'std_level2': 'orangered',
                'lstm_extreme': 'darkviolet',
                'lstm_level2': 'mediumorchid'
            }
        }
        
        # Override with custom config if provided
        if config_dict:
            self.columns.update(config_dict.get('columns', {}))
            self.plot_settings.update(config_dict.get('plot_settings', {}))
    
    @classmethod
    def from_json(cls, json_path: str):
        """Load configuration from JSON file"""
        with open(json_path, 'r') as f:
            config_dict = json.load(f)
        return cls(config_dict)
    
    def save_to_json(self, json_path: str):
        """Save configuration to JSON file"""
        config_dict = {
            'columns': self.columns,
            'plot_settings': self.plot_settings
        }
        with open(json_path, 'w') as f:
            json.dump(config_dict, f, indent=2)
        print(f"  Configuration saved to: {json_path}")
    
    def get_required_columns(self) -> List[str]:
        """Get list of required columns"""
        return list(self.columns.values())
    
    def get_output_filename(self, graph_type: str, extension: str = 'png') -> str:
        """
        Generate dynamic output filename based on graph type and actual_value column name
        
        Args:
            graph_type: Type of graph (e.g., '1_merged_comparison', '2_split_comparison')
            extension: File extension (default: 'png')
        
        Returns:
            Formatted filename like '1_merged_comparison_Borrowings.png'
        """
        actual_value_col = self.columns['actual_value']
        # Clean the column name (remove spaces, special chars)
        clean_name = actual_value_col.replace(' ', '_').replace('-', '_')
        return f"{graph_type}_{clean_name}.{extension}"


# ============================================================================
# DATA LOADER CLASS
# ============================================================================

class DataLoader:
    """Handles data loading and validation"""
    
    def __init__(self, config: AnomalyDetectionConfig):
        self.config = config
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """Validate that DataFrame has all required columns"""
        required_columns = self.config.get_required_columns()
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            print(f"  Missing required columns: {missing}")
            print(f"\nAvailable columns: {df.columns.tolist()}")
            return False
        
        print(f"  All required columns present")
        return True
    
    def load_data(self, file_path: str) -> Optional[pd.DataFrame]:
        """Load and validate data from CSV file"""
        
        # Check if file exists
        if not Path(file_path).exists():
            print(f"  File not found: {file_path}")
            return None
        
        try:
            df = pd.read_csv(file_path)
            print(f"  Data loaded successfully: {len(df)} rows, {len(df.columns)} columns")
            
        except pd.errors.EmptyDataError:
            print(f"  File is empty: {file_path}")
            return None
        except Exception as e:
            print(f"  Error loading data: {type(e).__name__}: {e}")
            return None
        
        # Validate columns
        if not self.validate_dataframe(df):
            return None
        
        # Parse dates
        date_col = self.config.columns['date']
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            null_dates = df[date_col].isna().sum()
            
            if null_dates > 0:
                print(f"   Warning: {null_dates} dates could not be parsed and will be removed")
            
            df = df[df[date_col].notna()].reset_index(drop=True)
            
            if len(df) == 0:
                print(f"   No valid dates found in dataset")
                return None
                
        except Exception as e:
            print(f"  Error parsing dates: {e}")
            return None
        
        # Sort by date
        df = df.sort_values(date_col).reset_index(drop=True)

        # Drop rows where BOTH expected series are missing (rolling mean AND lstm prediction)
        rolling_col = self.config.columns.get('rolling_mean')
        lstm_col = self.config.columns.get('lstm_predicted')
        if rolling_col in df.columns and lstm_col in df.columns:
            before_len = len(df)
            df = df[~(df[rolling_col].isna() & df[lstm_col].isna())].reset_index(drop=True)
            dropped = before_len - len(df)
            if dropped > 0:
                print(f"   Dropped {dropped} rows where both '{rolling_col}' and '{lstm_col}' are missing")
        
        # Display data info
        print(f"\n{'='*80}")
        print(f"Date range: {df[date_col].min().strftime('%Y-%m-%d')} to {df[date_col].max().strftime('%Y-%m-%d')}")
        print(f"Total valid records: {len(df)}")
        
        actual_col = self.config.columns['actual_value']
        print(f"{actual_col} range: {df[actual_col].min():.2f} to {df[actual_col].max():.2f}")
        print(f"{'='*80}\n")
        
        return df


# ============================================================================
# ANOMALY PROCESSOR CLASS
# ============================================================================

class AnomalyProcessor:
    """Processes and flags anomalies"""
    
    def __init__(self, config: AnomalyDetectionConfig):
        self.config = config
    
    @staticmethod
    def parse_anomaly_text(text: str, method: str = 'manual') -> Tuple[int, str]:
        """
        Parse anomaly detection text and return (flag, severity)
        
        Returns:
            flag (int): 1 if anomaly, 0 if not
            severity (str): 'Extreme', 'Level 2', 'Other', or 'Not Anomaly'
        """
        if pd.isna(text):
            return 0, 'Not Anomaly'
        
        text_lower = str(text).strip().lower()
        
        # Check if explicitly not an anomaly
        if 'not' in text_lower and 'anomaly' in text_lower:
            return 0, 'Not Anomaly'
        
        # Check severity levels
        if 'extreme' in text_lower or 'level 3' in text_lower:
            return 1, 'Extreme'
        elif 'level 2' in text_lower:
            return 1, 'Level 2'
        elif 'level' in text_lower or ('anomaly' in text_lower and 'not' not in text_lower):
            return 1, 'Other'
        
        return 0, 'Not Anomaly'
    
    def prepare_anomaly_flags(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Create binary anomaly flags and agreement metrics"""
        
        print("Preparing anomaly flags...")
        
        manual_col = self.config.columns['manual_anomaly']
        lstm_col = self.config.columns['lstm_anomaly']
        
        # Parse anomalies
        df['STD_Anomaly_Flag'] = df[manual_col].apply(
            lambda x: self.parse_anomaly_text(x, 'manual')[0]
        )
        df['STD_Severity'] = df[manual_col].apply(
            lambda x: self.parse_anomaly_text(x, 'manual')[1]
        )
        
        df['LSTM_Anomaly_Flag'] = df[lstm_col].apply(
            lambda x: self.parse_anomaly_text(x, 'lstm')[0]
        )
        df['LSTM_Severity'] = df[lstm_col].apply(
            lambda x: self.parse_anomaly_text(x, 'lstm')[1]
        )
        
        # Counts
        std_count = int(df['STD_Anomaly_Flag'].sum())
        lstm_count = int(df['LSTM_Anomaly_Flag'].sum())
        
        print(f"\n    Manual Anomaly Flags: {std_count} detected")
        print(f"    LSTM Anomaly Flags: {lstm_count} detected")
        
        # Agreement categories
        df['Agreement_Category'] = 'Normal'
        df.loc[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 1), 
               'Agreement_Category'] = 'Both Detected'
        df.loc[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 0), 
               'Agreement_Category'] = 'Only STD'
        df.loc[(df['STD_Anomaly_Flag'] == 0) & (df['LSTM_Anomaly_Flag'] == 1), 
               'Agreement_Category'] = 'Only LSTM'
        
        # Combined severity score
        def calculate_severity_score(row):
            score = 0
            if row['STD_Severity'] == 'Extreme':
                score += 2
            elif row['STD_Severity'] == 'Level 2':
                score += 1
            
            if row['LSTM_Severity'] == 'Extreme':
                score += 2
            elif row['LSTM_Severity'] == 'Level 2':
                score += 1
            
            return score
        
        df['Combined_Severity_Score'] = df.apply(calculate_severity_score, axis=1)
        
        # Summary
        agreement_summary = df['Agreement_Category'].value_counts()
        print(f"\n  Agreement Summary:")
        for category, count in agreement_summary.items():
            print(f"    {category}: {count}")
        
        return df


# ============================================================================
# VISUALIZATION CLASS
# ============================================================================

class AnomalyVisualizer:
    """Handles all visualization tasks"""
    
    def __init__(self, config: AnomalyDetectionConfig):
        self.config = config
    
    def add_quarterly_dividers(self, ax, df: pd.DataFrame, y_max: float):
        """Add quarterly dividers to plot"""
        date_col = self.config.columns['date']
        df['quarter'] = df[date_col].dt.to_period('Q')
        unique_quarters = df.groupby('quarter')[date_col].min()
        
        for quarter_start in unique_quarters:
            ax.axvline(x=quarter_start, color='gray', linestyle=':', 
                      linewidth=1.5, alpha=0.4, zorder=3)
            
            quarter_label = quarter_start.strftime('%Y-Q') + str((quarter_start.month - 1) // 3 + 1)
            ax.text(quarter_start, y_max * 1.02, quarter_label, 
                   rotation=0, ha='center', va='bottom', fontsize=8, 
                   color='gray', alpha=0.7)
    
    def _plot_severity_markers(self, ax, data: pd.DataFrame, method: str, zorder_start: int = 10):
        """Helper to plot severity-based markers"""
        if data.empty:
            return
        
        cols = self.config.columns
        settings = self.config.plot_settings
        
        severity_col = 'STD_Severity' if method == 'manual' else 'LSTM_Severity'
        extreme = data[data[severity_col] == 'Extreme']
        level2 = data[data[severity_col] == 'Level 2']
        other = data[~data[severity_col].isin(['Extreme', 'Level 2', 'Not Anomaly'])]
        
        color_prefix = 'std' if method == 'manual' else 'lstm'
        marker = 'X' if method == 'manual' else '*'
        label_prefix = 'Manual' if method == 'manual' else 'LSTM'
        
        if not extreme.empty:
            ax.scatter(extreme[cols['date']], extreme[cols['actual_value']], 
                      color=settings['colors'][f'{color_prefix}_extreme'], 
                      s=settings['marker_sizes']['extreme'], marker=marker, 
                      edgecolors='darkred', linewidth=4, 
                      label=f'{label_prefix} Extreme', zorder=zorder_start+2, alpha=1.0)
        
        if not level2.empty:
            ax.scatter(level2[cols['date']], level2[cols['actual_value']], 
                      color=settings['colors'][f'{color_prefix}_level2'], 
                      s=settings['marker_sizes']['level2'], marker='s' if method == 'manual' else 'D', 
                      edgecolors='darkorange' if method == 'manual' else 'darkviolet', linewidth=3, 
                      label=f'{label_prefix} Level 2', zorder=zorder_start+1, alpha=0.95)
        
        if not other.empty:
            color = 'orange' if method == 'manual' else 'plum'
            ax.scatter(other[cols['date']], other[cols['actual_value']], 
                      color=color, s=settings['marker_sizes']['other'], marker='o', 
                      edgecolors='darkorange' if method == 'manual' else 'purple', 
                      linewidth=2.5, label=f'{label_prefix} Other', 
                      zorder=zorder_start, alpha=0.9)
    
    def plot_merged_comparison(self, df: pd.DataFrame, output_dir: Path) -> bool:
        """
        PLOT 1: MERGED comparison with DEVIATION VISUALIZATION
        Shows how anomalies deviate from their respective prediction methods
        """
        
        try:
            cols = self.config.columns
            settings = self.config.plot_settings
            
            # Generate dynamic filename
            output_file = output_dir / self.config.get_output_filename('1_merged_comparison')
            
            fig, ax = plt.subplots(figsize=settings['figsize_single'])
            
            # Get actual value column name for labels
            actual_value_name = cols['actual_value']
            
            # Background STD bands
            ax.fill_between(df[cols['date']], df[cols['std_minus_2']], df[cols['std_plus_2']], 
                           alpha=0.12, color='gray', label='±2 STD (Manual)', zorder=1)
            ax.fill_between(df[cols['date']], df[cols['std_minus_1']], df[cols['std_plus_1']], 
                           alpha=0.20, color='lightblue', label='±1 STD (Manual)', zorder=2)
            
            # Base lines
            ax.plot(df[cols['date']], df[cols['rolling_mean']], 
                   color=settings['colors']['manual'], linewidth=3.5, linestyle='--', 
                   label='Rolling Mean (Manual)', zorder=4, alpha=0.85)
            
            ax.plot(df[cols['date']], df[cols['lstm_predicted']], 
                   color=settings['colors']['lstm'], linewidth=3.5, linestyle='-', 
                   label='LSTM Predicted', zorder=5, alpha=0.85)
            
            ax.plot(df[cols['date']], df[cols['actual_value']], 'ko-', linewidth=2, 
                   markersize=5, alpha=0.5, label=f'Actual {actual_value_name}', zorder=6)
            
            # Add quarterly dividers
            y_max = df[[cols['actual_value'], cols['lstm_predicted'], 
                       cols['rolling_mean'], cols['std_plus_2']]].max().max()
            self.add_quarterly_dividers(ax, df, y_max)
            
            # Deviation lines
            std_anomalies = df[df['STD_Anomaly_Flag'] == 1]
            lstm_anomalies = df[df['LSTM_Anomaly_Flag'] == 1]
            
            # Manual deviations
         # Manual deviations (vertical deviation lines commented out)
         # The vertical deviation lines acted like 'bars' connecting prediction and actual —
         # they are intentionally disabled to remove the bar-like visuals.
         # if not std_anomalies.empty:
         #     first_row = std_anomalies.iloc[0]
         #     ax.plot([first_row[cols['date']], first_row[cols['date']]], 
         #            [first_row[cols['rolling_mean']], first_row[cols['actual_value']]], 
         #            color='orange', linewidth=2.5, alpha=0.6, linestyle=':', 
         #            label='Manual Deviation', zorder=7)
         #     for _, row in std_anomalies.iloc[1:].iterrows():
         #         ax.plot([row[cols['date']], row[cols['date']]], 
         #                [row[cols['rolling_mean']], row[cols['actual_value']]], 
         #                color='orange', linewidth=2.5, alpha=0.6, linestyle=':', zorder=7)
            
            # LSTM deviations
         # LSTM deviations (vertical deviation lines commented out)
         # if not lstm_anomalies.empty:
         #     first_row = lstm_anomalies.iloc[0]
         #     ax.plot([first_row[cols['date']], first_row[cols['date']]], 
         #            [first_row[cols['lstm_predicted']], first_row[cols['actual_value']]], 
         #            color='purple', linewidth=2.5, alpha=0.6, linestyle=':', 
         #            label='LSTM Deviation', zorder=7)
         #     for _, row in lstm_anomalies.iloc[1:].iterrows():
         #         ax.plot([row[cols['date']], row[cols['date']]], 
         #                [row[cols['lstm_predicted']], row[cols['actual_value']]], 
         #                color='purple', linewidth=2.5, alpha=0.6, linestyle=':', zorder=7)
            
            # Anomaly markers - Both detected
            both_detected = df[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 1)]
            if not both_detected.empty:
                ax.scatter(both_detected[cols['date']], both_detected[cols['actual_value']], 
                          color=settings['colors']['both'], s=600, 
                          marker='*', edgecolors='darkred', linewidth=4.5, 
                          label='★ Both Detected', zorder=15, alpha=1.0)
            
            # Manual only anomalies
            only_std = df[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 0)]
            if not only_std.empty:
                self._plot_severity_markers(ax, only_std, 'manual', zorder_start=10)
            
            # LSTM only anomalies
            only_lstm = df[(df['STD_Anomaly_Flag'] == 0) & (df['LSTM_Anomaly_Flag'] == 1)]
            if not only_lstm.empty:
                self._plot_severity_markers(ax, only_lstm, 'lstm', zorder_start=10)
            
            # Formatting
            ax.set_xlabel('Date', fontsize=17, fontweight='bold')
            ax.set_ylabel(f'{actual_value_name} Amount', fontsize=17, fontweight='bold')
            ax.set_title(f'Merged Method Comparison: Manual (STD/Lag) vs LSTM Detection - {actual_value_name}\n' +
                        'Vertical Dotted Lines Show Deviation from Predictions | Gray Lines Mark Quarters', 
                        fontsize=19, fontweight='bold', pad=20)
            
            legend = ax.legend(loc='upper left', fontsize=10.5, framealpha=0.98, 
                              ncol=4, bbox_to_anchor=(0, -0.12), borderaxespad=0,
                              columnspacing=1.2, handletextpad=0.5, frameon=True,
                              fancybox=True, shadow=True, edgecolor='black')
            legend.get_frame().set_linewidth(1.5)
            
            ax.grid(True, alpha=0.3, linestyle='--', linewidth=1)
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=13)
            plt.setp(ax.yaxis.get_majorticklabels(), fontsize=13)
            
            # Statistics box
            std_count = int(df['STD_Anomaly_Flag'].sum())
            lstm_count = int(df['LSTM_Anomaly_Flag'].sum())
            both_count = len(both_detected)
            only_std_count = len(only_std)
            only_lstm_count = len(only_lstm)
            
            avg_std_dev = abs(std_anomalies[cols['actual_value']] - std_anomalies[cols['rolling_mean']]).mean() if not std_anomalies.empty else 0
            avg_lstm_dev = abs(lstm_anomalies[cols['actual_value']] - lstm_anomalies[cols['lstm_predicted']]).mean() if not lstm_anomalies.empty else 0
            
            stats_text = (
                f'DETECTION SUMMARY\n'
                f'{"─"*30}\n'
                f'Manual: {std_count} anomalies\n'
                f'  Avg Dev: {avg_std_dev:.2f}\n'
                f'LSTM: {lstm_count} anomalies\n'
                f'  Avg Dev: {avg_lstm_dev:.2f}\n'
                f'{"─"*30}\n'
                f'Both Agree: {both_count}\n'
                f'Only Manual: {only_std_count}\n'
                f'Only LSTM: {only_lstm_count}\n'
                f'{"─"*30}\n'
                f'Total Unique: {both_count + only_std_count + only_lstm_count}'
            )
            
            ax.text(0.01, 0.80, stats_text,
                    transform=ax.transAxes, fontsize=11.5, verticalalignment='top',
                    horizontalalignment='left', family='monospace',
                    bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', 
                             alpha=0.97, edgecolor='black', linewidth=2.5))
            
            plt.tight_layout(rect=[0, 0.08, 1, 1])
            plt.savefig(output_file, dpi=settings['dpi'], bbox_inches='tight')
            plt.close()
            print(f"     Saved: {output_file}")
            return True
            
        except Exception as e:
            print(f"     Error creating merged plot: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def plot_split_comparison(self, df: pd.DataFrame, output_dir: Path) -> bool:
        """
        PLOT 2: SPLIT comparison - Two horizontal subplots
        Top: Manual STD/Lag Detection | Bottom: LSTM Detection
        """
        
        try:
            cols = self.config.columns
            settings = self.config.plot_settings
            
            # Generate dynamic filename
            output_file = output_dir / self.config.get_output_filename('2_split_comparison')
            
            # Get actual value column name for labels
            actual_value_name = cols['actual_value']
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=settings['figsize_double'], sharex=True)
            
            # Prepare quarterly dividers
            df['quarter'] = df[cols['date']].dt.to_period('Q')
            unique_quarters = df.groupby('quarter')[cols['date']].min()
            
            # ====================================================================
            # TOP SUBPLOT: MANUAL STD/LAG DETECTION
            # ====================================================================
            
            # Background: Manual STD Bands
            ax1.fill_between(df[cols['date']], df[cols['std_minus_2']], df[cols['std_plus_2']], 
                            alpha=0.15, color='gray', label='±2 STD Band', zorder=1)
            ax1.fill_between(df[cols['date']], df[cols['std_minus_1']], df[cols['std_plus_1']], 
                            alpha=0.25, color='lightblue', label='±1 STD Band', zorder=2)
            
            # Rolling Mean Line
            ax1.plot(df[cols['date']], df[cols['rolling_mean']], 
                    color=settings['colors']['manual'], linewidth=3.5, linestyle='--', 
                    label='Rolling Mean', zorder=4, alpha=0.85)
            
            # Actual Borrowings (base line)
            ax1.plot(df[cols['date']], df[cols['actual_value']], 'k-', linewidth=2, 
                    alpha=0.4, label=f'Actual {actual_value_name}', zorder=3)
            
            # Quarterly Dividers
            y_max_manual = df[[cols['actual_value'], cols['rolling_mean'], cols['std_plus_2']]].max().max()
            for quarter_start in unique_quarters:
                ax1.axvline(x=quarter_start, color='gray', linestyle=':', 
                           linewidth=1.5, alpha=0.4, zorder=2)
                quarter_label = quarter_start.strftime('%Y-Q') + str((quarter_start.month - 1) // 3 + 1)
                ax1.text(quarter_start, y_max_manual * 1.02, quarter_label, 
                        rotation=0, ha='center', va='bottom', fontsize=9, 
                        color='gray', alpha=0.7)
            
            # Deviation lines for Manual
            std_anomalies = df[df['STD_Anomaly_Flag'] == 1]
            if not std_anomalies.empty:
                first_dev = std_anomalies.iloc[0]
                ax1.plot([first_dev[cols['date']], first_dev[cols['date']]], 
                        [first_dev[cols['rolling_mean']], first_dev[cols['actual_value']]], 
                        color='orange', linewidth=2.5, alpha=0.6, linestyle=':', 
                        label='Deviation Line', zorder=6)
                
                for _, row in std_anomalies.iloc[1:].iterrows():
                    ax1.plot([row[cols['date']], row[cols['date']]], 
                            [row[cols['rolling_mean']], row[cols['actual_value']]], 
                            color='orange', linewidth=2.5, alpha=0.6, linestyle=':', zorder=6)
            
            # Normal Points (Manual)
            normal_manual = df[df['STD_Anomaly_Flag'] == 0]
            ax1.scatter(normal_manual[cols['date']], normal_manual[cols['actual_value']], 
                       color='lightgray', s=60, marker='o', alpha=0.6, 
                       edgecolors='gray', linewidth=0.5, label='Normal Points', zorder=5)
            
            # Manual Anomalies with severity markers
            if not std_anomalies.empty:
                self._plot_severity_markers(ax1, std_anomalies, 'manual', zorder_start=8)
            
            # Formatting for Top Subplot
            ax1.set_ylabel(f'{actual_value_name} Amount', fontsize=16, fontweight='bold')
            ax1.set_title(f'MANUAL STD/LAG-BASED ANOMALY DETECTION - {actual_value_name}\n' +
                         f'Total Detected: {len(std_anomalies)} | Extreme: {len(std_anomalies[std_anomalies["STD_Severity"] == "Extreme"])} | ' +
                         f'Level 2: {len(std_anomalies[std_anomalies["STD_Severity"] == "Level 2"])}', 
                         fontsize=17, fontweight='bold', pad=15, color='darkorange')
            
            legend1 = ax1.legend(loc='upper left', fontsize=10, framealpha=0.97, 
                                ncol=2, borderaxespad=0.5, 
                                fancybox=True, shadow=True,
                                title='LEGEND - MANUAL DETECTION', title_fontsize=11,
                                markerscale=0.8, handlelength=2.5, handleheight=1.5)
            legend1.get_frame().set_linewidth(2.5)
            legend1.get_frame().set_edgecolor('steelblue')
            legend1.get_frame().set_facecolor('lightcyan')
            legend1.get_title().set_weight('bold')
            legend1.get_title().set_color('darkblue')
            
            ax1.grid(True, alpha=0.3, linestyle='--', linewidth=1)
            plt.setp(ax1.yaxis.get_majorticklabels(), fontsize=13)
            
            # Statistics Box for Manual
            avg_std_dev = abs(std_anomalies[cols['actual_value']] - std_anomalies[cols['rolling_mean']]).mean() if not std_anomalies.empty else 0
            
            stats_text_manual = (
                f'MANUAL DETECTION\n'
                f'{"─"*25}\n'
                f'Total: {len(std_anomalies)}\n'
                f'Avg Dev: {avg_std_dev:.2f}\n'
                f'Extreme: {len(std_anomalies[std_anomalies["STD_Severity"] == "Extreme"])}\n'
                f'Level 2: {len(std_anomalies[std_anomalies["STD_Severity"] == "Level 2"])}'
            )
            
            ax1.text(0.99, 0.97, stats_text_manual,
                    transform=ax1.transAxes, fontsize=11, verticalalignment='top',
                    horizontalalignment='right', family='monospace',
                    bbox=dict(boxstyle='round,pad=0.7', facecolor='mistyrose', 
                             alpha=0.95, edgecolor='darkorange', linewidth=2.5))
            
            # ====================================================================
            # BOTTOM SUBPLOT: LSTM DETECTION
            # ====================================================================
            
            # LSTM Predicted Line
            ax2.plot(df[cols['date']], df[cols['lstm_predicted']], 
                    color=settings['colors']['lstm'], linewidth=3.5, linestyle='-', 
                    label='LSTM Predicted', zorder=4, alpha=0.85)
            
            # Actual Borrowings (base line)
            ax2.plot(df[cols['date']], df[cols['actual_value']], 'k-', linewidth=2, 
                    alpha=0.4, label=f'Actual {actual_value_name}', zorder=3)
            
            # Quarterly Dividers
            y_max_lstm = df[[cols['actual_value'], cols['lstm_predicted']]].max().max()
            first_quarter = unique_quarters[0]
            ax2.axvline(x=first_quarter, color='gray', linestyle=':', 
                       linewidth=1.5, alpha=0.4, label='Quarter Dividers', zorder=2)
            
            for quarter_start in unique_quarters[1:]:
                ax2.axvline(x=quarter_start, color='gray', linestyle=':', 
                           linewidth=1.5, alpha=0.4, zorder=2)
                quarter_label = quarter_start.strftime('%Y-Q') + str((quarter_start.month - 1) // 3 + 1)
                ax2.text(quarter_start, y_max_lstm * 1.02, quarter_label, 
                        rotation=0, ha='center', va='bottom', fontsize=9, 
                        color='gray', alpha=0.7)
            
            # Add label to first quarter
            quarter_label = first_quarter.strftime('%Y-Q') + str((first_quarter.month - 1) // 3 + 1)
            ax2.text(first_quarter, y_max_lstm * 1.02, quarter_label, 
                    rotation=0, ha='center', va='bottom', fontsize=9, 
                    color='gray', alpha=0.7)
            
            # Normal Points (LSTM)
            normal_lstm = df[df['LSTM_Anomaly_Flag'] == 0]
            ax2.scatter(normal_lstm[cols['date']], normal_lstm[cols['actual_value']], 
                       color='lightgray', s=60, marker='o', alpha=0.6, 
                       edgecolors='gray', linewidth=0.5, label='Normal Points', zorder=5)
            
            # LSTM Anomalies
            lstm_anomalies = df[df['LSTM_Anomaly_Flag'] == 1]
            
            # Deviation lines for LSTM
            if not lstm_anomalies.empty:
                first_lstm_dev = lstm_anomalies.iloc[0]
                ax2.plot([first_lstm_dev[cols['date']], first_lstm_dev[cols['date']]], 
                        [first_lstm_dev[cols['lstm_predicted']], first_lstm_dev[cols['actual_value']]], 
                        color='purple', linewidth=2.5, alpha=0.6, linestyle=':', 
                        label='Deviation Line', zorder=6)
                
                for _, row in lstm_anomalies.iloc[1:].iterrows():
                    ax2.plot([row[cols['date']], row[cols['date']]], 
                            [row[cols['lstm_predicted']], row[cols['actual_value']]], 
                            color='purple', linewidth=2.5, alpha=0.6, linestyle=':', zorder=6)
            
            # LSTM Anomalies with severity markers
            if not lstm_anomalies.empty:
                self._plot_severity_markers(ax2, lstm_anomalies, 'lstm', zorder_start=8)
            
            # Formatting for Bottom Subplot
            ax2.set_xlabel('Date', fontsize=16, fontweight='bold')
            ax2.set_ylabel(f'{actual_value_name} Amount', fontsize=16, fontweight='bold')
            ax2.set_title(f'LSTM-BASED ANOMALY DETECTION - {actual_value_name}\n' +
                         f'Total Detected: {len(lstm_anomalies)} | Extreme: {len(lstm_anomalies[lstm_anomalies["LSTM_Severity"] == "Extreme"])} | ' +
                         f'Level 2: {len(lstm_anomalies[lstm_anomalies["LSTM_Severity"] == "Level 2"])}', 
                         fontsize=17, fontweight='bold', pad=15, color='darkviolet')
            
            legend2 = ax2.legend(loc='upper left', fontsize=10, framealpha=0.97, 
                                ncol=2, borderaxespad=0.5,
                                fancybox=True, shadow=True,
                                title='LEGEND - LSTM DETECTION', title_fontsize=11,
                                markerscale=0.8, handlelength=2.5, handleheight=1.5)
            legend2.get_frame().set_linewidth(2.5)
            legend2.get_frame().set_edgecolor('steelblue')
            legend2.get_frame().set_facecolor('lightcyan')
            legend2.get_title().set_weight('bold')
            legend2.get_title().set_color('darkblue')
            
            ax2.grid(True, alpha=0.3, linestyle='--', linewidth=1)
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=13)
            plt.setp(ax2.yaxis.get_majorticklabels(), fontsize=13)
            
            # Statistics Box for LSTM
            avg_lstm_dev = abs(lstm_anomalies[cols['actual_value']] - lstm_anomalies[cols['lstm_predicted']]).mean() if not lstm_anomalies.empty else 0
            
            stats_text_lstm = (
                f'LSTM DETECTION\n'
                f'{"─"*25}\n'
                f'Total: {len(lstm_anomalies)}\n'
                f'Avg Dev: {avg_lstm_dev:.2f}\n'
                f'Extreme: {len(lstm_anomalies[lstm_anomalies["LSTM_Severity"] == "Extreme"])}\n'
                f'Level 2: {len(lstm_anomalies[lstm_anomalies["LSTM_Severity"] == "Level 2"])}'
            )
            
            ax2.text(0.99, 0.97, stats_text_lstm,
                    transform=ax2.transAxes, fontsize=11, verticalalignment='top',
                    horizontalalignment='right', family='monospace',
                    bbox=dict(boxstyle='round,pad=0.7', facecolor='thistle', 
                             alpha=0.95, edgecolor='darkviolet', linewidth=2.5))
            
            # Comparison box
            both_detected = df[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 1)]
            only_std = df[(df['STD_Anomaly_Flag'] == 1) & (df['LSTM_Anomaly_Flag'] == 0)]
            only_lstm = df[(df['STD_Anomaly_Flag'] == 0) & (df['LSTM_Anomaly_Flag'] == 1)]
            
            comparison_text = (
                f'COMPARISON SUMMARY\n'
                f'{"═"*30}\n'
                f'Both Methods Agree: {len(both_detected)}\n'
                f'Only Manual Detected: {len(only_std)}\n'
                f'Only LSTM Detected: {len(only_lstm)}\n'
                f'{"═"*30}\n'
                f'Total Unique Anomalies: {len(both_detected) + len(only_std) + len(only_lstm)}'
            )
            
            ax1.text(0.99, 0.02, comparison_text,
                    transform=ax1.transAxes, fontsize=11.5, verticalalignment='bottom',
                    horizontalalignment='right', family='monospace',
                    bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', 
                             alpha=0.97, edgecolor='black', linewidth=3))
            
            # Main title
            fig.suptitle(f'Anomaly Detection Method Comparison: Manual (STD/Lag) vs LSTM - {actual_value_name}\n' +
                        'Vertical Dotted Lines = Deviations | Gray Lines = Quarterly Dividers', 
                        fontsize=20, fontweight='bold', y=0.995)
            
            plt.tight_layout(rect=[0, 0.02, 1, 0.99])
            plt.savefig(output_file, dpi=settings['dpi'], bbox_inches='tight')
            plt.close()
            print(f"   ✓ Saved: {output_file}")
            return True
            
        except Exception as e:
            print(f"     Error creating split plot: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# MAIN ANALYSIS CLASS
# ============================================================================

class AnomalyDetectionAnalyzer:
    """Main analyzer orchestrating all components"""
    
    def __init__(self, config: AnomalyDetectionConfig):
        self.config = config
        self.loader = DataLoader(config)
        self.processor = AnomalyProcessor(config)
        self.visualizer = AnomalyVisualizer(config)
    
    def run_analysis(self, csv_file: str, output_dir: str = './outputs'):
        """Run complete analysis pipeline"""
        
        print("\n" + "="*120)
        print("STARTING ENHANCED ANOMALY DETECTION ANALYSIS")
        print(f"User: dundaymo_msid | Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("="*120 + "\n")
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load data
        print("STEP 1: Loading data...")
        df = self.loader.load_data(csv_file)
        if df is None:
            print("\n  ANALYSIS ABORTED\n")
            return None
        
        # Process anomalies
        print("\nSTEP 2: Processing anomalies...")
        df = self.processor.prepare_anomaly_flags(df)
        if df is None:
            print("\n  ANALYSIS ABORTED\n")
            return None
        
        # Generate visualizations
        print("\nSTEP 3: Generating visualizations (2 plots)...")
        print(f"{'─'*80}")
        
        # Plot 1: Merged comparison
        plot1_success = self.visualizer.plot_merged_comparison(df, output_path)
        
        # Plot 2: Split comparison
        plot2_success = self.visualizer.plot_split_comparison(df, output_path)
        
        successful_plots = sum([plot1_success, plot2_success])
        print(f"{'─'*80}")
        print(f"Plots completed: {successful_plots}/2")
        
        # Save summary
        print("\nSTEP 4: Saving summary...")
        self._save_summary(df, output_path)
        
        # Generate report
        print("\nSTEP 5: Generating report...")
        self._generate_report(df)
        
        # Get actual value name for display
        actual_value_name = self.config.columns['actual_value']
        
        print("\n" + "="*120)
        print("  ANALYSIS COMPLETE!")
        print("="*120)
        print("\nGenerated Files:")
        print("    VISUALIZATIONS:")
        print(f"     1. {self.config.get_output_filename('1_merged_comparison')} - Merged comparison with deviations")
        print(f"     2. {self.config.get_output_filename('2_split_comparison')} - Split comparison (Manual vs LSTM)")
        print("    DATA:")
        print(f"     - anomaly_summary_{actual_value_name}.csv - Filtered anomaly data")
        print("\n" + "="*120 + "\n")
        
        return df
    
    def _save_summary(self, df: pd.DataFrame, output_path: Path):
        """Save anomaly summary to CSV"""
        anomaly_df = df[(df['STD_Anomaly_Flag'] == 1) | (df['LSTM_Anomaly_Flag'] == 1)].copy()
        
        if not anomaly_df.empty:
            actual_value_name = self.config.columns['actual_value'].replace(' ', '_').replace('-', '_')
            summary_file = output_path / f'anomaly_summary_{actual_value_name}.csv'
            anomaly_df.to_csv(summary_file, index=False)
            print(f"   ✓ Saved: {summary_file} ({len(anomaly_df)} anomalies)")
    
    def _generate_report(self, df: pd.DataFrame):
        """Generate text report"""
        print(f"\n{'='*120}")
        print("DETECTION SUMMARY REPORT")
        print(f"{'='*120}")
        
        both_detected = df[df['Agreement_Category'] == 'Both Detected']
        only_std = df[df['Agreement_Category'] == 'Only STD']
        only_lstm = df[df['Agreement_Category'] == 'Only LSTM']
        
        total_anomalies = len(both_detected) + len(only_std) + len(only_lstm)
        agreement_rate = (len(both_detected) / total_anomalies * 100) if total_anomalies > 0 else 0
        
        actual_value_name = self.config.columns['actual_value']
        
        print(f"\nAnalysis Target: {actual_value_name}")
        print(f"Total Anomalies: {total_anomalies}")
        print(f"  - Both Methods Agree: {len(both_detected)} ({agreement_rate:.1f}%)")
        print(f"  - Only Manual: {len(only_std)}")
        print(f"  - Only LSTM: {len(only_lstm)}")
        print(f"\nAgreement Rate: {agreement_rate:.2f}%")
        print(f"{'='*120}\n")


# ============================================================================
# CLI INTERFACE
# ============================================================================

def create_default_config():
    """Create and save default configuration file"""
    config = AnomalyDetectionConfig()
    config.save_to_json('config_default.json')
    print("✓ Default configuration created: config_default.json")
    print("  Edit this file to customize column mappings and settings")


def main():
    """Main entry point with CLI"""
    parser = argparse.ArgumentParser(
        description='Anomaly Detection Analysis Tool - Dynamic Filenames',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        # Basic usage (creates files like: 1_merged_comparison_Borrowings.png)
        python script.py data.csv
        
        # With custom config
        python script.py data.csv --config custom_config.json
        
        # Create default config template
        python script.py --create-config
                """
            )
    
    parser.add_argument('csv_file', nargs='?', 
                       help='Path to input CSV file')
    parser.add_argument('--config', '-c', 
                       help='Path to configuration JSON file')
    parser.add_argument('--output-dir', '-o', default='./outputs',
                       help='Output directory for results (default: ./outputs)')
    parser.add_argument('--create-config', action='store_true',
                       help='Create default configuration file and exit')
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        create_default_config()
        return
    
    # Validate input
    if not args.csv_file:
        parser.print_help()
        print(" Error: CSV file path is required")
        return
    
    # Load configuration
    if args.config:
        config = AnomalyDetectionConfig.from_json(args.config)
        print(f" Loaded configuration from: {args.config}")
    else:
        config = AnomalyDetectionConfig()
        print(" Using default configuration")
    
    # Display filename pattern
    print(f"   Output file pattern: {{graph_type}}_{config.columns['actual_value'].replace(' ', '_')}.png")
    print(f"   Example: 1_merged_comparison_{config.columns['actual_value'].replace(' ', '_')}.png\n")
    
    # Run analysis
    analyzer = AnomalyDetectionAnalyzer(config)
    analyzer.run_analysis(args.csv_file, args.output_dir)


if __name__ == "__main__":
    main()