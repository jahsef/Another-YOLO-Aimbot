from ultralytics import YOLO
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.engine.results import Boxes

import cv2
import threading
import time
import keyboard
import win32api
import win32con
import os
import torch
import sys
from pathlib import Path
import cupy as cp
import numpy as np
github_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(os.path.join(github_dir,'BettererCam')))
# can replace with bettercam just no cupy support
import betterercam
# print(betterercam.__file__)
from utils import targetselector
from argparse import Namespace  


class Main:
    def __init__(self):
        self.debug = False
        self.screen_x = 2560
        self.screen_y = 1440
        self.h_w_capture = (896,1440)#height,width
        self.is_key_pressed = False
        self.screen_center = (self.screen_x // 2,self.screen_y // 2)
        self.x_offset = (self.screen_x - self.h_w_capture[1])//2
        self.y_offset = (self.screen_y - self.h_w_capture[0])//2
        self.fps_tracker = FPSTracker()
        self.setup_tracking()
        self.setup_targeting()
        self.stop_event = threading.Event()
        if self.debug:
            window_height, window_width = self.h_w_capture
            cv2.namedWindow("Screen Capture Detection", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Screen Capture Detection", window_width, window_height)
        self.model = YOLO(os.path.join(os.getcwd(),"runs/train/EFPS_4000img_11s_1440p_batch6_epoch200/weights/best.engine"))
        # model = YOLO(os.path.join(cwd,"runs/train/EFPS_3000image_realtrain_1440x1440_100epoch_batch6_11s/weights/best.engine"))
        # model = YOLO(os.path.join(cwd,'runs/train/EFPS_4000img_11m_1440p_batch6_epoch200/weights/best.pt'))
        
        self.empty_boxes = Boxes(boxes=torch.empty((0, 6), device="cuda:0"),orig_shape=self.h_w_capture)
        capture_region = (0 + self.x_offset, 0 + self.y_offset, self.screen_x - self.x_offset, self.screen_y - self.y_offset)
        self.camera = betterercam.create(region = capture_region, output_color='BGR',max_buffer_len=2, nvidia_gpu = True)#yolo does bgr -> rgb conversion in model.predict automatically
        
    def main(self):     
        threading.Thread(target=self.input_detection, daemon=True).start()
        
        try:
            while True:
                frame = self.screen_cap()
                if frame is None:
                    continue
                
                torch_tensor = self.preprocess(frame)
                self.inference(torch_tensor)

                BYTETracker.multi_predict(self.tracker,self.tracker.tracked_stracks)
                
                tracked_objects = np.asarray([x.result for x in self.tracker.tracked_stracks if x.is_activated])
                
                if self.debug:
                    self.debug_render(cp.asnumpy(frame),tracked_objects)
                if self.is_key_pressed and len(tracked_objects) > 0:
                    self.aimbot(tracked_objects)
                self.fps_tracker.update()
                
        except KeyboardInterrupt:
            print('Shutting down...')
        finally:
            self.cleanup()
            
    def setup_tracking(self):
        target_frame_rate = 95
        args = Namespace(
            track_high_thresh=.65,
            track_low_thresh=.4,
            track_buffer=target_frame_rate//2,
            fuse_score=.5,
            match_thresh=.6,
            new_track_thresh=0.65
        )
        self.tracker = BYTETracker(args, frame_rate=target_frame_rate)
    
    def setup_targeting(self):
        self.screen_center = (self.screen_x // 2, self.screen_y // 2)
        self.x_offset = (self.screen_x - self.h_w_capture[1])//2
        self.y_offset = (self.screen_y - self.h_w_capture[0])//2
        
        self.target_selector = targetselector.TargetSelector(
            hysteresis=1.5,
            proximity_threshold_sq=75**2,
            screen_center=self.screen_center,
            x_offset=self.x_offset,
            y_offset=self.y_offset,
            head_toggle=True
        )

            
    def cleanup(self):
        self.stop_event.set()
        if self.camera:
            self.camera.close()
        if self.debug:
            cv2.destroyAllWindows()
        torch.cuda.empty_cache()
        
    def aimbot(self, tracked_objects):  
        target_bb = self.target_selector.get_target(tracked_objects)
        self.move_mouse_to_bounding_box(target_bb)
                
    def move_mouse_to_bounding_box(self, detection):
        center_bb_x = detection[0]
        center_bb_y = detection[1]
        delta_x = center_bb_x - self.screen_center[0]
        delta_y = center_bb_y - self.screen_center[1]
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(delta_x), int(delta_y), 0, 0)

    def input_detection(self):
        def on_key_press(event):
            if event.name.lower() == 'e':
                self.is_key_pressed = not self.is_key_pressed
                print(f"Key toggled: {self.is_key_pressed}")

                
        keyboard.on_press(on_key_press)
        while True:
            time.sleep(.1)
    
    #almost 25% speedup over np (preprocess + inference)
    #also python doesnt have method overloading by parameter type
    
    def preprocess(self,frame: cp.ndarray) -> torch.Tensor:
        bchw = cp.ascontiguousarray(frame.transpose(2, 0, 1)[cp.newaxis, ...])
        float_frame = bchw.astype(cp.float16, copy=False)
        float_frame /= 255.0 #/= is inplace, / creates a new cp arr
        return torch.as_tensor(float_frame, device='cuda')

    @torch.inference_mode()
    def inference(self,source):
        
        results = self.model(source=source,
            conf = .25,
            imgsz=self.h_w_capture,
            verbose = False
        )#could immediately pass this stuff to another thread/process but might add some latency
        
        if results[0].boxes.data.numel() == 0: 
            enemy_boxes = self.empty_boxes
        else:
            cls_target = 0
            enemy_mask = results[0].boxes.cls == cls_target
            filtered_data = results[0].boxes.data[enemy_mask]  # Filter the 'data' attribute
            enemy_boxes = Boxes(
                boxes=filtered_data,  # Pass the filtered 'data' tensor
                orig_shape=self.h_w_capture
            )
# coords = self.xyxy if self.angle is None else self.xywha
# return coords.tolist() + [self.track_id, self.score, self.cls, self.idx]
#STrack object results (byte tracker list[STrack])
        return self.tracker.update(enemy_boxes.cpu().numpy())#return results
        
    def screen_cap(self):
        return self.camera.grab()
    
    def debug_render(self,frame,tracked_objects):
        display_frame = cp.asnumpy(frame)
        # tracked_objects = np.asarray([x.result for x in self.tracker.tracked_stracks if x.is_activated])
        for i in range(len(tracked_objects)):
            x1, y1, x2, y2, = map(int,tracked_objects[i][:4])
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 0, 204), thickness = 2)
            cv2.putText(display_frame, f"ID: {tracked_objects[i][4]}", (int(x1), int(y1) - 10),cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 1)
        cv2.imshow("Screen Capture Detection", display_frame)
        cv2.waitKey(1)
        
class FPSTracker:
    def __init__(self, update_interval=1.0):
        self.frame_count = 0
        self.last_update = time.perf_counter()
        self.update_interval = update_interval

    def update(self):
        self.frame_count += 1
        current_time = time.perf_counter()
        
        if current_time - self.last_update >= self.update_interval:
            fps = self.frame_count / (current_time - self.last_update)
            print(f'FPS: {fps:.2f}')
            self.frame_count = 0
            self.last_update = current_time
            

if __name__ == "__main__":
    Main().main()