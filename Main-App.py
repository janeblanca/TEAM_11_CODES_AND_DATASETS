import sys
import time
from datetime import datetime
import logging
import cv2
import numpy as np
import winsound
import schedule
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialogButtonBox
import mediapipe as mp
import os
import wmi
import joblib
import warnings
import threading
from plyer import notification

import numpy as py

# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module='google.protobuf.symbol_daxbase')
warnings.filterwarnings("ignore", category=UserWarning, module='sklearn.base')

# Function to get the path to the APPDATA directory
def get_appdata_path():
    appdata_dir = os.getenv('APPDATA') or os.path.expanduser('~')
    log_dir = os.path.join(appdata_dir, 'DontWristIt')
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

# Configure logging to the APPDATA directory
log_file_path = os.path.join(get_appdata_path(), 'camera.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure logging for detection results
detection_log_file_path = os.path.join(get_appdata_path(), 'detection.log')
detection_logger = logging.getLogger('detection')
detection_handler = logging.FileHandler(detection_log_file_path)
detection_handler.setLevel(logging.DEBUG)
detection_formatter = logging.Formatter('%(asctime)s - %(message)s')
detection_handler.setFormatter(detection_formatter)
detection_logger.addHandler(detection_handler)

# Function to get absolute path to resource
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller creates this variable
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class HandLandmarksDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def extract_landmarks(self, frame):
        results = self.process_frame(frame)
        landmarks_data = []

        if results.multi_hand_landmarks:
            num_hands = min(2, len(results.multi_hand_landmarks))
            for hand_idx in range(num_hands):
                hand_landmarks = results.multi_hand_landmarks[hand_idx]
                for idx, landmark in enumerate(hand_landmarks.landmark):
                    if idx in [0, 1, 2, 5, 9, 13, 17]:
                        landmarks_data.extend([landmark.x, landmark.y, landmark.z if hasattr(landmark, 'z') else None])
                        
        return landmarks_data
        """indices_to_extract = [0, 1, 2, 5, 9, 13, 17]
        landmark_names = {
            0: 'wrist',
            1: 'thumb_cmc',
            2: 'thumb_mcp',
            5: 'index_finger_mcp',
            9: 'middle_finger_mcp',
            13: 'ring_finger_mcp',
            17: 'pinky_mcp',
        }
        combined_landmarks = []

        if results.multi_hand_landmarks:
            num_hands = min(2, len(results.multi_hand_landmarks))

            for hand_idx in range(num_hands):
                landmarks = []
                hand_landmarks = results.multi_hand_landmarks[hand_idx]
                for landmark in hand_landmarks.landmark:
                    landmark_data = [landmark.x, landmark.y]
                    if hasattr(landmark, 'z'):
                        landmark_data.append(landmark.z)
                    landmarks.extend(landmark_data)
                combined_landmarks.extend(landmarks)

        return combined_landmarks"""

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self.mp_hands.process(frame_rgb)

    def release_resources(self):
        self.mp_hands.close()

class Audio:
    def __init__(self):
        pass

    def speak_text(self):
        winsound.PlaySound(resource_path("audio3.wav"), winsound.SND_FILENAME)
    
    def speak_text2(self):
        winsound.PlaySound(resource_path("audio2.wav"), winsound.SND_FILENAME)

    def speak_text3(self):
        winsound.PlaySound(resource_path("audio.wav"), winsound.SND_FILENAME)
    

class Camera:
    def __init__(self):
        self.camera = None
        self.landmarks_detector = HandLandmarksDetector()
        self.model = joblib.load(resource_path('model/final rf.joblib'))
        self.running = True
        self.notifications_enabled = False
        self.log_file_path = os.path.expanduser(r'~\\AppData\\Roaming\\DontWristIt\\Notification.log')
        self.start_following_log()
        self.audio = Audio()
        self.app = QApplication(sys.argv)
        self.schedule_thread = Thread(target=self.stime)
        self.schedule_thread.daemon = True  # Daemonize the thread so it exits when the main thread does
        self.schedule_thread.start()
        self.notification_flag = False
        self.last_popup_time = time.time()
        self.start_time = time.time()  # Initialize start_time here with current time
        
        self.show_start_notification()

    def process_log_line(self, line):
        if line == '0':
            self.notifications_enabled = False
            #print(f'New log value: {line}')
        elif line == '1':
            self.notifications_enabled = True
            #print(f'New log value: {line}')
        else:
            print(f'Unexpected log value: {line}')

    def follow_log(self, file_path):
        last_line = None
        try:
            while True:
                with open(file_path, 'r') as log_file:
                    current_line = log_file.readline().strip()
                    if current_line != last_line:
                        last_line = current_line
                        self.process_log_line(current_line)
                time.sleep(0.1)
        except FileNotFoundError:
            print(f"The log file at {file_path} was not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def start_following_log(self):
        log_thread = threading.Thread(target=self.follow_log, args=(self.log_file_path,), daemon=True)
        log_thread.start()
        
    def show_start_notification(self):
        dialog = QMessageBox()
        dialog.setWindowTitle("Don't Wrist It")
        dialog.setText("The background application will start. Do you want to continue?")
        dialog.setIcon(QMessageBox.Question)
        dialog.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        result = dialog.exec_()
        if result == QMessageBox.Cancel:
            self.running = False
        else:
            self.initialize_camera()
    
    def check_break_time(self):
        elapsed_time = time.time() - self.start_time
        logging.debug(f"Elapsed time: {elapsed_time} seconds")
        if elapsed_time >= 2 * 60 * 60:  # Check if 2 hours have passed
            self.break_notif1("Take a Break", "You have been working for 2 hours. Please take a 5-minute break.")
            self.break_duration()  # Start the break duration countdown
            self.start_time = time.time()  # Reset the start time after the notification
    
    def break_duration(self):
        logging.info("Starting 5-minute break countdown.")
        time.sleep(5 * 60)  # Sleep for 5 minutes
        self.break_notif2("Break Over", "Your 5-minute break is over. Please resume work.")
        logging.info("5-minute break is over.")
        self.start_time = time.time()  # Start counting 2 hours again after the break

    def notify_take_break(self):
        notification.notify(
            title="Take a Break",
            message="You have been working for 2 hours. Please take a 5-minute break.",
            app_name="Don't Wrist It",
            timeout=10
        )
    
    def list_usb_cameras(self):
        c = wmi.WMI()
        usb_cameras = []
        for usb in c.Win32_PnPEntity():
            if 'USB' in usb.PNPDeviceID:
                name = getattr(usb, 'Name', '').lower()
                description = getattr(usb, 'Description', '').lower()
                if 'camera' in name or 'webcam' in name or 'camera' in description or 'webcam' in description:
                    usb_cameras.append(usb)
                    logging.debug(f"Detected USB Camera: {name}, {description}")
        logging.debug(f"Total USB Cameras Detected: {len(usb_cameras)}")
        return usb_cameras

    def initialize_camera(self):
        while self.running:
            usb_cameras = self.list_usb_cameras()
            if usb_cameras:
                logging.debug("USB camera(s) detected. Selecting USB camera.")
                # Attempt to open each camera index to find an external camera
                for index in range(1, 10):
                    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                    if camera.isOpened():
                        self.camera = camera
                        logging.debug(f"Camera opened at index {index}")
                        self.start()
                        return
                    else:
                        logging.debug(f"Failed to open camera at index {index}")
                    camera.release()  # Release camera if not opened successfully
            else:
                logging.debug("No USB camera detected. Please insert an external camera.")
                time.sleep(5)  # Wait for 5 seconds before checking again

    def stime(self):
        schedule.every(10).seconds.do(self.check_camera_and_notify)
        schedule.every(2).hours.do(self.notify_take_break)
    
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    def check_camera_and_notify(self):
        if self.camera is None or not self.camera.isOpened():
            self.cam_notif("No USB camera detected.", "Please insert an external camera.")
            if not self.notification_flag:
                self.notification_flag = True
                
    def show_notification(self):
        dialog = QMessageBox()
        dialog.setWindowTitle("External Camera Alert")
        dialog.setText("No external camera found, Please Insert an External Camera.")
        dialog.setIcon(QMessageBox.Question)
        dialog.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        result = dialog.exec_()
        self.notification_flag = False
        if result == QDialogButtonBox.Ok:
            self.initialize_camera()
        else:
            self.running = False
        
    def start(self):
        def notify_and_speak(message, notification_func, speak_func):
            notification_func(message, "Align both hands in the camera")
            speak_func()
        
        def inc_notif_and_speak(message, notification_fun, speak_fun):
            notification_fun(message, "Correct your posture immediately!")
            speak_fun()

        try:
            while self.running:
                if self.camera is None or not self.camera.isOpened():
                    time.sleep(1)
                    continue

                ret, frame = self.camera.read()
                if not ret:
                    logging.error("Failed to capture image")
                    break

                # Save the captured frame to a folder
                image_dir = os.path.join(get_appdata_path(), 'captured_images')
                os.makedirs(image_dir, exist_ok=True)  # Ensure directory exists

                # Extract landmarks
                landmarks = self.landmarks_detector.extract_landmarks(frame)
                landmarks_arr = np.array(landmarks)
                # print("Total Keypoints: ", landmarks_arr.shape)

                if landmarks_arr.shape == (0,):
                    logging.warning("No hands detected. Align both hands in the camera")
                    self.save_image_and_log(frame, image_dir, "Test_image", "No hands detected")
                    # print("No hands detected")
                    if self.process_log_line:
                        Thread(target=notify_and_speak, args=("No hands detected.", self.align_notif, self.audio.speak_text2)).start()
                        time.sleep(3)
                
                elif landmarks_arr.shape == (21,):
                    logging.warning("One hand is detected. Align both hands in the camera")
                    self.save_image_and_log(frame, image_dir, "Test_image", "One hand detected")
                    # print("One hand detected")
                    #self.flg = True
                    if self.process_log_line:
                        Thread(target=notify_and_speak, args=("One hand is detected.", self.oneh_notif, self.audio.speak_text)).start()
                        time.sleep(3)

                elif landmarks_arr.shape == (42,):
                    reshape_landmarks = landmarks_arr.reshape(1, -1)
                    try:
                        classify = self.model.predict_proba(reshape_landmarks)
                        if classify[0, 1] > 0.5:
                            logging.info("Correct position")
                            self.duration = 0
                            self.save_image_and_log(frame, image_dir, "Test_image", "Correct hand posture")
                            # print("Correct Hand Posture")
                        else:
                            logging.info("Incorrect position")
                            self.save_image_and_log(frame, image_dir, "Test_image", "Incorrect hand posture detected")
                            # print("Incorrect Hand Posture")
                            if self.process_log_line:
                                Thread(target=inc_notif_and_speak, args=("Incorrect hand posture detected.", self.inc_notif, self.audio.speak_text3)).start()
                                time.sleep(3)
                    except Exception as e:
                        logging.error(f"Error during classification: {e}")

                else:
                    logging.warning(f"Unexpected landmarks shape: {landmarks_arr.shape}")

                # Check for user input without blocking
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logging.info("User pressed 'q', but continuing the script execution")

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            self.stop()

        finally:
            self.stop()

    def save_image_and_log(self, frame, image_dir, image_prefix, log_message):
        def save_image(frame, image_dir, image_prefix):
            image_path = os.path.join(image_dir, f"{image_prefix}_{datetime.now().strftime('Y%Y-M%m-D%d_H%H-M%M-S%S-MS%f')[:-3]}.png")
            cv2.imwrite(image_path, frame)
            return image_path

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_image = executor.submit(save_image, frame, image_dir, image_prefix)
            detection_logger.info(log_message)
            logging.info(f"Saved {log_message.lower()} image to: {future_image.result()}")

    def stop(self):
        self.running = False
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()

#    def toggle_notifications(self):
#        self.notifications_enabled = not self.notifications_enabled

    def align_notif(self, title, message):
        if self.notifications_enabled:
            notification.notify(
                title=title,
                message=message,
                app_name="Don't Wrist It",
                timeout=3
            )

    def inc_notif(self, title, message):
        if self.notifications_enabled:
            notification.notify(
                title=title,
                message=message,
                app_name="Don't Wrist It",
                timeout=3
            )
    
    def cam_notif(self, title, message):
        notification.notify(
            title=title,
            message=message,
            app_name="Don't Wrist It",
            timeout=3
        )

    def start_notif(self):
        notification.notify(
            title="Don't Wrist It",
            message="App has started",
            app_name="Don't Wrist It",
            timeout=3
        )
    
    def break_notif1(self, title, message):
        logging.debug(f"Notification - Title: {title}, Message: {message}")
        notification.notify(
            title=title,
            message=message,
            app_name="Don't Wrist It",
            timeout=3
        )
    
    def break_notif2(self, title, message):
        logging.debug(f"Notification - Title: {title}, Message: {message}")
        notification.notify(
            title=title,
            message=message,
            app_name="Don't Wrist It",
            timeout=3
        )

    def oneh_notif(self, title, message):
        if self.notifications_enabled:
            notification.notify(
                title=title,
                message=message,
                app_name="Don't Wrist It",
                timeout=3,
            ) 

if __name__ == "__main__":
    try:
        camera = Camera()
        camera.start_notif()
        camera.start()

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
