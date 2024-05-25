import json
import asyncio
import websockets


class WebRTCSimpleServer(object):
    def __init__(self):
        self.addr = "0.0.0.0"
        self.port = 8080
        self.keepalive_timeout = 30
        self.peers = {}

    async def on_start(self, ws, path):
        peer_id = None
        # 开始处理消息
        try:
            while True:
                message = await ws.recv()
                print(message)
                msg = json.loads(message)

                type = msg["type"]
                data = msg["data"]

                if type == "CONNECT":
                    peer_id = data["peerId"]
                    if peer_id in self.peers:
                        await ws.close(code=1002, reason="peer_id already exists")
                        raise Exception("Peer id {!r} already exists".format(peer_id))
                    self.peers[peer_id] = [ws, None, None]
                    response = json.dumps({"type": "CONNECT_OK"})
                    await ws.send(response)

                # 建立会话
                elif type == "SESSION":
                    target_id = data["targetId"]
                    if target_id not in self.peers:
                        response = json.dumps(
                            {
                                "type": "SESSION_ERROR",
                                "data": {"error": "target not found"},
                            }
                        )
                        await ws.send(response)
                        continue
                    target_ws = self.peers[target_id][0]
                    self.peers[peer_id][1] = target_id
                    self.peers[target_id][1] = peer_id
                    response = json.dumps({"type": "SESSION_OK"})
                    await target_ws.send(response)
                    await ws.send(response)
                # 其他直接转发
                else:
                    target_id = self.peers[peer_id][1]
                    if target_id:
                        target_ws = self.peers[target_id][0]
                        await target_ws.send(message)
        finally:
            print("connection closed from peer: {} ".format(peer_id))
            target_id = self.peers[peer_id][1]
            if target_id:
                target_ws = self.peers[target_id][0]
                response = json.dumps({"type": "SESSION_END"})
                await target_ws.send(response)
                self.peers[target_id][1] = None
            del self.peers[peer_id]

    def run(self):
        start_server = websockets.serve(self.on_start, self.addr, self.port)
        print("server start at {}:{}".format(self.addr, self.port))
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    server = WebRTCSimpleServer()
    server.run()
