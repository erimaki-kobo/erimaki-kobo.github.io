(function(){
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
const bn=t=>{const m=/^b?(\d+)$/i.exec(String(t).trim());return m?+m[1]:null;};
const vk=v=>{const m=/^v?(\d+)\.(\d+)\.(\d+)/.exec(String(v).trim());return m?[+m[1],+m[2],+m[3]]:null;};
const vcmp=(a,b)=>{for(let i=0;i<3;i++){if(a[i]!==b[i])return a[i]<b[i]?-1:1;}return 0;};
const slug=n=>n.toLowerCase().replace(/[^a-z0-9]+/g,"-");
const rel=t=>t?'<a href="https://github.com/ggml-org/llama.cpp/releases/tag/'+t+'">'+t+'</a>':'no release yet (after '+D.head+')';
function verdict(cls,head,body){return '<div class="verdict '+cls+'">'+head+(body?'<span>'+body+'</span>':'')+'</div>';}
function buildCheck(need,label){
  const b=bn($("b").value);
  if(b===null||!$("b").value.trim())return "";
  if(!need)return '<li>Your build b'+b+': no release has it yet.</li>';
  return b>=bn(need)?'<li><span class="s y">yes</span> Your llama.cpp b'+b+' '+label+' (needs '+need+' or later).</li>'
                     :'<li><span class="s n">no</span> Your llama.cpp b'+b+' is older than '+need+'. Upgrade to '+need+' or later.</li>';
}
function relCheck(id,need,who){
  const v=vk($(id).value);
  if(!v||!$(id).value.trim())return "";
  if(!need)return '<li>'+who+' '+esc($(id).value.trim())+': no '+who+' release bundles it yet.</li>';
  return vcmp(v,vk(need))>=0?'<li><span class="s y">yes</span> '+who+' '+esc($(id).value.trim())+' bundles it (from '+need+').</li>'
                            :'<li><span class="s n">no</span> '+who+' '+esc($(id).value.trim())+' is older than '+need+'. Upgrade to '+need+' or later.</li>';
}
function nameInfo(n){
  const r=D.n[n];
  let h='<ul><li>llama.cpp loads it from '+rel(r[0])+(r[1]?' ('+r[1]+')':'')+'.</li>'+
    '<li>Ollama from '+(r[2]||'no release yet')+'; llama-cpp-python from '+(r[3]||'no release yet')+'.</li>';
  h+=buildCheck(r[0],"loads it")+relCheck("o",r[2],"Ollama")+relCheck("p",r[3],"llama-cpp-python");
  const older=r[4].filter(m=>D.n[m]&&D.n[m][0]&&r[0]&&bn(D.n[m][0])<bn(r[0])).sort((a,b)=>bn(D.n[a][0])-bn(D.n[b][0]));
  if(older.length){
    const m=older[0];
    h+='<li>Same handling as <code>'+esc(m)+'</code>, known since '+D.n[m][0]+'. If you cannot upgrade: <code>gguf-new-metadata --pre-tokenizer '+esc(m)+' in.gguf out.gguf</code> (see <a href="#rename">conditions</a>).</li>';
  }
  h+='<li><a href="#n-'+slug(n)+'">Row in the name table</a></li></ul>';
  return h;
}
function lookup(){
  const q=$("q").value, res=$("res"), st=$("status");
  st.textContent="";res.innerHTML="";
  document.querySelectorAll("tr.hit").forEach(t=>t.classList.remove("hit"));
  if(!q.trim()&&!$("b").value.trim()){st.textContent="Paste an error, a chkhsh or a name.";return;}
  let out="";
  const hs=[...new Set((q.match(/\b[0-9a-f]{64}\b/gi)||[]).map(x=>x.toLowerCase()))];
  if(/missing pre-tokenizer type/i.test(q)){
    out+=verdict("v-load","The file has no tokenizer.ggml.pre.","It was converted before the pre-tokenizer key existed (llama.cpp "+Object.values(D.n).map(r=>r[0]).filter(Boolean).sort((a,b)=>bn(a)-bn(b))[0]+"). It loads with a generic split and lower quality. Re-convert with a current llama.cpp, or download a newer conversion of the model.");
  }
  for(const h of hs){
    const r=D.h[h];
    if(!r){
      out+=verdict("v-bad","chkhsh "+h.slice(0,12)+"... is not recognized by any llama.cpp build up to "+D.head+".","Upgrading will not help yet. Your tokenizer differs from every registered one: see <a href=\"#not-listed\">what to do</a>.");
      continue;
    }
    let body='<ul><li>The converter writes <code>'+esc(r[0])+'</code>.'+(r[1]?' The hash was taken from <a href="'+esc(r[1])+'">'+esc(r[1].replace("https://huggingface.co/",""))+'</a>.':'')+'</li>';
    if(D.dup[h])body+='<li>This hash is listed for '+D.dup[h].map(x=>'<code>'+esc(x)+'</code>').join(", ")+'; the last entry wins. <a href="#shared">Why this matters</a></li>';
    body+=buildCheck(r[2],"recognizes it when converting");
    body+='</ul>';
    out+=verdict(r[2]?"v-ok":"v-load",(r[2]?"Recognized from llama.cpp "+r[2]+" ("+r[3]+").":"Recognized only on master after "+D.head+"."),"Convert with that checkout or later. <a href=\"#h-"+h.slice(0,16)+"\">Row in the hash table</a>")+body;
    if(D.n[r[0]])out+='<p><strong>Loading the result</strong> (name <code>'+esc(r[0])+'</code>):</p>'+nameInfo(r[0]);
    else if(D.hashonly.indexOf(r[0])>=0)out+='<p class="note"><code>'+esc(r[0])+'</code> is a WordPiece model; the loader does not check this name.</p>';
    const row=document.getElementById("h-"+h.slice(0,16));if(row)row.classList.add("hit");
  }
  if(!hs.length){
    let n=null;
    let m=/unknown pre-tokenizer type:\s*'([^']+)'/i.exec(q)||/tokenizer\.ggml\.pre\s*(?:str\s*)?[=:]?\s*['"]?([A-Za-z0-9_.\-]+)/i.exec(q);
    if(m)n=m[1];
    else if(/^\s*['"]?[A-Za-z0-9_.\-]+['"]?\s*$/.test(q))n=q.trim().replace(/['"]/g,"");
    if(n){
      const key=Object.keys(D.n).find(k=>k.toLowerCase()===n.toLowerCase());
      if(key){
        const r=D.n[key];
        out+=verdict(r[0]?"v-ok":"v-load",(r[0]?"'"+esc(key)+"' loads from llama.cpp "+r[0]+" ("+r[1]+").":"'"+esc(key)+"' is only on master after "+D.head+"."),"")+nameInfo(key);
        const row=document.getElementById("n-"+slug(key));if(row)row.classList.add("hit");
      }else if(D.hashonly.indexOf(n)>=0){
        out+=verdict("v-ok","'"+esc(n)+"' is a WordPiece model name; the loader does not check it.","");
      }else{
        const near=Object.keys(D.n).filter(k=>k.toLowerCase().indexOf(n.toLowerCase().slice(0,4))>=0).slice(0,8);
        out+=verdict("v-bad","No llama.cpp build up to "+D.head+" accepts '"+esc(n)+"'.","The name may come from a fork or a hand-edited file, or be newer than this table."+(near.length?" Similar names: "+near.map(x=>"<code>"+esc(x)+"</code>").join(", ")+".":""));
      }
    }else if(/pre-tokenizer was not recognized/i.test(q)){
      out+=verdict("v-load","Paste the whole warning block.","The line <code>** chkhsh: ...</code> above the error has the 64-character hash this lookup needs.");
    }else if(!out){
      st.textContent="No chkhsh or pre-tokenizer name found in the text.";
    }
  }
  res.innerHTML=out;
}
$("go").addEventListener("click",lookup);
$("q").addEventListener("keydown",ev=>{if(ev.key==="Enter"&&(ev.ctrlKey||ev.metaKey))lookup();});
function filt(inp,tb){$(inp).addEventListener("input",()=>{const f=$(inp).value.trim().toLowerCase();document.querySelectorAll("#"+tb+" tbody tr").forEach(r=>{r.style.display=!f||r.getAttribute("data-k").toLowerCase().indexOf(f)>=0?"":"none";});});}
filt("fh","ht");filt("fn","nt");
const p=new URLSearchParams(location.search).get("q");
if(p){$("q").value=p;lookup();}
})();
