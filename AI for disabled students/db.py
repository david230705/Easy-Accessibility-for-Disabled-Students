import firebase_admin
from firebase_admin import credentials, db
import time

cred = credentials.Certificate("jsa.json")

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://hacks-f28bb-default-rtdb.firebaseio.com'
})

seen = set()

def check_messages():
    global seen
    ref = db.reference("chat")
    while True:
        messages = ref.get() or {}
        for msg_id, msg in messages.items():
            if msg_id not in seen:
                print(f"[{msg['sender']}] {msg['message']}")
                seen.add(msg_id)
        time.sleep(3)

if __name__ == "__main__":
    print("Listening for new messages...\n")
    check_messages()
