const config = {
  iceServers: [
    {
      urls: 'stun:stun.l.google.com:19302'
    }
  ]
};

const constraints = {
  video: true
};

let pc;
let socket;

function connectSocket() {
  socket = io();

  socket.on('connect', () => {
    console.log('Connected to server');
  });

  socket.on('sdp_answer', async (data) => {
    console.log("Received SDP answer from server:", data);
    await pc.setRemoteDescription(new RTCSessionDescription(data));
  });

  socket.on('ice_candidate', async (data) => {
    console.log("Received ICE candidate from server:", data);
    try {
        await pc.addIceCandidate(new RTCIceCandidate(data));
        console.log("Successfully added ICE candidate from server");
    } catch (e) {
        console.error("Error adding received ICE candidate from server:", e);
    }
});
}

async function start() {
  try {
    console.log("Starting WebRTC connection...");
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    console.log("Got media stream:", stream);

    pc = new RTCPeerConnection(config);
    console.log("Created RTCPeerConnection");

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log("New ICE candidate:", event.candidate);
        socket.emit('ice_candidate', event.candidate);
      } else {
        console.log("ICE gathering completed");
      }
    };

    pc.onconnectionstatechange = (event) => {
      console.log("Connection state changed:", pc.connectionState);
    };

    pc.ontrack = (event) => {
      console.log("Received remote track:", event.track);
      const remoteVideo = document.querySelector('#remoteVideo');
      if (remoteVideo.srcObject !== event.streams[0]) {
        remoteVideo.srcObject = event.streams[0];
        console.log("Remote video stream set");
      }
    };

    stream.getTracks().forEach(track => {
      pc.addTrack(track, stream);
      console.log("Added track to peer connection:", track.kind);
    });

    console.log("Creating offer...");
    const offer = await pc.createOffer();
    console.log("Offer created:", offer);

    console.log("Setting local description...");
    await pc.setLocalDescription(offer);
    console.log("Local description set");

    socket.emit('sdp', { type: offer.type, sdp: offer.sdp });

  } catch (error) {
    console.error('Error starting the connection:', error);
  }
}

const startBtn = document.querySelector("button#startBtn");
startBtn.addEventListener("click", start);

connectSocket();

console.log("Script loaded. Click the start button to begin.");