# Index Sheet Mapping & Re-sequencing

##  PROJECT COMPLETE - January 16, 2026

**All 4 files successfully processed!** 280 new sheets created through multi-table splitting.  
 [**View Complete Results →**](project_complete.md)

---

##  Overview

This folder contains the complete specification and implementation for re-sequencing xlsx Index sheets and physically splitting multi-table sheets based on unique (Section + Table Title) combinations.

##  Folder Contents

| File | Description |
|------|-------------|
| **project_complete.md** |  **Project completion summary with all results and metrics** |
| **index_sheet_mapping_table.md** |  Complete planning document with all edge cases, scenarios, and specifications |
| **implementation_summary.md** |  Implementation status, test results, and technical details |
| **quick_start.md** |  Quick reference guide for running the tools |
| **README.md** |  This file - overview and navigation |

##  What This Solves

### Problem
Current xlsx files have:
- **Multi-table sheets**: Single sheet contains multiple tables stacked vertically
- **Duplicate Index entries**: Multiple Index rows pointing to the same sheet
- **Inconsistent IDs**: Manual split patterns like `4-1`, `4-2`

### Solution
This implementation:
-  Detects table blocks within sheets
-  Physically splits multi-table sheets into separate sheets
-  Assigns sequential IDs based on unique (Section + Table Title)
-  Uses consistent `_n` suffix pattern for sub-tables
-  Updates Index sheet links automatically

##  Key Concepts

### Unique Grouping Key
```
Group Key = Section + Table Title
```

Every unique combination gets a sequential base ID. Duplicates get suffixes.

### Naming Convention
| Pattern | Example | Meaning |
|---------|---------|---------|
| Base ID | `4` | First entry of unique (Section+Title) group |
| Sub-table | `4_1`, `4_2` | Additional entries with SAME (Section+Title) |

### Example Transformation

**Before:**
```
Index Entries:
  Row 1: [Section A] Title X → 2
  Row 2: [Section A] Title X → 2  (duplicate)
  Row 3: [Section B] Title Y → 3

Sheet 2: Contains 2 tables (Section A Title X + Section B Title Y)
Sheet 3: Contains 1 table
```

**After:**
```
Index Entries:
  Row 1: [Section A] Title X → 2
  Row 2: [Section A] Title X → 2_1
  Row 3: [Section B] Title Y → 3

Sheet 2:   Contains only first Section A Title X table
Sheet 2_1: Contains only second Section A Title X table (NEW)
Sheet 3:   Contains Section B Title Y table
```

##  Quick Start

### 1. Analyze Structure (No Changes Made)
```bash
cd .
python3 scripts/test_index_resequencer.py --mode analyze --file data/processed/10q0925_tables.xlsx
```

### 2. Process Test File
```bash
python3 scripts/test_index_resequencer.py --mode single --file data/processed/10q0925_tables.xlsx
```
Output: `data/processed/test_output/10q0925_tables.xlsx`

### 3. Process All Files
```bash
python3 scripts/test_index_resequencer.py --mode all --dir data/processed
```
Output: `data/processed/test_output/*.xlsx`

##  Documentation Guide

### New to This?
Start here:
1. **quick_start.md** - Commands and examples
2. **Visual diagram** in implementation_summary.md
3. **index_sheet_mapping_table.md** - Full specification

### Implementing or Debugging?
1. **implementation_summary.md** - Technical details
2. **index_sheet_mapping_table.md** - Edge cases and scenarios
3. Source code: `src/index_sheet_resequencer.py`

### Testing?
1. **quick_start.md** - Test commands
2. **implementation_summary.md** - Expected results
3. Test script: `scripts/test_index_resequencer.py`

##  Edge Cases Handled

The implementation handles 5 major edge cases:

1. **Sub-Table WITH Metadata Block** - Full metadata preserved
2. **Sub-Table WITHOUT Metadata** - Minimal metadata structure created
3. **Data-Only Table** - Fallback to Index data
4. **Single Metadata + Multiple Data Blocks** - Metadata copied to each sheet
5. **Multi-Page Continuous Table** - Consolidated to single entry

See `index_sheet_mapping_table.md` for detailed examples of each case.

##  Test Results

Sample results from `10q0925_tables.xlsx`:

- **235 Index entries** total
- **160 unique (Section, Title)** combinations
- **47 groups** have multiple entries
- **75 sheets** will be created through splitting

##  Implementation Status

| Component | Status |
|-----------|--------|
| Planning & Specification |  Complete |
| Core Implementation |  Complete |
| Block Detection Logic |  Complete |
| Test Framework |  Complete |
| Documentation |  Complete |
| Production Testing |  **COMPLETE - All 4 files processed** |
| Integration with CSV Export |  Next Phase |

**Results:** 280 new sheets created, 999 total sheets across 4 files. See [project_complete.md](project_complete.md) for details.

##  Related Files

**Implementation:**
- `src/index_sheet_resequencer.py` - Main implementation
- `scripts/test_index_resequencer.py` - Test & analysis tool

**Input:**
- `data/processed/*.xlsx` - Original files to process

**Output:**
- `data/processed/test_output/*.xlsx` - Re-sequenced files
- `data/processed/resequenced/*.xlsx` - Production output (when ready)

##  Next Steps

1. **Review** the quick_start.md for running commands
2. **Analyze** structure with `--mode analyze`
3. **Test** on single file with `--mode single`
4. **Verify** output structure and data integrity
5. **Process** all files with `--mode all`
6. **Integrate** with CSV export pipeline

##  Support

For questions or issues:
- Check **quick_start.md** for common commands
- Review **implementation_summary.md** for technical details
- See **index_sheet_mapping_table.md** for edge case examples
- Examine source code with detailed comments

---

**Last Updated:** 2026-01-16  
**Status:** Implementation Complete   
**Next Phase:** Production Testing & Integration
