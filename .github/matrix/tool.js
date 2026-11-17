(function(){
var DATA=JSON.parse(document.getElementById("matrix-data").textContent);
/* logic-begin */
function parseVer(s){return String(s).split(".").map(function(x){return parseInt(x,10)||0})}
function cmpVer(a,b){for(var i=0;i<Math.max(a.length,b.length);i++){var x=a[i]||0,y=b[i]||0;if(x!==y)return x<y?-1:1}return 0}
function cuF(n){var d=n.replace("cu","");return parseInt(d.slice(0,2),10)+parseInt(d.slice(2),10)/10}
function pyOk(spec,py){if(!py)return true;var p=parseVer(py);return spec.split(",").every(function(c){
  var m=c.trim().match(/^(>=|<=|<|>|==)\s*([0-9.]+)$/);if(!m)return true;var k=cmpVer(p,parseVer(m[2]));
  return m[1]===">="?k>=0:m[1]==="<="?k<=0:m[1]==="<"?k<0:m[1]===">"?k>0:k===0})}
function glibcOk(pl,g){if(!g)return true;var m=pl.match(/^manylinux_(\d+)_(\d+)$/);if(!m)return true;
  return cmpVer(parseVer(g),[parseInt(m[1],10),parseInt(m[2],10)])>=0}
function vllmGpu(build,archs,cc){if(cc==="6.x")return false;var f=parseFloat(cc);
  if(f===7)return archs.indexOf("7.0")>=0&&build<13;
  if(f>=10)return build>=12.8&&archs.indexOf(cc)>=0;
  return true}
function torchGpu(tc,cc){if(cc==="6.x")return false;var f=parseFloat(cc);
  if(f===7)return tc<13;if(f>=10)return tc>=12.8;return true}
function evalRelease(D,r,inp){
  var common=[];
  if(!pyOk(r.py,inp.py))common.push("python");
  var p1={kind:"pypi",v:r.v,torch:r.torch,cm:r.cm,variant:null,tindex:null,pl:r.pl,why:common.slice()};
  if(!glibcOk(r.pl,inp.glibc))p1.why.push("glibc");
  if(!vllmGpu(parseFloat(r.bc),r.ar,inp.cc))p1.why.push("gpu");
  else if(!torchGpu(parseFloat(r.tc),inp.cc)){
    var c=(D.torch[r.torch]||[]).filter(function(n){var f=cuF(n);return Math.floor(f)===r.cm&&torchGpu(f,inp.cc)});
    if(c.length)p1.tindex=c[0];else p1.why.push("torch-gpu")}
  if(cmpVer(inp.driver,D.dmin[String(r.cm)])<0)p1.why.push("driver");
  var best=null;
  r["var"].forEach(function(x){
    var b=cuF(x.n),why=common.slice();
    if(!glibcOk(x.pl,inp.glibc))why.push("glibc");
    if(!vllmGpu(b,r.ar,inp.cc)||!torchGpu(b,inp.cc))why.push("gpu");
    if(cmpVer(inp.driver,D.dmin[String(x.cm)])<0)why.push("driver");
    if(!why.length&&(best===null||b>cuF(best.variant)))
      best={kind:"variant",v:r.v,torch:x.t,cm:x.cm,variant:x.n,tindex:x.n,pl:x.pl,url:x.u,why:[]}});
  var path=p1.why.length?best:p1;
  if(path){
    path.cmd=path.kind==="pypi"
      ?"uv pip install vllm=="+r.v+(path.tindex?" --extra-index-url https://download.pytorch.org/whl/"+path.tindex:"")
      :"uv pip install \""+path.url+"\" --extra-index-url https://download.pytorch.org/whl/"+path.variant;
    path.docker=path.kind==="pypi"?(r.dk.indexOf("default")>=0?"vllm/vllm-openai:v"+r.v:null)
      :(r.dk.indexOf(path.variant)>=0?"vllm/vllm-openai:v"+r.v+"-"+path.variant:null)}
  return {v:r.v,path:path||null,pypiWhy:p1.why,cm:r.cm,py:r.py,pl:r.pl}}
function lookup(D,inp){
  if(!/^\d{3}(\.\d{1,3}){0,2}$/.test(inp.driverText||""))return {error:"driver"};
  inp.driver=parseVer(inp.driverText);
  var all=D.rel.map(function(r){return evalRelease(D,r,inp)});
  var latest=all[all.length-1],best=null;
  for(var i=all.length-1;i>=0;i--){if(all[i].path){best=all[i];break}}
  var br=inp.driver[0];
  return {error:null,all:all,latest:latest,best:best,
    compat:(br===535||br===570)&&cmpVer(inp.driver,D.dmin["13"])<0,
    below12:cmpVer(inp.driver,D.dmin["12"])<0}}
/* logic-end */
var $=function(id){return document.getElementById(id)};
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var GPU={"12.0":"compute capability 12.0","10.0":"compute capability 10.0","9.0":"compute capability 9.0","8.9":"compute capability 8.9",
  "8.6":"compute capability 8.6","8.0":"compute capability 8.0","7.5":"compute capability 7.5","7.0":"compute capability 7.0","6.x":"compute capability 6.x"};
function why(code,e,inp){
  if(code==="driver")return "driver "+inp.driverText+" is below "+DATA.dmin[String(e.cm)].join(".")+", the floor for CUDA "+e.cm+" builds";
  if(code==="gpu")return GPU[inp.cc]+" is not covered by this release's build";
  if(code==="torch-gpu")return "the pinned PyTorch has no build for this GPU in the same CUDA major";
  if(code==="python")return "Python "+inp.py+" is outside "+e.py;
  if(code==="glibc")return "glibc "+inp.glibc+" is older than the wheel tag "+e.pl;
  return code}
function run(){
  var inp={driverText:$("drv").value.trim(),cc:$("gpu").value,py:$("py").value,glibc:$("glibc").value.trim()};
  if(inp.glibc&&!/^\d\.\d{1,2}$/.test(inp.glibc)){$("status").textContent="glibc should look like 2.35 (first line of: ldd --version).";return}
  var res=lookup(DATA,inp);
  if(res.error){$("status").textContent="Enter the driver version as nvidia-smi prints it, for example 570.133.07.";$("res").innerHTML="";return}
  $("status").textContent="";
  var L=res.latest,B=res.best,x="";
  if(B&&B.v===L.v&&B.path.kind==="pypi")
    x+='<div class="verdict v-ok">v'+esc(L.v)+' (the latest release) installs from PyPI on this system<span>Driver '+esc(inp.driverText)+' meets the floor for its CUDA '+L.cm+' build, and '+GPU[inp.cc]+' is in the build targets.</span></div>';
  else if(B)
    x+='<div class="verdict v-load">Newest release with a prebuilt wheel for this system: v'+esc(B.v)+(B.path.kind==="variant"?" (the +"+esc(B.path.variant)+" wheel)":"")+'<span>v'+esc(L.v)+' does not fit: '+esc(L.pypiWhy.map(function(c){return why(c,L,inp)}).join("; "))+'.</span></div>';
  else
    x+='<div class="verdict v-bad">No prebuilt vLLM wheel from v'+esc(DATA.rel[0].v)+' to v'+esc(L.v)+' fits this system<span>v'+esc(L.v)+': '+esc(L.pypiWhy.map(function(c){return why(c,L,inp)}).join("; "))+'. The remaining route is a source build, or a newer driver or GPU.</span></div>';
  if(B){var p=B.path;
    x+="<p><strong>Install</strong> (PyTorch "+esc(p.torch)+(p.kind==="variant"?"+"+esc(p.variant):"")+", CUDA "+p.cm+" runtime):</p><pre><code>"+esc(p.cmd)+"</code></pre>";
    if(p.kind==="pypi"&&!p.tindex)x+='<p class="note">Plain <code>pip install vllm=='+esc(B.v)+'</code> resolves to the same wheels. With uv, <code>--torch-backend=auto</code> is fine here because the driver supports this CUDA major.</p>';
    if(p.kind==="pypi"&&p.tindex)x+='<p class="note">The extra index is needed because the PyTorch that PyPI serves for this pin is built for an older CUDA that does not include this GPU.</p>';
    if(p.kind==="variant")x+='<p class="note">The same wheel is on <code>https://wheels.vllm.ai/'+esc(B.v)+'/'+esc(p.variant)+'/</code>. Do not combine the default PyPI wheel of this release with <code>--torch-backend='+esc(p.variant)+'</code>: that pairs a CUDA 13 vLLM with a CUDA 12 PyTorch.</p>';
    x+="<p><strong>Check after installing:</strong></p><pre><code>python -c \"import torch, vllm; print(vllm.__version__, torch.__version__, torch.version.cuda)\"</code></pre>";
    if(p.docker)x+="<p><strong>Docker:</strong> <code>"+esc(p.docker)+"</code></p>"}
  if(res.compat)x+='<p class="note"><strong>Driver branch '+inp.driver[0]+':</strong> on data center GPUs (not GeForce), NVIDIA\'s forward-compatibility package for CUDA 13.0 supports this branch. In the vLLM Docker images from v0.17.0 it is opt-in: start the container with <code>VLLM_ENABLE_CUDA_COMPATIBILITY=1</code>. See the section on older drivers below.</p>';
  if(res.below12&&B)x+='<p class="note">This driver is below 525.60.13, so only the CUDA 11.8 wheels (up to v0.10.1.1) remain.</p>';
  if(parseFloat(inp.cc)>=10)x+='<p class="note">Blackwell GPUs also need a driver new enough to recognise the card; the floors above are for the CUDA runtime only.</p>';
  $("res").innerHTML=x;
  var by={};res.all.forEach(function(e){by[e.v]=e});
  Array.prototype.forEach.call(document.querySelectorAll("#matrix tbody tr"),function(tr){
    var e=by[tr.getAttribute("data-v")],td=tr.querySelector(".you");if(!e)return;
    td.innerHTML=e.path?'<span class="s y">'+(e.path.kind==="pypi"?(e.path.tindex?"PyPI + "+esc(e.path.tindex)+" torch":"PyPI"):"+"+esc(e.path.variant))+"</span>"
      :'<span class="s n">no</span> <span class="note">'+esc(e.pypiWhy.join(", "))+"</span>"});
  try{var q="?driver="+encodeURIComponent(inp.driverText)+"&gpu="+encodeURIComponent(inp.cc)+(inp.py?"&py="+inp.py:"")+(inp.glibc?"&glibc="+inp.glibc:"");
    history.replaceState(null,"",location.pathname+q+"#lookup")}catch(err){}
}
$("go").addEventListener("click",run);
$("drv").addEventListener("keydown",function(ev){if(ev.key==="Enter")run()});
try{var sp=new URLSearchParams(location.search);
  if(sp.get("gpu")&&GPU[sp.get("gpu")])$("gpu").value=sp.get("gpu");
  if(sp.get("py"))$("py").value=sp.get("py");
  if(sp.get("glibc"))$("glibc").value=sp.get("glibc");
  if(sp.get("driver")){$("drv").value=sp.get("driver");run()}}catch(err){}
})();
