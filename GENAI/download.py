import os
import requests
from requests.exceptions import RequestException
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_file_urls(base_url, year, month=None, file_extension="pdf"):
    """
    Generate file names and URLs based on user input.
    
    IMPORTANT: Handles both 10-Q (quarterly) and 10-K (annual/December) patterns:
    - 10-Q: https://...shareholder/10q0325.pdf (March, June, September)
    - 10-K: https://...shareholder/10k2025/10k1225.pdf (December - annual report)
    
    SPECIAL CASE: Q1 2023 uses 05 instead of 03 (10q0523.pdf)
    
    SMART FILTERING: Only generates URLs for files that should exist based on current date:
    - 10-Q: Available ~45 days after quarter end
    - 10-K: Available ~60 days after year end

    :param base_url: The base URL to append the file names to.
    :param year: The year input as a two-digit string (e.g., "25").
    :param month: The month input as a two-digit string (e.g., "03"). If None, generate for all valid months.
    :param file_extension: The file extension (default is "pdf").
    :return: A list of full URLs with the generated file names.
    """
    from datetime import datetime, timedelta
    
    try:
        # Validate the year
        if not (0 <= int(year) <= 99):
            raise ValueError("Invalid year. Must be a two-digit number.")

        # Define valid months
        valid_months = ["03", "06", "09", "12"]

        # If no month is provided, generate for all valid months
        if month is None:
            months_to_generate = valid_months
        else:
            # Validate the month
            if month not in valid_months:
                raise ValueError(f"Invalid month. Must be one of {valid_months}.")
            months_to_generate = [month]

        # Get current date for smart filtering
        now = datetime.now()
        
        # Generate file names and URLs
        urls = []
        for m in months_to_generate:
            year_padded = year.zfill(2)
            full_year = f"20{year_padded}"  # Convert 25 → 2025
            
            # Determine filing availability date
            # 10-Q: Available ~45 days after quarter end
            # 10-K: Available ~60 days after year end
            if m == "03":  # Q1 ends March 31
                filing_available_date = datetime(int(full_year), 3, 31) + timedelta(days=45)
            elif m == "06":  # Q2 ends June 30
                filing_available_date = datetime(int(full_year), 6, 30) + timedelta(days=45)
            elif m == "09":  # Q3 ends September 30
                filing_available_date = datetime(int(full_year), 9, 30) + timedelta(days=45)
            elif m == "12":  # Year ends December 31, 10-K available ~60 days later
                filing_available_date = datetime(int(full_year), 12, 31) + timedelta(days=60)
            
            # Skip if file shouldn't exist yet
            if now < filing_available_date:
                logger.info(f"⏭️  Skipping {m}/{year_padded} - Not available until {filing_available_date.strftime('%Y-%m-%d')}")
                continue
            
            # SPECIAL CASE: Q1 2023 uses 05 instead of 03
            if m == "03" and year_padded == "23":
                file_name = f"10q05{year_padded}"  # 10q0523 instead of 10q0323
                full_url = f"{base_url}/{file_name}.{file_extension}"
            # December = 10-K (annual report) with special directory structure
            elif m == "12":
                # 10-K pattern: /10k2025/10k1225.pdf
                file_name = f"10k{m}{year_padded}"
                full_url = f"{base_url}/10k{full_year}/{file_name}.{file_extension}"
            else:
                # 10-Q pattern: /10q0325.pdf (no extra directory)
                file_name = f"10q{m}{year_padded}"
                full_url = f"{base_url}/{file_name}.{file_extension}"
            
            urls.append(full_url)

        return urls
    except Exception as e:
        raise ValueError(f"Error generating file URLs: {e}")



def get_file_names_to_download(base_url, month, yr):
    """
    Returns a list of full URLs to download based on month and year/range.
    
    :param base_url: The base URL to append the file names to.
    :param month: Month as string (e.g., "03") or None for all valid months.
    :param yr: Year as string (e.g., "25") or range (e.g., "20-25").
    :return: List of full URLs
    """
    if yr is None:
        raise ValueError("Year (--yr) argument is required.")
    
    # Parse year input
    if "-" in yr:
        start_year, end_year = map(int, yr.split("-"))
        years = [str(y).zfill(2) for y in range(start_year, end_year + 1)]
    else:
        years = [yr.zfill(2)]
    
    # Generate file URLs for all years
    file_urls = []
    for year in years:
        file_urls.extend(generate_file_urls(base_url, year, month=month))
    
    return file_urls



