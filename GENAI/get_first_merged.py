import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
try:
    # Read Index to find the sheet name for the merged entry
    df_index = pd.read_excel(file, sheet_name="Index")
    merged_rows = df_index[df_index['Sources'].str.contains(',', na=False)]
    
    for _, row in merged_rows.head(1).iterrows():
        title = row['Table Title']
        # The sheet name is in the 'Link' column but might have an arrow
        sheet = str(row['Link']).replace('→ ', '').strip()
        # But wait, 'Link' is the hyperlink text, the actual sheet name might be truncated.
        # Let's find a sheet that starts with the same characters.
        xl = pd.ExcelFile(file)
        actual_sheet = None
        for s in xl.sheet_names:
            if s.startswith(sheet[:10]):
                actual_sheet = s
                break
        
        if actual_sheet:
            print(f"### Sample Merged Table: {title}")
            df = pd.read_excel(file, sheet_name=actual_sheet)
            print(df.head(15).to_markdown(index=False))
            
except Exception as e:
    print(f"Error: {e}")
