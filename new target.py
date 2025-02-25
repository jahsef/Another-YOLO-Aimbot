from ultralytics import YOLO
import cv2
import numpy as np
import dxcam
import threading
import time
import keyboard
import logging
import win32api
import win32con
import math
from multiprocessing import Process, Manager
import os
import torch
import tkinter
import TargetSelector as ts

# Suppress YOLO logs by adjusting the logging level
logging.getLogger('ultralytics').setLevel(logging.ERROR)

class Main:
     
    def main(self):     
        self.debug = False
        self.screen_center_x = 2560 / 2  # Replace with your screen's width / 2
        self.screen_center_y = 1440 / 2  # Replace with your screen's height / 2
        self.is_key_pressed = False
        self.frame_times = []
        self.time_interval_frames = 60
        self.results = []
        self.detections = []
        self.target_selector = ts.TargetSelector(motion_prediction=False)

        
        threading.Thread(target=self.input_detection, daemon=True).start()
        threading.Thread(target=self.calculate_fps, daemon=True).start()

        # Run screen capture in the main thread
        self.run_screen_capture_detection()

    def aimbot(self):  
        detection = self.select_target_bounding_box()
        self.move_mouse_to_bounding_box(detection)
                
    def move_mouse_to_bounding_box(self, detection):
        center_bb_x = detection[0]
        center_bb_y = detection[1]
        delta_x = center_bb_x - self.screen_center_x
        delta_y = center_bb_y - self.screen_center_y
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(delta_x), int(delta_y), 0, 0)

    def select_target_bounding_box(self) -> tuple[int, int]:
        screen_center = (self.screen_center_x, self.screen_center_y)
        return self.target_selector.select_target(self.detections, screen_center)

    def input_detection(self):
        def on_key_press(event):
            if event.name == 'e':
                self.is_key_pressed = not self.is_key_pressed
                print(f"Key toggled: {self.is_key_pressed}")
        keyboard.on_press(on_key_press)
        while True:
            time.sleep(2)

    def run_screen_capture_detection(self):
        capture_region =[560,0,2000,1440]
        #[560,0,2000,1440] center of screen
        #[768, 180, 1792, 1260]
        
        cwd = os.getcwd()
        
        # model = YOLO(os.path.join(cwd,"runs//train//train_run//weights//best.engine"))
        model = YOLO(os.path.join(cwd, "runs/detect/tune4/weights/best.engine"))
        device = torch.device("cuda")
        
        if self.debug:
            window_width, window_height = capture_region[2] - capture_region[0],capture_region[3]-capture_region[1]
            cv2.namedWindow("Screen Capture Detection", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Screen Capture Detection", window_width, window_height)
        
        camera = dxcam.create(region = capture_region, output_color='RGB',max_buffer_len=2)
        # camera.start(target_fps = 160, video_mode= True)
        if camera is None:
            print("Camera initialization failed.")
            return

        while True:
            
            start = time.time_ns()
            frame = camera.grab()
            
            if frame is None:
                print("frame none")
                time.sleep(.01)
                continue
            # 2. Convert to tensor WITH PROPER FORMATTING
            img_tensor = torch.from_numpy(frame).to(device)
            img_tensor = img_tensor.permute(2, 0, 1)        # HWC -> CHW
            img_tensor = img_tensor.unsqueeze(0)            # Add batch dim -> BCHW
            img_tensor = img_tensor.half() / 255.0          # Normalize AFTER casting
            img_tensor = img_tensor.contiguous()            # Critical for TensorRT
            
            # with torch.no_grad():
            self.results = model(source=img_tensor, conf=0.6, imgsz=(1440,1440),max_det = 16) 

            for box in self.results[0].boxes:
                detection = {
                    "class_name": model.names[int(box.cls[0])],
                    "bbox": list(map(int, box.xyxy[0])),
                    "confidence": float(box.conf[0])
                }
                self.detections.append(detection)
                
            if self.debug:
                display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)#opencv does bgr while yolo needs rgb
                for obj in self.detections:
                    x1, y1, x2, y2 = obj['bbox']
                    label = f"{obj['class_name']} {obj['confidence']:.2f}"
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), thickness = 1)
                    cv2.putText(display_frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), thickness = 1)
                
                cv2.imshow("Screen Capture Detection", display_frame)
                cv2.waitKey(1)
                
            if(self.is_key_pressed and self.detections):
                self.aimbot()
            # Trim unused entries
            self.detections.clear()
            end = time.time_ns()
            runtime_ms = (end - start)/1000000
            self.append_time(runtime_ms)

    def append_time(self, time):
        
        if len(self.frame_times) >= self.time_interval_frames:
            self.frame_times.pop(0)

        self.frame_times.append(time)
    
    def calculate_fps(self):
        while True:
            if len(self.frame_times) > 0:
                avg_time_ms = sum(self.frame_times) / len(self.frame_times)  # Average time for the last N frames
                fps = 1000 / avg_time_ms  # FPS calculation based on average frame time (ms -> fps)
                print(f"FPS: {fps:.2f} (based on last {len(self.frame_times)} frames)")
            time.sleep(1)  # Adjust the reporting frequency as needed
        
            

if __name__ == "__main__":
    Main().main()