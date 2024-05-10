import sys
import json
from asyncio import get_event_loop, sleep
import supervision as sv
from ultralytics import YOLO
import cv2
import numpy as np
import os
import argparse
import time
from datetime import datetime
from reswarm import Reswarm
from collections import Counter
from datetime import datetime
import shutil
from pathlib import Path
from pprint import pprint
import base64
import torch
import functools
import urllib.request
import traceback

print = functools.partial(print, flush=True)

with open('/app/video/coco_classes.json', 'r') as f:
  class_id_topic = json.load(f)

OBJECT_MODEL = os.environ.get('OBJECT_MODEL')
RESOLUTION_X = int(os.environ.get('RESOLUTION_X', 640))
RESOLUTION_Y = int(os.environ.get('RESOLUTION_Y', 480))
FRAMERATE = int(os.environ.get('FRAMERATE', 30))

DEVICE_KEY = os.environ.get('DEVICE_KEY')
DEVICE_NAME = os.environ.get('DEVICE_NAME')
DEVICE_URL = os.environ.get('DEVICE_URL')
TUNNEL_PORT = os.environ.get('TUNNEL_PORT')
CONF = float(os.environ.get('CONF', '0.1'))
IOU = float(os.environ.get('IOU', '0.8'))
CLASS_LIST = os.environ.get('CLASS_LIST', '')
CLASS_LIST = CLASS_LIST.split(',')
try:
    CLASS_LIST = [int(num.strip()) for num in CLASS_LIST]
except Exception as err:
    print('Invalid Class list given', CLASS_LIST)
    CLASS_LIST = []

if len(CLASS_LIST) <= 1:
    CLASS_LIST = list(class_id_topic.keys())
    CLASS_LIST = [int(item) for item in CLASS_LIST]

saved_masks = []

def downloadModel(model_name, model_path):
    print(f'Downloading Pytorch model {model_name}...')
    urllib.request.urlretrieve(f'https://github.com/ultralytics/assets/releases/download/v0.0.0/{model_name}.pt', model_path)
    print(f'Download complete!')

def getModel(model_name):
    pytorch_model_path = f'/app/{model_name}.pt'
    tensorrt_initial_model_path = f'/app/{model_name}.engine'

    stored_pytorch_model_path = f'/data/{model_name}.pt'
    stored_tensorrt_model_path = f'/data/{model_name}-{MODEL_RESY}-{MODEL_RESX}.engine'
    model_download_path = f'/app/download/{model_name}.pt'

    stored_tensorrt_file = Path(stored_tensorrt_model_path)
    if stored_tensorrt_file.is_file():
        print(f'Found existing TensorRT Model for {model_name}')
        return YOLO(stored_tensorrt_model_path)

    pytorch_model_file = Path(stored_pytorch_model_path)
    if not pytorch_model_file.is_file():
        print('Original Pytorch model was not found, will download model')

        downloadModel(model_name, model_download_path)

        print('Copying downloaded Pytorch model to /app directory')
        # Move to /app directory to then export it, in case the export fails we don't have any bad data in the /data folder
        shutil.copy(model_download_path, pytorch_model_path)

        print('Moving downloaded Pytorch model to /data directory')
        shutil.move(model_download_path, stored_pytorch_model_path)
    else:
        print('Original Pytorch model was found, copying to main directory to avoid corrupted items in /data')

        print('Copying existing Pytorch model to /app directory')
        # Copy to /app directory to then export it, in case the export fails we don't have any bad data in the /data folder
        shutil.copyfile(stored_pytorch_model_path, pytorch_model_path)
    
    print("Exporting Pytorch model from /app directory into TensorRT....")
    pytorch_model = YOLO(pytorch_model_path)
    pytorch_model.export(format='engine', imgsz=(MODEL_RESY, MODEL_RESX))
    print("Model exported!")

    print(f'Moving exported TensorRT model {model_name} to data folder...')
    shutil.move(tensorrt_initial_model_path, stored_tensorrt_model_path)

    return YOLO(stored_tensorrt_model_path)

parser = argparse.ArgumentParser(description='Start a Video Stream for the given Camera Device')

parser.add_argument('device', type=str, help='A device path like e.g. /dev/video0')
parser.add_argument('camStream', type=str, help='One of frontCam, leftCam, rightCam, backCam')

args = parser.parse_args()

portMap = {"frontCam": 5004,
           "leftCam": 5005,
           "rightCam": 5006,
           "backCam": 5007}

device = args.device
print('CAMERA USED:' + device)

def get_youtube_video(url, height):
    import yt_dlp
    with yt_dlp.YoutubeDL() as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [])
        output_resolution = {"height": 0, "width": 0}
        for format in formats:
            resolution = format.get('height')
            if resolution == None:
                continue
            if height and height == int(resolution):
                output_resolution = format
                break
            elif output_resolution is None or resolution > output_resolution['height']:
                output_resolution = format
        return output_resolution

