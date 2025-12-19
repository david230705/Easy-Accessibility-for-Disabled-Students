import sys
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QStackedWidget, QMessageBox, QScrollArea, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
import json
import random
import requests
import time

# ----------------------------
# Firebase Base URL
# ----------------------------
FIREBASE_URL = "https://hacks-f28bb-default-rtdb.firebaseio.com"

# ----------------------------
# Vosk Model Setup
# ----------------------------
model_path = "vosk-model-small-en-us-0.15"
model = Model(model_path)
recognizer = KaldiRecognizer(model, 16000)
audio_queue = queue.Queue()

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
# Teacher Page
# ==========================================================
class TeacherPage(QWidget):
    def __init__(self):
        super().__init__()
        self.listening = False
        self.stream = None
        self.session_code = None
        self.current_transcript = ""
        self.session_id = None

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("🎓 Teacher Live Session")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Session creation
        session_layout = QHBoxLayout()
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("Enter session name (optional)")
        self.session_input.setFont(QFont("Segoe UI", 16))
        self.session_input.setStyleSheet(
            "background-color: #ecf0f1; padding: 10px; border-radius: 8px; border: 1px solid #bdc3c7;"
        )
        session_layout.addWidget(self.session_input)

        self.create_button = QPushButton("Create Session")
        self.create_button.setFont(QFont("Segoe UI", 16))
        self.create_button.setStyleSheet(
            "background-color: #3498db; color: white; padding: 10px; border-radius: 8px;"
        )
        self.create_button.clicked.connect(self.create_session)
        session_layout.addWidget(self.create_button)
        layout.addLayout(session_layout)

        # Session code display
        self.session_label = QLabel("Session Code: -")
        self.session_label.setFont(QFont("Segoe UI", 20))
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_label.setStyleSheet("color: #27ae60;")
        layout.addWidget(self.session_label)

        # Start / Stop listening
        self.session_button = QPushButton("Start Listening")
        self.session_button.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.session_button.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 16px; border-radius: 12px;"
        )
        self.session_button.clicked.connect(self.toggle_session)
        layout.addWidget(self.session_button)

        # Status label
        self.status_label = QLabel("Session not started")
        self.status_label.setFont(QFont("Segoe UI", 18))
        self.status_label.setStyleSheet("color: #7f8c8d;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Firebase status
        self.firebase_status = QLabel("🔴 Firebase: Disconnected")
        self.firebase_status.setFont(QFont("Segoe UI", 14))
        self.firebase_status.setStyleSheet("color: #e74c3c;")
        self.firebase_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.firebase_status)

        # Current transcript display
        self.transcript_label = QLabel("Current speech will appear here...")
        self.transcript_label.setFont(QFont("Segoe UI", 14))
        self.transcript_label.setStyleSheet(
            "background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; color: #495057; min-height: 60px;"
        )
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.transcript_label)

        self.setLayout(layout)

        # Timer for Vosk audio
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_audio)
        self.timer.start(20)

  
    def push_to_firebase(self, session_name):
        """Create new session in Firebase"""
        data = {
            "session_code": self.session_code,
            "session_name": session_name,
            "status": "active",
            "current_transcript": "",
            "created_at": time.time(),
            "last_updated": time.time()
        }
        try:
            response = requests.post(f"{FIREBASE_URL}/sessions.json", json=data)
            if response.status_code == 200:
                result = response.json()
                self.session_id = result['name']  # Firebase generates unique ID
                self.firebase_status.setText("🟢 Firebase: Connected")
                self.firebase_status.setStyleSheet("color: #27ae60;")
                print(f"✅ Session created in Firebase: {self.session_id}")
                return True
            else:
                self.firebase_status.setText("🔴 Firebase: Failed to create session")
                print("⚠️ Firebase push failed:", response.text)
                return False
        except Exception as e:
            self.firebase_status.setText("🔴 Firebase: Connection error")
            print("🔥 Firebase error:", e)
            return False

    def update_transcript_in_firebase(self, transcript):
        """Update the current transcript in Firebase"""
        if not self.session_id:
            print("❌ No session ID available")
            return False
            
        try:
            update_data = {
                "current_transcript": transcript,
                "last_updated": time.time()
            }
            response = requests.patch(f"{FIREBASE_URL}/sessions/{self.session_id}.json", json=update_data)
            if response.status_code == 200:
                return True
            else:
                print("⚠️ Transcript update failed:", response.text)
                return False
        except Exception as e:
            print("Firebase update error:", e)
            return False

    def cleanup_firebase_session(self):
        """Clean up session from Firebase when done"""
        if self.session_id:
            try:
                requests.delete(f"{FIREBASE_URL}/sessions/{self.session_id}.json")
                print("✅ Session cleaned up from Firebase")
            except Exception as e:
                print("Firebase cleanup error:", e)


    def create_session(self):
        self.session_code = str(random.randint(100000, 999999))
        session_name = self.session_input.text().strip() or "Live Teaching Session"
        self.session_label.setText(f"Session Code: {self.session_code}")
        
        if self.push_to_firebase(session_name):
            self.status_label.setText("✅ Session created - Ready to start listening")
            self.status_label.setStyleSheet("color: #27ae60;")
        else:
            self.status_label.setText("❌ Failed to create session")
            self.status_label.setStyleSheet("color: #e74c3c;")

   
    def toggle_session(self):
        if not self.listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        try:
            self.stream = sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self.audio_callback
            )
            self.stream.start()
            self.listening = True
            self.session_button.setText("Stop Listening")
            self.session_button.setStyleSheet("background-color: #e74c3c; color: white; padding: 16px; border-radius: 12px;")
            self.status_label.setText("🎧 Listening... Speak now!")
            self.status_label.setStyleSheet("color: #27ae60;")
        except Exception as e:
            QMessageBox.critical(self, "Audio Error", f"Failed to start audio input:\n{str(e)}")

    def stop_listening(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.listening = False
        self.session_button.setText("Start Listening")
        self.session_button.setStyleSheet("background-color: #2ecc71; color: white; padding: 16px; border-radius: 12px;")
        self.status_label.setText("Session stopped")
        self.status_label.setStyleSheet("color: #7f8c8d;")

    def audio_callback(self, indata, frames, time, status):
        if status:
            print(status)
        audio_queue.put(bytes(indata))

    def process_audio(self):
        while not audio_queue.empty() and self.listening:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    print(f"🎤 Recognized: {text}")
                    self.current_transcript = text
                    self.transcript_label.setText(text)
                    
                    # Send to Firebase for students
                    if self.update_transcript_in_firebase(text):
                        self.firebase_status.setText("🟢 Firebase: Connected")
                        self.firebase_status.setStyleSheet("color: #27ae60;")
                    else:
                        self.firebase_status.setText("🔴 Firebase: Update failed")
                        self.firebase_status.setStyleSheet("color: #e74c3c;")
            else:
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "")
                if partial_text:
                    display_text = f"{self.current_transcript} {partial_text}" if self.current_transcript else partial_text
                    self.transcript_label.setText(display_text)

    def closeEvent(self, event):
        """Clean up when closing"""
        self.cleanup_firebase_session()
        event.accept()



