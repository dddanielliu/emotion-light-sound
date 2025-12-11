// --- GLOBALS ---
let socket = null;
let audioContext = null;
let processorNode = null;
let micSource = null;
let videoInterval = null;

// Unified audio+video media stream (created on page load)
let mediaStream = null;

// Status UI Update Helpers
function setSocketStatus(text) { document.getElementById("s_socket").textContent = text; }
function setMicStatus(text) { document.getElementById("s_mic").textContent = text; }
function setVideoStatus(text) { document.getElementById("s_video").textContent = text; }

let mic_available = false;
function start_msg() { console.log("Microphone streaming started."); }


// --- DOM READY ---
document.addEventListener('DOMContentLoaded', () => {
    const connectButton = document.getElementById('connect_button');
    const clientIdInput = document.getElementById('client_id_input');
    const statusMessage = document.getElementById('status_message');

    const urlParams = new URLSearchParams(window.location.search);
    const clientIdFromUrl = urlParams.get('client_id');
    const autoStart = urlParams.get('autoStart');

    // Start preview immediately (audio+video) but do not process audio yet
    startPreviewAudioVideo();

    if (clientIdFromUrl) {
        clientIdInput.value = clientIdFromUrl;
        console.log(`Client ID '${clientIdFromUrl}' loaded from URL.`);
    }

    connectButton.addEventListener('click', () => {
        const clientId = clientIdInput.value;
        if (!clientId) {
            statusMessage.textContent = 'Status: Please enter a Client ID.';
            statusMessage.style.backgroundColor = '#ffcccc';
            return;
        }
        connectSocket(clientId, statusMessage, connectButton, clientIdInput);
    });

    if (clientIdFromUrl && autoStart === 'true') {
        console.log("autoStart is true, connecting in 1.5 seconds...");
        statusMessage.textContent = `Status: Auto-connecting with Client ID '${clientIdFromUrl}'...`;
        setTimeout(() => {
            connectSocket(clientIdFromUrl, statusMessage, connectButton, clientIdInput);
        }, 1500);
    }
});


// --- START PREVIEW ON PAGE LOAD ---
async function startPreviewAudioVideo() {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });

        const video = document.getElementById('cam');
        video.srcObject = mediaStream;
        video.muted = true;
        await video.play();

        setVideoStatus("preview active");
        setMicStatus("captured (inactive)");

    } catch (err) {
        console.error("Preview error:", err);
        setVideoStatus(`Error: ${err.name} - ${err.message}`);
        setMicStatus(`Error: ${err.name}`);
    }
}



// --- SOCKET CONNECTION LOGIC ---
function connectSocket(clientId, statusEl, buttonEl, inputEl) {
    if (socket) socket.disconnect();

    statusEl.textContent = "Status: Connecting...";
    buttonEl.disabled = true;
    inputEl.disabled = true;
    setSocketStatus("connecting");

    const wsprotocol = window.location.protocol === "https:" ? "wss" : "ws";

    socket = io(`${wsprotocol}://${window.location.host}/`, {
        auth: { 'client_id': clientId }
    });

    socket.on('connect', () => {
        console.log("✅ Socket connected!");
        statusEl.textContent = `Status: Connected (Client ID: ${clientId})`;
        statusEl.style.backgroundColor = '#ccffcc';
        setSocketStatus("connected");

        // NOW enable audio + video streaming
        startMediaStreaming(clientId);
    });

    socket.on('disconnect', (reason) => {
        console.log("❌ Socket disconnected:", reason);
        statusEl.textContent = `Status: Disconnected (${reason})`;
        statusEl.style.backgroundColor = '#e0e0e0';
        buttonEl.disabled = false;
        inputEl.disabled = false;

        setSocketStatus("disconnected");
        setMicStatus("inactive");
        setVideoStatus("preview active"); // preview stays active!

        if (videoInterval) {
            clearInterval(videoInterval);
            videoInterval = null;
        }
    });

    socket.on('connect_error', (error) => {
        console.error("Socket connection error:", error);
        statusEl.textContent = `Status: Error (${error.message})`;
        statusEl.style.backgroundColor = '#ffcccc';
        buttonEl.disabled = false;
        inputEl.disabled = false;
        setSocketStatus("error");
    });

    socket.on('processed_video_frame', (metadata, blob) => {
        console.log("📹 Received processed_video_frame:", metadata);
        // 1. Get the display element (now an <img>)
        const processedImage = document.getElementById('processed_cam');

        if (processedImage && blob) {
            // The 'blob' from Socket.IO is a JavaScript ArrayBuffer (binary data).
            const receivedBlob = new Blob([blob], { type: 'image/webp' });

            // Revoke the previous Object URL to free memory
            if (processedImage.src && processedImage.src.startsWith('blob:')) {
                URL.revokeObjectURL(processedImage.src);
            }

            // 2. Create the URL and set it as the source
            const imgUrl = URL.createObjectURL(receivedBlob);
            processedImage.src = imgUrl;

            // Update emotion display
            if (metadata.emotion) {
                const emotionEl = document.getElementById('emotion_result');
                if (emotionEl) {
                    emotionEl.textContent = metadata.emotion.toUpperCase();
                }

                // Update bubble visualization
                console.log("Calling setBubbleEmotion with:", metadata.emotion);
                if (typeof setBubbleEmotion === 'function') {
                    setBubbleEmotion(metadata.emotion);
                } else {
                    console.warn("setBubbleEmotion is not a function!");
                }
            }
        }
    });

    socket.on('music_generated', (data) => {
        console.log("Music generated event received:", data);
        if (data && data.url) {
            playMusic(data.url);
        }

        // Display music emotion info in the top right corner
        if (data) {
            console.log("Displaying music emotion:", data);
            displayMusicEmotion(data);
        }
    });

}

