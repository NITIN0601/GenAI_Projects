"""
Text Normalizer - Clean and normalize row labels and text fields.

Handles:
- Extra spaces around dashes: "text - text" → "text-text"
- Footnote references: "Item 1" → "Item"
- Multiple spaces: "text  text" → "text text"
- Special characters: em dashes, non-breaking spaces
- OCR artifacts and broken words
"""

import re
from typing import Optional


class TextNormalizer:
    """
    Normalize text values for consistency in row labels and metadata.
    
    Used for:
    - Category (Parent) field
    - Line Items field
    - Row labels in data tables
    """
    
    # Footnote patterns to remove
    FOOTNOTE_PATTERNS = [
        r'\s+\d+$',          # Trailing number: "Item 1" → "Item"
        r'\s+\(\d+\)$',      # Trailing (1): "Item (1)" → "Item"
        r'\s+\[\d+\]$',      # Trailing [1]: "Item [1]" → "Item"
        r'\*+$',             # Trailing asterisks
        r'\s+[a-z]$',        # Trailing single letter: "Item a"
    ]
    
    # Special character replacements
    CHAR_REPLACEMENTS = {
        '—': '-',          # Em dash → hyphen
        '–': '-',          # En dash → hyphen
        '\xa0': ' ',       # Non-breaking space → space
        '\u200b': '',      # Zero-width space → remove
        ''': "'",          # Smart quote
        ''': "'",          # Smart quote
        '"': '"',          # Smart quote
        '"': '"',          # Smart quote
    }
    
    @classmethod
    def normalize(cls, text: Optional[str], preserve_case: bool = True) -> str:
        """
        Normalize text by cleaning spaces, dashes, and removing footnotes.
        
        Args:
            text: Input text to normalize
            preserve_case: If True, preserve original case; if False, apply title case
            
        Returns:
            Normalized text string
        """
        if not text or not isinstance(text, str):
            return ''
        
        result = text.strip()
        
        # Replace special characters
        for char, replacement in cls.CHAR_REPLACEMENTS.items():
            result = result.replace(char, replacement)
        
        # Remove footnote references
        for pattern in cls.FOOTNOTE_PATTERNS:
            result = re.sub(pattern, '', result)
        
        # Fix spaces around dashes: "text - text" → "text-text"
        result = cls._fix_dash_spacing(result)
        
        # Collapse multiple spaces
        result = re.sub(r'\s+', ' ', result)
        
        # Clean up punctuation spacing
        result = cls._fix_punctuation_spacing(result)
        
        # Strip again after all processing
        result = result.strip()
        
        # Apply case normalization if requested
        if not preserve_case:
            result = cls._apply_title_case(result)
        
        return result
    
    @classmethod
    def _fix_dash_spacing(cls, text: str) -> str:
        """
        Fix inconsistent spacing around dashes.
        
        Examples:
            "equity- related" → "equity-related"
            "non - GAAP" → "non-GAAP"
            "Adjusted Net revenues-non- GAAP" → "Adjusted Net revenues-non-GAAP"
        """
        # Remove space before dash when followed by letter
        text = re.sub(r'\s+-([a-zA-Z])', r'-\1', text)
        
        # Remove space after dash when preceded by letter
        text = re.sub(r'([a-zA-Z])-\s+', r'\1-', text)
        
        # Handle " - " (space-dash-space) → "-"
        text = re.sub(r'\s+-\s+', '-', text)
        
        return text
    
    @classmethod
    def _fix_punctuation_spacing(cls, text: str) -> str:
        """
        Fix spacing around punctuation.
        
        Examples:
            "Item ,text" → "Item, text"
            "text ." → "text."
        """
        # No space before comma, period, colon
        text = re.sub(r'\s+([,.:;])', r'\1', text)
        
        # Space after comma, colon (if followed by letter)
        text = re.sub(r'([,:])([a-zA-Z])', r'\1 \2', text)
        
        return text
    
    @classmethod
    def _apply_title_case(cls, text: str) -> str:
        """
        Apply smart title case, keeping acronyms uppercase.
        
        Examples:
            "net revenues" → "Net Revenues"
            "ROE" → "ROE" (preserved)
            "GAAP" → "GAAP" (preserved)
        """
        # Words to keep uppercase
        uppercase_words = {'ROE', 'ROTCE', 'GAAP', 'DCP', 'HQLA', 'CRE', 'LTV', 'FICO', 'US', 'UK'}
        
        # Words to keep lowercase (after first word)
        lowercase_words = {'and', 'or', 'the', 'of', 'to', 'in', 'for', 'on', 'at', 'by', 'with'}
        
        words = text.split()
        result = []
        
        for i, word in enumerate(words):
            if word.upper() in uppercase_words:
                result.append(word.upper())
            elif i > 0 and word.lower() in lowercase_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)
    
    @classmethod
    def normalize_list(cls, items: list, preserve_case: bool = True) -> list:
        """Normalize a list of text items."""
        return [cls.normalize(item, preserve_case) for item in items]
    
    @classmethod
    def clean_footnotes(cls, text: str) -> str:
        """
        Remove only footnote references, keeping other formatting.
        """
        if not text:
            return ''
        
        result = text
        for pattern in cls.FOOTNOTE_PATTERNS:
            result = re.sub(pattern, '', result)
        
        return result.strip()


# Convenience functions
def normalize_text(text: str, preserve_case: bool = True) -> str:
    """Normalize a text string. Convenience wrapper."""
    return TextNormalizer.normalize(text, preserve_case)


def clean_footnotes(text: str) -> str:
    """Remove footnote references from text. Convenience wrapper."""
    return TextNormalizer.clean_footnotes(text)
