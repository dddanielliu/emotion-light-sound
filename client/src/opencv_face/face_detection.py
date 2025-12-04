import numpy as np
import cv2
from deepface import DeepFace
import shutil
import tempfile
import os
import time
import asyncio
from collections import deque, Counter

print("OpenCV version:", cv2.__version__)

# Global variables for frame skipping logic
latest_frame_bytes = None
is_processing = False
last_processed_image = None
last_emotion_result = "neutral"
emotion_buffer = deque(maxlen=10)  # Now stores (emotion, score) tuples

# Global variables for timed emotion updates
last_pre_update_time = 0
last_post_update_time = 0
emotion_update_callback = None
main_event_loop = None


def calculate_confidence(buffer, dominant_emotion):
    """
    Calculate confidence as the average score of all entries matching the dominant emotion.

    Args:
        buffer: deque of (emotion, score) tuples
        dominant_emotion: the emotion to calculate confidence for

    Returns:
        float: average score of matching emotions (0.0-1.0), or 0.0 if no matches
    """
    matching_scores = [
        score for emotion, score in buffer if emotion == dominant_emotion
    ]
    if not matching_scores:
        return 0.0
    # DeepFace returns scores in 0-100 range, convert to 0.0-1.0
    avg_score = sum(matching_scores) / len(matching_scores)
    return avg_score / 100.0


def set_emotion_update_callback(callback, loop=None):
    """
    Register a callback function to be called when emotion updates are ready.

    Args:
        callback: async function with signature: callback(stage, emotion, metadata)
        loop: the main event loop to schedule the callback on
    """
    global emotion_update_callback, main_event_loop
    emotion_update_callback = callback
    main_event_loop = loop


def detect_faces(image_bytes: bytes) -> tuple[bytes, str]:
    global \
        latest_frame_bytes, \
        is_processing, \
        last_processed_image, \
        last_emotion_result, \
        emotion_buffer

    frame_start_time = time.time()

    # Always update the latest frame
    latest_frame_bytes = image_bytes

    # If already processing, return the last result immediately (frame skipping)
    if is_processing:
        print(f"⏭️  FRAME SKIPPED - DeepFace busy, returning cached result")
        if last_processed_image is not None:
            return last_processed_image, last_emotion_result
        else:
            # First time, no previous result, convert to image and return neutral
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            ret, buffer = cv2.imencode(".png", image)
            return buffer.tobytes(), "neutral"

    # Mark as processing
    print(f"🔄 START PROCESSING - Frame entered at {frame_start_time:.3f}")
    is_processing = True
    processing_start_time = time.time()

    try:
        # convert bytes to cv2 image
        nparr = np.frombuffer(latest_frame_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        emotion_result = "neutral"

        try:
            # face detection logic using OpenCV with red box around detected faces
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier()

            try:
                # Create a temporary file with .xml extension
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
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
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=8, minSize=(60, 60)
            )

            # Optimization: Only keep the largest face to reduce background interference
            if len(faces) > 0:
                largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
                # Overwrite faces list to contain only the largest face
                faces = [largest_face]

            for x, y, w, h in faces:
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
                margin = 0  # You can adjust margin if needed
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
            emotion_score = 0.0
            try:
                analyze = DeepFace.analyze(
                    target_img,
                    actions=["emotion"],
                    enforce_detection=False,
                    silent=True,
                )
                if analyze:
                    # analyze is a list of dicts
                    result = analyze[0]
                    current_emotion = result.get("dominant_emotion", "neutral")
                    # Extract the score for the detected emotion
                    emotion_score = result.get("emotion", {}).get(current_emotion, 0.0)
            except ValueError:
                # DeepFace might raise ValueError if image is too small or other issues
                pass

            # Add current emotion AND score to buffer as a tuple
            emotion_buffer.append((current_emotion, emotion_score))

            # Calculate the most frequent emotion in the buffer (Mode)
            # Extract just the emotion names for counting
            if emotion_buffer:
                emotion_names = [emo for emo, _ in emotion_buffer]
                counts = Counter(emotion_names)
                emotion_result = counts.most_common(1)[0][0]

                # Calculate confidence as average score of matching emotions
                confidence = calculate_confidence(emotion_buffer, emotion_result)

                print(
                    f"Raw: {current_emotion:10} (score: {emotion_score:.2f}) | Smoothed: {emotion_result:10} (confidence: {confidence:.2f}) | Buffer: {list(emotion_buffer)}"
                )
            else:
                emotion_result = current_emotion
                confidence = emotion_score
                print(
                    f"Raw: {current_emotion:10} (score: {emotion_score:.2f}) | Smoothed: {emotion_result:10} (confidence: {confidence:.2f})"
                )

            # Check if we need to send timed emotion updates
            current_time = time.time()
            global last_pre_update_time, last_post_update_time

            # Send "pre" update every 0.5 seconds
            if current_time - last_pre_update_time >= 0.5:
                if emotion_update_callback and main_event_loop:
                    metadata = {
                        "confidence": float(confidence)
                    }  # Convert to Python float for JSON serialization
                    # Use run_coroutine_threadsafe to schedule callback on main loop from thread
                    try:
                        asyncio.run_coroutine_threadsafe(
                            emotion_update_callback("pre", emotion_result, metadata),
                            main_event_loop,
                        )
                    except Exception as e:
                        print(f"Error calling emotion update callback (pre): {e}")
                last_pre_update_time = current_time

            # Send "post" update every 1.0 seconds
            if current_time - last_post_update_time >= 1.0:
                if emotion_update_callback and main_event_loop:
                    metadata = {
                        "confidence": float(confidence)
                    }  # Convert to Python float for JSON serialization
                    # Use run_coroutine_threadsafe to schedule callback on main loop from thread
                    try:
                        asyncio.run_coroutine_threadsafe(
                            emotion_update_callback("post", emotion_result, metadata),
                            main_event_loop,
                        )
                    except Exception as e:
                        print(f"Error calling emotion update callback (post): {e}")
                last_post_update_time = current_time

        except Exception as e:
            print(f"Analysis failed: {e}")
            emotion_result = "error"

        # convert cv2 image back to png bytes
        ret, buffer = cv2.imencode(".png", image)
        image_processed = buffer.tobytes()

        # Update global variables with the latest results
        last_processed_image = image_processed
        last_emotion_result = emotion_result

        # Calculate and print timing statistics
        processing_end_time = time.time()
        processing_duration = processing_end_time - processing_start_time
        total_duration = processing_end_time - frame_start_time

        print(
            f"✅ PROCESSING COMPLETE - Total: {total_duration:.3f}s | DeepFace: {processing_duration:.3f}s | Result: {emotion_result}"
        )

        return image_processed, emotion_result

    finally:
        # Release the processing lock
        is_processing = False
