import os
import ssl
import argparse
import json
import cv2
from aiohttp import web
import socketio
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCIceServer,
    RTCConfiguration,
)
from aiortc.contrib.media import MediaRelay
from av import VideoFrame

ROOT = os.path.dirname(__file__)

pcs = set()
relay = MediaRelay()

ice_servers = [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
app = web.Application()
sio.attach(app)


class GrayVideoStreamTrack(VideoStreamTrack):
    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        # Gri filtreyi uygula
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Yeni frame oluştur
        new_frame = VideoFrame.from_ndarray(gray, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "app.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


@sio.on("connect")
async def connect(sid, environ):
    print(f"Client connected: {sid}")


@sio.on("disconnect")
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


@sio.on("sdp")
async def handle_sdp(sid, data):
    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    pc = RTCPeerConnection()
    pc._configuration = RTCConfiguration(iceServers=ice_servers)
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        print(f"Track received: {track.kind}")
        if track.kind == "video":
            gray_track = GrayVideoStreamTrack(relay.subscribe(track))
            print("Track pc ye eklendi")
            pc.addTrack(gray_track)

    @pc.on("icecandidate")
    async def on_icecandidate(event):
        if event.candidate:
            print(f"Server generated ICE candidate: {event.candidate}")
            try:
                await sio.emit(
                    "ice_candidate",
                    {
                        "candidate": event.candidate.candidate,
                        "sdpMid": event.candidate.sdpMid,
                        "sdpMLineIndex": event.candidate.sdpMLineIndex,
                    },
                    room=sid,
                )
                print(f"ICE candidate sent to client: {sid}")
            except Exception as e:
                print(f"Error sending ICE candidate to client: {e}")
        else:
            print("ICE gathering completed")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    print("Generated SDP Answer:")
    print(
        json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}, indent=2
        )
    )
    print("1")
    await sio.emit(
        "sdp_answer",
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
        room=sid,
    )
    print("2")

    @sio.on("ice_candidate")
    async def handle_ice_candidate(sid, data):
        print("Received ICE candidate:")
        print(json.dumps(data, indent=2))


app.router.add_get("/", index)
app.router.add_get("/app.js", javascript)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run an HTTPS server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host IP address")
    parser.add_argument("--port", type=int, default=8000, help="Port Number")
    args = parser.parse_args()

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        certfile="/home/dogan/cert.pem", keyfile="/home/dogan/key.pem"
    )
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
