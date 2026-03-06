#!/usr/bin/env python3
"""
Goodreads Review Scraper - Interactive TUI Version
Fetches ALL reviews from any Goodreads book URL with live progress

Usage:
  Interactive:  ./scraper_tui.py
  CLI:          ./scraper_tui.py --url <goodreads_url> [--type json|jsonl|csv|xml]
"""

import argparse
import requests
import json
import csv
import time
import re
import sys
import os
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Output formats
OUTPUT_FORMATS = {
    '1': ('JSON', 'json', 'Standard JSON format - good for APIs and JavaScript'),
    '2': ('JSONL', 'jsonl', 'JSON Lines - one review per line, great for streaming/big data'),
    '3': ('CSV', 'csv', 'Comma-separated values - opens in Excel/spreadsheets'),
    '4': ('XML', 'xml', 'Extensible Markup Language - structured and verbose'),
}

# Base output directory
DATASETS_DIR = Path("datasets")

# GraphQL endpoint
GRAPHQL_URL = "https://kxbwmqov6jgg3daaamb744ycu4.appsync-api.us-east-1.amazonaws.com/graphql"

# Headers for GraphQL requests
GRAPHQL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.goodreads.com/",
    "Content-Type": "application/json",
    "x-api-key": "da2-xpgsdydkbregjhpr6ejzqdhuwy",
    "Origin": "https://www.goodreads.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# Headers for page fetching
PAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
}

# GraphQL query
GRAPHQL_QUERY = """
query getReviews($filters: BookReviewsFilterInput!, $pagination: PaginationInput) {
  getReviews(filters: $filters, pagination: $pagination) {
    ...BookReviewsFragment
    __typename
  }
}

fragment BookReviewsFragment on BookReviewsConnection {
  totalCount
  edges {
    node {
      ...ReviewCardFragment
      __typename
    }
    __typename
  }
  pageInfo {
    prevPageToken
    nextPageToken
    __typename
  }
  __typename
}

fragment ReviewCardFragment on Review {
  __typename
  id
  creator {
    ...ReviewerProfileFragment
    __typename
  }
  updatedAt
  createdAt
  spoilerStatus
  lastRevisionAt
  text
  rating
  shelving {
    taggings {
      tag {
        name
        webUrl
        __typename
      }
      __typename
    }
    __typename
  }
  likeCount
  commentCount
}

fragment ReviewerProfileFragment on User {
  id: legacyId
  imageUrlSquare
  isAuthor
  followersCount
  textReviewsCount
  name
  webUrl
  __typename
}
"""


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header():
    """Print the application header."""
    print("\033[1;36m" + "=" * 60 + "\033[0m")
    print("\033[1;36m       📚 GOODREADS REVIEW SCRAPER 📚\033[0m")
    print("\033[1;36m" + "=" * 60 + "\033[0m")
    print()


def print_separator():
    """Print a separator line."""
    print("\033[90m" + "-" * 60 + "\033[0m")


