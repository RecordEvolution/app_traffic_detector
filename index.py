from ultralytics import YOLO
# from reswarm import Reswarm
# import gi
# gi.require_version('Gtk', '3.0')
# from gi.repository import Gtk
import cv2
import math
import os
# start webcam

CAM_NUM = os.environ.get('CAM_NUM', 0)
RESOLUTION_X = int(os.environ.get('RESOLUTION_X', 640))
RESOLUTION_Y = int(os.environ.get('RESOLUTION_Y', 480))

cap = cv2.VideoCapture(0)
cap.set(3, RESOLUTION_X)
cap.set(4, RESOLUTION_Y)

# model
model = YOLO("./yolov8n.pt")

# object classes
classNames = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
              "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
              "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
              "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
              "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
              "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
              "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
              "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
              "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
              "teddy bear", "hair drier", "toothbrush"
              ]

framerate = 25.0

out = cv2.VideoWriter('appsrc ! videoconvert ! '
                      'vp8enc deadline=2 threads=2 keyframe-max-dist=60 ! video/x-vp8 ! '
                      'rtpvp8pay !'
                      'udpsink host=127.0.0.1 port=5004',
                      0, framerate, (RESOLUTION_X, RESOLUTION_Y))

while True:
    success, img = cap.read()
    results = model(img, stream=True, imgsz=RESOLUTION_X, classes=[2])
    
    # coordinates
    for r in results:
        boxes = r.boxes

        for box in boxes:
            # bounding box
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2) # convert to int values

            # put box in cam
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 2)

            # confidence
            confidence = math.ceil((box.conf[0]*100))/100
            # print("Confidence --->",confidence)

            # class name
            cls = int(box.cls[0])
            # print("Class name -->", classNames[cls])

            # object details
            org = (x1, y1)
            font = cv2.FONT_HERSHEY_SIMPLEX
            fontScale = 1
            color = (255, 0, 255)
            thickness = 2

            cv2.putText(img, classNames[cls], org, font, fontScale, color, thickness)

    # cv2.imshow('Webcam', img)
    out.write(img)
    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()