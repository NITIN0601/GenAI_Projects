import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
title = "Difference Between Contractual Principal and Fair Value"

try:
    df_index = pd.read_excel(file, sheet_name="Index")
    # Get the merged 10-Q one (it has 2 sources)
    merged_match = df_index[df_index['Sources'].str.contains(',', na=False)]
    if merged_match.empty:
        # Fallback to searching by title
        merged_match = df_index[df_index['Table Title'].str.contains(title) & df_index['Sheet Name'].str.contains('Financial', na=False)]
    
    if not merged_match.empty:
        sheet = merged_match.iloc[0]['Link'].replace('→ ', '').strip()
        print(f"SHEET_M_NAME: {sheet}")
        df = pd.read_excel(file, sheet_name=sheet)
        print("\nMERGED TABLE (First 10 rows):")
        print(df.head(10).to_markdown(index=False))
        
    # Get the 10-K one
    k_match = df_index[df_index['Sources'].str.contains('10k', case=False, na=False)]
    if not k_match.empty:
        sheet_k = k_match.iloc[0]['Link'].replace('→ ', '').strip()
        print(f"\nSHEET_K_NAME: {sheet_k}")
        df_k = pd.read_excel(file, sheet_name=sheet_k)
        print("\n10-K TABLE (First 10 rows):")
        print(df_k.head(10).to_markdown(index=False))

except Exception as e:
    print(f"Error: {e}")
