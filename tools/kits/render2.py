import json, sys, time, urllib.request, urllib.parse, subprocess, threading, re
B="http://127.0.0.1:8001"
OUT=sys.argv[7]
def post(path, d):
    r=urllib.request.Request(B+path, json.dumps(d).encode(), {"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))
peak=[0]
def vram():
    while True:
        try:
            v=int(subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"]).split()[0]); peak[0]=max(peak[0],v)
        except Exception: pass
        time.sleep(1)
threading.Thread(target=vram,daemon=True).start()
lyr=open(sys.argv[1]).read(); style=sys.argv[2]; name=sys.argv[3]; seed=int(sys.argv[4]); dur=float(sys.argv[5]); bpm=int(sys.argv[6])
t0=time.time()
r=post("/release_task",{"prompt":style,"lyrics":lyr,"audio_duration":dur,"bpm":bpm,"time_signature":(sys.argv[8] if len(sys.argv)>8 else "4"),"vocal_language":"en","audio_format":"mp3","batch_size":2,"use_random_seed":False,"seed":seed,"inference_steps":8,"thinking":False,"use_cot_caption":False,"use_cot_language":False})
tid=r["data"]["task_id"]
DEADLINE=840  # seconds; the server cannot cancel a job, so stop waiting well before the factory's 900 s cap
while True:
    q=post("/query_result",{"task_id_list":[tid]})["data"][0]
    if q["status"]!=0: break
    if time.time()-t0>DEADLINE: print("TIMEOUT waiting for the audio server, task",tid); sys.exit(3)
    time.sleep(3)
el=time.time()-t0
print("status",q["status"],"elapsed %.1f"%el,"peakVRAM",peak[0])
if q["status"]!=1: print(q); sys.exit(1)
res=json.loads(q["result"])
for i,x in enumerate(res):
    fn=OUT+name+("" if i==0 else "b")+".mp3"
    urllib.request.urlretrieve(B+x["file"], fn)
    print(fn, x.get("seed_value"), x.get("metas"))
