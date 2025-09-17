import cv2
import numpy as np
import threading
import time
from flask import Flask, Response

app = Flask(__name__)

class CameraFeedHandler:
    def __init__(self, camera_index=0, width=1280, height=720):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.width = width
        self.height = height
        self.running = False
        self.last_boxes = []
        self.lock = threading.Lock()

        # HSV color ranges for bright TPU colors
        self.color_ranges = {
            "Orange": ([0, 120, 120], [25, 255, 255]),   # wider hue & lower sat
            "Green":  ([40,  80,  80], [85, 255, 255]),  # same
            "Blue":   ([95, 120,  80], [135, 255, 255]), # same
            "Yellow": ([20, 100, 120], [40, 255, 255]),  # more tolerance
        }

        self.color_bgr = {
            "Orange": (0, 92, 255),
            "Green":  (0, 255, 0),
            "Blue":   (255, 0, 0),
            "Yellow": (0, 255, 255),
        }


    def detect_colors(self, frame):
        """Detect bounding boxes for each color."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        boxes = []

        for color, (lower, upper) in self.color_ranges.items():
            lower_np = np.array(lower, dtype=np.uint8)
            upper_np = np.array(upper, dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_np, upper_np)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) > 500:  # filter tiny noise
                    x, y, w, h = cv2.boundingRect(cnt)
                    boxes.append((color, x, y, w, h))
        return boxes

    def detection_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            boxes = self.detect_colors(frame)
            with self.lock:
                self.last_boxes = boxes
            time.sleep(0.1)  # 10 Hz

    def generate_frames(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Resize to full HD (so Fire TV fills the screen)
            #frame = cv2.resize(frame, (1920, 1080))

            # Draw bounding boxes from last detection
            with self.lock:
                boxes = list(self.last_boxes)

            for color, x, y, w, h in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), self.color_bgr[color], 3)

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


    def start(self):
        self.running = True
        # Non-daemon thread to keep running
        self.detection_thread = threading.Thread(target=self.detection_loop)
        self.detection_thread.start()

    def stop(self):
        self.running = False
        # Wait for detection thread to finish
        self.detection_thread.join()
        self.cap.release()
        print("CameraFeedHandler stopped cleanly.")


# Initialize handler
handler = CameraFeedHandler()
handler.start()

# Flask route for MJPEG streaming
@app.route('/video_feed')
def video_feed():
    return Response(handler.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    try:
        # Run Flask server; blocking call keeps main thread alive
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        handler.stop()