class StudentPage(QWidget):
    def __init__(self):
        super().__init__()
        self.session_code = None
        self.firebase_listener = None
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel("  deaf Students ")
        self.title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.title)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter 6-digit Session Code")
        self.code_input.setFont(QFont("Segoe UI", 18))
        self.code_input.setStyleSheet(
            "background-color: #ecf0f1; padding: 12px; border-radius: 8px; border: 1px solid #bdc3c7;"
        )
        self.main_layout.addWidget(self.code_input)

        self.join_button = QPushButton("Join Session")
        self.join_button.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.join_button.setStyleSheet("background-color: #2980b9; color: white; padding: 12px; border-radius: 10px;")
        self.join_button.clicked.connect(self.check_session)
        self.main_layout.addWidget(self.join_button)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 16))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

        self.setLayout(self.main_layout)

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
                self.status_label.setStyleSheet("color: #e74c3c;")
                self.reset_join_button()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
            self.reset_join_button()

    def reset_join_button(self):
        self.join_button.setText("Join Session")
        self.join_button.setEnabled(True)

    def setup_live_session(self):
        """Setup the live session view with empty spaces for character and visualization"""
        # Clear existing layout
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Set white background for the entire page
        self.setStyleSheet("background-color: white;")

        # Main container for the layout
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Header section
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        session_label = QLabel(f"Session: {self.session_code}")
        session_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        session_label.setStyleSheet("color: #27ae60;")
        session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(session_label)

        # Connection status
        self.connection_label = QLabel("🟢 Connected to Teacher")
        self.connection_label.setFont(QFont("Segoe UI", 14))
        self.connection_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.connection_label)

        container_layout.addLayout(header_layout)

        # Main content area - Split into two columns
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 10, 20, 20)

        # Left Column - Empty space for character
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        
        # Empty character box
        character_frame = QFrame()
        character_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #bdc3c7;
                border-radius: 10px;
                min-height: 250px;
                min-width: 300px;
            }
        """)
        left_column.addWidget(character_frame)
        left_column.addStretch()
        content_layout.addLayout(left_column)

        # Right Column - Empty space for visualization
        right_column = QVBoxLayout()
        right_column.setSpacing(10)
        
        # Empty visualization box
        visualization_frame = QFrame()
        visualization_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #bdc3c7;
                border-radius: 10px;
                min-height: 450px;
                min-width: 550px;
            }
        """)
        right_column.addWidget(visualization_frame)
        content_layout.addLayout(right_column)

        container_layout.addLayout(content_layout)

        # Teacher's transcript display at bottom
        transcript_layout = QVBoxLayout()
        transcript_layout.setContentsMargins(20, 10, 20, 20)
        
        transcript_title = QLabel("🎤 Teacher's Live Speech")
        transcript_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        transcript_title.setStyleSheet("color: #2c3e50;")
        transcript_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        transcript_layout.addWidget(transcript_title)
        
        self.transcript_display = QLabel("Waiting for teacher's speech...")
        self.transcript_display.setFont(QFont("Segoe UI", 16))
        self.transcript_display.setStyleSheet("""
            background-color: #f8f9fa;
            color: #2c3e50;
            border: 2px solid #bdc3c7;
            border-radius: 10px;
            padding: 20px;
            min-height: 80px;
        """)
        self.transcript_display.setWordWrap(True)
        self.transcript_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        transcript_layout.addWidget(self.transcript_display)
        
        container_layout.addLayout(transcript_layout)

        self.main_layout.addLayout(container_layout)

        # Start listening for Firebase updates
        self.start_firebase_listener()

    def start_firebase_listener(self):
        """Start listening for transcript updates from Firebase"""
        self.firebase_listener = FirebaseListener(self.session_code)
        self.firebase_listener.new_transcript.connect(self.update_display)
        self.firebase_listener.connection_status.connect(self.update_connection_status)
        self.firebase_listener.start()

    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_label.setText("🟢 Connected to Teacher")
            self.connection_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.connection_label.setText("🔴 Connection Issues")
            self.connection_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def update_display(self, transcript):
        """Update the transcript display with new transcript"""
        if transcript.strip():
            self.transcript_display.setText(transcript)
            self.transcript_display.setStyleSheet("""
                background-color: #e8f6f3;
                color: #1a5276;
                border: 2px solid #27ae60;
                border-radius: 10px;
                padding: 20px;
                min-height: 80px;
                font-size: 16px;
            """)

    def closeEvent(self, event):
        """Clean up when window closes"""
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
        event.accept()



