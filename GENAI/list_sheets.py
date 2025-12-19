import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
try:
    xl = pd.ExcelFile(file)
    print("Sheets available:")
    for s in xl.sheet_names:
        print(f"  - {s}")
except Exception as e:
    print(f"Error: {e}")
