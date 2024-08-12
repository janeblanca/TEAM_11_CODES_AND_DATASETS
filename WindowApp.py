import os
import sys
import subprocess
import time
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QDialog, QVBoxLayout, QTextEdit, QDesktopWidget, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QPalette, QColor, QPixmap, QFont, QIcon, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
import comtypes
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
# Class for switch button
class PowerSwitch(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 30)
        self.setCheckable(True)
        self.setText("OFF")
        self.setStyleSheet(self.get_style(False))
        self.clicked.connect(self.toggle_style)

    def get_style(self, checked):
        return f"""
        QPushButton {{
            background-color: {'#6A6F4C' if checked else '#E5E5E5'};
            border: #5F6368;
            border-radius: 15px;
            color: {'#FFFFFF' if checked else '#5F6368'};
            font-weight: bold;
        }}
        """

    def toggle_style(self):
        self.setStyleSheet(self.get_style(self.isChecked()))
        self.setText("ON" if self.isChecked() else "OFF")
        self.parent().toggle_application(self.isChecked())

class NotifButton(QPushButton):
    state_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.state_changed.connect(self.write_log)
        self.toggled.connect(self.update_style)
        self.toggled.connect(self.emit_state_changed)
        self.update_style(self.isChecked())
    
    def emit_state_changed(self, checked):
        self.state_changed.emit(checked)
    
    def update_style(self, checked):
        self.setStyleSheet(self.get_style(checked))
        self.setText("ON" if checked else "OFF")
    
    def get_style(self, checked):
        return f"""
        QPushButton {{
            background-color: {'#92C292' if checked else '#E5E5E5'};
            border-radius: 15px;
            color: {'#FFFFFF' if checked else '#5F6368'};
            font-weight: bold;
        }}
        """
    
    def write_log(self, checked):
        try:
            log_dir = self.get_log_directory()
            log_file = os.path.join(log_dir, 'Notification.log')
            
            with open(log_file, 'w') as file: 
                file.write('1' if checked else '0')
        except Exception as e:
            print(f"Error writing log: {e}")

    @staticmethod
    def get_log_directory():
        appdata_dir = os.path.expanduser('~')
        log_dir = os.path.join(appdata_dir, 'AppData', 'Roaming', 'DontWristIt')
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
            
# Class for mute/unmute button
class MuteUnmuteButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 30)
        self.setCheckable(True)
        self.setText("Mute")
        self.setStyleSheet(self.get_style(False))
        self.clicked.connect(self.toggle_style)

    def get_style(self, checked):
        return f"""
        QPushButton {{
            background-color: {'#D0D0D0' if checked else '#92C292'};
            border-radius: 15px;
            color: {'#5F6368' if checked else '#FFFFFF'};
            font-weight: bold;
        }}
        """

    def toggle_style(self):
        self.setStyleSheet(self.get_style(self.isChecked()))
        self.setText("Unmute" if self.isChecked() else "Mute")
        if self.isChecked():
            self.parent().mute_application()
        else:
            self.parent().unmute_application()

class LogReaderThread(QThread):
    new_log_content = pyqtSignal(str)

    def __init__(self, log_file_path, parent=None):
        super().__init__(parent)
        self.log_file_path = log_file_path
        self.last_read_position = 0
        self.running = True

    def run(self):
        while self.running:
            if os.path.exists(self.log_file_path):
                current_modified_time = os.path.getmtime(self.log_file_path)
                with open(self.log_file_path, 'r') as file:
                    file.seek(self.last_read_position)
                    new_content = file.read()
                    if new_content:
                        self.last_read_position = file.tell()
                        self.new_log_content.emit(new_content)
            time.sleep(2)  # Adjust sleep interval to balance between responsiveness and performance

    def stop(self):
        self.running = False
        self.wait()