class MuteStudentPage(QWidget):
    def __init__(self):
        super().__init__()
        self.session_code = None
        self.firebase_listener = None
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel("🔇 Mute Student")
        self.title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.title)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter 6-digit Session Code")
        self.code_input.setFont(QFont("Segoe UI", 18))
        self.code_input.setStyleSheet(
            "background-color: #ecf0f1; padding: 12px; border-radius: 8px; border: 1px solid #bdc3c7;"
        )
        self.main_layout.addWidget(self.code_input)

        self.join_button = QPushButton("Join Session")
        self.join_button.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.join_button.setStyleSheet("background-color: #2980b9; color: white; padding: 12px; border-radius: 10px;")
        self.join_button.clicked.connect(self.check_session)
        self.main_layout.addWidget(self.join_button)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 16))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.status_label)

        self.setLayout(self.main_layout)

   
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
                self.status_label.setStyleSheet("color: #e74c3c;")
                self.reset_join_button()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {str(e)}")
            self.reset_join_button()

    def reset_join_button(self):
        self.join_button.setText("Join Session")
        self.join_button.setEnabled(True)

    def setup_live_session(self):
        """Setup the live session view with blank page"""
        # Clear existing layout
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Set white background for the entire page
        self.setStyleSheet("background-color: white;")

        # Main container for the layout
        container_layout = QVBoxLayout()
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Header section
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        session_label = QLabel(f"Session: {self.session_code}")
        session_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        session_label.setStyleSheet("color: #27ae60;")
        session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(session_label)

        # Connection status
        self.connection_label = QLabel("🟢 Connected to Teacher")
        self.connection_label.setFont(QFont("Segoe UI", 14))
        self.connection_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.connection_label)

        container_layout.addLayout(header_layout)

        # Blank content area
        blank_layout = QVBoxLayout()
        blank_layout.setContentsMargins(20, 20, 20, 20)
        
        # Blank space
        blank_frame = QFrame()
        blank_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #bdc3c7;
                border-radius: 10px;
                min-height: 500px;
            }
        """)
        blank_layout.addWidget(blank_frame)
        container_layout.addLayout(blank_layout)

        self.main_layout.addLayout(container_layout)

        # Start listening for Firebase updates (optional for mute student)
        self.start_firebase_listener()

    def start_firebase_listener(self):
        """Start listening for transcript updates from Firebase"""
        self.firebase_listener = FirebaseListener(self.session_code)
        self.firebase_listener.connection_status.connect(self.update_connection_status)
        self.firebase_listener.start()

    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_label.setText("🟢 Connected to Teacher")
            self.connection_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.connection_label.setText("🔴 Connection Issues")
            self.connection_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def closeEvent(self, event):
        """Clean up when window closes"""
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
        event.accept()



class MainInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Classroom - Real-time Transcription")
        self.setGeometry(100, 50, 1200, 800)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Buttons to switch between teacher, student, and mute student
        button_layout = QHBoxLayout()
        self.teacher_btn = QPushButton("👨‍🏫 Teacher")
        self.student_btn = QPushButton("👨‍🎓 Deaf Student")
        self.mute_student_btn = QPushButton("🔇 Mute Student")
        
        for btn in [self.teacher_btn, self.student_btn, self.mute_student_btn]:
            btn.setFont(QFont("Segoe UI", 14))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #34495e;
                    color: white;
                    padding: 12px 20px;
                    border-radius: 8px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #2c3e50;
                }
                QPushButton:pressed {
                    background-color: #1a252f;
                }
            """)

        self.teacher_btn.clicked.connect(lambda: self.switch_page(0))
        self.student_btn.clicked.connect(lambda: self.switch_page(1))
        self.mute_student_btn.clicked.connect(lambda: self.switch_page(2))

        button_layout.addWidget(self.teacher_btn)
        button_layout.addWidget(self.student_btn)
        button_layout.addWidget(self.mute_student_btn)
        layout.addLayout(button_layout)

        # Stacked pages
        self.pages = QStackedWidget()
        self.pages.addWidget(TeacherPage())
        self.pages.addWidget(StudentPage())
        self.pages.addWidget(MuteStudentPage())
        layout.addWidget(self.pages)

        self.setLayout(layout)

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainInterface()
    window.show()
    sys.exit(app.exec())