#!/usr/bin/env python3
"""
Final NCSL 2025 Summit Session Scraper with deduplication
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FinalNCSLScraper:
    def __init__(self):
        self.base_url = "https://www.ncsl.org/events/2025-ncsl-legislative-summit/agenda"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.seen_sessions = set()  # For deduplication
        
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        text = ' '.join(text.split())
        text = re.sub(r'[\xa0\u200b\u200c\u200d\ufeff]', ' ', text)
        return text.strip()
    
    def parse_time_location(self, text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse date, time, and location from text"""
        date = None
        time = None
        location = ""
        
        if '|' in text:
            parts = text.split('|', 1)
            date_str = parts[0].strip()
            time_location = parts[1].strip() if len(parts) > 1 else ""
            
            # Convert date patterns
            date_map = {
                'Saturday, Aug. 2': '2025-08-02',
                'Sunday, Aug. 3': '2025-08-03',
                'Monday, Aug. 4': '2025-08-04',
                'Tuesday, Aug. 5': '2025-08-05',
                'Wednesday, Aug. 6': '2025-08-06'
            }
            date = date_map.get(date_str, date_str)
            
            # Extract time and location
            time_match = re.match(r'(\d{1,2}:\d{2}\s*[ap]m\s*-\s*\d{1,2}:\d{2}\s*[ap]m)(.*)', time_location, re.IGNORECASE)
            if time_match:
                time = time_match.group(1).strip()
                location = time_match.group(2).strip()
            else:
                if re.match(r'\d{1,2}:\d{2}\s*[ap]m', time_location, re.IGNORECASE):
                    time = time_location
                else:
                    location = time_location
        else:
            if re.match(r'\d{1,2}:\d{2}\s*[ap]m', text, re.IGNORECASE):
                time = text
            else:
                location = text
                
        return date, time, location
    
    def extract_speakers_from_text(self, text: str) -> List[Dict[str, str]]:
        """Extract speaker information from text"""
        speakers = []
        
        # Look for speaker patterns in text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        for line in lines:
            # Skip lines that are clearly descriptions
            if len(line) > 100 or any(word in line.lower() for word in 
                                    ['summary:', 'join', 'learn', 'explore', 'session', 'discuss', 'will', 'this']):
                continue
            
            # Look for name patterns
            if ',' in line and len(line.split()) <= 8:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    name = parts[0]
                    title = parts[1] if len(parts) > 1 else ""
                    org = ', '.join(parts[2:]) if len(parts) > 2 else ""
                    
                    # Basic validation - name should look like a name
                    if (name and len(name.split()) <= 4 and 
                        not any(word in name.lower() for word in ['track', 'room', 'floor', 'level'])):
                        speakers.append({
                            'name': name,
                            'title': title,
                            'organization': org
                        })
        
        return speakers
    
    def extract_speakers_from_structured_text(self, text: str) -> Dict[str, Any]:
        """Extract speakers and track from structured text like 'Moderator: Name, Title, Org'"""
        speakers = []
        track = ""
        
        # Look for track information
        track_match = re.search(r'Track:\s*([^\n<]+)', text)
        if track_match:
            track = track_match.group(1).strip()
        
        # Look for speaker patterns
        # Pattern: "Speaker: Name, Title, Organization"
        speaker_matches = re.findall(r'(?:Speaker|Moderator|Presenter|Panelist):\s*([^\n<]+)', text)
        
        for match in speaker_matches:
            # Parse the speaker information
            speaker_text = match.strip()
            if not speaker_text:
                continue
            
            # Split by comma to separate name, title, organization
            parts = [p.strip() for p in speaker_text.split(',')]
            
            name = parts[0] if parts else ""
            title = parts[1] if len(parts) > 1 else ""
            organization = ', '.join(parts[2:]) if len(parts) > 2 else ""
            
            if name:  # Only add if we have at least a name
                speakers.append({
                    'name': name,
                    'title': title,
                    'organization': organization
                })
        
        return {
            'speakers': speakers,
            'track': track
        }
    
    def determine_session_type(self, title: str) -> str:
        """Determine session type based on title"""
        title_lower = title.lower()
        
        type_map = {
            'general session': 'General Session',
            'opening session': 'General Session',
            'closing session': 'General Session',
            'breakfast': 'Breakfast Session',
            'lunch': 'Lunch Session',
            'reception': 'Reception',
            'committee meeting': 'Committee Meeting',
            'business meeting': 'Business Meeting',
            'task force': 'Task Force Meeting',
            'caucus': 'Caucus Meeting',
            'registration': 'Registration',
            'exhibit hall': 'Exhibit Hall Event',
            'learning hub': 'Learning Hub Session',
            'workshop': 'Workshop',
            'roundtable': 'Roundtable',
            'professional development': 'Professional Development',
            'training': 'Training',
            'forum': 'Forum',
            'panel': 'Panel Discussion',
            'plenary': 'Plenary Session'
        }
        
        for key, value in type_map.items():
            if key in title_lower:
                return value
        
        return 'Session'
    
    def create_session_hash(self, session_data: Dict[str, Any]) -> str:
        """Create a hash for session deduplication"""
        # Use title, date, time, and location for uniqueness
        unique_string = f"{session_data.get('title', '')}{session_data.get('date', '')}{session_data.get('time', '')}{session_data.get('location', '')}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def extract_session_from_cell(self, date_cell) -> Optional[Dict[str, Any]]:
        """Extract session information from a date cell and its row"""
        try:
            # Get the parent row to access all cells
            row = date_cell.find_parent('tr')
            if not row:
                return None
            
            # Get all cells in the row
            cells = row.find_all('td')
            if len(cells) < 3:  # Need at least title, date, description
                return None
            
            # Parse date from date_cell
            date_value = date_cell.get('data-value', '')
            if not date_value:
                return None
            
            try:
                date_obj = datetime.strptime(date_value, '%m/%d/%Y')
                date = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                date = date_value
            
            # Parse time and location from date cell
            date_cell_text = self.clean_text(date_cell.get_text())
            lines = [line.strip() for line in date_cell_text.split('\n') if line.strip()]
            if not lines:
                return None
            
            first_line = lines[0]
            _, time, location = self.parse_time_location(first_line)
            
            # Additional location info
            if len(lines) > 1:
                additional_location = self.clean_text('\n'.join(lines[1:]))
                if additional_location and not location:
                    location = additional_location
                elif additional_location and location:
                    location = f"{location}, {additional_location}"
            
            # Find title cell (usually the one before date cell)
            title = ""
            title_cell = date_cell.find_previous_sibling('td')
            if title_cell:
                title = self.clean_text(title_cell.get_text())
            
            # Find description cell (usually after date cell)
            description = ""
            desc_cell = date_cell.find_next_sibling('td')
            if desc_cell:
                desc_text = self.clean_text(desc_cell.get_text())
                # Extract description (remove "Summary:" prefix if present)
                if desc_text.startswith('Summary:'):
                    description = desc_text[8:].strip()
                else:
                    description = desc_text
            
            # Find speaker cell (look for cells containing "Speaker:" or "Moderator:")
            speakers = []
            track = ""
            
            for cell in cells:
                cell_text = cell.get_text()
                if 'Speaker:' in cell_text or 'Moderator:' in cell_text or 'Track:' in cell_text:
                    # Parse speakers from this cell
                    speakers_data = self.extract_speakers_from_structured_text(cell_text)
                    speakers.extend(speakers_data['speakers'])
                    if speakers_data['track']:
                        track = speakers_data['track']
            
            if not title:
                return None
            
            session = {
                'date': date,
                'time': time,
                'title': title,
                'location': location.strip(),
                'speakers': speakers,
                'description': description,
                'track': track,
                'session_type': self.determine_session_type(title)
            }
            
            return session
            
        except Exception as e:
            logger.error(f"Error extracting session from cell: {e}")
            return None
    
    def get_page_sessions(self, page: int) -> List[Dict[str, Any]]:
        """Get unique sessions from a specific page"""
        url = f"{self.base_url}?page={page}"
        logger.info(f"Fetching page {page}: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find date cells
            date_cells = soup.find_all('td', {'data-value': lambda x: x and '/' in str(x) and len(str(x)) == 10})
            
            if not date_cells:
                logger.warning(f"No date cells found on page {page}")
                return []
            
            sessions = []
            new_sessions = 0
            
            for date_cell in date_cells:
                session = self.extract_session_from_cell(date_cell)
                if session:
                    # Check for duplicates
                    session_hash = self.create_session_hash(session)
                    if session_hash not in self.seen_sessions:
                        self.seen_sessions.add(session_hash)
                        sessions.append(session)
                        new_sessions += 1
            
            logger.info(f"Page {page}: Found {len(date_cells)} cells, extracted {new_sessions} new unique sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            return []
    
    def scrape_all_sessions(self) -> Dict[str, Any]:
        """Scrape all unique sessions from all pages"""
        logger.info("Starting final NCSL 2025 Summit scraping with deduplication...")
        
        all_sessions = []
        page = 1
        max_pages = 10  # Reasonable limit
        pages_without_new_content = 0
        
        while page <= max_pages and pages_without_new_content < 3:
            page_sessions = self.get_page_sessions(page)
            
            if not page_sessions:
                pages_without_new_content += 1
                logger.info(f"No new sessions on page {page}")
            else:
                pages_without_new_content = 0
                all_sessions.extend(page_sessions)
            
            page += 1
            time.sleep(1)  # Be nice to the server
        
        # Build speakers list
        all_speakers = {}
        for session in all_sessions:
            for speaker in session['speakers']:
                speaker_key = speaker['name']
                if speaker_key and speaker_key not in all_speakers:
                    all_speakers[speaker_key] = {
                        'name': speaker['name'],
                        'title': speaker['title'],
                        'organization': speaker['organization'],
                        'sessions': []
                    }
                if speaker_key:
                    all_speakers[speaker_key]['sessions'].append(session['title'])
        
        speakers_list = sorted(all_speakers.values(), key=lambda x: x['name'])
        
        # Calculate statistics
        sessions_by_date = {}
        sessions_by_type = {}
        tracks = set()
        
        for session in all_sessions:
            if session['date']:
                sessions_by_date[session['date']] = sessions_by_date.get(session['date'], 0) + 1
            
            session_type = session['session_type']
            sessions_by_type[session_type] = sessions_by_type.get(session_type, 0) + 1
            
            if session['track']:
                track_list = [t.strip() for t in session['track'].split(',')]
                tracks.update(track_list)
        
        # Create output
        output = {
            'event': {
                'name': 'NCSL 2025 Legislative Summit',
                'year': '2025',
                'location': 'Boston, MA',
                'dates': 'August 2-6, 2025',
                'venue': 'Boston Convention and Exhibition Center (BCEC)'
            },
            'metadata': {
                'extracted_at': datetime.now().isoformat(),
                'total_sessions': len(all_sessions),
                'total_unique_speakers': len(speakers_list),
                'total_tracks': len(tracks),
                'sessions_by_date': sessions_by_date,
                'sessions_by_type': sessions_by_type,
                'pages_scraped': page - 1,
                'deduplication_enabled': True
            },
            'sessions': all_sessions,
            'speakers': speakers_list,
            'tracks': sorted(list(tracks))
        }
        
        logger.info(f"Scraping complete!")
        logger.info(f"Total unique sessions: {len(all_sessions)}")
        logger.info(f"Total speakers: {len(speakers_list)}")
        logger.info(f"Total tracks: {len(tracks)}")
        logger.info(f"Pages scraped: {page - 1}")
        
        return output
    
    def save_results(self, data: Dict[str, Any], filename: str = 'ncsl_sessions_complete_final.json'):
        """Save results to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Data saved to {filename}")

def main():
    scraper = FinalNCSLScraper()
    data = scraper.scrape_all_sessions()
    scraper.save_results(data)
    
    # Print detailed summary
    print("\n" + "="*50)
    print("FINAL NCSL 2025 SUMMIT SCRAPING RESULTS")
    print("="*50)
    print(f"Total sessions: {data['metadata']['total_sessions']}")
    print(f"Total speakers: {data['metadata']['total_unique_speakers']}")
    print(f"Total tracks: {data['metadata']['total_tracks']}")
    print(f"Pages scraped: {data['metadata']['pages_scraped']}")
    
    print(f"\nSessions by date:")
    for date, count in sorted(data['metadata']['sessions_by_date'].items()):
        print(f"  {date}: {count} sessions")
    
    print(f"\nTop session types:")
    for stype, count in sorted(data['metadata']['sessions_by_type'].items(), 
                              key=lambda x: x[1], reverse=True):
        print(f"  {stype}: {count}")
    
    # Show sample sessions with details
    print(f"\n" + "="*50)
    print("SAMPLE SESSIONS WITH DETAILS")
    print("="*50)
    
    sessions_with_speakers = [s for s in data['sessions'] if s['speakers']]
    sample_sessions = data['sessions'][:5] if len(data['sessions']) >= 5 else data['sessions']
    
    for i, session in enumerate(sample_sessions):
        print(f"\n{i+1}. {session['title'][:80]}...")
        print(f"   Date: {session['date']} | Time: {session['time']}")
        print(f"   Location: {session['location']}")
        print(f"   Type: {session['session_type']}")
        if session['track']:
            print(f"   Track: {session['track']}")
        if session['description']:
            print(f"   Description: {session['description'][:100]}...")
        if session['speakers']:
            print(f"   Speakers ({len(session['speakers'])}):")
            for speaker in session['speakers'][:3]:  # Show max 3
                parts = [speaker['name']]
                if speaker['title']:
                    parts.append(speaker['title'])
                if speaker['organization']:
                    parts.append(speaker['organization'])
                print(f"     - {', '.join(parts)}")
    
    print(f"\n" + "="*50)
    print("Data saved to ncsl_sessions_complete_final.json")
    print("="*50)

if __name__ == "__main__":
    main()