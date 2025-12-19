import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget
from PyQt6.QtGui import QFont
from teacher_page import TeacherPage
from student_page import StudentPage
from mute_studentpage import MuteStudentPage

class MainInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Classroom - Real-time Transcription")
        self.setGeometry(100, 50, 1200, 800)

        layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        self.teacher_btn = QPushButton("Teacher")
        self.student_btn = QPushButton("Deaf Student")
        self.mute_student_btn = QPushButton("Mute Student")

        for btn in [self.teacher_btn, self.student_btn, self.mute_student_btn]:
            btn.setFont(QFont("Segoe UI", 14))
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)
        self.pages = QStackedWidget()
        self.pages.addWidget(TeacherPage())
        self.pages.addWidget(StudentPage())
        self.pages.addWidget(MuteStudentPage())
        layout.addWidget(self.pages)

        self.teacher_btn.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.student_btn.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.mute_student_btn.clicked.connect(lambda: self.pages.setCurrentIndex(2))

        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainInterface()
    window.show()
    sys.exit(app.exec())