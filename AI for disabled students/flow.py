import sys
import requests
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QScrollArea, QFrame)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPixmap
from graphviz import Digraph
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize
from collections import Counter

# Download NLTK data if needed
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

# Firebase configuration
FIREBASE_BASE_URL = "https://hacks-f28bb-default-rtdb.firebaseio.com"

def get_latest_transcript():
    """Get the latest transcript from Firebase"""
    try:
        response = requests.get(f"{FIREBASE_BASE_URL}/sessions.json", timeout=5)
        if response.status_code == 200:
            sessions = response.json() or {}
            
            # Find the most recently updated session
            latest_session = None
            latest_time = 0
            
            for session_id, session_data in sessions.items():
                last_updated = session_data.get("last_updated", 0)
                if last_updated > latest_time:
                    latest_time = last_updated
                    latest_session = session_data
            
            if latest_session:
                transcript = latest_session.get("current_transcript", "")
                return transcript
        return ""
    except Exception as e:
        print(f"Firebase error: {e}")
        return ""

def generate_flowchart(text):
    """Generate a simple flowchart from text"""
    if not text or len(text.strip()) < 10:
        dot = Digraph()
        dot.node('empty', 'Waiting for speech input...\n(Speak in teacher app)')
        return dot
    
    try:
        sentences = sent_tokenize(text)
        if len(sentences) < 2:
            dot = Digraph()
            dot.node('single', f'Current Speech:\n{sentences[0][:150]}...' if sentences else 'No content')
            return dot
        
        # Simple processing
        stop_words = set(stopwords.words('english'))
        
        dot = Digraph()
        dot.attr(rankdir='TB')
        
        # Start node
        dot.node('start', 'Start', shape='ellipse', style='filled', color='lightgreen')
        
        # Add sentences as nodes
        prev_node = 'start'
        for i, sentence in enumerate(sentences):
            node_id = f's{i}'
            # Clean and truncate sentence for display
            clean_sentence = ' '.join(sentence.split()[:15])  # First 15 words
            if len(sentence.split()) > 15:
                clean_sentence += '...'
            
            dot.node(node_id, f'Step {i+1}:\n{clean_sentence}', 
                    shape='rect', style='rounded', color='lightblue')
            dot.edge(prev_node, node_id)
            prev_node = node_id
        
        # End node
        dot.node('end', 'End', shape='ellipse', style='filled', color='lightcoral')
        dot.edge(prev_node, 'end')
        
        return dot
        
    except Exception as e:
        dot = Digraph()
        dot.node('error', f'Error:\n{str(e)}')
        return dot

class SimpleFlowchartApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Speech Flowchart")
        self.setGeometry(100, 100, 1000, 700)
        
        self.current_transcript = ""
        self.flowchart_image = None
        
        self.setup_ui()
        self.start_auto_refresh()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📊 Live Speech Flowchart Generator")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("🟢 Ready - Waiting for speech...")
        self.status_label.setFont(QFont("Arial", 12))
        layout.addWidget(self.status_label)
        
        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh Now")
        self.refresh_btn.setFont(QFont("Arial", 12))
        self.refresh_btn.clicked.connect(self.generate_flowchart)
        layout.addWidget(self.refresh_btn)
        
        # Flowchart display area
        self.flowchart_label = QLabel()
        self.flowchart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flowchart_label.setStyleSheet("border: 1px solid #ccc; background-color: white;")
        self.flowchart_label.setMinimumHeight(500)
        layout.addWidget(self.flowchart_label)
        
        # Current text preview
        self.text_preview = QTextEdit()
        self.text_preview.setMaximumHeight(100)
        self.text_preview.setPlaceholderText("Current speech will appear here...")
        self.text_preview.setReadOnly(True)
        layout.addWidget(self.text_preview)
        
        self.setLayout(layout)
        
    def start_auto_refresh(self):
        """Start automatic refresh every 3 seconds"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.generate_flowchart)
        self.timer.start(3000)  # 3 seconds
        
    def generate_flowchart(self):
        """Generate and display flowchart from latest transcript"""
        try:
            # Get latest transcript
            transcript = get_latest_transcript()
            
            if transcript == self.current_transcript:
                # No new content
                return
            
            self.current_transcript = transcript
            
            if transcript:
                self.status_label.setText(f"🟢 Processing {len(transcript)} characters...")
                self.text_preview.setPlainText(transcript[:200] + "..." if len(transcript) > 200 else transcript)
            else:
                self.status_label.setText("🟡 No speech detected yet...")
                self.text_preview.setPlainText("")
            
            # Generate flowchart
            flowchart = generate_flowchart(transcript)
            flowchart.format = 'png'
            
            # Render and display
            image_data = flowchart.pipe()
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            
            # Scale image to fit
            scaled_pixmap = pixmap.scaled(800, 500, Qt.AspectRatioMode.KeepAspectRatio, 
                                        Qt.TransformationMode.SmoothTransformation)
            self.flowchart_label.setPixmap(scaled_pixmap)
            
            self.status_label.setText(f"✅ Flowchart Updated - {time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.status_label.setText(f"❌ Error: {str(e)}")
            self.flowchart_label.setText(f"Error generating flowchart:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleFlowchartApp()
    window.show()
    sys.exit(app.exec())