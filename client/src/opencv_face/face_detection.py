import numpy as np
import cv2
print("OpenCV version:", cv2.__version__)

def detect_faces(image_bytes: bytes) -> bytes:
    # convert bytes to cv2 image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    # face detection logic using OpenCV with red box around detected faces without locading external files
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    for (x, y, w, h) in faces:
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
    # convert cv2 image back to png bytes
    ret, buffer = cv2.imencode('.png', image)
    image_processed = buffer.tobytes()
    return image_processed
