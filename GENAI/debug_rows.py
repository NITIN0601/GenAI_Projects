import pandas as pd
import re

p1 = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/processed/10q0624_tables.xlsx"
p2 = "/Users/nitin/Desktop/Chatbot/Morgan/GENAI/data/processed/10q0325_tables.xlsx"
title = "Difference Between Contractual Principal and Fair Value"

def normalize(label):
    if not label: return ""
    label = str(label).strip()
    label = re.sub(r'[\(\[\{]\d+[\)\]\}]', ' ', label)
    label = re.sub(r'\*+', ' ', label)
    label = re.sub(r'[:\.]$', '', label)
    label = re.sub(r'\s+', ' ', label)
    return label.lower().strip()

def get_sig(path):
    idx = pd.read_excel(path, sheet_name="Index")
    match = idx[idx['Table Title'].str.contains(title, case=False, na=False)]
    if match.empty: return None
    sheet = str(match.iloc[0]['Link']).replace('→ ', '').strip()
    df = pd.read_excel(path, sheet_name=sheet, header=None).iloc[2:]
    
    norm_rows = []
    for r in df.iloc[:, 0].tolist():
        r_clean = str(r).strip()
        if not r_clean or r_clean.lower() == 'nan': continue
        r_lower = r_clean.lower()
        if r_lower == 'row label': continue
        if r_lower.startswith('source:'): continue
        if r_lower.startswith('page '): continue
        if r_lower.startswith('$ in'): continue
        norm_rows.append(normalize(r_clean))
    return "|".join(norm_rows)

s1 = get_sig(p1)
s2 = get_sig(p2)

if s1 == s2:
    print("SUCCESS: Row signatures match!")
    print(f"Signature: {s1[:100]}...")
else:
    print("FAILURE: Signatures still differ!")
    print(f"S1: {s1[:100]}...")
    print(f"S2: {s2[:100]}...")
