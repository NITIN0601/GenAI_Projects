import argparse
import os
from run_conversion import convert_pdfs
from extract_from_docx import extract_docx
from download import download_files, get_file_names_to_download


def main():
    parser = argparse.ArgumentParser(description="PDF to Extraction Pipeline")
    parser.add_argument("--step", choices = ["all","convert","extract","summary"], default="all", help="Step to run (default: all)")
    parser.add_argument("--file", nargs='+', help="Specific PDF file(s) to process")
    parser.add_argument("--table", nargs='+', help="Specific Table Title to extract")
    parser.add_argument("--dir", nargs='+', help="Directory for raw PDF files")
    parser.add_argument("--docx-dir", nargs='+', help="Directory for converted DOCX files")
    parser.add_argument("--extract-dir", nargs='+', help="Directory for extracted Excel files")
    parser.add_argument("--output-file", nargs='+', help="Final Output file name")
    parser.add_argument("--m", type=str, choices=["03", "06", "09", "12"], help="Specific month (03, 06, 09, 12)")
    parser.add_argument("--yr", type=str, help="Year or range of years (e.g., 25 or 20-25)")

    args = parser.parse_args()

    # Provide default values if arguments are not provided
    args.dir = args.dir[0] if isinstance(args.dir, list) else args.dir or './raw_data/'
    args.docx_dir = args.docx_dir[0] if isinstance(args.docx_dir, list) else args.docx_dir or './converted_docx/'
    args.extract_dir = args.extract_dir[0] if isinstance(args.extract_dir, list) else args.extract_dir or './extracted_excel/'

    # Ensure raw_data directory exists
    if not os.path.exists(args.dir):
        print(f"Error: Directory {args.dir} does not exist.")
        return

    # Check for specific files or process all PDFs in the directory
    if args.file:
        args.file = [f for f in args.file if os.path.exists(os.path.join(args.dir, f))]
        if not args.file:
            print("Error: None of the specified files exist in the raw_data directory.")
            return
    else:
        args.file = [f for f in os.listdir(args.dir) if f.lower().endswith('.pdf')] 
        if not args.file:
            print("Error: No PDF files found in the raw_data directory.")
            return


    # Base URL to fetch the pdfs
    base_url = "https://www.morganstanley.com/content/dam/msdotcom/en/about-us-ir/shareholder"

    # Step 1: Download files
    if args.yr:
        print("=== Step 1: Downloading Files ===")
        file_names = get_file_names_to_download(base_url, args.m, args.yr)
        download_results = download_files(file_names, base_url, args.dir, timeout=30, max_retries=3)
        
        if download_results['successful']:
            downloaded_pdfs = [f"{fname}.pdf" for fname in download_results['successful']]
            args.file = downloaded_pdfs if not args.file else args.file + downloaded_pdfs
    
    if not args.file:
        args.file = [f for f in os.listdir(args.dir) if f.lower().endswith('.pdf')]
        if not args.file:
            print("Error: No PDF files found in the raw_data directory.")
            return

    
if __name__ == "__main__":
    main()
