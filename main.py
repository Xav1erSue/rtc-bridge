from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from webrtc_service import WebRTCService, TransformMethod
import random
import sys
from multiprocessing import Process
from time import sleep

# 创建FastAPI应用程序实例
app = FastAPI(docs_url="/documentation", redoc_url=None)

peers = set()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def getResErrData(msg):
    return {"code": -1024, "data": None, "msg": msg}


def getResSuccessData(data=None):
    return {"code": 2000, "data": data, "msg": "success"}


def start_service(rtsp_url, peer_id, method):
    service = WebRTCService(rtsp_url=rtsp_url, peer_id=peer_id, method=method)
    asyncio.get_event_loop().run_until_complete(service.connect())
    res = asyncio.get_event_loop().run_until_complete(service.loop())
    sys.exit(res)


# rtsp 转 webrtc
class CreateSessionModel(BaseModel):
    # 转换方式：推流/拉流
    method: TransformMethod
    # 推/拉流地址
    rtspUrl: str


@app.post("/createSession")
async def createSession(model: CreateSessionModel):
    if model.method is None:
        return getResErrData("method is required")
    if model.rtspUrl is None:
        return getResErrData("rtspUrl is required")

    our_id = None
    while our_id is None:
        our_id = random.randrange(10, 10000)
        if our_id in peers:
            our_id = None

    peers.add(our_id)
    p = Process(target=start_service, args=(model.rtspUrl, our_id, model.method))
    p.start()
    sleep(3)

    return getResSuccessData(our_id)


if __name__ == "__main__":
    # 运行FastAPI应用程序
    uvicorn.run(app="main:app", host="127.0.0.1", port=8081, reload=True)
    pass
