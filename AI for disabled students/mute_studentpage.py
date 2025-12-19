import sys
import requests
import cv2
import numpy as np
from collections import deque
import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QMessageBox, QFrame, QTextEdit
)
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread

# ----------------------------
# Firebase Base URL
# ----------------------------
FIREBASE_URL = "https://hacks-f28bb-default-rtdb.firebaseio.com"

# ==========================================================
# Enhanced Sign Language Recognition Thread with Finger Detection
# ==========================================================
class EnhancedSignLanguageRecognition(QThread):
    frame_ready = pyqtSignal(QImage)
    prediction_ready = pyqtSignal(str)
    sentence_updated = pyqtSignal(str)
    
    def __init__(self, session_code):
        super().__init__()
        self.running = False
        self.detection_enabled = True
        self.cap = None
        self.session_code = session_code
        
        # Sign Language Settings
        self.OUTPUT_FILE = "mute_student_transcript.txt"
        self.frame_count = 0
        
        # Create / clear transcript file
        with open(self.OUTPUT_FILE, "w") as f:
            f.write("---- MUTE STUDENT SIGN LANGUAGE TRANSCRIPT ----\n")
        
        self.current_sentence = ""
        self.last_upload_time = 0
        self.upload_cooldown = 2  # seconds between uploads
        
        # Finger detection parameters
        self.finger_tips = [
            (4, 8, "INDEX"),    # Index finger
            (8, 12, "MIDDLE"),  # Middle finger  
            (12, 16, "RING"),   # Ring finger
            (16, 20, "PINKY"),  # Pinky finger
            (4, 20, "THUMB")    # Thumb (special case)
        ]
        
        # Gesture history for stability
        self.gesture_history = deque(maxlen=5)
        
    def toggle_detection(self):
        """Toggle sign language detection on/off"""
        self.detection_enabled = not self.detection_enabled
        
    def detect_fingers_skeletal(self, frame):
        """Detect fingers using convex hull and defect points (skeletal analysis)"""
        # Convert to HSV for skin detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Skin color range
        lower_skin = np.array([0, 20, 70], dtype=np.uint8)
        upper_skin = np.array([20, 255, 255], dtype=np.uint8)
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Morphological operations to clean mask
        kernel = np.ones((3, 3), np.uint8)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        skin_mask = cv2.medianBlur(skin_mask, 5)
        
        # Find contours
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return "NO_HAND", frame, 0.0, []
        
        # Get largest contour (hand)
        hand_contour = max(contours, key=cv2.contourArea)
        
        # Filter small contours (noise)
        if cv2.contourArea(hand_contour) < 5000:
            return "NO_HAND", frame, 0.0, []
        
        # Draw hand contour
        cv2.drawContours(frame, [hand_contour], -1, (0, 255, 0), 2)
        
        # Convex hull and defects for finger detection
        hull = cv2.convexHull(hand_contour, returnPoints=False)
        hull_points = cv2.convexHull(hand_contour)
        
        # Draw convex hull
        cv2.drawContours(frame, [hull_points], -1, (255, 0, 0), 2)
        
        # Get convexity defects
        defects = []
        finger_count = 0
        finger_tips = []
        
        if len(hull) > 3:
            try:
                defects = cv2.convexityDefects(hand_contour, hull)
            except:
                defects = None
        
        # Analyze defects to find fingers
        if defects is not None:
            for i in range(defects.shape[0]):
                s, e, f, d = defects[i, 0]
                start = tuple(hand_contour[s][0])
                end = tuple(hand_contour[e][0])
                far = tuple(hand_contour[f][0])
                
                # Calculate angles and distances
                a = np.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
                b = np.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
                c = np.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)
                
                # Angle between fingers
                angle = np.arccos((b**2 + c**2 - a**2) / (2 * b * c)) if b * c != 0 else 0
                angle = np.degrees(angle)
                
                # Filter valid finger defects
                if angle < 90 and d > 10000:  # Valid finger defect
                    finger_count += 1
                    cv2.circle(frame, far, 8, (0, 0, 255), -1)
                    cv2.line(frame, start, end, (255, 255, 0), 2)
                    
                    # Store finger tip positions
                    finger_tips.append((start, end, far))
        
        # Count fingers (add 1 for the base of fingers)
        total_fingers = min(finger_count + 1, 5)
        
        # Draw finger count
        cv2.putText(frame, f"Fingers: {total_fingers}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # Classify gesture based on finger count and hand shape
        gesture, confidence = self.classify_gesture_by_fingers(total_fingers, hand_contour)
        
        return gesture, frame, confidence, finger_tips
    
    def classify_gesture_by_fingers(self, finger_count, contour):
        """Classify gesture based on finger count and hand shape analysis"""
        # Calculate hand area and bounding box
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0
        
        # Gesture classification based on finger count
        if finger_count == 0:
            return "FIST", 0.9
        elif finger_count == 1:
            # Could be pointing or thumb
            if aspect_ratio > 1.5:
                return "POINT", 0.8
            else:
                return "THUMB_UP", 0.7
        elif finger_count == 2:
            return "VICTORY", 0.85  # Peace sign
        elif finger_count == 3:
            return "THREE_FINGERS", 0.8
        elif finger_count == 4:
            return "FOUR_FINGERS", 0.8
        elif finger_count == 5:
            return "OPEN_HAND", 0.9
        else:
            return "UNKNOWN", 0.5
    
    def map_gesture_to_word(self, gesture):
        """Map detected gestures to words"""
        gesture_mapping = {
            "FIST": "YES",
            "OPEN_HAND": "HELLO", 
            "VICTORY": "I HAVE A DOUBT ON THIS",
            "POINT": "THANKYOU",
            "THUMB_UP": "I HAVE A DOUBT ON THIS",
            "THREE_FINGERS": "HI",
            "FOUR_FINGERS": "CAN YOU REPEAT THIS",
            "NO_HAND": "NO"
        }
        return gesture_mapping.get(gesture, "")
    
    def upload_to_firebase(self, sentence, is_chat=False):
        """Upload sentence to Firebase in real-time"""
        current_time = time.time()
        if not is_chat and current_time - self.last_upload_time < self.upload_cooldown:
            return False
            
        try:
            # Find the session in Firebase
            response = requests.get(f"{FIREBASE_URL}/sessions.json")
            if response.status_code == 200:
                sessions = response.json() or {}
                session_id = None
                
                # Find our session
                for sid, session_data in sessions.items():
                    if session_data.get("session_code") == self.session_code:
                        session_id = sid
                        break
                
                if session_id:
                    # Update the student_transcript field
                    update_data = {
                        "student_transcript": sentence,
                        "last_updated": int(current_time)
                    }
                    
                    response = requests.patch(
                        f"{FIREBASE_URL}/sessions/{session_id}.json",
                        json=update_data
                    )
                    
                    if response.status_code == 200:
                        if not is_chat:
                            self.last_upload_time = current_time
                        return True
            return False
                
        except Exception as e:
            print(f"Firebase upload error: {e}")
            return False
    
    def run(self):
        self.running = True
        self.cap = cv2.VideoCapture(0)
        
        # Set camera resolution for better detection
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            return
        
        print("[INFO] Starting skeletal finger detection...")
        
        last_gesture = ""
        gesture_stability = 0
        required_stability = 5  # Reduced for more responsive detection
        last_word_time = 0
        word_cooldown = 2  # seconds between word additions
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Always process frame for display
            gesture, processed_frame, confidence, finger_tips = self.detect_fingers_skeletal(frame)
            
            current_time = time.time()
            detected_word = ""
            
            # Only process high-confidence detections if detection is enabled
            if self.detection_enabled and confidence > 0.6:
                if gesture == last_gesture:
                    gesture_stability += 1
                else:
                    gesture_stability = 1
                    last_gesture = gesture
                
                # Add word if gesture is stable and cooldown has passed
                if (gesture_stability >= required_stability and 
                    gesture != "NO_HAND" and 
                    gesture != "UNKNOWN" and
                    current_time - last_word_time >= word_cooldown):
                    
                    detected_word = self.map_gesture_to_word(gesture)
                    if detected_word:
                        self.current_sentence += detected_word + " "
                        last_word_time = current_time
                        
                        # Write to local file
                        with open(self.OUTPUT_FILE, "a") as f:
                            f.write(detected_word + " ")
                        
                        # Emit signals
                        self.prediction_ready.emit(detected_word)
                        self.sentence_updated.emit(self.current_sentence)
                        
                        # Real-time Firebase upload
                        if self.upload_to_firebase(self.current_sentence):
                            print(f"Uploaded to Firebase: {self.current_sentence}")
            
            # Add comprehensive text overlays
            status_text = "🟢 Detection: ACTIVE" if self.detection_enabled else "🔴 Detection: PAUSED"
            cv2.putText(processed_frame, status_text, (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if self.detection_enabled else (0, 0, 255), 2)
            
            cv2.putText(processed_frame, f"Gesture: {gesture}", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            cv2.putText(processed_frame, f"Confidence: {confidence:.2f}", (20, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            cv2.putText(processed_frame, f"Stability: {gesture_stability}/{required_stability}", (20, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            if detected_word:
                cv2.putText(processed_frame, f"Word: {detected_word}", (20, 170),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
            
            cv2.putText(processed_frame, f"Sentence: {self.current_sentence}", (20, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.putText(processed_frame, "Skeletal Finger Detection Active", (20, 450),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Draw finger analysis info
            cv2.putText(processed_frame, "Green: Hand Contour", (400, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.putText(processed_frame, "Blue: Convex Hull", (400, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            
            cv2.putText(processed_frame, "Red: Finger Joints", (400, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            # Convert frame to QImage for display in PyQt
            rgb_image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            self.frame_ready.emit(qt_image)
            
            self.frame_count += 1
        
        # Cleanup
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def stop_recognition(self):
        self.running = False
        if self.cap:
            self.cap.release()

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
            
            QThread.msleep(300)
    
    def stop(self):
        self.running = False

# ==========================================================
# Mute Student Page with Skeletal Finger Detection
# ==========================================================
class MuteStudentPage(QWidget):
    def __init__(self):
        super().__init__()
        self.session_code = None
        self.firebase_listener = None
        self.sign_language_thread = None
        self.current_sentence = ""
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel(" Mute Student - Skeletal Finger Detection")
        self.title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #1a73e8; padding: 20px; background-color: #f8f9fa;")
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
        self.status_label.setText("🔍 Checking session code...")
        self.status_label.setStyleSheet("color: #fbbc04; padding: 10px;")

        try:
            response = requests.get(f"{FIREBASE_URL}/sessions.json", timeout=10)
            if response.status_code != 200:
                self.show_error("Failed to connect to database")
                return

            data = response.json() or {}
            session_found = False
            
            for session_id, session_data in data.items():
                if session_data.get("session_code") == code:
                    session_found = True
                    break

            if session_found:
                self.session_code = code
                self.status_label.setText("✅ Session found! Joining...")
                self.status_label.setStyleSheet("color: #34a853; padding: 10px;")
                QTimer.singleShot(800, self.setup_live_session)
            else:
                self.show_error("Session not found. Please check the code")

        except Exception as e:
            self.show_error(f"Connection error: {str(e)}")

    def show_error(self, message):
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: #ea4335; padding: 10px;")
        self.reset_join_button()

    def reset_join_button(self):
        self.join_button.setText("Join Session")
        self.join_button.setEnabled(True)

    def setup_live_session(self):
        """Setup the live session with skeletal finger detection"""
        # Clear existing layout
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Set dark background for session screen
        self.setStyleSheet("background-color: #202124;")

        # Main container
        container = QVBoxLayout()
        container.setSpacing(10)
        container.setContentsMargins(20, 15, 20, 15)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        
        # Session info
        session_info = QVBoxLayout()
        session_title = QLabel("Mute Student - Skeletal Finger Detection")
        session_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        session_title.setStyleSheet("color: white;")
        session_info.addWidget(session_title)
        
        session_code = QLabel(f"Session: {self.session_code}")
        session_code.setFont(QFont("Segoe UI", 12))
        session_code.setStyleSheet("color: #9aa0a6;")
        session_info.addWidget(session_code)
        
        header.addLayout(session_info)
        header.addStretch()

        # Connection status
        self.connection_label = QLabel("🟢 Connected")
        self.connection_label.setFont(QFont("Segoe UI", 12))
        self.connection_label.setStyleSheet("""
            color: #34a853; 
            font-weight: bold; 
            padding: 5px 10px; 
            background-color: #303134; 
            border-radius: 15px;
        """)
        header.addWidget(self.connection_label)

        # Leave button
        leave_btn = QPushButton("Leave Session")
        leave_btn.setFont(QFont("Segoe UI", 12))
        leave_btn.setStyleSheet("""
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
        leave_btn.clicked.connect(self.leave_session)
        header.addWidget(leave_btn)

        container.addLayout(header)

        # Main content area
        content = QHBoxLayout()
        content.setSpacing(20)
        content.setContentsMargins(0, 10, 0, 10)

        # Left panel - Camera feed
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        camera_label = QLabel("📷 Skeletal Finger Detection")
        camera_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        camera_label.setStyleSheet("color: #e8eaed; padding: 5px;")
        camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(camera_label)
        
        # Camera display frame
        self.camera_frame = QLabel()
        self.camera_frame.setStyleSheet("""
            QLabel {
                background-color: #303134;
                border: 2px solid #5f6368;
                border-radius: 12px;
                min-height: 400px;
                min-width: 500px;
            }
        """)
        self.camera_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_frame.setText("Starting skeletal detection...")
        self.camera_frame.setStyleSheet("""
            QLabel {
                background-color: #303134;
                color: #9aa0a6;
                border: 2px solid #5f6368;
                border-radius: 12px;
                min-height: 400px;
                min-width: 500px;
                font-size: 16px;
            }
        """)
        left_panel.addWidget(self.camera_frame)
        
        # Detection control button
        self.detection_button = QPushButton("⏸️ Pause Detection")
        self.detection_button.setFont(QFont("Segoe UI", 12))
        self.detection_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                padding: 10px;
                border-radius: 8px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.detection_button.clicked.connect(self.toggle_detection)
        left_panel.addWidget(self.detection_button)
        
        left_panel.addStretch()
        content.addLayout(left_panel)

        # Right panel - Recognition output and chat
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)
        
        # Current prediction
        prediction_label = QLabel("🎯 Detected Word")
        prediction_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        prediction_label.setStyleSheet("color: #e8eaed; padding: 5px;")
        right_panel.addWidget(prediction_label)
        
        self.prediction_display = QLabel("Show hand to camera...")
        self.prediction_display.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.prediction_display.setStyleSheet("""
            QLabel {
                background-color: #303134;
                color: #e8eaed;
                border: 2px solid #5f6368;
                border-radius: 12px;
                padding: 20px;
                min-height: 80px;
                font-size: 24px;
            }
        """)
        self.prediction_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(self.prediction_display)
        
        # Sentence display
        sentence_label = QLabel("📝 Live Sentence (Auto-upload to Teacher)")
        sentence_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        sentence_label.setStyleSheet("color: #e8eaed; padding: 5px;")
        right_panel.addWidget(sentence_label)
        
        self.sentence_display = QLabel("Sentence will auto-upload to teacher...")
        self.sentence_display.setFont(QFont("Segoe UI", 16))
        self.sentence_display.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: #e8eaed;
                border: 2px solid #4285f4;
                border-radius: 12px;
                padding: 15px;
                min-height: 100px;
            }
        """)
        self.sentence_display.setWordWrap(True)
        self.sentence_display.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_panel.addWidget(self.sentence_display)
        
        # Upload status
        self.upload_status = QLabel("🟢 Real-time Firebase upload active")
        self.upload_status.setFont(QFont("Segoe UI", 12))
        self.upload_status.setStyleSheet("color: #34a853; padding: 10px; background-color: #303134; border-radius: 8px;")
        self.upload_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(self.upload_status)
        
        # Chat Section
        chat_label = QLabel("💬 Text Chat with Teacher")
        chat_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        chat_label.setStyleSheet("color: #e8eaed; padding: 5px; margin-top: 10px;")
        right_panel.addWidget(chat_label)
        
        # Chat input area
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message to teacher...")
        self.chat_input.setFont(QFont("Segoe UI", 12))
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #303134;
                color: white;
                padding: 12px;
                border-radius: 8px;
                border: 2px solid #5f6368;
            }
        """)
        chat_input_layout.addWidget(self.chat_input)
        
        self.send_button = QPushButton("Send")
        self.send_button.setFont(QFont("Segoe UI", 12))
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4285f4;
                color: white;
                padding: 12px 20px;
                border-radius: 8px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3367d6;
            }
        """)
        self.send_button.clicked.connect(self.send_chat_message)
        chat_input_layout.addWidget(self.send_button)
        
        right_panel.addLayout(chat_input_layout)
        
        # Gesture guide
        gesture_guide = QLabel(
            "Gesture Guide:\n"
            "• 👊 Fist (0 fingers) → 'YES'\n"
            "• 🖐️ Open Hand (5 fingers) → 'HELLO'\n"
            "• ✌️ Victory (2 fingers) → 'I HAVE A DOUBT ON THIS'\n"
            "• 👆 Pointing (1 finger) → 'THANK YOU'\n"
            "• 👍 Thumb Up → 'I HAVE A DOUBT ON THIS'\n"
            "• 🤟 Three Fingers → 'HI'\n"
            "• 🖖 Four Fingers → 'CAN YOU REPEAT THIS'"
        )
        gesture_guide.setFont(QFont("Segoe UI", 12))
        gesture_guide.setStyleSheet("color: #9aa0a6; padding: 10px; background-color: #303134; border-radius: 8px;")
        gesture_guide.setWordWrap(True)
        right_panel.addWidget(gesture_guide)
        
        content.addLayout(right_panel)
        container.addLayout(content)

        self.main_layout.addLayout(container)

        # Start skeletal finger detection
        self.start_sign_language_recognition()
        
        # Start Firebase listener
        self.start_firebase_listener()

    def toggle_detection(self):
        """Toggle sign language detection on/off"""
        if self.sign_language_thread:
            self.sign_language_thread.toggle_detection()
            if self.sign_language_thread.detection_enabled:
                self.detection_button.setText("⏸️ Pause Detection")
                self.detection_button.setStyleSheet("""
                    QPushButton {
                        background-color: #f39c12;
                        color: white;
                        padding: 10px;
                        border-radius: 8px;
                        border: none;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #e67e22;
                    }
                """)
                self.upload_status.setText("🟢 Detection ACTIVE - Real-time upload active")
            else:
                self.detection_button.setText("▶️ Resume Detection")
                self.detection_button.setStyleSheet("""
                    QPushButton {
                        background-color: #27ae60;
                        color: white;
                        padding: 10px;
                        border-radius: 8px;
                        border: none;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #219a52;
                    }
                """)
                self.upload_status.setText("⏸️ Detection PAUSED - Camera still active")

    def send_chat_message(self):
        """Send chat message to teacher"""
        message = self.chat_input.text().strip()
        if not message:
            return
            
        if self.sign_language_thread:
            # Upload chat message immediately
            if self.sign_language_thread.upload_to_firebase(f"[CHAT]: {message}", is_chat=True):
                self.upload_status.setText("✅ Chat message sent to teacher!")
                self.chat_input.clear()
                
                # Show confirmation
                QTimer.singleShot(2000, lambda: self.upload_status.setText("🟢 Real-time Firebase upload active"))

    def start_sign_language_recognition(self):
        """Start the skeletal finger detection thread"""
        self.sign_language_thread = EnhancedSignLanguageRecognition(self.session_code)
        self.sign_language_thread.frame_ready.connect(self.update_camera_frame)
        self.sign_language_thread.prediction_ready.connect(self.update_prediction)
        self.sign_language_thread.sentence_updated.connect(self.update_sentence)
        self.sign_language_thread.start()

    def update_camera_frame(self, image):
        """Update the camera display with new frame"""
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(500, 400, Qt.AspectRatioMode.KeepAspectRatio)
        self.camera_frame.setPixmap(scaled_pixmap)

    def update_prediction(self, word):
        """Update the prediction display"""
        self.prediction_display.setText(word)
        self.prediction_display.setStyleSheet("""
            QLabel {
                background-color: #1e3a5f;
                color: #e8eaed;
                border: 2px solid #4285f4;
                border-radius: 12px;
                padding: 20px;
                min-height: 80px;
                font-size: 24px;
            }
        """)

    def update_sentence(self, sentence):
        """Update the sentence display"""
        self.current_sentence = sentence
        self.sentence_display.setText(sentence)
        self.upload_status.setText("✅ Sentence auto-uploaded to teacher!")
        self.upload_status.setStyleSheet("color: #34a853; padding: 10px; background-color: #303134; border-radius: 8px;")

    def start_firebase_listener(self):
        """Start listening for transcript updates from Firebase"""
        self.firebase_listener = FirebaseListener(self.session_code)
        self.firebase_listener.connection_status.connect(self.update_connection_status)
        self.firebase_listener.start()

    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_label.setText("🟢 Connected to Teacher")
            self.connection_label.setStyleSheet("color: #34a853; font-weight: bold; padding: 5px 10px; background-color: #303134; border-radius: 15px;")
        else:
            self.connection_label.setText("🔴 Connection Issues")
            self.connection_label.setStyleSheet("color: #fbbc04; font-weight: bold; padding: 5px 10px; background-color: #303134; border-radius: 15px;")

    def leave_session(self):
        """Leave session and return to join screen"""
        # Stop sign language recognition
        if self.sign_language_thread:
            self.sign_language_thread.stop_recognition()
            self.sign_language_thread.wait(1000)
            self.sign_language_thread = None
        
        # Stop Firebase listener
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
            self.firebase_listener = None
        
        # Return to initial join interface
        self.__init__()
        self.show()

    def closeEvent(self, event):
        """Clean up when window closes"""
        if self.sign_language_thread:
            self.sign_language_thread.stop_recognition()
            self.sign_language_thread.wait(1000)
        
        if self.firebase_listener:
            self.firebase_listener.stop()
            self.firebase_listener.wait(1000)
        
        event.accept()