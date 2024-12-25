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


# from pynput.mouse import Controller

# Suppress YOLO logs by adjusting the logging level
logging.getLogger('ultralytics').setLevel(logging.ERROR)

# Load YOLOv8 model


class Main:
    
    def main(self):
        self.screen_center_x = 2560 / 2  # Replace with your screen's width / 2
        self.screen_center_y = 1440 / 2  # Replace with your screen's height / 2
        self.is_key_pressed = False
        # self.parser_process = None
        # self.queue = Queue()
        self.frame_times = []
        self.time_interval_frames = 60
        self.manager = Manager()
        self.results = []
        self.detections = self.manager.list()
        
        
        # aimbot_thread = threading.Thread(target=self.aimbot)
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
        # def sigmoid_abs_scaled(input, beta=0.05, sensitivity = 1):
        #     input = input * sensitivity
        #     scaled_value = (abs(input) / (1 + math.exp(-beta * abs(input)))) * sensitivity
        #     return int(scaled_value)
        delta_x = center_bb_x - self.screen_center_x
        delta_y = center_bb_y - self.screen_center_y
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(delta_x), int(delta_y), 0, 0)



    def select_target_bounding_box(self) -> tuple[int,int]:
        head_detection_dict = {}# center(tuple) : list[dist(int NEED TO CONVERT),area(int)]
        zombie_detection_dict = {}

        for detection in self.detections:
            x1, y1, x2, y2 = detection['bbox']
            curr_center_coords = ((x2 + x1) / 2, (y2 + y1) / 2)
            curr_area = (x2-x1)*(y2-y1)
            curr_dist = ((x2-x1)**2 + (y2-y1)**2)**.5
        
            if curr_dist == 0:
                score = float('inf')
            else:
                score = curr_area**3/curr_dist**4

            if detection['class_name'] == 'Head':
                head_detection_dict[curr_center_coords] = score
            else:
                zombie_detection_dict[curr_center_coords] = score
        if len(head_detection_dict) > 0: 
            sorted_heads = sorted(head_detection_dict, key = head_detection_dict.__getitem__,reverse = True)
            return sorted_heads[0]
        else:
            sorted_zombies = sorted(zombie_detection_dict, key = zombie_detection_dict.__getitem__,reverse = True)
            return sorted_zombies[0]
            
        
        
        
        # return largest_head_coords if largest_head_area > 0 else largest_body_coords#edgecase no detections handled in aimbot prolly 
    
    def input_detection(self):
        def on_key_press(event):
            if event.name == 'e':
                self.is_key_pressed = not self.is_key_pressed
                print(f"Key toggled: {self.is_key_pressed}")

        keyboard.on_press(on_key_press)

        while True:  # Keep the thread running
            time.sleep(3)
    
    def run_screen_capture_detection(self):
        model = YOLO(r"C:\Users\kevin\Documents\GitHub\YOLO11-Final-Poop-2\runs\train\train_run\weights\best.pt")  # Replace with your trained YOLOv8 model

        # window_width, window_height = 2560, 1440
        # cv2.namedWindow("Screen Capture Detection", cv2.WINDOW_NORMAL)
        # cv2.resizeWindow("Screen Capture Detection", window_width, window_height)
        camera = dxcam.create(output_color='BGR')
        if camera is None:
            print("Camera initialization failed.")
            return
        # parser_process = Process(target=self.parse_detections)
        # parser_process.start()
        while True:
            
            start = time.time_ns()
            frame = camera.grab()

            if frame is None or len(frame) == 0 or frame.shape[0] == 0 or frame.shape[1] == 0:
                # print("Invalid frame captured")
                continue
            # Scale the captured frame to fit 1920x1080 resolution while maintaining aspect ratio
            # frame_resized = cv2.resize(frame, (window_width, window_height), interpolation=cv2.INTER_LINEAR)
            # Perform detection
            
            self.results = model.predict(source=frame, conf=0.6,imgsz=1440)
            # self.queue.put(results)
            
            # if not self.queue.empty():
            #     self.detections = self.queue.get()
            # Extract bounding boxes and group objects
            self.detections = [
                {
                    "class_name": model.names[int(box.cls[0])],
                    "bbox": list(map(int, box.xyxy[0]))
                }
                for box in self.results[0].boxes
            ]
            if(self.is_key_pressed and self.detections):
                self.aimbot()

            # Update detections for the parser process
            # with self.manager.Lock():  # Synchronize access
            #     self.detections[:] = [
            #         {
            #             "class_name": self.model.names[int(box.cls[0])],
            #             "bbox": list(map(int, box.xyxy[0])),
            #             "confidence": float(box.conf[0])
            #         }s
            #         for box in self.results[0].boxes
            # ]
                
            end = time.time_ns()
            runtime_ms = (end - start)/1000000
            self.append_time(runtime_ms)
            # Draw bounding boxes and labels
            # for obj in self.detections:
            #     x1, y1, x2, y2 = obj['bbox']
            #     label = f"{obj['class_name']} {obj['confidence']:.2f}"
            #     cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), thickness = 1)
            #     cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), thickness = 1)

            # Show the output frame
            # cv2.imshow("Screen Capture Detection", frame)

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