import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
try:
    xl = pd.ExcelFile(file)
    target = "Accrued Interest"
    for s in xl.sheet_names:
        if s.startswith("Accrued Interest"):
            df = pd.read_excel(file, sheet_name=s)
            # Check if it has multiple data columns (more than 2: Row Label + data)
            if len(df.columns) > 2:
                print(f"### SAMPLE MERGED TABLE: {s}")
                print(df.head(15).to_markdown(index=False))
                break
except Exception as e:
    print(f"Error: {e}")
