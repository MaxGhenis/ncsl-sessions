import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from typing import List, Dict, Any

def fetch_ncsl_2025_sessions():
    """Fetch all sessions from the NCSL 2025 Summit agenda"""
    url = "https://www.ncsl.org/events/2025-ncsl-legislative-summit/agenda"
    
    print("Fetching NCSL 2025 Summit agenda...")
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        sessions = []
        speakers_set = set()
        tracks_set = set()
        
        # Find all session containers - they're in table rows
        all_rows = soup.find_all('tr')
        
        print(f"Found {len(all_rows)} potential session rows")
        
        for row in all_rows:
            cells = row.find_all(['td', 'th'])
            
            # Skip header rows or rows with insufficient cells
            if len(cells) < 2:
                continue
                
            # Skip if first cell contains header text
            first_cell_text = cells[0].get_text(strip=True).lower()
            if first_cell_text in ['time', 'date', '']:
                continue
            
            session = {}
            
            # Extract time from first cell
            time_text = cells[0].get_text(strip=True)
            if time_text:
                session['time'] = time_text
            
            # Extract session details from second cell
            if len(cells) > 1:
                content_cell = cells[1]
                
                # Get all text content
                full_text = content_cell.get_text(separator='\n')
                lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                
                if not lines:
                    continue
                
                # First line is usually the title
                session['title'] = lines[0]
                
                # Look for location
                for line in lines:
                    if 'Location:' in line:
                        session['location'] = line.replace('Location:', '').strip()
                        break
                
                # Look for track/category info
                for line in lines:
                    if 'Track:' in line:
                        track = line.replace('Track:', '').strip()
                        session['track'] = track
                        tracks_set.add(track)
                        break
                
                # Extract speakers - look for lines that are likely names
                # (after title, before location, not containing keywords)
                speakers = []
                skip_keywords = ['location:', 'track:', 'description:', 'note:', 'sponsored']
                
                for i, line in enumerate(lines[1:], 1):  # Skip title
                    line_lower = line.lower()
                    
                    # Skip if contains keywords
                    if any(keyword in line_lower for keyword in skip_keywords):
                        continue
                    
                    # Skip if it's the location or track line
                    if line == session.get('location') or line == session.get('track'):
                        continue
                    
                    # Heuristics for speaker names:
                    # - Contains comma (Name, Title format)
                    # - 2-5 words and starts with capital
                    # - Not too long (under 100 chars)
                    if (',' in line or 
                        (2 <= len(line.split()) <= 5 and line[0].isupper())) and \
                       len(line) < 100:
                        speakers.append(line)
                        # Extract just the name part (before comma if present)
                        name_part = line.split(',')[0].strip()
                        if name_part:
                            speakers_set.add(name_part)
                
                if speakers:
                    session['speakers'] = speakers
                
                # Try to identify session type
                title_lower = session['title'].lower()
                if 'general session' in title_lower:
                    session['type'] = 'General Session'
                elif 'breakfast' in title_lower:
                    session['type'] = 'Breakfast Session'
                elif 'lunch' in title_lower:
                    session['type'] = 'Lunch Session'
                elif 'reception' in title_lower:
                    session['type'] = 'Reception'
                elif 'workshop' in title_lower:
                    session['type'] = 'Workshop'
                elif 'roundtable' in title_lower:
                    session['type'] = 'Roundtable'
                elif 'meeting' in title_lower:
                    session['type'] = 'Meeting'
                else:
                    session['type'] = 'Session'
                
                # Only add if we have a valid title
                if session.get('title') and session['title'] not in ['', 'Time']:
                    sessions.append(session)
        
        print(f"Successfully extracted {len(sessions)} sessions")
        print(f"Found {len(speakers_set)} unique speakers")
        print(f"Found {len(tracks_set)} tracks")
        
        # Save to JSON
        output_data = {
            'year': '2025',
            'location': 'Boston, MA',
            'dates': 'August 4-6, 2025',
            'scraped_at': datetime.now().isoformat(),
            'sessions': sessions,
            'speakers': sorted(list(speakers_set)),
            'tracks': sorted(list(tracks_set))
        }
        
        with open('ncsl_sessions_2025.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Data saved to ncsl_sessions_2025.json")
        
        # Also update the main sessions file
        with open('ncsl_sessions.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Data also saved to ncsl_sessions.json")
        
        return output_data
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

if __name__ == "__main__":
    data = fetch_ncsl_2025_sessions()
    
    if data:
        # Print some sample sessions
        print("\nSample sessions:")
        for i, session in enumerate(data['sessions'][:5]):
            print(f"\n{i+1}. {session.get('title', 'No title')}")
            print(f"   Time: {session.get('time', 'TBD')}")
            if 'speakers' in session:
                print(f"   Speakers: {', '.join(session['speakers'][:2])}...")
            if 'location' in session:
                print(f"   Location: {session['location']}")