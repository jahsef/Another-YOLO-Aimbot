from ultralytics import YOLO
import os
import pickle
import torch
import time
import yaml
def main():
    torch.cuda.empty_cache()
        
    # Define the paths to the dataset and YAML file
    cwd = os.getcwd()
    data_yaml_path = os.path.join(cwd,'datasets/pf_1600img//data.yaml')  # Update with your data.yaml path
    print(data_yaml_path)
    epochs = 100  # Adjust the number of epochs as needed
    batch = 8 # Adjust based on your GPU memory
    nbs = 8 #nominal/effective batch size, updates gradients every 4 iterations (24/6)
    imgsz = 640  # Image size for training 
    
    # base_dir = 'models/EFPS_11n_4000img_640x640_batch16/weights'
    # model_name = "best.pt"
    # model_path = os.path.join(os.getcwd(), base_dir, model_name)
    # model = YOLO(model_path)
    model = YOLO("yolo11s.pt")  # Use the YOLOv8 pre-trained weights or your own
    model.train(
        data=data_yaml_path,  # Path to your dataset configuration file
        epochs=epochs,  # Number of training epochs
        batch=batch,  # Batch size for training
        imgsz=imgsz,  # Image size for training
        project='models/pf_1600img_11s',  # Directory to save the tra  ining results
        resume = False,
        device = 0,
        name='base_augment',  # Directory name for the run
        exist_ok=True,  # Overwrite the existing directory if necessary
        cache = 'disk',#takes in bool or string ig what
        patience = 16,#0 = no early stopping
        rect = False, #may need to experiment with this, default False
        save_period = 5,
        fraction = 1,#fraction of train
        plots = True,#generates some more plots
        cos_lr = True,#cos learning rate scheduler, convergence more stable
        profile = True,
        optimizer = 'adamw',
        amp = True,
        pretrained = True,
        warmup_epochs=3,
        nbs=nbs,    
        lr0 = 8e-5,
        augment = True,
        deterministic = False,
        weight_decay = 1e-3,#default 5e-4
        # degrees = 5,
        # shear = 5,
        # scale = .4,
        # perspective = 1e-4
    )

    model.save()
    
if __name__ == '__main__':
    main()