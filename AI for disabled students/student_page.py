import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread

# ----------------------------
# Firebase Base URL
# ----------------------------
FIREBASE_URL = "https://hacks-f28bb-default-rtdb.firebaseio.com"

# ==========================================================
# Enhanced Firebase Listener Thread
# ==========================================================
class FirebaseListener(QThread):
    new_transcript = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self, session_code):
        super().__init__()
        self.session_code = session_code
        self.running = True
        self.last_transcript = ""
        self.session_id = None
        
    def run(self):
        while self.running:
            try:
                # Check for new transcripts in Firebase
                response = requests.get(f"{FIREBASE_URL}/sessions.json")
                if response.status_code == 200:
                    self.connection_status.emit(True)
                    sessions = response.json() or {}
                    
                    # Find our session
                    for session_id, session_data in sessions.items():
                        if session_data.get("session_code") == self.session_code:
                            self.session_id = session_id
                            transcript = session_data.get("current_transcript", "")
                            
                            # Only emit if transcript is new and not empty
                            if transcript and transcript != self.last_transcript:
                                self.last_transcript = transcript
                                self.new_transcript.emit(transcript)
                            break
                else:
                    self.connection_status.emit(False)
                    
            except Exception as e:
                print("Firebase listener error:", e)
                self.connection_status.emit(False)
            
            QThread.msleep(300)  # Faster polling for better real-time experience
    
    def stop(self):
        self.running = False

