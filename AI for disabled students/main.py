import sys
from app_window import MainInterface 
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget
from PyQt6.QtGui import QFont
 # import the main window class

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainInterface()
    window.show()
    sys.exit(app.exec())
