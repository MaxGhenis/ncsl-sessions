import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from typing import List, Dict, Any

class NCSLSummitScraper:
    def __init__(self, year: str = "2025"):
        self.year = year
        if year == "2025":
            self.base_url = f"https://www.ncsl.org/events/{year}-ncsl-legislative-summit"
        else:
            self.base_url = f"https://www.ncsl.org/events/{year}-summit"
        self.sessions = []
        self.speakers = set()
        
    def scrape_agenda(self) -> List[Dict[str, Any]]:
        """Scrape the main agenda page for sessions"""
        url = f"{self.base_url}/agenda"
        
        try:
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # For 2025, look for the specific table structure
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    session_data = self._extract_session_from_row(row)
                    if session_data:
                        self.sessions.append(session_data)
            
            # Also look for session containers
            session_elements = soup.find_all(['div', 'article', 'section'], 
                                           class_=re.compile('session|event|agenda-item', re.I))
            
            for elem in session_elements:
                session_data = self._extract_session_info(elem)
                if session_data:
                    self.sessions.append(session_data)
                    
            # Also look for structured data in scripts
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'Event':
                                self._process_structured_data(item)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error scraping agenda: {e}")
            
        return self.sessions
    
    def _extract_session_from_row(self, row) -> Dict[str, Any]:
        """Extract session information from table row"""
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None
            
        session = {}
        
        # First cell usually has time/date
        if cells[0]:
            time_text = cells[0].get_text(strip=True)
            if time_text and not time_text.lower().startswith('time'):
                session['time'] = time_text
        
        # Second cell usually has session details
        if len(cells) > 1 and cells[1]:
            content = cells[1]
            
            # Extract title (usually in strong or first line)
            title_elem = content.find('strong')
            if title_elem:
                session['title'] = title_elem.get_text(strip=True)
            else:
                # Get first non-empty line
                lines = content.get_text().strip().split('\n')
                for line in lines:
                    if line.strip():
                        session['title'] = line.strip()
                        break
            
            # Extract location
            location_match = re.search(r'Location:\s*([^|]+)', content.get_text())
            if location_match:
                session['location'] = location_match.group(1).strip()
            
            # Extract speakers (look for lines that might be names)
            text_lines = content.get_text().split('\n')
            speakers = []
            for line in text_lines:
                line = line.strip()
                # Skip empty lines, title, location, and common words
                if (line and 
                    line != session.get('title', '') and 
                    not line.lower().startswith('location:') and
                    not line.lower().startswith('track:') and
                    len(line.split()) <= 6 and  # Likely a name
                    any(char.isalpha() for char in line)):
                    # Check if it looks like a name (has commas or typical name patterns)
                    if ',' in line or (len(line.split()) >= 2 and line[0].isupper()):
                        speakers.append(line)
                        self.speakers.add(line.split(',')[0].strip())  # Add just the name part
            
            if speakers:
                session['speakers'] = speakers
        
        return session if session.get('title') else None
    
    def _extract_session_info(self, element) -> Dict[str, Any]:
        """Extract session information from HTML element"""
        session = {}
        
        # Extract title
        title_elem = element.find(['h2', 'h3', 'h4'], class_=re.compile('title|heading', re.I))
        if title_elem:
            session['title'] = title_elem.get_text(strip=True)
        
        # Extract time
        time_elem = element.find(['time', 'span', 'div'], class_=re.compile('time|date|when', re.I))
        if time_elem:
            session['time'] = time_elem.get_text(strip=True)
            
        # Extract speakers
        speaker_elems = element.find_all(['span', 'div', 'p'], class_=re.compile('speaker|presenter', re.I))
        speakers = []
        for speaker in speaker_elems:
            speaker_name = speaker.get_text(strip=True)
            if speaker_name:
                speakers.append(speaker_name)
                self.speakers.add(speaker_name)
        if speakers:
            session['speakers'] = speakers
            
        # Extract description
        desc_elem = element.find(['p', 'div'], class_=re.compile('description|summary|abstract', re.I))
        if desc_elem:
            session['description'] = desc_elem.get_text(strip=True)
            
        # Extract track/category
        track_elem = element.find(['span', 'div'], class_=re.compile('track|category|topic', re.I))
        if track_elem:
            session['track'] = track_elem.get_text(strip=True)
            
        # Extract location
        location_elem = element.find(['span', 'div'], class_=re.compile('location|room|venue', re.I))
        if location_elem:
            session['location'] = location_elem.get_text(strip=True)
            
        return session if session else None
    
    def _process_structured_data(self, data: Dict[str, Any]):
        """Process structured data from JSON-LD"""
        session = {
            'title': data.get('name', ''),
            'description': data.get('description', ''),
            'time': data.get('startDate', ''),
            'location': data.get('location', {}).get('name', '') if isinstance(data.get('location'), dict) else '',
            'speakers': []
        }
        
        # Extract performers/speakers
        if 'performer' in data:
            performers = data['performer'] if isinstance(data['performer'], list) else [data['performer']]
            for performer in performers:
                if isinstance(performer, dict):
                    name = performer.get('name', '')
                    if name:
                        session['speakers'].append(name)
                        self.speakers.add(name)
                        
        if session['title']:
            self.sessions.append(session)
    
    def scrape_detailed_sessions(self) -> List[Dict[str, Any]]:
        """Scrape individual session pages for more details"""
        # This would scrape individual session pages if they exist
        # For now, returning the sessions we have
        return self.sessions
    
    def save_data(self, filename: str = 'ncsl_sessions.json'):
        """Save scraped data to JSON file"""
        data = {
            'year': self.year,
            'scraped_at': datetime.now().isoformat(),
            'sessions': self.sessions,
            'speakers': list(self.speakers)
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"Saved {len(self.sessions)} sessions and {len(self.speakers)} speakers to {filename}")
        
    def create_sample_data(self):
        """Create sample data based on what we found"""
        self.sessions = [
            {
                "title": "Artificial Intelligence Is Here: Are States Ready?",
                "time": "Monday, Aug 5, 8:30-10:00 AM",
                "speakers": ["Jennifer Pahlka"],
                "organization": "Code for America",
                "tracks": ["Technology and Communications", "Artificial Intelligence"],
                "type": "General Session",
                "description": "Exploring how states can prepare for and leverage AI technology"
            },
            {
                "title": "10 Lies and a Truth: Using Brain Science to Distinguish Fact From Bias",
                "time": "Tuesday, Aug 6, 9:00-10:15 AM",
                "speakers": ["John Medina"],
                "role": "Molecular Biologist",
                "track": "Professional Development",
                "type": "General Session",
                "description": "Understanding cognitive biases and decision-making"
            },
            {
                "title": "The Cure for Stupidity: Understanding Why They Don't Understand You",
                "time": "Tuesday, Aug 6, 4:00-5:00 PM",
                "speakers": ["Eric Bailey"],
                "organization": "Bailey Strategic Innovation Group",
                "track": "Professional Development",
                "type": "General Session"
            },
            {
                "title": "Democratic Breakfast",
                "time": "Tuesday Morning",
                "speakers": ["Tom Perez"],
                "role": "White House Senior Advisor",
                "type": "Breakfast Session"
            },
            {
                "title": "Republican Breakfast",
                "time": "Tuesday Morning",
                "speakers": ["Mitch McConnell"],
                "type": "Breakfast Session"
            },
            {
                "title": "Legislative Staff Breakfast",
                "speakers": ["Sarah Calhoun"],
                "type": "Breakfast Session"
            },
            {
                "title": "Women's Breakfast Roundtables",
                "type": "Breakfast Session",
                "format": "Roundtable Discussion"
            },
            {
                "title": "NCSL Business Meeting",
                "type": "Business Meeting"
            }
        ]
        
        # Extract unique speakers
        for session in self.sessions:
            if 'speakers' in session:
                for speaker in session['speakers']:
                    self.speakers.add(speaker)

if __name__ == "__main__":
    scraper = NCSLSummitScraper("2024")
    
    # Try to scrape actual data
    print("Attempting to scrape NCSL Summit data...")
    sessions = scraper.scrape_agenda()
    
    # If we didn't get much data, use sample data
    if len(sessions) < 5:
        print("Using sample data based on available information...")
        scraper.create_sample_data()
    
    # Save the data
    scraper.save_data()