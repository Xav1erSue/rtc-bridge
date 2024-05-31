import json
import asyncio
from lib import *
import gi
import websockets
from enum import Enum

gi.require_version("GstSdp", "1.0")
from gi.repository import GstSdp

gi.require_version("GstWebRTC", "1.0")
from gi.repository import GstWebRTC


class TransformMethod(Enum):
    RTSP_TO_WEB_RTC = 0
    WEB_RTC_TO_RTSP = 1


class WebRTCService:
    def __init__(self, method, rtsp_url, peer_id):
        self.method = method
        self.rtsp_url = rtsp_url
        self.peer_id = peer_id
        self.server = "ws://127.0.0.1:8080"
        self.ws = None
        self.wrtc = None

    async def connect(self):
        self.ws = await websockets.connect(self.server)
        message = json.dumps({"type": "CONNECT", "data": {"peerId": self.peer_id}})
        await self.ws.send(message)

    def start_pipeline(self):

        outsink = None

        if self.method == TransformMethod.WEB_RTC_TO_RTSP:
            outsink = RTSPSink(self.rtsp_url)
        else:
            outsink = FakeSink()

        self.wrtc = WebRTC(outsink=outsink)

        # if self.method == TransformMethod.WEB_RTC_TO_RTSP:
        #     self.wrtc.add_transceiver(WebRTC.RECVONLY, "VP8")
        # else:
        #     self.wrtc.add_transceiver(WebRTC.SENDONLY, "VP8")

        @self.wrtc.on("candidate")
        def on_candidate(candidate):
            message = json.dumps(
                {"type": "ON_ICE_CANDIDATE", "data": {"candidate": candidate}}
            )
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.ws.send(message))
            print("send candidate", candidate)

        @self.wrtc.on("answer")
        def on_answer(answer):
            self.wrtc.set_local_description(answer)

        @self.wrtc.on("offer")
        def on_offer(offer):
            self.wrtc.set_local_description(offer)
            message = json.dumps(
                {"type": "OFFER_SDP", "data": {"sdp": offer.sdp.as_text()}}
            )
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.ws.send(message))
            print("send offer", offer.sdp.as_text())

        @self.wrtc.on("negotiation-needed")
        def on_negotiation_needed(element):
            print("Negotiation needed!")

        source = None

        if self.method == TransformMethod.RTSP_TO_WEB_RTC:
            source = RTSPSource(self.rtsp_url)
        else:
            source = TestSource()

        self.wrtc.add_stream(source)

    async def loop(self):
        async for message in self.ws:
            print(message)
            msg = json.loads(message)
            type = msg["type"]

            if type == "CONNECT_OK":
                self.start_pipeline()

            elif type == "SESSION_OK":
                self.wrtc.create_offer()

            elif type == "OFFER_SDP":
                data = msg["data"]
                sdp = data["sdp"]
                _, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(
                    GstWebRTC.WebRTCSDPType.OFFER, sdpmsg
                )
                self.wrtc.set_remote_description(answer)

            elif type == "ANSWER_SDP":
                data = msg["data"]
                sdp = data["sdp"]
                _, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(
                    GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg
                )
                self.wrtc.set_remote_description(answer)

            elif type == "ON_ICE_CANDIDATE":
                print("add_ice_candidate")
                self.wrtc.add_ice_candidate(msg["candidate"])

            elif type == "SESSION_END":
                return 0
