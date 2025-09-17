import cv2
import numpy as np
import subprocess
import threading
import time

class CameraFeedHandler:
    def __init__(self, camera_index=0, width=1280, height=720, fps=30, rtsp_port=8554, use_cuda=True):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        self.width = width
        self.height = height
        self.fps = fps
        self.rtsp_port = rtsp_port
        self.use_cuda = use_cuda

        self.running = False
        self.last_boxes = []
        self.lock = threading.Lock()

        # HSV color ranges
        self.color_ranges = {
            "Orange": ([5, 150, 150], [15, 255, 255]),
            "Green":  ([40, 100, 100], [80, 255, 255]),
            "Blue":   ([100, 150, 100], [130, 255, 255]),
            "Yellow": ([20, 150, 150], [30, 255, 255]),
        }

        # Launch FFmpeg RTSP stream
        self.ffmpeg = subprocess.Popen([
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "h264_nvenc",  # GPU encoder
            "-preset", "llhp",
            "-tune", "ll",
            "-f", "rtsp",
            f"rtsp://0.0.0.0:{rtsp_port}/live"
        ], stdin=subprocess.PIPE)

        if use_cuda:
            print("CUDA enabled for OpenCV operations.")

    def detect_colors(self, frame):
        """Detect bounding boxes for all defined colors."""
        if self.use_cuda:
            gpu_frame = cv2.cuda_GpuMat()
            gpu_frame.upload(frame)
            gpu_hsv = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2HSV)
        else:
            gpu_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        boxes = []
        for color, (lower, upper) in self.color_ranges.items():
            lower_np = np.array(lower, dtype=np.uint8)
            upper_np = np.array(upper, dtype=np.uint8)

            if self.use_cuda:
                mask_gpu = cv2.cuda.inRange(gpu_hsv, lower_np, upper_np)
                mask = mask_gpu.download()
            else:
                mask = cv2.inRange(gpu_hsv, lower_np, upper_np)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) > 500:
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

    def streaming_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            with self.lock:
                boxes = list(self.last_boxes)

            for color, x, y, w, h in boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                cv2.putText(frame, color, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            try:
                self.ffmpeg.stdin.write(frame.tobytes())
            except BrokenPipeError:
                print("FFmpeg pipe broken — stopping stream.")
                break

            time.sleep(1 / self.fps)

    def start(self):
        self.running = True
        threading.Thread(target=self.detection_loop, daemon=True).start()
        threading.Thread(target=self.streaming_loop, daemon=True).start()

    def stop(self):
        self.running = False
        time.sleep(0.5)
        self.cap.release()
        self.ffmpeg.stdin.close()
        self.ffmpeg.wait()
