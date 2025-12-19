import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
import json, random, requests, time
import win32com.client
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading

FIREBASE_URL = "https://hacks-f28bb-default-rtdb.firebaseio.com"

# Disable SSL warnings for better performance
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

model_path = "vosk-model-small-en-us-0.15"
model = Model(model_path)
recognizer = KaldiRecognizer(model, 16000)
audio_queue = queue.Queue()

# ==========================================================
# High-Performance Text-to-Speech Engine using win32com
# ==========================================================
class TextToSpeechEngine:
    def __init__(self):
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.word_queue = queue.Queue()
        self.is_speaking = False
        self.running = True
        self.processing_thread = None
        self.start_processing()
        
    def start_processing(self):
        """Start the background processing thread"""
        self.processing_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.processing_thread.start()
        
    def _process_queue(self):
        """Process the word queue in background thread"""
        while self.running:
            try:
                if not self.word_queue.empty() and not self.is_speaking:
                    word = self.word_queue.get_nowait()
                    self.is_speaking = True
                    try:
                        # Speak the word using win32com - this is non-blocking!
                        self.speaker.Speak(word, 1)  # 1 = async speak
                        # Wait a bit for the speech to complete
                        time.sleep(0.5 + len(word) * 0.1)  # Dynamic delay based on word length
                    except Exception as e:
                        print(f"TTS Error: {e}")
                    finally:
                        self.is_speaking = False
                time.sleep(0.05)  # Small delay to prevent CPU overload
            except:
                time.sleep(0.1)
        
    def speak(self, word):
        """Add word to queue for speaking - NON-BLOCKING"""
        if word.strip() and len(word.strip()) > 1:
            self.word_queue.put(word.strip())
            
    def stop(self):
        """Stop the TTS engine"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)

# ==========================================================
# Optimized Firebase Student Transcript Listener
# ==========================================================
class StudentTranscriptListener(QThread):
    new_transcript = pyqtSignal(str)
    connection_status = pyqtSignal(bool)
    
    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id
        self.running = True
        self.last_transcript = ""
        
    def run(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        while self.running:
            try:
                response = session.get(
                    f"{FIREBASE_URL}/sessions/{self.session_id}.json",
                    timeout=5,
                    verify=False
                )
                if response.status_code == 200:
                    self.connection_status.emit(True)
                    session_data = response.json() or {}
                    student_transcript = session_data.get("student_transcript", "")
                    
                    if student_transcript and student_transcript != self.last_transcript:
                        self.last_transcript = student_transcript
                        self.new_transcript.emit(student_transcript)
                else:
                    self.connection_status.emit(False)
                    
            except Exception as e:
                print(f"Firebase listener: {e}")
                self.connection_status.emit(False)
            
            QThread.msleep(300)
    
    def stop(self):
        self.running = False

class TeacherPage(QWidget):
    def __init__(self):
        super().__init__()
        self.listening = False
        self.stream = None
        self.session_code = None
        self.current_transcript = ""
        self.session_id = None
        self.student_listener = None
        self.tts_engine = TextToSpeechEngine()
        self.tts_enabled = True
        self.last_full_transcript = ""
        self.currently_speaking_word = ""
        
        # Create session with retry capability
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("🎓 Teacher Live Session")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        session_layout = QHBoxLayout()
        self.session_input = QLineEdit()
        self.session_input.setPlaceholderText("Enter session name (optional)")
        self.session_input.setFont(QFont("Segoe UI", 14))
        self.session_input.setStyleSheet(
            "background-color: #ecf0f1; padding: 8px; border-radius: 6px; border: 1px solid #bdc3c7;"
        )
        session_layout.addWidget(self.session_input)

        self.create_button = QPushButton("Create Session")
        self.create_button.setFont(QFont("Segoe UI", 14))
        self.create_button.setStyleSheet(
            "background-color: #3498db; color: white; padding: 8px; border-radius: 6px;"
        )
        self.create_button.clicked.connect(self.create_session)
        session_layout.addWidget(self.create_button)
        layout.addLayout(session_layout)

        self.session_label = QLabel("Session Code: -")
        self.session_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_label.setStyleSheet("color: #27ae60; padding: 5px;")
        layout.addWidget(self.session_label)

        # TTS Control Section
        tts_control_layout = QHBoxLayout()
        
        self.tts_button = QPushButton("🔊 TTS: ON")
        self.tts_button.setFont(QFont("Segoe UI", 12))
        self.tts_button.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 6px 12px; border-radius: 6px;"
        )
        self.tts_button.clicked.connect(self.toggle_tts)
        tts_control_layout.addWidget(self.tts_button)
        
        tts_control_layout.addStretch()
        
        self.session_button = QPushButton("Start Listening")
        self.session_button.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.session_button.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 12px; border-radius: 8px;"
        )
        self.session_button.clicked.connect(self.toggle_session)
        tts_control_layout.addWidget(self.session_button)
        
        layout.addLayout(tts_control_layout)

        self.status_label = QLabel("Session not started")
        self.status_label.setFont(QFont("Segoe UI", 14))
        self.status_label.setStyleSheet("color: #7f8c8d; padding: 5px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.firebase_status = QLabel("🔴 Firebase: Disconnected")
        self.firebase_status.setFont(QFont("Segoe UI", 12))
        self.firebase_status.setStyleSheet("color: #e74c3c; padding: 4px;")
        self.firebase_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.firebase_status)

        # Student transcript section
        student_section_label = QLabel("📝 Student's Live Signs (Spoken Instantly)")
        student_section_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        student_section_label.setStyleSheet("color: #2c3e50; margin-top: 10px;")
        student_section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(student_section_label)

        self.student_transcript_label = QLabel("Waiting for student to join and start signing...")
        self.student_transcript_label.setFont(QFont("Segoe UI", 14))
        self.student_transcript_label.setStyleSheet(
            "background-color: #fff3cd; padding: 15px; border-radius: 8px; border: 2px solid #ffeaa7; color: #856404; min-height: 80px;"
        )
        self.student_transcript_label.setWordWrap(True)
        self.student_transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.student_transcript_label)

        # TTS Status
        self.tts_status_label = QLabel("🔊 TTS: Ready - Words spoken instantly")
        self.tts_status_label.setFont(QFont("Segoe UI", 11))
        self.tts_status_label.setStyleSheet("color: #27ae60; padding: 6px; background-color: #d5f4e6; border-radius: 5px;")
        self.tts_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.tts_status_label)

        # Currently Speaking
        self.current_word_label = QLabel("")
        self.current_word_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.current_word_label.setStyleSheet("color: #e74c3c; padding: 10px;")
        self.current_word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.current_word_label)

        # Teacher speech section
        teacher_section_label = QLabel("🎤 Your Speech (Optional)")
        teacher_section_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        teacher_section_label.setStyleSheet("color: #7f8c8d; margin-top: 10px;")
        teacher_section_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(teacher_section_label)

        self.teacher_transcript_label = QLabel("Your speech will appear here if you speak...")
        self.teacher_transcript_label.setFont(QFont("Segoe UI", 12))
        self.teacher_transcript_label.setStyleSheet(
            "background-color: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #dee2e6; color: #6c757d; min-height: 50px;"
        )
        self.teacher_transcript_label.setWordWrap(True)
        self.teacher_transcript_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.teacher_transcript_label)

        self.setLayout(layout)
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_audio)
        self.timer.start(30)

    def toggle_tts(self):
        """Toggle text-to-speech on/off"""
        self.tts_enabled = not self.tts_enabled
        if self.tts_enabled:
            self.tts_button.setText("🔊 TTS: ON")
            self.tts_button.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 12px; border-radius: 6px;")
            self.tts_status_label.setText("🔊 TTS: Ready - Words spoken instantly")
            self.tts_status_label.setStyleSheet("color: #27ae60; padding: 6px; background-color: #d5f4e6; border-radius: 5px;")
        else:
            self.tts_button.setText("🔇 TTS: OFF")
            self.tts_button.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 12px; border-radius: 6px;")
            self.tts_status_label.setText("🔇 TTS: Disabled")
            self.tts_status_label.setStyleSheet("color: #e74c3c; padding: 6px; background-color: #fadbd8; border-radius: 5px;")

    def get_new_words(self, current_transcript):
        """Get only the new words that haven't been spoken yet"""
        if not self.last_full_transcript:
            return current_transcript.split()
        
        current_words = current_transcript.split()
        previous_words = self.last_full_transcript.split()
        
        # Find words that are new (at the end of the current transcript)
        new_words = []
        if len(current_words) > len(previous_words):
            new_words = current_words[len(previous_words):]
        
        return new_words

    def speak_new_words(self, transcript):
        """Speak only the new words from the student's transcript"""
        if not self.tts_enabled or not transcript.strip():
            return
            
        # Filter out initialization messages
        if any(phrase in transcript.lower() for phrase in [
            "student has not started", 
            "waiting for student", 
            "session created",
            "share the code"
        ]):
            return
        
        # Get new words
        new_words = self.get_new_words(transcript)
        self.last_full_transcript = transcript
        
        # Speak each new word immediately using the non-blocking TTS engine
        for word in new_words:
            if len(word) > 1:  # Only speak meaningful words
                self.currently_speaking_word = word
                self.current_word_label.setText(f"🔊 Speaking: {word}")
                self.tts_status_label.setText(f"Speaking: {word}")
                self.tts_status_label.setStyleSheet("color: #f39c12; padding: 6px; background-color: #fdebd0; border-radius: 5px;")
                
                # Add word to TTS queue (NON-BLOCKING)
                self.tts_engine.speak(word)
                
                # Update status after the word is spoken
                QTimer.singleShot(1000, self._clear_current_word)

    def _clear_current_word(self):
        """Clear the current word display"""
        self.current_word_label.setText("")
        if self.tts_enabled:
            self.tts_status_label.setText("🔊 TTS: Ready")
            self.tts_status_label.setStyleSheet("color: #27ae60; padding: 6px; background-color: #d5f4e6; border-radius: 5px;")

    def push_to_firebase(self, session_name):
        data = {
            "session_code": self.session_code,
            "session_name": session_name,
            "status": "active",
            "current_transcript": "",
            "student_transcript": "Student has not started signing yet...",
            "created_at": time.time(),
            "last_updated": time.time()
        }
        try:
            response = self.session.post(
                f"{FIREBASE_URL}/sessions.json", 
                json=data,
                timeout=10,
                verify=False
            )
            if response.status_code == 200:
                result = response.json()
                self.session_id = result['name']
                self.firebase_status.setText("🟢 Firebase: Connected")
                self.firebase_status.setStyleSheet("color: #27ae60;")
                self.start_student_listener()
                return True
            return False
        except Exception as e:
            print(f"Firebase push error: {e}")
            return False

    def start_student_listener(self):
        """Start listening for student transcript updates"""
        if self.session_id:
            self.student_listener = StudentTranscriptListener(self.session_id)
            self.student_listener.new_transcript.connect(self.update_student_transcript)
            self.student_listener.connection_status.connect(self.update_connection_status)
            self.student_listener.start()

    def update_student_transcript(self, transcript):
        """Update the display with student's transcript and speak new words"""
        self.student_transcript_label.setText(transcript)
        self.student_transcript_label.setStyleSheet(
            "background-color: #d1ecf1; padding: 15px; border-radius: 8px; border: 2px solid #bee5eb; color: #0c5460; min-height: 80px;"
        )
        
        # Speak only the new words from the student's transcript
        self.speak_new_words(transcript)

    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.firebase_status.setText("🟢 Firebase: Connected - Live")
            self.firebase_status.setStyleSheet("color: #27ae60;")
        else:
            self.firebase_status.setText("🔴 Firebase: Disconnected")
            self.firebase_status.setStyleSheet("color: #e74c3c;")

    def update_transcript_in_firebase(self, transcript):
        if not self.session_id:
            return False
        try:
            self.session.patch(
                f"{FIREBASE_URL}/sessions/{self.session_id}.json",
                json={"current_transcript": transcript, "last_updated": time.time()},
                timeout=5,
                verify=False
            )
            return True
        except:
            return False

    def cleanup_firebase_session(self):
        if self.session_id:
            try:
                self.session.delete(
                    f"{FIREBASE_URL}/sessions/{self.session_id}.json",
                    timeout=5,
                    verify=False
                )
            except:
                pass
        if self.student_listener:
            self.student_listener.stop()
            self.student_listener.wait(500)
        if self.tts_engine:
            self.tts_engine.stop()

    def create_session(self):
        self.session_code = str(random.randint(100000, 999999))
        session_name = self.session_input.text().strip() or "Live Session"
        self.session_label.setText(f"Session Code: {self.session_code}")
        if self.push_to_firebase(session_name):
            self.status_label.setText("✅ Session created - Ready")
            self.status_label.setStyleSheet("color: #27ae60;")
            self.student_transcript_label.setText("✅ Session created! Share the code with student.")

    def toggle_session(self):
        if not self.listening:
            self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        try:
            self.stream = sd.RawInputStream(
                samplerate=16000, 
                blocksize=4000,
                dtype="int16", 
                channels=1, 
                callback=self.audio_callback
            )
            self.stream.start()
            self.listening = True
            self.session_button.setText("Stop Listening")
            self.status_label.setText("🎧 Listening...")
        except Exception as e:
            QMessageBox.critical(self, "Audio Error", f"Failed to start audio:\n{str(e)}")

    def stop_listening(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.listening = False
        self.session_button.setText("Start Listening")
        self.status_label.setText("Session stopped")

    def audio_callback(self, indata, frames, time, status):
        audio_queue.put(bytes(indata))

    def process_audio(self):
        while not audio_queue.empty() and self.listening:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    self.current_transcript = text
                    self.teacher_transcript_label.setText(text)
                    self.update_transcript_in_firebase(text)

    def closeEvent(self, event):
        self.cleanup_firebase_session()
        event.accept()