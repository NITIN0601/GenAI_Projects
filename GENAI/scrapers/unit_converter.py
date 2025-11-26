"""Convert financial values between units."""

from typing import Tuple, Optional
import re


class UnitConverter:
    """
    Convert financial values between units.
    
    Handles conversion from display units (millions, billions) to base units
    and provides multiple representations for storage and display.
    """
    
    # Unit multipliers
    MULTIPLIERS = {
        'thousands': 1_000,
        'thousand': 1_000,
        'millions': 1_000_000,
        'million': 1_000_000,
        'billions': 1_000_000_000,
        'billion': 1_000_000_000,
        'trillions': 1_000_000_000_000,
        'trillion': 1_000_000_000_000,
    }
    
    # Unit detection patterns
    UNIT_PATTERNS = [
        (r'\$?\s*in\s+(thousands|millions|billions|trillions)', 'unit'),
        (r'\(in\s+(thousands|millions|billions|trillions)\)', 'unit'),
        (r'\$\s*(thousands|millions|billions|trillions)', 'unit'),
    ]
    
    def detect_unit(self, text: str) -> Optional[str]:
        """
        Detect unit from text (typically from column header).
        
        Args:
            text: Text to search for unit
        
        Returns:
            Unit name (thousands, millions, billions) or None
        """
        text_lower = text.lower()
        
        for pattern, _ in self.UNIT_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)
        
        # Check for simple mentions
        for unit in self.MULTIPLIERS.keys():
            if unit in text_lower:
                return unit
        
        return None
    
    def convert_to_base(
        self, 
        value: float, 
        unit: str
    ) -> Tuple[float, str, str]:
        """
        Convert value to base unit (actual dollars).
        
        Args:
            value: Original value
            unit: Unit (thousands, millions, billions)
        
        Returns:
            (base_value, base_unit, display_value)
        """
        unit_lower = unit.lower() if unit else ''
        
        # Find multiplier
        multiplier = 1
        unit_name = None
        for unit_key, mult in self.MULTIPLIERS.items():
            if unit_key in unit_lower:
                multiplier = mult
                unit_name = unit_key
                break
        
        # Convert to base
        base_value = value * multiplier
        base_unit = 'usd'
        
        # Create display value
        if unit_name:
            display_value = f'$ {value:,.0f} {unit_name}'
        else:
            display_value = f'$ {value:,.0f}'
        
        return base_value, base_unit, display_value
    
    def format_value(
        self,
        value: float,
        unit: Optional[str] = None,
        decimal_places: int = 0
    ) -> str:
        """
        Format value for display.
        
        Args:
            value: Value to format
            unit: Unit (if any)
            decimal_places: Number of decimal places
        
        Returns:
            Formatted string
        """
        if unit:
            if decimal_places > 0:
                return f'$ {value:,.{decimal_places}f} {unit}'
            else:
                return f'$ {value:,.0f} {unit}'
        else:
            if decimal_places > 0:
                return f'$ {value:,.{decimal_places}f}'
            else:
                return f'$ {value:,.0f}'
    
    def parse_value_with_unit(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse value and unit from text.
        
        Args:
            text: Text containing value (e.g., "$ 17,739 million")
        
        Returns:
            (value, unit) tuple
        """
        # Remove currency symbols and commas
        cleaned = text.replace('$', '').replace(',', '').strip()
        
        # Try to extract number
        number_match = re.search(r'([-+]?\d+\.?\d*)', cleaned)
        if not number_match:
            return None, None
        
        value = float(number_match.group(1))
        
        # Detect unit in remaining text
        unit = self.detect_unit(cleaned)
        
        return value, unit


# Global converter instance
_converter: Optional[UnitConverter] = None


def get_unit_converter() -> UnitConverter:
    """Get or create global unit converter instance."""
    global _converter
    if _converter is None:
        _converter = UnitConverter()
    return _converter