# ==========================================================
# Student Page (Deaf Student) - Google Meet Style
# ==========================================================
class StudentPage(QWidget):
    def __init__(self):
        super().__init__()
        self.session_code = None
        self.firebase_listener = None
        self.is_in_session = False
        
        self.setup_join_interface()

    def setup_join_interface(self):
        """Setup the initial join session interface"""
        # Clear existing layout
        if hasattr(self, 'main_layout'):
            for i in reversed(range(self.main_layout.count())):
                widget = self.main_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(40, 40, 40, 40)

        # Set light background for join screen
        self.setStyleSheet("background-color: #f8f9fa;")

        self.title = QLabel(" Deaf Student - Live Classroom")
        self.title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #1a73e8; padding: 20px;")
        self.main_layout.addWidget(self.title)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter 6-digit Session Code")
        self.code_input.setFont(QFont("Segoe UI", 18))
        self.code_input.setStyleSheet(
            "background-color: white; padding: 15px; border-radius: 10px; border: 2px solid #dadce0; font-size: 16px;"
        )
        self.main_layout.addWidget(self.code_input)

        self.join_button = QPushButton("Join Session")
        self.join_button.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.join_button.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                padding: 15px;
                border-radius: 10px;
                border: none;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #1669d6;
            }
            QPushButton:disabled {
                background-color: #dadce0;
            }
        """)
        self.join_button.clicked.connect(self.check_session)
        self.main_layout.addWidget(self.join_button)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 16))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("padding: 10px; color: #5f6368;")
        self.main_layout.addWidget(self.status_label)

        # Add some stretch to center the content
        self.main_layout.addStretch()
        
        self.setLayout(self.main_layout)
        self.is_in_session = False

    # ----------------------------
    # Firebase session check
    # ----------------------------
    def check_session(self):
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, "Error", "Please enter a session code.")
            return

        if len(code) != 6 or not code.isdigit():
            QMessageBox.warning(self, "Error", "Please enter a valid 6-digit code.")
            return

        self.join_button.setText("Checking...")
        self.join_button.setEnabled(False)

        try:
            response = requests.get(f"{FIREBASE_URL}/sessions.json", timeout=10)
            if response.status_code != 200:
                QMessageBox.critical(self, "Error", "Failed to connect to database.")
                self.reset_join_button()
                return

            data = response.json() or {}
            session_found = None
            
            for session_id, session_data in data.items():
                if session_data.get("session_code") == code:
                    session_found = session_data
                    break

            if session_found:
                self.session_code = code
                QTimer.singleShot(500, self.setup_live_session)  # Small delay for smooth transition
            else:
                self.status_label.setText("❌ Session not found. Please check the code.")
                self.status_label.setStyleSheet("color: #ea4335; padding: 10px;")
                self.reset_join_button()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
            self.reset_join_button()

    def reset_join_button(self):
        self.join_button.setText("Join Session")
        self.join_button.setEnabled(True)

    def setup_live_session(self):
        """Setup the Google Meet-style live session view"""
        # Clear existing layout
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Set modern background
        self.setStyleSheet("background-color: #202124;")

        # Main container for the layout with proper spacing for full screen
        container_layout = QVBoxLayout()
        container_layout.setSpacing(10)  # Reduced spacing for better full-screen
        container_layout.setContentsMargins(15, 10, 15, 15)

        # Header section - Google Meet style
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 10)
        header_layout.setSpacing(20)
        
        # Left side: Session info
        session_info_layout = QVBoxLayout()
        
        session_title = QLabel("Live Classroom Session")
        session_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        session_title.setStyleSheet("color: white;")
        session_info_layout.addWidget(session_title)
        
        session_code_label = QLabel(f"Session Code: {self.session_code}")
        session_code_label.setFont(QFont("Segoe UI", 12))
        session_code_label.setStyleSheet("color: #9aa0a6;")
        session_info_layout.addWidget(session_code_label)
        
        header_layout.addLayout(session_info_layout)
        header_layout.addStretch()

        # Right side: Connection status and controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        self.connection_label = QLabel("🟢 Connected")
        self.connection_label.setFont(QFont("Segoe UI", 12))
        self.connection_label.setStyleSheet("color: #34a853; font-weight: bold; padding: 5px 10px; background-color: #303134; border-radius: 15px;")
        controls_layout.addWidget(self.connection_label)

        leave_button = QPushButton("Leave Session")
        leave_button.setFont(QFont("Segoe UI", 12))
        leave_button.setStyleSheet("""
            QPushButton {
                background-color: #ea4335;
                color: white;
                padding: 8px 16px;
                border-radius: 15px;
                border: none;
            }
            QPushButton:hover {
                background-color: #d33426;
            }
        """)
        leave_button.clicked.connect(self.leave_session)
        controls_layout.addWidget(leave_button)
        
        header_layout.addLayout(controls_layout)
        container_layout.addLayout(header_layout)

        # Main content area - Split into two columns with proper ratios
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(0, 10, 0, 10)

        # Left Column - Empty space for character (Google Meet video style)
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        
        character_label = QLabel("🤖 Avatar/Character")
        character_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        character_label.setStyleSheet("color: #e8eaed; padding: 5px;")
        character_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_column.addWidget(character_label)
        
        # Empty character box - Google Meet video style
        character_frame = QFrame()
        character_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #303134, stop:1 #202124);
                border: 2px solid #5f6368;
                border-radius: 12px;
                min-height: 300px;
                min-width: 350px;
            }
        """)
        left_column.addWidget(character_frame)
        left_column.addStretch()
        content_layout.addLayout(left_column)

        # Right Column - Empty space for visualization
        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        
        visualization_label = QLabel("📊 Live Visualization")
        visualization_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        visualization_label.setStyleSheet("color: #e8eaed; padding: 5px;")
        visualization_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_column.addWidget(visualization_label)
        
        # Empty visualization box - Google Meet style
        visualization_frame = QFrame()
        visualization_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #303134, stop:1 #202124);
                border: 2px solid #5f6368;
                border-radius: 12px;
                min-height: 450px;
                min-width: 550px;
            }
        """)
        right_column.addWidget(visualization_frame)
        content_layout.addLayout(right_column)

        container_layout.addLayout(content_layout)

        # Teacher's transcript display at bottom - Fixed positioning for full screen
        transcript_layout = QVBoxLayout()
        transcript_layout.setContentsMargins(0, 10, 0, 0)
        transcript_layout.setSpacing(5)
        
        transcript_title = QLabel("🎤 Live Captions")
        transcript_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        transcript_title.setStyleSheet("color: #e8eaed; padding: 8px; background-color: #303134; border-radius: 8px;")
        transcript_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        transcript_layout.addWidget(transcript_title)
        
        self.transcript_display = QLabel("Waiting for teacher's speech to appear here...")
        self.transcript_display.setFont(QFont("Segoe UI", 18))
        self.transcript_display.setStyleSheet("""
            QLabel {
                background-color: #303134;
                color: #e8eaed;
                border: 2px solid #5f6368;
                border-radius: 12px;
                padding: 20px;
                min-height: 80px;
                font-size: 18px;
            }
        """)
        self.transcript_display.setWordWrap(True)
        self.transcript_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        transcript_layout.addWidget(self.transcript_display)
        
        # Captions status
        captions_status = QLabel("Live captions will appear when the teacher speaks")
        captions_status.setFont(QFont("Segoe UI", 12))
        captions_status.setStyleSheet("color: #9aa0a6; padding: 5px;")
        captions_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        transcript_layout.addWidget(captions_status)
        
        container_layout.addLayout(transcript_layout)

        # Add stretch to push everything up and prevent pushing captions too high
        container_layout.addStretch(1)

        self.main_layout.addLayout(container_layout)

        # Start listening for Firebase updates
        self.start_firebase_listener()
        self.is_in_session = True

    def leave_session(self):
        """Leave the current session and return to join screen"""
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
            self.firebase_listener = None
        
        # Return to initial join interface
        self.setup_join_interface()

    def start_firebase_listener(self):
        """Start listening for transcript updates from Firebase"""
        self.firebase_listener = FirebaseListener(self.session_code)
        self.firebase_listener.new_transcript.connect(self.update_display)
        self.firebase_listener.connection_status.connect(self.update_connection_status)
        self.firebase_listener.start()

    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_label.setText("🟢 Connected")
            self.connection_label.setStyleSheet("color: #34a853; font-weight: bold; padding: 5px 10px; background-color: #303134; border-radius: 15px;")
        else:
            self.connection_label.setText("🔴 Connecting...")
            self.connection_label.setStyleSheet("color: #fbbc04; font-weight: bold; padding: 5px 10px; background-color: #303134; border-radius: 15px;")

    def update_display(self, transcript):
        """Update the transcript display with new transcript"""
        if transcript.strip():
            self.transcript_display.setText(transcript)
            self.transcript_display.setStyleSheet("""
                QLabel {
                    background-color: #1e3a5f;
                    color: #e8eaed;
                    border: 2px solid #4285f4;
                    border-radius: 12px;
                    padding: 20px;
                    min-height: 80px;
                    font-size: 18px;
                }
            """)

    def resizeEvent(self, event):
        """Handle window resize events for better full-screen experience"""
        super().resizeEvent(event)
        if self.is_in_session:
            # Adjust layout margins and spacing based on window size
            width = self.width()
            height = self.height()
            
            # You can add responsive adjustments here if needed
            # For example, adjust font sizes or spacing based on window dimensions

    def closeEvent(self, event):
        """Clean up when window closes"""
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
        event.accept()