# Class for logs
class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Logs')
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.resize(parent.size())
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout()
        self.text_edit = QTextEdit(self)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        self.log_file_path = access_file.get_detection_log_path()
        self.log_reader_thread = LogReaderThread(self.log_file_path)
        self.log_reader_thread.new_log_content.connect(self.update_log_contents)
        self.log_reader_thread.start()

    def update_log_contents(self, contents):
        self.text_edit.append(contents)  # Append new content to the text edit
        self.text_edit.moveCursor(QTextCursor.End)

    def closeEvent(self, event):
        self.log_reader_thread.stop()
        super().closeEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.icon_path = os.path.join(os.path.dirname(__file__), 'icons')
        self.process = None
        self.start_application_thread = Thread(target=self.process)
        self.start_application_thread.daemon = True

        self.create_tray_icon()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Dont Wrist It')
        self.setFixedSize(500, 350)
        self.setPalette(QPalette(QColor("#828E82")))

        self.power = PowerSwitch(self)
        self.power.setGeometry(420, 20, 60, 30)

        self.updateStatusLabel()
        self.add_buttons_and_labels()

        desktop = QDesktopWidget()
        screenRect = desktop.screenGeometry()
        windowRect = self.geometry()
        self.move(screenRect.width() - windowRect.width() - 15, screenRect.height() - windowRect.height() - 105)

        # Override the close event to minimize to the tray
        self.setWindowIcon(QIcon(os.path.join(self.icon_path, resource_path('logo.png'))))
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def updateStatusLabel(self):
        
        self.create_square(15, 50, 370, 290, "#F9EBC7") 
        
        log_file_path = access_file.get_detection_log_path()
        try:
            with open(log_file_path, 'r') as file:
                lines = file.readlines()
                if lines:
                    latest_entry = lines[-1].strip()
                    if "Correct hand posture" in latest_entry:
                        self.create_square(23, 131, 170, 200, "#7E998D")
                        self.create_square(208, 130, 169, 200, "#B99470")
                        
                        self.createLabel("Correct Hand Posture", 32, 100, "#7E998D", 16, QFont.Bold, 170)
                        self.createLabel("Incorrect Hand Posture", 210, 100, "#B99470", 16, QFont.Bold, 170)
                        self.createPixmapLabel(resource_path('good1.png'), 20, 100, 150, 150)
                        self.createPixmapLabel(resource_path('good2.png'), 35, 200, 140, 140)
                        self.createPixmapLabel(resource_path('bad1.png'), 205, 100, 175, 175)
                        self.createPixmapLabel(resource_path('bad2.png'), 235, 210, 125, 125)
                        
                    elif "Incorrect hand posture" in latest_entry:
                        self.create_square(23, 131, 170, 200, "#B99470")
                        self.create_square(208, 130, 169, 200, "#B74443")
                        
                        self.createLabel("Correct Hand Posture", 32, 100, "#B99470", 16, QFont.Bold, 170)
                        self.createLabel("Incorrect Hand Posture", 210, 100, "#B74443", 16, QFont.Bold, 170)
                        self.createPixmapLabel(resource_path('good1.png'), 20, 100, 150, 150)
                        self.createPixmapLabel(resource_path('good2.png'), 35, 200, 140, 140)
                        self.createPixmapLabel(resource_path('bad1.png'), 205, 100, 175, 175)
                        self.createPixmapLabel(resource_path('bad2.png'), 235, 210, 125, 125)   
                    else:
                        self.create_square(23, 131, 170, 200, "#B99470")
                        self.create_square(208, 130, 169, 200, "#B99470")
                        
                        self.createLabel("Correct Hand Posture", 32, 100, "#B99470", 16, QFont.Bold, 170)
                        self.createLabel("Incorrect Hand Posture", 210, 100, "#B99470", 16, QFont.Bold, 170)
                        self.createPixmapLabel(resource_path('good1.png'), 20, 100, 150, 150)
                        self.createPixmapLabel(resource_path('good2.png'), 35, 200, 140, 140)
                        self.createPixmapLabel(resource_path('bad1.png'), 205, 100, 175, 175)
                        self.createPixmapLabel(resource_path('bad2.png'), 235, 210, 125, 125)
                        
                        
        except FileNotFoundError:
            print(f"File not found: {log_file_path}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

    def create_square(self, x, y, width, height, color):
        square = QLabel(self)
        square.setGeometry(x, y, width, height)
        square.setStyleSheet(f"background-color: {color}; border-radius: 7px;")


    def add_buttons_and_labels(self):
        self.createLabel("Don't Wrist It", 65, 9, "white", 15, QFont.Bold)
        self.createLabel("Hand Posture Guidelines", 50, 60, "black", 28, QFont.Bold, 400)
        self.createLabel("View History Logs", 395, 75, "white", 12, QFont.Bold)
        self.createLabel("Alert Cue", 415, 160, "white", 12, QFont.Bold)
        self.createLabel("Notification Cue", 400, 250, "white", 12, QFont.Bold)
        self.createPixmapLabel(resource_path('logo.png'), 15, 0, 50, 50)

        button = QPushButton('View Logs', self)
        button.setGeometry(395, 110, 100, 30)
        button.setStyleSheet("background-color: #EDE1D2; border-radius: 5px;")
        button.clicked.connect(self.show_log_dialog)

        self.mute_unmute_button = MuteUnmuteButton(self)
        self.mute_unmute_button.setGeometry(395, 190, 100, 30)
        
        self.notification_button = NotifButton(self)
        self.notification_button.setGeometry(395, 280, 100, 30)
        #self.notification_button.state_changed.connect(self.handle_state_change)
    
    #def handle_state_change(self, state):
    #    print(f'Notification state changed to: {"ON" if state else "OFF"}')

    def createLabel(self, text, x, y, color, size, weight, width=180):
        label = QLabel(text, self)
        label.setGeometry(x, y, width, 30)
        label.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {weight};")

    def createPixmapLabel(self, path, x, y, width, height):
        label = QLabel(self)
        pixmap = QPixmap(path).scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(pixmap)
        label.setGeometry(x, y, width, height)

    def show_log_dialog(self):
        self.log_dialog = LogDialog(self)
        self.log_dialog.show()

    def toggle_application(self, state):
        if state:
            self.start_application()
        else:
            self.stop_application()

    def start_application(self):
        exe_name = 'Don-t_Wrist_It.exe'
        exe_path = self.find_executable(exe_name)
        if exe_path:
            self.process = subprocess.Popen([exe_path])
            self.start_application_thread.start()
            print(f"Started '{exe_name}' at '{exe_path}'.")
        else:
            print(f"Executable '{exe_name}' not found.")

    def stop_application(self):
        if self.process is not None:
            exe_name = 'Don-t_Wrist_It.exe'
            try:
                subprocess.run(["taskkill", "/F", "/IM", exe_name], check=True)
                self.process = None
                print("All instances of the application terminated.")
            except subprocess.CalledProcessError as e:
                print(f"Failed to terminate application: {e}")
        else:
            print("No application is running.")

    def find_executable(self, exe_name, search_path="C:\\"):
        for root, dirs, files in os.walk(search_path):
            if exe_name in files:
                return os.path.join(root, exe_name)
        return None

    def set_application_volume(self, volume_level, target_application="Don-t_Wrist_It.exe"):
        try:
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name() == target_application:
                    volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                    volume.SetMasterVolume(volume_level, None)
                    break  # Stop after finding and setting volume for the target application
        except Exception as e:
            print(f"Failed to set volume: {str(e)}")

    def mute_application(self):
        self.set_application_volume(0.0, "Don-t_Wrist_It.exe")

    def unmute_application(self):
        self.set_application_volume(1.0, "Don-t_Wrist_It.exe")

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Don't Wrist It")
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Don't Wrist It",
            "Application was minimized to tray",
            QSystemTrayIcon.Information,
            2000
        )

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show()

class access_file:
    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
    @staticmethod
    def get_detection_log_path():
        user_home_dir = os.path.expanduser('~')
        return os.path.join(user_home_dir, 'AppData', 'Roaming', 'DontWristIt', 'detection.log')
    
    @staticmethod
    def follow_file(thefile):
        thefile.seek(0, os.SEEK_END) # End-of-Life
        while True:
            line = thefile.readline()
            if not line:
                time.sleep(0.1) # Sleep Briefly
                continue
            yield line

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