if device.startswith('http'):
    if device.startswith('https://youtu'):
        video = get_youtube_video(device, RESOLUTION_Y)
        RESOLUTION_X = video["width"]
        RESOLUTION_Y = video["height"]
        device = video.get('url')
    cap = cv2.VideoCapture(device)
    # device = f"uridecay url='{device}' ! nvenc-hwaccel=true ! nvdec_hwaccel ! videoconvert ! appsink"
    # cap = cv2.VideoCapture(device, cv2.CAP_GSTREAMER)

elif device.startswith('rtsp:'):
    cap = cv2.VideoCapture(device)
else:
    device = int(device[-1])
    cap = cv2.VideoCapture(device)

print('RESOLUTION', RESOLUTION_X, RESOLUTION_Y, device)
cap.set(3, RESOLUTION_X)
cap.set(4, RESOLUTION_Y)

MODEL_RESX = (RESOLUTION_X // 32) * 32 # must be multiple of max stride 32
MODEL_RESY = (RESOLUTION_Y // 32) * 32
model = getModel(OBJECT_MODEL)

# Supervision Annotations
bounding_box_annotator = sv.BoundingBoxAnnotator()
# bounding_box_annotator = sv.DotAnnotator(radius=6)
label_annotator = sv.LabelAnnotator(text_scale=0.4, text_thickness=1, text_padding=3)

# START = sv.Point(10, 400)
# END = sv.Point(1200, 400)
# line_zone = sv.LineZone(start=START, end=END)

# line_zone_annotator = sv.LineZoneAnnotator(
#     thickness=1,
#     text_thickness=1,
#     text_scale=0.5)

tracker = sv.ByteTrack()
smoother = sv.DetectionsSmoother(length=5)

# print("CUDA available:", torch.cuda.is_available(), 'GPUs', torch.cuda.device_count())

outputFormat = " videoconvert ! vp8enc deadline=2 threads=4 keyframe-max-dist=6 ! video/x-vp8 ! rtpvp8pay pt=96"
# outputFormat = "nvvidconv ! nvv4l2h264enc maxperf-enable=1 insert-sps-pps=true insert-vui=true ! h264parse ! rtph264pay"

writerStream = "appsrc do-timestamp=true ! " + outputFormat + " ! udpsink host=janus port=" + str(portMap[args.camStream])
# print(writerStream)

out = cv2.VideoWriter(writerStream, 0, FRAMERATE, (RESOLUTION_X, RESOLUTION_Y))

# Function to display frame rate and timestamp on the frame
def overlay_text(frame, text, position=(10, 30), font_scale=1, color=(0, 255, 0), thickness=2):
    cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)

def count_polygon_zone(zone):
    count_dict = {}
    for class_id in CLASS_LIST:
        count = zone.class_in_current_count.get(class_id, 0)
        count_dict[class_id] = count
    return count_dict

def count_detections(detections):
    count_dict = {}
    try:
        for xyxy, mask, conf, class_id, tracker_id, data in detections:
            if class_id in count_dict:
                count_dict[class_id] += 1
            else:
                count_dict[class_id] = 1
    except Exception as e:
        print('failed to count', e)
    return count_dict

async def main():
    try:
        print('starting main video loop...')
        fps_monitor = sv.FPSMonitor()
        start_time = time.time()
        start_time1 = time.time()
        start_time2 = time.time()

        prev_frame_time = time.time()
        frame_skip_threshold = 1.0 / FRAMERATE  # Maximum allowed processing time per frame

        global out

        while cap.isOpened():
            elapsed_time = time.time() - start_time
            elapsed_time1 = time.time() - start_time1
            elapsed_time2 = time.time() - start_time2

            success, frame = cap.read()
            if not success:
                continue

            curr_frame_time = time.time()

            # Check if processing time for previous frame exceeded threshold
            if curr_frame_time - prev_frame_time > frame_skip_threshold:
                # print("Skipping frame!", curr_frame_time - prev_frame_time)
                prev_frame_time = curr_frame_time
                continue

            # print("process frame", curr_frame_time - prev_frame_time)
            # Update previous frame time for next iteration
            prev_frame_time = curr_frame_time
            
            counts = {}
            results = []
            fps_monitor.tick()
            results = model(frame, imgsz=(MODEL_RESY, MODEL_RESX), conf=CONF, iou=IOU, verbose=False, classes=CLASS_LIST)
            start_time2 = time.time()
            
            if len(results) > 0:
                frame, counts = processFrame(frame, results)

            # Draw FPS and Timestamp
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            overlay_text(frame, f'Timestamp: {current_time}', position=(10, 30))
            overlay_text(frame, f'FPS: {fps_monitor.fps:.2f}', position=(10, 60))

            # Publish data
            if elapsed_time1 >= 2.0:
                for item in counts:
                    publishImage(frame)
                    publishClassCount(item["count"], item["label"])
                    start_time1 = time.time()
            
            if elapsed_time > 10.0:
                publishCameras()
                start_time = time.time()

            out.write(frame)

            if cv2.waitKey(1) == ord('q'):
                break

            await sleep(0) # Give other ask time to run, not a hack: https://superfastpython.com/what-is-asyncio-sleep-zero/#:~:text=You%20can%20force%20the%20current,before%20resuming%20the%20current%20task.

        cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        print(f'############################# Error in video loop: {str(e)}')
        traceback.print_exc()
        import sys
        sys.exit(1)

def processFrame(frame, results):
    global saved_masks
    if len(results) == 0:
        return frame, []          
    detections = sv.Detections.from_ultralytics(results[0])
    try:
        detections = tracker.update_with_detections(detections)
        detections = smoother.update_with_detections(detections)
    except Exception as e:
        print('Error when smoothing detections', str(e))

    counts = []

    # line_zone.trigger(detections)
    # frame = line_zone_annotator.annotate(frame, line_counter=line_zone)

    for saved_mask in saved_masks:
        zone = saved_mask['zone']
        zone_annotator = saved_mask['annotator']
        try:
            zone_mask = zone.trigger(detections=detections)
        except Exception as e:
            print('Failed to get detections')
            continue

        count = zone.current_count
        zone_label = str(count) + ' - ' + saved_mask['label']

        filtered_detections = detections[zone_mask]
        
        # labels = [f"{class_id_topic[str(class_id)]} #{tracker_id}" for class_id, tracker_id in zip(filtered_detections.class_id, filtered_detections.tracker_id)]

        count_dict = count_polygon_zone(zone)
        counts.append({'label': saved_mask['label'], 'count': count_dict})

        frame = bounding_box_annotator.annotate(scene=frame, detections=filtered_detections)
        frame = label_annotator.annotate(scene=frame, detections=filtered_detections)
        frame = zone_annotator.annotate(scene=frame, label=zone_label)

    # Annotate all detections if no masks are defined
    if len(saved_masks) == 0:
        frame = bounding_box_annotator.annotate(scene=frame, detections=detections)
        # labels = [f"{class_id_topic[str(class_id)]} #{tracker_id}" for class_id, tracker_id in zip(detections.class_id, detections.tracker_id)]
        frame = label_annotator.annotate(scene=frame, detections=detections)

        count_dict = count_detections(detections)
        counts.append({'label': DEVICE_NAME + "_" + "default", 'count': count_dict})
    return frame, counts

def publishImage(frame):
    _, encoded_frame = cv2.imencode('.jpg', frame)
    base64_encoded_frame = base64.b64encode(encoded_frame.tobytes()).decode('utf-8')
    now = datetime.now().astimezone().isoformat()

    get_event_loop().create_task(rw.publish_to_table('images', {"tsp": now, "image": 'data:image/jpeg;base64,' + base64_encoded_frame}))

def publishCameras():
    now = datetime.now().astimezone().isoformat()
    payload = {"tsp": now}
    payload["videolink"] = f"https://{DEVICE_KEY}-traffic-1100.app.record-evolution.com"
    payload["devicelink"] = DEVICE_URL
    get_event_loop().create_task(rw.publish_to_table('cameras', payload))

def publishClassCount(result, zone_name):
    now = datetime.now().astimezone().isoformat()
    payload = {"tsp": now}
    payload["zone_name"] = zone_name

    for class_id in CLASS_LIST:
        payload[class_id_topic[str(class_id)]] = result.get(class_id, 0)

    print(payload)

    get_event_loop().create_task(rw.publish_to_table('detections', payload))

async def readMasksFromStdin():
    print("Reading STDIN")

    try:
        with open('/data/mask.json', 'r') as f:
            loaded_masks = json.load(f)

        prepMasks(loaded_masks)
    except Exception as e:
        print('Failed to load masks initially', e)

    while True:
        try:
            masksJSON = await get_event_loop().run_in_executor(None, sys.stdin.readline)

            print("Got masks from stdin:", masksJSON)

            stdin_masks = json.loads(masksJSON)

            prepMasks(stdin_masks)
            
        except Exception as e:
            print(e)
        await sleep(0)

def prepMasks(in_masks):
    global saved_masks

    pre_masks = [
        {
            'label': mask['label'],
            'points': [(int(point['x']), int(point['y'])) for point in mask['points'][:-1]],
            'color': mask['lineColor']
        }
        for mask in in_masks['polygons']
    ]
    out_masks = []
    for mask in pre_masks:
        polygon = np.array(mask['points'])
        polygon.astype(int)

        polygon_zone = sv.PolygonZone(polygon=polygon, frame_resolution_wh=(RESOLUTION_X, RESOLUTION_Y), triggering_position=sv.Position.CENTER)
        mask['zone'] = polygon_zone
        zone_annotator = sv.PolygonZoneAnnotator(
            zone=polygon_zone,
            color=sv.Color.from_hex(mask['color']),
        )
        mask['annotator'] = zone_annotator

        out_masks.append(mask)
    saved_masks = out_masks
    print('Refreshed Masks', saved_masks)

rw = Reswarm()

if __name__ == "__main__":
    # run the main coroutine
    task1 = get_event_loop().create_task(readMasksFromStdin())
    task2 = get_event_loop().create_task(main())

    # run the reswarm component
    rw.run()
