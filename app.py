from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import json
import os
from typing import List, Dict, Any
from datetime import datetime

app = Flask(__name__)
CORS(app)

class SessionManager:
    def __init__(self):
        self.sessions = []
        self.speakers = []
        self.tracks = set()
        self.load_data()
        
    def load_data(self):
        """Load session data from JSON file"""
        try:
            with open('ncsl_sessions.json', 'r') as f:
                data = json.load(f)
                self.sessions = data.get('sessions', [])
                self.speakers = data.get('speakers', [])
                
                # Extract unique tracks
                for session in self.sessions:
                    if 'track' in session:
                        self.tracks.add(session['track'])
                    elif 'tracks' in session:
                        for track in session['tracks']:
                            self.tracks.add(track)
                            
        except FileNotFoundError:
            print("Session data not found. Please run scraper.py first.")
            
    def search_sessions(self, query: str = "", track: str = "", speaker: str = "") -> List[Dict[str, Any]]:
        """Search sessions based on query, track, and speaker"""
        results = self.sessions
        
        # Filter by search query
        if query:
            query_lower = query.lower()
            results = [s for s in results if 
                      query_lower in s.get('title', '').lower() or
                      query_lower in s.get('description', '').lower() or
                      any(query_lower in sp.lower() for sp in s.get('speakers', []))]
        
        # Filter by track
        if track:
            results = [s for s in results if 
                      track == s.get('track', '') or
                      track in s.get('tracks', [])]
        
        # Filter by speaker
        if speaker:
            results = [s for s in results if 
                      speaker in s.get('speakers', [])]
        
        return results
    
    def get_speaker_sessions(self, speaker_name: str) -> List[Dict[str, Any]]:
        """Get all sessions for a specific speaker"""
        return [s for s in self.sessions if speaker_name in s.get('speakers', [])]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the summit"""
        return {
            'total_sessions': len(self.sessions),
            'total_speakers': len(self.speakers),
            'total_tracks': len(self.tracks),
            'tracks': list(self.tracks),
            'session_types': list(set(s.get('type', 'Session') for s in self.sessions))
        }

# Initialize session manager
session_manager = SessionManager()

@app.route('/')
def index():
    """Main page with search interface"""
    return render_template('index.html', 
                         stats=session_manager.get_stats(),
                         initial_sessions=session_manager.sessions[:20])

@app.route('/api/sessions')
def api_sessions():
    """API endpoint for searching sessions"""
    query = request.args.get('q', '')
    track = request.args.get('track', '')
    speaker = request.args.get('speaker', '')
    
    results = session_manager.search_sessions(query, track, speaker)
    return jsonify(results)

@app.route('/api/speakers')
def api_speakers():
    """API endpoint for getting all speakers"""
    return jsonify(session_manager.speakers)

@app.route('/api/speaker/<speaker_name>')
def api_speaker_sessions(speaker_name):
    """API endpoint for getting sessions by a specific speaker"""
    sessions = session_manager.get_speaker_sessions(speaker_name)
    return jsonify(sessions)

@app.route('/api/stats')
def api_stats():
    """API endpoint for summit statistics"""
    return jsonify(session_manager.get_stats())

@app.route('/speakers')
def speakers_page():
    """Page listing all speakers"""
    return render_template('speakers.html', speakers=sorted(session_manager.speakers))

@app.route('/sessions')
def sessions_page():
    """Page listing all sessions with filters"""
    return render_template('sessions.html', 
                         sessions=session_manager.sessions,
                         tracks=sorted(session_manager.tracks))

if __name__ == '__main__':
    # First run the scraper to ensure we have data
    if not os.path.exists('ncsl_sessions.json'):
        print("Running scraper to fetch session data...")
        import subprocess
        subprocess.run(['python', 'scraper.py'])
    
    app.run(debug=True, port=5000)