// --- START STREAMING USING EXISTING STREAM ---
async function startMediaStreaming(clientId) {
    try {
        if (!mediaStream) {
            console.error("No media stream from preview!");
            return;
        }

        // Video processing (same track used, no restart)
        const videoTrack = mediaStream.getVideoTracks()[0];
        if (videoTrack) {
            startVideoProcessing(clientId, mediaStream);
        } else {
            setVideoStatus("not available");
        }

    } catch (e) {
        console.error("Streaming start error:", e);
        setMicStatus("error");
        setVideoStatus("error");
    }
}

// --- VIDEO PROCESSING ---
function startVideoProcessing(client_id, stream) {
    const video = document.getElementById('cam');
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Stream already attached to video from preview; just reuse it
    video.srcObject = stream;
    video.muted = true;
    video.play();

    video.onloadedmetadata = () => {
        const srcW = video.videoWidth;
        const srcH = video.videoHeight;

        const maxW = 1280;
        const maxH = 720;

        const scale = Math.min(maxW / srcW, maxH / srcH, 1);

        const newW = Math.round(srcW * scale);
        const newH = Math.round(srcH * scale);

        canvas.width = newW;
        canvas.height = newH;

        if (videoInterval) clearInterval(videoInterval);

        videoInterval = setInterval(() => {
            if (socket && socket.connected) {
                ctx.drawImage(video, 0, 0, newW, newH);
                canvas.toBlob((blob) => {
                    if (blob) {
                        socket.emit(
                            'video_frame',
                            {
                                client_id,
                                timestamp: Date.now(),
                                originalWidth: video.videoWidth,
                                originalHeight: video.videoHeight,
                                width: canvas.width,
                                height: canvas.height
                            },
                            blob
                        );
                    }
                }, 'image/webp', 0.6);
            }
        }, 80); // ~10 FPS

        setVideoStatus("active");
    };
}

// --- AUDIO PLAYBACK ---
let currentAudio = null;
const FADE_DURATION = 2000; // 2 seconds

function playMusic(url) {
    console.log("Playing music from:", url);
    const newAudio = new Audio(url);
    newAudio.volume = 0; // Start silent for fade-in

    // Play the new audio
    newAudio.play().then(() => {
        console.log("Music started playing");

        // Fade In New Audio
        const fadeInInterval = setInterval(() => {
            if (newAudio.volume < 1.0) {
                newAudio.volume = Math.min(1.0, newAudio.volume + 0.05); // Increase volume
            } else {
                clearInterval(fadeInInterval);
            }
        }, FADE_DURATION / 20); // Update 20 times within fade duration

        // Fade Out Old Audio (if exists)
        if (currentAudio) {
            const oldAudio = currentAudio;
            const fadeOutInterval = setInterval(() => {
                if (oldAudio.volume > 0.05) {
                    oldAudio.volume = Math.max(0, oldAudio.volume - 0.05); // Decrease volume
                } else {
                    clearInterval(fadeOutInterval);
                    oldAudio.pause();
                    oldAudio.remove(); // Clean up
                    console.log("Old music stopped and removed");
                }
            }, FADE_DURATION / 20);
        }

        // Update current audio reference
        currentAudio = newAudio;

        // Handle when the song ends (optional: loop or just stop)
        newAudio.onended = () => {
            console.log("Music finished");
            // If this is still the current audio, clear it
            if (currentAudio === newAudio) {
                currentAudio = null;
            }
        };

    }).catch(err => {
        console.error("Error playing music:", err);
    });
}

// --- DISPLAY MUSIC EMOTION ---
function displayMusicEmotion(data) {
    const display = document.getElementById('music_emotion_display');
    const emotionValue = document.getElementById('music_emotion_value');

    if (!display || !emotionValue) {
        console.warn("Music emotion display elements not found");
        return;
    }

    // Extract emotion
    const emotion = data.emotion || 'unknown';

    // Update content
    emotionValue.textContent = emotion.toUpperCase();

    // Change gradient color based on emotion
    const emotionColors = {
        'happy': 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        'sad': 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        'angry': 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        'neutral': 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
        'fear': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'surprise': 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
        'disgust': 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)'
    };

    display.style.background = emotionColors[emotion.toLowerCase()] ||
        'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

    // Show the display with animation
    display.classList.add('visible');

    console.log(`✨ Music emotion displayed: ${emotion}`);
}