def get_book_info_from_url(goodreads_url: str) -> dict:
    """
    Extract book info and resource ID from a Goodreads book URL.
    
    Returns dict with: resource_id, title, author, rating, ratings_count, reviews_count
    """
    print("\033[33m⏳ Fetching book information...\033[0m")
    
    response = requests.get(goodreads_url, headers=PAGE_HEADERS, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find __NEXT_DATA__ script tag
    next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
    if not next_data_script:
        raise ValueError('Could not find page data. Is this a valid Goodreads book URL?')
    
    data = json.loads(next_data_script.string)
    apollo_state = data['props']['pageProps']['apolloState']
    
    # Find resource ID
    resource_id = None
    book_data = None
    work_data = None
    
    for key, value in apollo_state.items():
        if key.startswith('Work:kca://work/'):
            resource_id = key.replace('Work:', '')
            work_data = value
        if key.startswith('Book:kca://book/') and isinstance(value, dict):
            if 'title' in value:
                book_data = value
    
    if not resource_id:
        raise ValueError('Could not find work resource ID in page data')
    
    # Extract book info
    info = {
        'resource_id': resource_id,
        'url': goodreads_url,
        'title': 'Unknown',
        'author': 'Unknown',
        'rating': None,
        'ratings_count': 0,
        'reviews_count': 0,
    }
    
    if book_data:
        info['title'] = book_data.get('title', 'Unknown')
    
    if work_data:
        stats = work_data.get('stats', {})
        if isinstance(stats, dict):
            info['rating'] = stats.get('averageRating')
            info['ratings_count'] = stats.get('ratingsCount', 0)
            info['reviews_count'] = stats.get('textReviewsCount', 0)
    
    # Try to get author from page
    for key, value in apollo_state.items():
        if key.startswith('Contributor:') and isinstance(value, dict):
            if value.get('name'):
                info['author'] = value.get('name')
                break
    
    return info


def display_book_info(info: dict):
    """Display book information in a nice format."""
    print()
    print("\033[1;32m✓ Book found!\033[0m")
    print()
    print(f"  \033[1mTitle:\033[0m  {info['title']}")
    print(f"  \033[1mAuthor:\033[0m {info['author']}")
    if info['rating']:
        stars = "★" * int(round(info['rating'])) + "☆" * (5 - int(round(info['rating'])))
        print(f"  \033[1mRating:\033[0m {info['rating']:.2f}/5 {stars}")
    print(f"  \033[1mTotal Ratings:\033[0m  {info['ratings_count']:,}")
    print(f"  \033[1mTotal Reviews:\033[0m  {info['reviews_count']:,}")
    print()


def clean_html_text(text: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Remove Unicode line/paragraph separators (problematic on Linux)
    clean = clean.replace('\u2028', ' ').replace('\u2029', ' ')
    return clean


def sanitize_text(text: str) -> str:
    """Remove problematic Unicode characters from text while preserving content."""
    if not text:
        return ""
    # Replace Unicode line separator (LS) and paragraph separator (PS)
    return text.replace('\u2028', '\n').replace('\u2029', '\n\n')


def transform_review(node: dict) -> dict:
    """Transform raw API response into clean review data."""
    creator = node.get("creator", {}) or {}
    shelving = node.get("shelving", {}) or {}
    taggings = shelving.get("taggings", []) or []
    
    raw_text = node.get("text", "")
    
    return {
        "reviewer": {
            "id": creator.get("id"),
            "name": creator.get("name"),
            "profile_url": creator.get("webUrl"),
            "image_url": creator.get("imageUrlSquare"),
            "is_author": creator.get("isAuthor"),
            "reviews_count": creator.get("textReviewsCount"),
            "followers_count": creator.get("followersCount"),
        },
        "rating": node.get("rating"),
        "review": {
            "id": node.get("id"),
            "text": clean_html_text(raw_text),
            "text_raw": sanitize_text(raw_text),
            "is_spoiler": node.get("spoilerStatus"),
            "created_at": node.get("createdAt"),
            "updated_at": node.get("updatedAt"),
            "tags": [t.get("tag", {}).get("name") for t in taggings if t.get("tag")],
        },
        "engagement": {
            "likes": node.get("likeCount"),
            "comments": node.get("commentCount"),
        }
    }


def fetch_reviews_page(resource_id: str, pagination_token: str = None, limit: int = 30) -> dict:
    """Fetch a single page of reviews from the GraphQL API."""
    payload = {
        "operationName": "getReviews",
        "variables": {
            "filters": {
                "resourceType": "WORK",
                "resourceId": resource_id
            },
            "pagination": {
                "limit": limit
            }
        },
        "query": GRAPHQL_QUERY
    }
    
    if pagination_token:
        payload["variables"]["pagination"]["after"] = pagination_token
    
    response = requests.post(GRAPHQL_URL, headers=GRAPHQL_HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    
    return response.json()


def scrape_reviews_streaming(book_info: dict, output_file: Path, output_format: str, delay: float = 0.3):
    """
    Scrape all reviews and write to file incrementally.
    
    Supports: json, jsonl, csv, xml
    """
    resource_id = book_info['resource_id']
    
    # Initialize file based on format
    if output_format == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('{\n')
            f.write('  "metadata": {\n')
            f.write(f'    "title": {json.dumps(book_info["title"])},\n')
            f.write(f'    "author": {json.dumps(book_info["author"])},\n')
            f.write(f'    "url": {json.dumps(book_info["url"])},\n')
            f.write(f'    "resource_id": {json.dumps(resource_id)},\n')
            f.write(f'    "scraped_at": {json.dumps(datetime.now().isoformat())}\n')
            f.write('  },\n')
            f.write('  "reviews": [\n')
    elif output_format == 'jsonl':
        # Write metadata as first line
        with open(output_file, 'w', encoding='utf-8') as f:
            metadata = {
                "_type": "metadata",
                "title": book_info["title"],
                "author": book_info["author"],
                "url": book_info["url"],
                "resource_id": resource_id,
                "scraped_at": datetime.now().isoformat()
            }
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
    elif output_format == 'csv':
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'reviewer_id', 'reviewer_name', 'reviewer_url', 'is_author',
                'reviews_count', 'followers_count', 'rating', 'review_id',
                'review_text', 'is_spoiler', 'created_at', 'updated_at',
                'tags', 'likes', 'comments'
            ])
    elif output_format == 'xml':
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<reviews_data>\n')
            f.write('  <metadata>\n')
            f.write(f'    <title>{_xml_escape(book_info["title"])}</title>\n')
            f.write(f'    <author>{_xml_escape(book_info["author"])}</author>\n')
            f.write(f'    <url>{_xml_escape(book_info["url"])}</url>\n')
            f.write(f'    <resource_id>{_xml_escape(resource_id)}</resource_id>\n')
            f.write(f'    <scraped_at>{datetime.now().isoformat()}</scraped_at>\n')
            f.write('  </metadata>\n')
            f.write('  <reviews>\n')
    
    next_token = None
    page = 0
    total_fetched = 0
    total_available = book_info.get('reviews_count', 0)
    first_review = True
    start_time = time.time()
    
    # Stats for summary
    ratings = []
    total_likes = 0
    total_comments = 0
    
    print("\033[1;33m📥 Starting download...\033[0m")
    print()
    
    try:
        while True:
            page += 1
            
            # Fetch page
            try:
                result = fetch_reviews_page(resource_id, next_token)
            except requests.RequestException as e:
                print(f"\n\033[31m✗ Error on page {page}: {e}\033[0m")
                break
            
            reviews_data = result.get("data", {}).get("getReviews", {})
            
            # Update total if we get it from API
            api_total = reviews_data.get("totalCount", 0)
            if api_total > 0:
                total_available = api_total
            
            edges = reviews_data.get("edges", [])
            
            if not edges:
                break
            
            # Process reviews
            reviews_batch = []
            for edge in edges:
                node = edge.get("node", {})
                if node:
                    review = transform_review(node)
                    reviews_batch.append(review)
                    
                    # Collect stats
                    if review['rating']:
                        ratings.append(review['rating'])
                    total_likes += review['engagement']['likes'] or 0
                    total_comments += review['engagement']['comments'] or 0
            
            # Write batch based on format
            _write_reviews_batch(output_file, reviews_batch, output_format, first_review)
            if first_review and reviews_batch:
                first_review = False
            
            total_fetched += len(reviews_batch)
            
            # Progress display with ETA
            if total_available > 0:
                pct = (total_fetched / total_available) * 100
                bar_width = 30
                filled = int(bar_width * total_fetched / total_available)
                bar = "█" * filled + "░" * (bar_width - filled)
                
                # Calculate ETA
                elapsed = time.time() - start_time
                if total_fetched > 0:
                    rate = total_fetched / elapsed  # reviews per second
                    remaining = total_available - total_fetched
                    eta_seconds = remaining / rate if rate > 0 else 0
                    
                    if eta_seconds < 60:
                        eta_str = f"{int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                    else:
                        eta_str = f"{int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
                else:
                    eta_str = "..."
                
                print(f"\r  \033[1m[{bar}]\033[0m {pct:5.1f}% | {total_fetched:,}/{total_available:,} | Page {page} | ETA: {eta_str}  ", end="", flush=True)
            else:
                print(f"\r  Fetched {total_fetched:,} reviews | Page {page}", end="", flush=True)
            
            # Check for next page
            page_info = reviews_data.get("pageInfo", {})
            next_token = page_info.get("nextPageToken")
            
            if not next_token:
                break
            
            time.sleep(delay)
    
    except KeyboardInterrupt:
        print("\n\n\033[33m⚠ Interrupted by user. Saving progress...\033[0m")
    
    # Close file based on format
    _close_output_file(output_file, output_format)
    
    print()
    print()
    print_separator()
    print(f"\033[1;32m✓ Download complete!\033[0m")
    print()
    print(f"  \033[1mReviews saved:\033[0m {total_fetched:,}")
    print(f"  \033[1mOutput file:\033[0m   {output_file}")
    
    # Show stats
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        print()
        print(f"  \033[1mAverage rating:\033[0m {avg_rating:.2f}/5")
        print(f"  \033[1mTotal likes:\033[0m    {total_likes:,}")
        print(f"  \033[1mTotal comments:\033[0m {total_comments:,}")
        print()
        print("  \033[1mRating distribution:\033[0m")
        for star in range(5, 0, -1):
            count = sum(1 for r in ratings if r == star)
            pct = (count / len(ratings)) * 100
            bar = "█" * int(pct / 2)
            print(f"    {star}★: {count:4} ({pct:5.1f}%) \033[33m{bar}\033[0m")
    
    return total_fetched


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def _write_reviews_batch(output_file: Path, reviews: list, output_format: str, is_first: bool):
    """Write a batch of reviews to file in the specified format."""
    if not reviews:
        return
    
    if output_format == 'json':
        with open(output_file, 'a', encoding='utf-8') as f:
            for i, review in enumerate(reviews):
                if not (is_first and i == 0):
                    f.write(',\n')
                # Pretty-print each review with proper indentation
                review_json = json.dumps(review, ensure_ascii=False, indent=6)
                # Indent the whole block by 4 spaces (inside "reviews" array)
                indented = '    ' + review_json.replace('\n', '\n    ')
                f.write(indented)
    
    elif output_format == 'jsonl':
        with open(output_file, 'a', encoding='utf-8') as f:
            for review in reviews:
                f.write(json.dumps(review, ensure_ascii=False) + '\n')
    
    elif output_format == 'csv':
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for review in reviews:
                writer.writerow([
                    review['reviewer']['id'],
                    review['reviewer']['name'],
                    review['reviewer']['profile_url'],
                    review['reviewer']['is_author'],
                    review['reviewer']['reviews_count'],
                    review['reviewer']['followers_count'],
                    review['rating'],
                    review['review']['id'],
                    review['review']['text'],
                    review['review']['is_spoiler'],
                    review['review']['created_at'],
                    review['review']['updated_at'],
                    '|'.join(review['review']['tags']) if review['review']['tags'] else '',
                    review['engagement']['likes'],
                    review['engagement']['comments']
                ])
    
    elif output_format == 'xml':
        with open(output_file, 'a', encoding='utf-8') as f:
            for review in reviews:
                f.write('    <review>\n')
                f.write('      <reviewer>\n')
                f.write(f'        <id>{review["reviewer"]["id"] or ""}</id>\n')
                f.write(f'        <name>{_xml_escape(review["reviewer"]["name"] or "")}</name>\n')
                f.write(f'        <profile_url>{_xml_escape(review["reviewer"]["profile_url"] or "")}</profile_url>\n')
                f.write(f'        <is_author>{review["reviewer"]["is_author"] or False}</is_author>\n')
                f.write(f'        <reviews_count>{review["reviewer"]["reviews_count"] or 0}</reviews_count>\n')
                f.write(f'        <followers_count>{review["reviewer"]["followers_count"] or 0}</followers_count>\n')
                f.write('      </reviewer>\n')
                f.write(f'      <rating>{review["rating"] or 0}</rating>\n')
                f.write('      <review_content>\n')
                f.write(f'        <id>{_xml_escape(review["review"]["id"] or "")}</id>\n')
                f.write(f'        <text>{_xml_escape(review["review"]["text"] or "")}</text>\n')
                f.write(f'        <is_spoiler>{review["review"]["is_spoiler"] or False}</is_spoiler>\n')
                f.write(f'        <created_at>{review["review"]["created_at"] or ""}</created_at>\n')
                f.write(f'        <updated_at>{review["review"]["updated_at"] or ""}</updated_at>\n')
                f.write('        <tags>\n')
                for tag in (review['review']['tags'] or []):
                    f.write(f'          <tag>{_xml_escape(tag)}</tag>\n')
                f.write('        </tags>\n')
                f.write('      </review_content>\n')
                f.write('      <engagement>\n')
                f.write(f'        <likes>{review["engagement"]["likes"] or 0}</likes>\n')
                f.write(f'        <comments>{review["engagement"]["comments"] or 0}</comments>\n')
                f.write('      </engagement>\n')
                f.write('    </review>\n')


def _close_output_file(output_file: Path, output_format: str):
    """Close the output file with proper ending."""
    if output_format == 'json':
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write('\n  ]\n')
            f.write('}\n')
    elif output_format == 'xml':
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write('  </reviews>\n')
            f.write('</reviews_data>\n')
    # JSONL and CSV don't need closing


def select_output_format() -> tuple[str, str]:
    """Display format selection menu and return (format_name, extension)."""
    print("\033[1mSelect output format:\033[0m")
    print()
    for key, (name, ext, desc) in OUTPUT_FORMATS.items():
        print(f"  \033[1m{key}.\033[0m {name:6} (.{ext:5}) - {desc}")
    print()
    
    try:
        choice = input("\033[1m→ Choice [1]: \033[0m").strip() or '1'
    except (KeyboardInterrupt, EOFError):
        return None, None
    
    if choice not in OUTPUT_FORMATS:
        print("\033[33m⚠ Invalid choice, defaulting to JSON\033[0m")
        choice = '1'
    
    name, ext, _ = OUTPUT_FORMATS[choice]
    return name, ext


def run_cli(url: str, output_type: str):
    """Run the scraper in non-interactive CLI mode."""
    print_header()
    
    # Validate URL format
    if 'goodreads.com/book/show/' not in url:
        print("\033[31m✗ Invalid URL. Please provide a Goodreads book URL.\033[0m")
        return 1
    
    # Validate output type
    valid_types = {v[1]: v[0] for v in OUTPUT_FORMATS.values()}  # ext -> name mapping
    if output_type not in valid_types:
        print(f"\033[31m✗ Invalid type '{output_type}'. Valid options: {', '.join(valid_types.keys())}\033[0m")
        return 1
    
    format_name = valid_types[output_type]
    format_ext = output_type
    
    print_separator()
    
    # Fetch book info
    try:
        book_info = get_book_info_from_url(url)
    except Exception as e:
        print(f"\033[31m✗ Error fetching book info: {e}\033[0m")
        return 1
    
    display_book_info(book_info)
    print_separator()
    
    # Create output directory structure: datasets/<book_title>/
    safe_title = re.sub(r'[^\w\s-]', '', book_info['title'])[:50].strip()
    safe_title = re.sub(r'\s+', '_', safe_title)
    book_dir = DATASETS_DIR / safe_title
    book_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = book_dir / f"reviews_{timestamp}.{format_ext}"
    
    print()
    print(f"Output format: \033[1m{format_name}\033[0m")
    print(f"Output file:   \033[1m{output_file}\033[0m")
    print()
    print_separator()
    print()
    
    # Scrape!
    try:
        total = scrape_reviews_streaming(book_info, output_file, format_ext, delay=0.3)
    except Exception as e:
        print(f"\n\033[31m✗ Error during scraping: {e}\033[0m")
        return 1
    
    print()
    print_separator()
    print("\033[1;36m🎉 All done! Happy analyzing!\033[0m")
    print()
    
    return 0


def main():
    """Main entry point with TUI."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Goodreads Review Scraper - Fetch all reviews from any Goodreads book',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Interactive mode:
    ./scraper_tui.py
  
  CLI mode:
    ./scraper_tui.py --url https://www.goodreads.com/book/show/88077.The_Magic_Mountain
    ./scraper_tui.py --url https://www.goodreads.com/book/show/88077 --type csv
'''
    )
    parser.add_argument('--url', type=str, help='Goodreads book URL to scrape')
    parser.add_argument('--type', type=str, default='json', 
                        choices=['json', 'jsonl', 'csv', 'xml'],
                        help='Output format (default: json)')
    
    args = parser.parse_args()
    
    # If URL provided via CLI, run non-interactive mode
    if args.url:
        return run_cli(args.url, args.type)
    
    # Otherwise, run interactive TUI
    clear_screen()
    print_header()
    
    # Get URL from user
    print("Enter a Goodreads book URL to scrape reviews:")
    print("\033[90m(Example: https://www.goodreads.com/book/show/88077.The_Magic_Mountain)\033[0m")
    print()
    
    try:
        url = input("\033[1m→ URL: \033[0m").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n\n\033[33mGoodbye!\033[0m")
        return 0
    
    if not url:
        print("\033[31m✗ No URL provided.\033[0m")
        return 1
    
    # Validate URL format
    if 'goodreads.com/book/show/' not in url:
        print("\033[31m✗ Invalid URL. Please provide a Goodreads book URL.\033[0m")
        return 1
    
    print()
    print_separator()
    
    # Fetch book info
    try:
        book_info = get_book_info_from_url(url)
    except Exception as e:
        print(f"\033[31m✗ Error fetching book info: {e}\033[0m")
        return 1
    
    display_book_info(book_info)
    print_separator()
    
    # Select output format
    print()
    format_name, format_ext = select_output_format()
    if format_name is None:
        print("\n\n\033[33mCancelled.\033[0m")
        return 0
    
    print()
    print_separator()
    print()
    
    # Create output directory structure: datasets/<book_title>/
    safe_title = re.sub(r'[^\w\s-]', '', book_info['title'])[:50].strip()
    safe_title = re.sub(r'\s+', '_', safe_title)
    book_dir = DATASETS_DIR / safe_title
    book_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = book_dir / f"reviews_{timestamp}.{format_ext}"
    
    print(f"Output format: \033[1m{format_name}\033[0m")
    print(f"Output file:   \033[1m{output_file}\033[0m")
    print()
    
    # Confirm
    try:
        confirm = input("Start scraping? [\033[1mY\033[0m/n]: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n\n\033[33mCancelled.\033[0m")
        return 0
    
    if confirm and confirm != 'y':
        print("\033[33mCancelled.\033[0m")
        return 0
    
    print()
    print_separator()
    print()
    
    # Scrape!
    try:
        total = scrape_reviews_streaming(book_info, output_file, format_ext, delay=0.3)
    except Exception as e:
        print(f"\n\033[31m✗ Error during scraping: {e}\033[0m")
        return 1
    
    print()
    print_separator()
    print("\033[1;36m🎉 All done! Happy analyzing!\033[0m")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
