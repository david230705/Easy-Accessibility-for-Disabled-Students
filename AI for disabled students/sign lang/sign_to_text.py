import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import os

# === SETTINGS ===
OUTPUT_FILE = "transcript.txt"
SEQUENCE_LENGTH = 20
CONFIDENCE_THRESHOLD = 0.8
REPEAT_THRESHOLD = 3

# Define basic words for demo
BASIC_WORDS = ["HELLO", "YES", "NO", "THANK YOU", "STOP", "GOOD", "OK", "COME"]

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# --- Fake demo model ---
def fake_model_predict(sequence):
    """
    Simulated predictions for demo purposes:
    Uses simple heuristics on hand openness and landmarks.
    """
    last_frame = sequence[-1]
    hand_openness = sum(last_frame[0::3])  # sum x-coordinates

    if hand_openness > 5.5:
        return "HELLO", 0.95
    elif hand_openness < 2:
        return "YES", 0.9
    elif 2 <= hand_openness < 3:
        return "NO", 0.85
    elif 3 <= hand_openness < 4:
        return "THANK YOU", 0.85
    elif 4 <= hand_openness < 5:
        return "STOP", 0.85
    elif 5 <= hand_openness < 5.3:
        return "GOOD", 0.85
    elif 5.3 <= hand_openness < 5.5:
        return "OK", 0.85
    else:
        return "COME", 0.85

# Create / clear transcript file
with open(OUTPUT_FILE, "w") as f:
    f.write("---- SIGN LANGUAGE TRANSCRIPT ----\n")

# === REALTIME CAPTURE ===
cap = cv2.VideoCapture(0)
sequence = deque(maxlen=SEQUENCE_LENGTH)
sentence = ""
last_prediction = ""
repeat_count = 0

print("[INFO] Starting webcam. Press 'q' to quit.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    image = cv2.flip(frame, 1)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)

    hand_landmarks = []
    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            for lm in handLms.landmark:
                hand_landmarks.extend([lm.x, lm.y, lm.z])
            mp_drawing.draw_landmarks(image, handLms, mp_hands.HAND_CONNECTIONS)

        if len(hand_landmarks) < 63:
            hand_landmarks += [0] * (63 - len(hand_landmarks))
        else:
            hand_landmarks = hand_landmarks[:63]

        sequence.append(hand_landmarks)

        if len(sequence) == SEQUENCE_LENGTH:
            pred_class, conf = fake_model_predict(sequence)

            if conf > CONFIDENCE_THRESHOLD:
                if pred_class == last_prediction:
                    repeat_count += 1
                else:
                    repeat_count = 0
                last_prediction = pred_class

                if repeat_count == REPEAT_THRESHOLD:
                    sentence += pred_class + " "
                    with open(OUTPUT_FILE, "a") as f:
                        f.write(pred_class + " ")

                cv2.putText(image, f"{pred_class}", (30, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
            else:
                last_prediction = ""
                repeat_count = 0
    else:
        cv2.putText(image, "No hand detected", (30, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        last_prediction = ""
        repeat_count = 0

    cv2.imshow("Sign to Text - Live", image)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print(f"[INFO] Session ended. Transcript saved to {os.path.abspath(OUTPUT_FILE)}")
