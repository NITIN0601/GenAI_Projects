# Quick Start Guide: Index Sheet Re-sequencer

## What This Does

Re-sequences xlsx Index sheets and physically splits multi-table sheets based on unique (Section + Table Title) combinations.

## Quick Commands

### 1️⃣ Analyze First (Recommended)
See what will be changed without modifying files:

```bash
cd .
python3 scripts/test_index_resequencer.py --mode analyze --file data/processed/10q0925_tables.xlsx
```

**Output shows:**
- How many unique (Section, Title) combinations exist
- Which groups have multiple entries (need splitting)
- Sample table block detection results

### 2️⃣ Test on Single File
Process one file to verify results:

```bash
python3 scripts/test_index_resequencer.py --mode single --file data/processed/10q0925_tables.xlsx
```

**Output:** `data/processed/test_output/10q0925_tables.xlsx`

### 3️⃣ Batch Process All Files
Process all xlsx files in the directory:

```bash
python3 scripts/test_index_resequencer.py --mode all --dir data/processed
```

**Output:** `data/processed/test_output/*.xlsx`

## What Gets Changed

### Before:
```
Index Sheet:
Row 1: Section A | Title X | → 2
Row 2: Section A | Title X | → 2  (duplicate pointing to same sheet)
Row 3: Section A | Title X | → 2  (duplicate pointing to same sheet)
Row 4: Section B | Title Y | → 3

Sheet 2: Contains 3 sub-tables stacked vertically
Sheet 3: Contains 1 table
```

### After:
```
Index Sheet:
Row 1: Section A | Title X | → 2
Row 2: Section A | Title X | → 2_1
Row 3: Section A | Title X | → 2_2
Row 4: Section B | Title Y | → 3

Sheet 2:   Contains sub-table 1 only
Sheet 2_1: Contains sub-table 2 only (NEW)
Sheet 2_2: Contains sub-table 3 only (NEW)
Sheet 3:   Contains 1 table (unchanged)
```

## Expected Results

For `10q0925_tables.xlsx`:
- **235 Index entries** → **160 unique groups**
- Creates **75 new sheets** through splitting
- **47 groups** have multiple entries (need splitting/consolidation)

## Verification Steps

After processing, check:

1. **Index Sheet:** 
   - Link column shows sequential IDs with `_n` suffixes
   - No gaps in numbering

2. **Data Sheets:**
   - Each sheet has only one table
   - Metadata preserved
   - "← Back to Index" link present

3. **Sheet Count:**
   - Should match total Index entries (235 for 10q0925)

## Troubleshooting

### Command not found: python
Use `python3` instead:
```bash
python3 scripts/test_index_resequencer.py ...
```

### File not found
Make sure you're in the  directory:
```bash
cd .
pwd  # Should show: /path/to/project/root
```

### Output directory doesn't exist
The script creates it automatically. Check `data/processed/test_output/`

## File Locations

- **Planning Doc:** `req_update/index_sheet_mapping/index_sheet_mapping_table.md`
- **Implementation:** `src/index_sheet_resequencer.py`
- **Test Script:** `scripts/test_index_resequencer.py` 
- **Summary:** `req_update/index_sheet_mapping/implementation_summary.md`
- **Input Files:** `data/processed/*.xlsx`
- **Output Files:** `data/processed/test_output/*.xlsx`

## Next Steps After Processing

1. Review output files in `data/processed/test_output/`
2. Compare Index sheets (before/after)
3. Verify a few randomly selected data sheets
4. If satisfied, process all 4 files
5. Update CSV export pipeline to use re-sequenced files