def _download_single_file(full_url, download_dir, timeout, max_retries):
    """
    Download a single file with progress bar (helper function for parallel processing).
    
    Args:
        full_url: Complete URL to download from
        download_dir: Directory to save file to
        timeout: Request timeout in seconds
        max_retries: Number of retry attempts
    
    Returns:
        tuple: (file_name, success: bool, error_message: str or None, file_size: int)
    """
    # Extract filename from URL
    file_name = full_url.split("/")[-1].replace(".pdf", "")
    local_path = os.path.join(download_dir, f"{file_name}.pdf")
    
    # Skip if file already exists
    if os.path.exists(local_path):
        file_size = os.path.getsize(local_path)
        if file_size > 0:  # Valid file exists
            logger.info(f"⚡ {file_name}.pdf - Already exists ({file_size / 1024 / 1024:.2f} MB)")
            return (file_name, True, "Already exists (skipped)", file_size)
    
    attempt = 0
    
    while attempt < max_retries:
        attempt += 1
        try:
            # Add headers to mimic a browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            logger.info(f"📥 Downloading {file_name}.pdf (attempt {attempt}/{max_retries})...")
            
            # Get file size first
            response = requests.get(full_url, stream=True, timeout=timeout, headers=headers)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress bar
            with open(local_path, 'wb') as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"{file_name}.pdf",
                    ncols=100,
                    bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            file_size = os.path.getsize(local_path)
            logger.info(f"✓ {file_name}.pdf - Downloaded successfully ({file_size / 1024 / 1024:.2f} MB)")
            return (file_name, True, None, file_size)
            
        except RequestException as e:
            if attempt == max_retries:
                logger.error(f"✗ {file_name}.pdf - Failed after {max_retries} attempts: {e}")
                return (file_name, False, f"Failed after {max_retries} attempts: {e}", 0)
            logger.warning(f"⚠ {file_name}.pdf - Attempt {attempt} failed, retrying...")
                
        except IOError as e:
            logger.error(f"✗ {file_name}.pdf - Error writing file: {e}")
            return (file_name, False, f"Error writing file: {e}", 0)
    
    return (file_name, False, "Unknown error", 0)




def download_files(file_urls, download_dir='./raw_data', timeout=30, max_retries=3, max_workers=5):
    """
    Downloads a list of files in parallel using batch processing with progress bars.
    
    OPTIMIZED: Uses ThreadPoolExecutor for parallel downloads (5-10x faster!)

    Args:
        file_urls (list): A list of full URLs to download.
        download_dir (str): The local directory to save files in. Defaults to './raw_data'.
        timeout (int): Timeout in seconds for each request (default: 30).
        max_retries (int): Number of retries for each file (default: 3).
        max_workers (int): Number of parallel download threads (default: 5).
    
    Returns:
        dict: Summary with 'successful', 'failed', 'downloaded', 'skipped' file lists and total_size.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Ensure the download directory exists
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logger.info(f"Created directory: {download_dir}")

    successful = []
    failed = []
    skipped = []
    total_size = 0
    
    logger.info("="*70)
    logger.info(f"Starting parallel download of {len(file_urls)} files...")
    logger.info(f"Max parallel workers: {max_workers}")
    logger.info("="*70)

    # Use ThreadPoolExecutor for parallel downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks
        future_to_url = {
            executor.submit(
                _download_single_file, 
                url, 
                download_dir, 
                timeout, 
                max_retries
            ): url 
            for url in file_urls
        }
        
        # Process completed downloads
        for future in as_completed(future_to_url):
            file_name, success, error_msg, file_size = future.result()
            total_size += file_size
            
            if success:
                if error_msg == "Already exists (skipped)":
                    skipped.append(file_name)
                else:
                    successful.append(file_name)
            else:
                failed.append(file_name)

    # Print summary
    logger.info("="*70)
    logger.info("Download Summary:")
    logger.info(f"  Downloaded: {len(successful)}/{len(file_urls)}")
    logger.info(f"  Skipped (exists): {len(skipped)}/{len(file_urls)}")
    logger.info(f"  Failed: {len(failed)}/{len(file_urls)}")
    logger.info(f"  Total Size: {total_size / 1024 / 1024:.2f} MB")
    if failed:
        logger.warning(f"  Failed files: {', '.join(failed)}")
    logger.info("="*70)
    
    return {
        'successful': successful + skipped,  # Include skipped as successful
        'failed': failed,
        'downloaded': successful,
        'skipped': skipped,
        'total_size': total_size
    }