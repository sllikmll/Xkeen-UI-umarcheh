(function(){
  'use strict';
  const CGI = '/cgi-bin/unified-ui-api';
  const nativeFetch = window.fetch.bind(window);
  const jsonResponse = (obj, init={}) => new Response(JSON.stringify(obj), Object.assign({status:200, headers:{'Content-Type':'application/json; charset=utf-8'}}, init));
  const enc = encodeURIComponent;
  async function cgi(path, opts){ return nativeFetch(CGI + path, Object.assign({cache:'no-store'}, opts||{})); }
  async function cgiJson(path, opts){ const r=await cgi(path, opts); const d=await r.json().catch(()=>({})); if(!r.ok || d.ok===false){ throw new Error(d.error || d.message || ('HTTP '+r.status)); } return d; }
  function delayOf(p){ const h=Array.isArray(p&&p.history)?p.history:[]; const last=h.length?h[h.length-1]:null; const d=last&&typeof last.delay==='number'?last.delay:null; return d; }
  function summarizeProxies(raw){
    const proxies = raw && raw.proxies && typeof raw.proxies==='object' ? raw.proxies : {};
    const selectors=[]; const nodes=[];
    Object.entries(proxies).forEach(([name,p])=>{
      p = p && typeof p==='object' ? p : {};
      const item={name:String(name), type:p.type, now:p.now, all:Array.isArray(p.all)?p.all:[], alive:p.alive, udp:p.udp, delay:delayOf(p), provider:p['provider-name']||p.provider, hidden:p.hidden};
      if(Array.isArray(item.all) && item.all.length) selectors.push(item); else nodes.push(item);
    });
    selectors.sort((a,b)=>String(a.name).localeCompare(String(b.name),'ru'));
    nodes.sort((a,b)=>String(a.name).localeCompare(String(b.name),'ru'));
    return {ok:true, selectors, nodes, raw_count:Object.keys(proxies).length, provider_node_count:0, providerByNode:{}, controller:'http://127.0.0.1:9090'};
  }
  async function proxyDelay(name, timeout){
    const data = await cgiJson('/delay', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nameEncoded:enc(name), timeout:timeout||5000})});
    return {ok:true, proxy:name, delay:data.delay};
  }
  async function handleApi(url, opts){
    const method=String((opts&&opts.method)||'GET').toUpperCase();
    const u = new URL(url, window.location.origin);
    const path = u.pathname;
    if(path==='/api/unified/status' || path==='/api/status') {
      const d = await cgiJson('/status');
      return jsonResponse(Object.assign({}, d, { ok: true, running: !!d.pid, core: 'mihomo', status: d.pid ? 'running' : 'stopped' }));
    }
    if(path==='/api/capabilities') return jsonResponse({ok:true, platform:'openwrt', websocket:false, terminal:{enabled:false,pty:false,ws:false}, features:{mihomo:true,xray:false,files:false,commands:false}});
    if(path==='/api/restart') return cgi('/restart', Object.assign({},opts,{method:'GET'}));
    if(path==='/api/build' || path==='/api/self-update/state') return cgi('/status', opts);
    if(path==='/api/mihomo-config') {
      if(method==='GET') return cgi('/config-get', opts);
      if(method==='POST') {
        const body = JSON.parse((opts&&opts.body)||'{}');
        return cgi('/config-save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({content:body.content||'', apply:!!body.restart})});
      }
    }
    if(path==='/api/proxy-connections' && method==='GET') return cgi('/proxy-connections', opts);
    if(path==='/api/proxy-connections/import' && method==='POST') return cgi('/proxy-connections-import', opts);
    if(path==='/api/proxy-connections/apply' && method==='POST') return cgi('/proxy-connections-apply', opts);
    if(path==='/api/proxy-connections/preview' && method==='POST') return cgi('/proxy-connections-preview', opts);
    let pcm = path.match(/^\/api\/proxy-connections\/([^/]+)$/);
    if(pcm && (method==='PATCH' || method==='DELETE')) return cgi('/proxy-connections-item/'+enc(decodeURIComponent(pcm[1])), opts);
    if(path==='/api/mihomo/clash/proxies' && method==='GET') return jsonResponse(summarizeProxies(await cgiJson('/proxies')));
    if(path==='/api/mihomo/clash/proxies/delay-all' && method==='POST'){
      const body=JSON.parse((opts&&opts.body)||'{}'); const names=Array.isArray(body.names)?body.names:[]; const results=[];
      for(const n of names){ try{ const d=await proxyDelay(n, body.timeout||5000); results.push({ok:true, proxy:n, delay:d.delay}); }catch(e){ results.push({ok:false, proxy:n, error:String(e.message||e)}); } }
      return jsonResponse({ok:true, results});
    }
    let m = path.match(/^\/api\/mihomo\/clash\/proxies\/(.+?)\/delay$/);
    if(m) return jsonResponse(await proxyDelay(decodeURIComponent(m[1]), 5000));
    m = path.match(/^\/api\/mihomo\/clash\/proxies\/(.+)$/);
    if(m && method==='PUT'){
      const body=JSON.parse((opts&&opts.body)||'{}'); const selector=decodeURIComponent(m[1]);
      return cgi('/select', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({groupEncoded:enc(selector), name:body.name||''})});
    }
    if(path==='/api/mihomo/clash/connections'){
      if(method==='DELETE') return cgi('/connections-close-all', {method:'POST'});
      const d = await cgiJson('/connections');
      if(!Array.isArray(d.connections)) d.connections = [];
      return jsonResponse(d);
    }
    m = path.match(/^\/api\/mihomo\/clash\/connections\/(.+)$/);
    if(m && method==='DELETE') return cgi('/connection-close', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:decodeURIComponent(m[1])})});
    if(path==='/api/mihomo/clash/providers/proxies/update-all') return jsonResponse({ok:true, message:'OpenWrt standalone: proxy providers update через Mihomo runtime пока no-op'});
    m = path.match(/^\/api\/mihomo\/clash\/providers\/rules\/(.+)$/);
    if(m) return jsonResponse({ok:true, provider:decodeURIComponent(m[1]), status:200});
    m = path.match(/^\/api\/mihomo\/rule-provider\/(.+)$/);
    if(m){
      const provider=decodeURIComponent(m[1]);
      if(method==='POST') return cgi('/rule-provider/'+enc(provider), {method:'POST', headers:{'Content-Type':'application/json'}, body:(opts&&opts.body)||'{}'});
      return cgi('/rule-provider/'+enc(provider), opts);
    }
    m = path.match(/^\/api\/mihomo\/selector-inspector\/(.+)$/);
    if(m) return jsonResponse({ok:true, selector:decodeURIComponent(m[1]), provider:'manual-proxy', editable:false, content:'payload:\n', meta:{type:'selector'}, providers:[]});
    if(path==='/api/routing/geodat/status') return jsonResponse({ok:true, installed:false, available:false, message:'OpenWrt: DAT inspector требует xk-geodat build для OpenWrt'});
    if(path==='/api/routing/geodat/install') return jsonResponse({ok:false, error:'OpenWrt DAT installer пока не перенесён в full-panel build'}, {status:501});
    if(path==='/api/mihomo/config' || path==='/api/mihomo/config/load') return cgi('/config-get', opts);
    if(path==='/api/mihomo/config/validate' || path==='/api/mihomo/validate') return cgi('/config-validate', opts);
    if(path==='/api/mihomo/config/save' || path==='/api/mihomo/save') return cgi('/config-save', opts);
    if(path==='/api/mihomo/profile_defaults') return jsonResponse({ok:true, defaults:{profile:'openwrt-standalone', mixed_port:7890, controller:'127.0.0.1:9090'}});
    if(path==='/api/mihomo/preview') return jsonResponse({ok:false, error:'Mihomo generator preview backend на OpenWrt ещё не портирован'}, {status:501});
    if(path==='/api/mihomo/subscriptions') return jsonResponse({ok:true, subscriptions:[]});
    if(path.startsWith('/api/mihomo/subscriptions/')) return jsonResponse({ok:false, error:'Subscriptions backend на OpenWrt ещё не портирован'}, {status:501});
    if(path==='/api/restart-log') return jsonResponse({ok:true, content:''});
    if(path==='/api/restart-log/clear') return jsonResponse({ok:true});
    return cgi('/api-raw?path='+enc(path)+(u.search||''), opts);
  }
  window.fetch = function(input, opts){
    try{
      const url = typeof input==='string' ? input : (input && input.url) || '';
      if(url && (url.startsWith('/api/') || url.startsWith(window.location.origin + '/api/'))) return handleApi(url, opts||{});
    }catch(e){ return Promise.resolve(jsonResponse({ok:false,error:String(e.message||e)}, {status:500})); }
    return nativeFetch(input, opts);
  };
})();
