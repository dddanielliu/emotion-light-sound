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
        setVideoStatus("preview error");
        setMicStatus("preview error");
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
        statusEl.textContent = `Status: Connected (Client ID: ${clientId})`;
        statusEl.style.backgroundColor = '#ccffcc';
        setSocketStatus("connected");

        // NOW enable audio + video streaming
        startMediaStreaming(clientId);
    });

    socket.on('disconnect', (reason) => {
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

        // if (audioContext) {
        //     audioContext.close().then(() => {
        //         audioContext = null;
        //     });
        // }
    });

    socket.on('connect_error', (error) => {
        statusEl.textContent = `Status: Error (${error.message})`;
        statusEl.style.backgroundColor = '#ffcccc';
        buttonEl.disabled = false;
        inputEl.disabled = false;
        setSocketStatus("error");
    });

    socket.on('processed_video_frame', (metadata, blob) => {
        // 1. Get the display element (now an <img>)
        const processedImage = document.getElementById('processed_cam'); 
        
        if (processedImage && blob) {
            // The 'blob' from Socket.IO is a JavaScript ArrayBuffer (binary data).
            const receivedBlob = new Blob([blob], { type: 'image/webp' }); 
            // console.log("Received processed video frame blob:", receivedBlob);
            // console.log("Metadata:", metadata);
            
            // Revoke the previous Object URL to free memory
            // This check is important for continuous streaming
            if (processedImage.src && processedImage.src.startsWith('blob:')) {
                URL.revokeObjectURL(processedImage.src);
            }
            
            // 2. Create the URL and set it as the source
            const imgUrl = URL.createObjectURL(receivedBlob);
            processedImage.src = imgUrl;

            // Note: No need for .play().catch() since we are using <img>!
            
            // Optional: Log latency
            // const latency = Date.now() - metadata.original_timestamp;
            // console.log(`Frame received. Latency: ${latency}ms`);
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

        // Audio processing (turn mic on now)
        // const audioTrack = mediaStream.getAudioTracks()[0];
        // if (audioTrack) {
        //     setupMicrophoneProcessing(clientId, mediaStream);
        // } else {
        //     setMicStatus("not available");
        // }

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



// --- MICROPHONE PROCESSING ---
// async function setupMicrophoneProcessing(clientId, stream) {
//     try {
//         audioContext = new AudioContext();

//         micSource = audioContext.createMediaStreamSource(stream);

//         await audioContext.audioWorklet.addModule('/js/mic-resampler.js');
//         processorNode = new AudioWorkletNode(audioContext, 'mic-resampler', { numberOfOutputs: 0 });
//         processorNode.port.postMessage({ type: 'set-sample-rate', sampleRate: audioContext.sampleRate });

//         micSource.connect(processorNode);
//         mic_available = true;
//         start_msg();
//         setMicStatus("active");

//         processorNode.port.onmessage = function(event) {
//             const { audioData, sampleRate } = event.data;
//             if (audioData && socket && socket.connected) {
//                 socket.emit('audio_chunk', { client_id: clientId, sampleRate }, audioData);
//             }
//         };

//     } catch (e) {
//         console.error("Microphone processing setup error:", e);
//         setMicStatus("error");
//     }
// }



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