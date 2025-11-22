import numpy as np
import cv2
from deepface import DeepFace
import shutil
import tempfile
import os
from collections import deque, Counter

print("OpenCV version:", cv2.__version__)

def detect_faces(image_bytes: bytes) -> tuple[bytes, str]:
    # convert bytes to cv2 image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    emotion_result = "neutral"
    
    global emotion_buffer

    
    # Initialize buffer if not exists (size 10 means smoothing over approx 1 second if 10fps)
    if 'emotion_buffer' not in globals() or emotion_buffer is None:
        emotion_buffer = deque(maxlen=10)

    try:
        # face detection logic using OpenCV with red box around detected faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier()

        try:
            # Create a temporary file with .xml extension
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp:
                tmp_path = tmp.name
            
            # Copy the cascade file content to the temp file
            shutil.copy2(cascade_path, tmp_path)
            
            # Load from the temp file (which has a safe ASCII path)
            if not face_cascade.load(tmp_path):
                print(f"Error loading cascade from temp path: {tmp_path}")
            
            # Clean up the temp file
            try:
                os.remove(tmp_path)
            except:
                pass
                
        except Exception as e:
            print(f"Error handling cascade file: {e}")
            # Fallback: try loading original path just in case
            face_cascade.load(cascade_path)

        # Increase minNeighbors to reduce false positives (ghost faces)
        # Increase minSize to ignore very small faces that might be noise
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=8, minSize=(60, 60))
        
        # Optimization: Only keep the largest face to reduce background interference
        if len(faces) > 0:
            largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
            # Overwrite faces list to contain only the largest face
            faces = [largest_face]
        
        for (x, y, w, h) in faces:
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
            
        # Emotion analysis
        # Optimization: If faces are detected by OpenCV, pass the largest face to DeepFace
        # This avoids DeepFace re-running face detection and improves accuracy by focusing on the face
        
        target_img = image
        
        if len(faces) > 0:
            # Find the largest face
            largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
            x, y, w, h = largest_face
            # Crop the face with a small margin
            margin = 0 # You can adjust margin if needed
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(image.shape[1], x + w + margin)
            y2 = min(image.shape[0], y + h + margin)
            target_img = image[y1:y2, x1:x2]

        # To avoid crashing if no face is found by DeepFace (enforce_detection=False)
        # We use a faster model 'ssd' or 'mtcnn' if possible, but 'opencv' is default backend.
        # Since we already cropped the face (or passed full image), we can tell DeepFace to skip detection
        # if we are sure we passed a face. However, for robustness, let's keep enforce_detection=False.
        
        current_emotion = "neutral"
        try:
            analyze = DeepFace.analyze(target_img, actions=["emotion"], enforce_detection=False, silent=True)
            if analyze:
                # analyze is a list of dicts
                result = analyze[0]
                current_emotion = result.get("dominant_emotion", "neutral")
        except ValueError:
            # DeepFace might raise ValueError if image is too small or other issues
            pass
        
        # Add current emotion to buffer
        emotion_buffer.append(current_emotion)
        
        # Calculate the most frequent emotion in the buffer (Mode)
        if emotion_buffer:
            counts = Counter(emotion_buffer)
            emotion_result = counts.most_common(1)[0][0]
            print(f"Raw: {current_emotion:10} | Smoothed: {emotion_result:10} | Buffer: {list(emotion_buffer)}")
        else:
            emotion_result = current_emotion
            print(f"Raw: {current_emotion:10} | Smoothed: {emotion_result:10}")
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        emotion_result = "error"

    # convert cv2 image back to png bytes
    ret, buffer = cv2.imencode('.png', image)
    image_processed = buffer.tobytes()
    
    return image_processed, emotion_result
