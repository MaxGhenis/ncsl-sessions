import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from typing import List, Dict, Any

def extract_all_ncsl_sessions():
    """Extract ALL sessions from the NCSL 2025 Summit agenda"""
    url = "https://www.ncsl.org/events/2025-ncsl-legislative-summit/agenda"
    
    print("Fetching NCSL 2025 Summit agenda...")
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        sessions = []
        all_speakers = set()
        all_tracks = set()
        
        # Find the main content area with sessions
        # Look for all table rows that contain session data
        tables = soup.find_all('table')
        
        session_count = 0
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:
                    # First cell usually has date/time
                    time_cell = cells[0].get_text(strip=True)
                    
                    # Skip header rows
                    if time_cell.lower() in ['time', 'date', 'time/room', '']:
                        continue
                    
                    # Second cell has session details
                    content_cell = cells[1]
                    
                    # Get all text lines
                    lines = [line.strip() for line in content_cell.get_text(separator='\n').split('\n') if line.strip()]
                    
                    if not lines:
                        continue
                    
                    session = {}
                    
                    # Parse date and time
                    if '|' in time_cell:
                        parts = time_cell.split('|')
                        date_part = parts[0].strip()
                        time_part = parts[1].strip() if len(parts) > 1 else ''
                        
                        # Convert date to ISO format
                        date_map = {
                            'Saturday, Aug. 2': '2025-08-02',
                            'Sunday, Aug. 3': '2025-08-03',
                            'Monday, Aug. 4': '2025-08-04',
                            'Tuesday, Aug. 5': '2025-08-05',
                            'Wednesday, Aug. 6': '2025-08-06'
                        }
                        
                        session['date'] = date_map.get(date_part, date_part)
                        session['time'] = time_part
                    else:
                        session['time'] = time_cell
                    
                    # First line is usually the title
                    session['title'] = lines[0]
                    
                    # Extract location
                    location_found = False
                    for i, line in enumerate(lines):
                        if 'Location:' in line:
                            session['location'] = line.replace('Location:', '').strip()
                            location_found = True
                            break
                        # Sometimes location is just after title without "Location:" prefix
                        elif i > 0 and ('BCEC' in line or 'Westin' in line or 'Omni' in line):
                            session['location'] = line
                            location_found = True
                            break
                    
                    # Extract speakers - lines between title and location
                    speakers = []
                    speaker_lines = []
                    
                    start_idx = 1
                    end_idx = len(lines)
                    
                    for i, line in enumerate(lines[1:], 1):
                        # Stop at location or track info
                        if ('Location:' in line or 'Track:' in line or 
                            'BCEC' in line or 'Westin' in line or 'Omni' in line):
                            end_idx = i
                            break
                        
                        # Lines that look like speaker info
                        if (',' in line or  # Name, Title format
                            (len(line.split()) >= 2 and len(line.split()) <= 6 and line[0].isupper()) or  # Likely a name
                            any(title in line.lower() for title in ['senator', 'representative', 'speaker', 'president', 'director', 'chair'])):
                            speaker_lines.append(line)
                    
                    # Process speaker lines
                    for line in speaker_lines:
                        if line and len(line) < 200:  # Reasonable length for speaker info
                            speakers.append(line)
                            # Extract just the name part for the master list
                            name_part = line.split(',')[0].strip()
                            if name_part and len(name_part.split()) <= 5:  # Reasonable name length
                                all_speakers.add(name_part)
                    
                    if speakers:
                        session['speakers'] = speakers
                    
                    # Extract track/category
                    for line in lines:
                        if 'Track:' in line:
                            track = line.replace('Track:', '').strip()
                            session['track'] = track
                            all_tracks.add(track)
                            break
                    
                    # Determine session type based on title
                    title_lower = session['title'].lower()
                    if 'general session' in title_lower:
                        session['session_type'] = 'General Session'
                    elif 'breakfast' in title_lower:
                        session['session_type'] = 'Breakfast Session'
                    elif 'lunch' in title_lower:
                        session['session_type'] = 'Lunch Session'
                    elif 'reception' in title_lower:
                        session['session_type'] = 'Reception'
                    elif 'committee' in title_lower and 'meeting' in title_lower:
                        session['session_type'] = 'Committee Meeting'
                    elif 'task force' in title_lower:
                        session['session_type'] = 'Task Force Meeting'
                    elif 'workshop' in title_lower:
                        session['session_type'] = 'Workshop'
                    elif 'roundtable' in title_lower:
                        session['session_type'] = 'Roundtable'
                    elif 'exhibit hall' in title_lower:
                        session['session_type'] = 'Exhibit Hall Event'
                    elif 'learning hub' in title_lower:
                        session['session_type'] = 'Learning Hub Session'
                    else:
                        session['session_type'] = 'Session'
                    
                    # Add session if it has a valid title
                    if session.get('title') and session['title'] not in ['Time/Room', '']:
                        sessions.append(session)
                        session_count += 1
        
        # Also look for sessions in div elements with specific classes
        session_divs = soup.find_all('div', class_=re.compile('session|event|agenda-item', re.I))
        
        for div in session_divs:
            session = {}
            
            # Extract title
            title_elem = div.find(['h2', 'h3', 'h4', 'a'], class_=re.compile('title|heading|session-name', re.I))
            if title_elem:
                session['title'] = title_elem.get_text(strip=True)
            
            # Extract time
            time_elem = div.find(['time', 'span', 'div'], class_=re.compile('time|date|when|session-time', re.I))
            if time_elem:
                session['time'] = time_elem.get_text(strip=True)
            
            # Extract speakers
            speaker_elems = div.find_all(['span', 'div', 'p'], class_=re.compile('speaker|presenter|moderator', re.I))
            if speaker_elems:
                speakers = []
                for elem in speaker_elems:
                    speaker_text = elem.get_text(strip=True)
                    if speaker_text:
                        speakers.append(speaker_text)
                        name_part = speaker_text.split(',')[0].strip()
                        if name_part:
                            all_speakers.add(name_part)
                if speakers:
                    session['speakers'] = speakers
            
            # Extract location
            location_elem = div.find(['span', 'div'], class_=re.compile('location|room|venue', re.I))
            if location_elem:
                session['location'] = location_elem.get_text(strip=True)
            
            # Extract track
            track_elem = div.find(['span', 'div'], class_=re.compile('track|category|topic', re.I))
            if track_elem:
                track = track_elem.get_text(strip=True)
                session['track'] = track
                all_tracks.add(track)
            
            # Add if valid
            if session.get('title'):
                sessions.append(session)
                session_count += 1
        
        print(f"\nExtracted {len(sessions)} total sessions")
        print(f"Found {len(all_speakers)} unique speakers")
        print(f"Found {len(all_tracks)} tracks")
        
        # Remove duplicates based on title and time
        unique_sessions = []
        seen = set()
        for session in sessions:
            key = (session.get('title', ''), session.get('time', ''))
            if key not in seen:
                seen.add(key)
                unique_sessions.append(session)
        
        print(f"After deduplication: {len(unique_sessions)} unique sessions")
        
        # Save to JSON
        output_data = {
            'year': '2025',
            'location': 'Boston, MA',
            'dates': 'August 2-6, 2025',
            'scraped_at': datetime.now().isoformat(),
            'total_sessions': len(unique_sessions),
            'sessions': unique_sessions,
            'speakers': sorted(list(all_speakers)),
            'tracks': sorted(list(all_tracks))
        }
        
        # Save comprehensive data
        with open('ncsl_sessions_full.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nFull data saved to ncsl_sessions_full.json")
        
        # Also update the main file
        with open('ncsl_sessions.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Data also saved to ncsl_sessions.json")
        
        # Print sample sessions
        print("\nSample sessions:")
        for i, session in enumerate(unique_sessions[:5]):
            print(f"\n{i+1}. {session.get('title', 'No title')}")
            if 'date' in session:
                print(f"   Date: {session['date']}")
            print(f"   Time: {session.get('time', 'TBD')}")
            if 'speakers' in session and session['speakers']:
                print(f"   Speakers: {'; '.join(session['speakers'][:2])}")
            if 'location' in session:
                print(f"   Location: {session['location']}")
        
        return output_data
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    extract_all_ncsl_sessions()