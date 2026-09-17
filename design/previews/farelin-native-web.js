const root = document.documentElement;
const themeButton = document.querySelector('.theme-button');
themeButton.addEventListener('click', () => {
  const light = root.dataset.theme !== 'light';
  root.dataset.theme = light ? 'light' : 'dark';
  themeButton.setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} mode`);
});
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-mode]').forEach(other => other.classList.toggle('selected', other === button));
  const ask = button.dataset.mode === 'ask';
  document.querySelector('.ask-field').hidden = !ask;
  document.querySelector('.search-fields').hidden = ask;
}));
document.querySelectorAll('.mood-row button').forEach(button => button.addEventListener('click', () => {
  button.setAttribute('aria-pressed', String(button.getAttribute('aria-pressed') !== 'true'));
}));
document.querySelector('#preview-search').addEventListener('submit', event => {
  event.preventDefault();
  document.querySelector('#search-status').textContent = 'Three fictional demo trips below. This preview did not run an AI or fare-provider search.';
  document.querySelector('.results-heading').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block:'center'});
});
document.querySelectorAll('.save-button').forEach(button => button.addEventListener('click', () => {
  const saved = button.classList.toggle('saved');
  button.setAttribute('aria-pressed', String(saved));
  document.querySelector('#search-status').textContent = saved ? 'Demo bookmark selected in this preview only. Nothing was saved to an account.' : 'Demo bookmark removed from this preview.';
}));
const dialog = document.querySelector('#trip-dialog');
document.querySelectorAll('[data-trip]').forEach(button => button.addEventListener('click', () => {
  document.querySelector('#dialog-title').textContent = button.dataset.trip;
  dialog.showModal();
}));
document.querySelectorAll('.dialog-close,.dialog-done').forEach(button => button.addEventListener('click', () => dialog.close()));
document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => {
  document.querySelectorAll('nav a').forEach(other => other.classList.toggle('active', other === link));
}));

// Local Natural Earth geometry, shared with the native app; no remote textures.
const canvas = document.querySelector('#earth');
const ctx = canvas.getContext('2d');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let features = [], rotation = 18, latitude = 26, dragging = false, pointer = null, paused = false, size = 500, last = 0;
const rad = Math.PI / 180;
function project(lon, lat) {
  const lambda = (lon - rotation) * rad, phi = lat * rad, tilt = latitude * rad;
  return {x:Math.cos(phi)*Math.sin(lambda), y:Math.cos(tilt)*Math.sin(phi)-Math.sin(tilt)*Math.cos(phi)*Math.cos(lambda),
    visible:Math.sin(tilt)*Math.sin(phi)+Math.cos(tilt)*Math.cos(phi)*Math.cos(lambda)>0};
}
function point(lon, lat, radius) { const p = project(lon, lat); return {...p,x:size/2+p.x*radius,y:size/2-p.y*radius}; }
function drawLine(coords, radius, color, width=0.5) {
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();let drawing=false;
  coords.forEach(([lon,lat])=>{const p=point(lon,lat,radius);if(p.visible){if(drawing)ctx.lineTo(p.x,p.y);else ctx.moveTo(p.x,p.y);drawing=true;}else drawing=false;});ctx.stroke();
}
function draw(time) {
  const elapsed = last ? Math.min(time-last,50) : 0;last=time;
  if(!paused&&!dragging&&!reduced.matches&&!document.hidden) rotation += elapsed*0.001;
  const light=root.dataset.theme==='light', r=size*.425;
  ctx.clearRect(0,0,size,size);
  ctx.save();ctx.beginPath();ctx.arc(size/2,size/2,r,0,Math.PI*2);ctx.clip();
  ctx.fillStyle=light?'#d9eaf0':'#0e1d27';ctx.fillRect(0,0,size,size);
  features.forEach(feature=>{
    const code=feature.properties.ADM0_A3;
    const polygons=feature.geometry.type==='Polygon'?[feature.geometry.coordinates]:feature.geometry.coordinates;
    ctx.fillStyle=['DNK','SWE','FIN'].includes(code)?(light?'#4baf96':'#6bac9d'):code==='SVN'?'#ff9978':light?'#8199a3':'#5f7f90';
    ctx.strokeStyle=light?'rgba(255,255,255,.4)':'rgba(0,0,0,.3)';ctx.lineWidth=.5;
    polygons.forEach(polygon=>{ctx.beginPath();let valid=false;polygon.forEach(ring=>{
      const points=ring.map(([lon,lat])=>point(lon,lat,r)).filter(p=>p.visible);
      if(points.length<3)return;valid=true;points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();
    });if(valid){ctx.fill('evenodd');ctx.stroke();}});
  });
  for(let lat=-60;lat<=75;lat+=15)drawLine(Array.from({length:181},(_,i)=>[-180+i*2,lat]),r,light?'rgba(35,70,80,.13)':'rgba(150,190,210,.12)');
  for(let lon=-180;lon<180;lon+=15)drawLine(Array.from({length:91},(_,i)=>[lon,-90+i*2]),r,light?'rgba(35,70,80,.13)':'rgba(150,190,210,.12)');
  const origin=[12.57,55.68];
  [[18.06,59.33],[24.94,60.17],[2.35,48.86],[-9.14,38.72],[14.51,46.05],[23.73,37.98]].forEach(dest=>{
    const a=point(...origin,r),b=point(...dest,r);if(!a.visible||!b.visible)return;
    ctx.strokeStyle=light?'rgba(8,123,104,.6)':'rgba(125,222,194,.65)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.quadraticCurveTo((a.x+b.x)/2,(a.y+b.y)/2-size*.08,b.x,b.y);ctx.stroke();
    ctx.fillStyle='#ff9978';ctx.beginPath();ctx.arc(b.x,b.y,size*.006,0,Math.PI*2);ctx.fill();
  });
  const o=point(...origin,r);if(o.visible){ctx.fillStyle='#7ddec2';ctx.beginPath();ctx.arc(o.x,o.y,size*.008,0,Math.PI*2);ctx.fill();}
  const shade=ctx.createRadialGradient(size*.37,size*.32,r*.1,size*.52,size*.52,r*1.1);shade.addColorStop(0,'rgba(255,255,255,.06)');shade.addColorStop(.6,'rgba(0,0,0,0)');shade.addColorStop(1,light?'rgba(30,60,75,.24)':'rgba(0,0,0,.65)');ctx.fillStyle=shade;ctx.fillRect(0,0,size,size);ctx.restore();
  requestAnimationFrame(draw);
}
new ResizeObserver(entries=>{size=entries[0].contentRect.width;const dpr=Math.min(devicePixelRatio,2);canvas.width=size*dpr;canvas.height=size*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);}).observe(canvas);
canvas.addEventListener('pointerdown',event=>{dragging=true;pointer={x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);});
canvas.addEventListener('pointermove',event=>{if(!dragging)return;rotation-=(event.clientX-pointer.x)*.35;latitude=Math.max(-65,Math.min(65,latitude+(event.clientY-pointer.y)*.25));pointer={x:event.clientX,y:event.clientY};});
canvas.addEventListener('pointerup',()=>dragging=false);canvas.addEventListener('pointercancel',()=>dragging=false);
canvas.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();rotation+=event.key==='ArrowLeft'?-8:event.key==='ArrowRight'?8:0;latitude=Math.max(-65,Math.min(65,latitude+(event.key==='ArrowUp'?8:event.key==='ArrowDown'?-8:0)));}});
document.querySelector('.rotate-button').addEventListener('click',()=>{paused=!paused;document.querySelector('.rotate-button').setAttribute('aria-label',paused?'Resume globe rotation':'Pause globe rotation');document.querySelector('.rotate-button use').setAttribute('href',paused?'#play-icon':'#pause-icon');});
fetch('../../apps/ios/Farelin/Resources/Geometry/NaturalEarthCountries.geojson').then(response=>{if(!response.ok)throw new Error('Geometry unavailable');return response.json();}).then(data=>features=data.features).catch(()=>document.querySelector('.globe-hint').textContent='Globe geometry unavailable');
requestAnimationFrame(draw);
