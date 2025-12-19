import pandas as pd

file = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/extracted/consolidated_tables.xlsx"
try:
    df_index = pd.read_excel(file, sheet_name="Index")
    print("### INDEX CONTENT (TOP 20)")
    print(df_index[['Table Title', 'Link', 'Sources']].head(20).to_markdown(index=False))
except Exception as e:
    print(f"Error: {e}")
