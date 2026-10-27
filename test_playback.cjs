// Run the actual player script against a deterministic YouTube/DOM stub.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(){this.value='';this.checked=false;this.textContent='';this.options=[{}];this.children=[];this.classList={add(){},remove(){},toggle(){}};}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  add(option){this.options.push(option);}
  remove(index){this.options.splice(index,1);}
  setAttribute(){}
  addEventListener(){}
}
const makeSong=(id,video)=>({id,year:2024,artist:'Test artist',title:'Test '+id,genre:'Test',difficulty:2,youtube_id:video,start_sec:40,end_sec:50,answer_lyrics:'original test line'});
const nodes=new Map();
const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
get('songData').textContent=JSON.stringify([makeSong(1,'AAAAAAAAAAA'),makeSong(2,'BBBBBBBBBBB')]);
get('mask').checked=true;
let tick,events,state=-1,time=0,video='',loads=0,seeks=0,pauses=0,plays=0;
const timers=new Map();let timerId=0;
const fakePlayer={getVideoData:()=>({video_id:video}),getPlayerState:()=>state,getCurrentTime:()=>time,unMute(){},pauseVideo(){pauses++;state=2;},playVideo(){plays++;state=1;},seekTo(t){seeks++;time=t;},loadVideoById(s){loads++;video=s.videoId;time=s.startSeconds;state=3;},cueVideoById(s){video=s.videoId;time=s.startSeconds;state=5;}};
const context=vm.createContext({document:{getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener(){},head:new Element()},window:{addEventListener(){}},location:{protocol:'https:',origin:'https://example.test'},localStorage:{getItem:()=>null,setItem(){}},Option:function(text,value){this.value=value;},setInterval:f=>{tick=f;},setTimeout:f=>{timers.set(++timerId,f);return timerId;},clearTimeout:id=>timers.delete(id),YT:{Player:function(id,options){events=options.events;return fakePlayer;}},console});
const source=fs.readFileSync('index.html','utf8').split('<script>')[1].split('</script>')[0];
vm.runInContext(source,context);
const run=source=>vm.runInContext(source,context);
run('selectSong(songs[0],true)');
assert.equal(loads,0,'click before API ready must queue playback');
run('window.onYouTubeIframeAPIReady()');events.onReady();
assert.equal(loads,1,'ready must play the queued song without a second click');
state=1;time=40;events.onStateChange({data:1});tick();
assert.equal(run('used.has(1)'),true);
state=3;events.onStateChange({data:3});assert.match(get('status').textContent,/버퍼링/);
state=1;events.onStateChange({data:1});assert.match(get('status').textContent,/듣는 중/);
time=43.25;
get('pauseBtn').onclick();
assert.equal(state,2);
assert.equal(get('resumeBtn').disabled,false,'pause in the passage must enable resume');
const resumeLoads=loads,resumeSeeks=seeks,resumePlays=plays;
get('resumeBtn').onclick();
assert.equal(time,43.25,'resume must keep the exact paused position');
assert.equal(loads,resumeLoads,'resume must not reload the video');
assert.equal(seeks,resumeSeeks,'resume must not seek back to the section start');
assert.equal(plays,resumePlays+1);
assert.equal(get('resumeBtn').disabled,true);
events.onStateChange({data:1});tick();
time=50.1;tick();assert.equal(run('active'),false);
assert.equal(get('resumeBtn').disabled,true,'completed passage must not offer resume');
const before=loads;run('play()');
assert.equal(loads,before,'replay must reuse loaded video');
assert.equal(seeks,1);assert.equal(plays,resumePlays+2);assert.equal(time,40);
tick();time=50.1;tick();
assert.equal(run('active'),false,'replay must stop even though seekTo clears native endSeconds');
const pauseBefore=pauses;run('selectSong(songs[1],true)');assert.equal(loads,before+1);
assert.equal(get('resumeBtn').disabled,true,'new selection must clear the paused song');
video='AAAAAAAAAAA';state=1;time=90;tick();
assert.equal(run('active'),true,'old video events must not stop new selection');
assert.equal(run('used.has(2)'),false,'old video events must not mark new song used');
assert.equal(pauses,pauseBefore+1);
video='BBBBBBBBBBB';state=3;time=4;
for(const callback of [...timers.values()])callback();
assert.equal(get('mask').checked,false,'delayed playback must expose actual video status');
assert.match(get('status').textContent,/대기/);
state=1;time=40;events.onStateChange({data:1});tick();time=50.1;tick();
assert.equal(run('active'),false);
run('songs[0].lead_in_start_sec=30;used.delete(1);selectSong(songs[0],false);ready=false;playLeadIn()');
events.onReady();
assert.equal(time,30,'queued lead-in must start before the question');
state=1;time=31;events.onStateChange({data:1});tick();
assert.equal(run('used.has(1)'),false,'lead-in alone must not mark the question used');
time=34;get('pauseBtn').onclick();
assert.equal(get('resumeBtn').disabled,false,'manual pause during lead-in must allow continuing it');
get('resumeBtn').onclick();assert.equal(time,34);
tick();time=39.81;tick();
assert.equal(run('active'),false,'lead-in must pause before the question begins');
assert.equal(time,40,'the paused player must be positioned at the question start');
assert.equal(get('resumeBtn').disabled,false);
assert.match(get('status').textContent,/여기서부터 받쓰/);
assert.equal(run('used.has(1)'),false);
get('resumeBtn').onclick();events.onStateChange({data:1});tick();
assert.equal(run('used.has(1)'),true);
time=50.1;tick();assert.equal(run('active'),false,'resumed question must still stop at its end');
run('selectSong(songs[0],true)');
assert.equal(time,30,'choosing a song with a lead-in must not reveal the question first');
console.log('PASS: queued playback/lead-in, lead-in checkpoint, exact-position resume, replay end guard, stale events, delay recovery');
