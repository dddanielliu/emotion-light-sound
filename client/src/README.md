# OpenCV Face Detection & Emotion Recognition

This module (`opencv_face`) provides robust face detection and real-time emotion analysis capabilities for the client application.

## Features

### 1. Face Detection
- **Algorithm**: Uses OpenCV's Haar Cascade Classifier (`haarcascade_frontalface_default.xml`).
- **Robust Loading**: Implements a workaround for Windows paths containing non-ASCII characters (e.g., Chinese) by copying the cascade file to a temporary ASCII path before loading.
- **Optimization**: 
    - Configured with `minNeighbors=8` and `minSize=(60, 60)` to minimize false positives and background noise.
    - **Largest Face Priority**: Automatically filters detections to focus only on the largest face in the frame, ensuring the system analyzes the primary user and ignores background distractions.

### 2. Emotion Recognition
- **Engine**: Powered by **DeepFace** (using the `tf-keras` backend).
- **Workflow**:
    1. Detects the largest face using OpenCV.
    2. Crops the face region from the frame.
    3. Passes the cropped face to DeepFace for emotion analysis.
- **Smoothing Mechanism**:
    - Implements a **Sliding Window** approach using a buffer (deque) of size 10.
    - Calculates the **Mode** (most frequent emotion) from the buffer to determine the displayed emotion.
    - Effectively stabilizes the output, preventing rapid flickering between different emotions.

### 3. Frame Skipping for Real-time Performance
- **Problem**: When DeepFace processing time exceeds the frame arrival rate, frames accumulate in the queue, causing increasing lag.
- **Solution**: Implements a **frame skipping mechanism** to maintain real-time responsiveness:
    - **Global State Management**:
        - `is_processing`: Boolean flag indicating if DeepFace is currently processing
        - `latest_frame_bytes`: Stores the most recent frame received
        - `last_processed_image` & `last_emotion_result`: Cached results from the last successful processing
    - **Logic**:
        1. Every incoming frame updates `latest_frame_bytes` (always stores the newest frame)
        2. If `is_processing == True`: Return cached results immediately (skips the frame)
        3. If `is_processing == False`: Process the latest frame from `latest_frame_bytes`
        4. After processing completes, `is_processing` is reset via `finally` block
    - **Benefits**:
        - ✅ No frame queue accumulation
        - ✅ Always processes the most recent frame (avoids processing stale frames)
        - ✅ Maintains real-time responsiveness
        - ✅ Automatically adapts to varying processing speeds

### 4. Performance Monitoring
- **Detailed Logging**: Each frame processing outputs timing statistics and frame status:
    ```
    🔄 START PROCESSING - Frame entered at 1764211710.069
    Raw: happy      | Smoothed: neutral    | Buffer: ['neutral', 'neutral', 'happy', ...]
    ✅ PROCESSING COMPLETE - Total: 0.039s | DeepFace: 0.039s | Result: neutral
    ```
    Or when a frame is skipped:
    ```
    ⏭️  FRAME SKIPPED - DeepFace busy, returning cached result
    ```
- **Metrics**:
    - **Total**: Time from frame entry to result return
    - **DeepFace**: Pure DeepFace processing time
    - **Raw**: Current frame's detected emotion
    - **Smoothed**: Mode of the last 10 processed frames (final output)
    - **Buffer**: Complete history of the last 10 emotions

## Dependencies
- `opencv-python`: For image processing and face detection.
- `deepface`: For deep learning-based emotion analysis.
- `tf-keras`: Required backend for DeepFace.
- `numpy`: For array manipulations.

## Usage

The main entry point is the `detect_faces` function in `face_detection.py`:

```python
from ..opencv_face.face_detection import detect_faces

# image_bytes: Raw bytes of the image frame
processed_image_bytes, emotion_result = detect_faces(image_bytes)
```

- **Input**: Raw image bytes (e.g., from a video stream).
- **Output**: 
    - `processed_image_bytes`: The image with a red bounding box drawn around the detected face.
    - `emotion_result`: A string representing the smoothed dominant emotion (e.g., "happy", "neutral", "sad").
```