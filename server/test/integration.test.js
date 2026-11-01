const {test} = require('node:test');
const assert = require('node:assert/strict');
const {createProvider,toMessages,convertResponse} = require('../src/core/provider');
const {findPath} = require('../src/services/pathfinding');
const supervision = require('../src/core/supervision');
const {buildGameDataJson} = require('../src/services/pythonService');

const settings = {provider:'ollama',baseURL:'http://127.0.0.1:11434/v1',model:'qwen3.8:27b',timeout:1000};
const completion = (message,finish_reason='stop') => ({choices:[{message,finish_reason}],usage:{prompt_tokens:4,completion_tokens:6,total_tokens:10}});

test('default provider is local Ollama without paid key', () => {
  const {config} = require('../src/config');
  assert.equal(config.ai.provider,'ollama');assert.equal(config.ai.model,'qwen3.8:27b');
  assert.equal(config.ai.baseURL,'http://127.0.0.1:11434/v1');
  assert.doesNotThrow(()=>createProvider(settings));
});
test('chat facade maps upstream prompts, history, images and tool outputs',()=>{
  const messages=toMessages([{role:'developer',content:'policy'},{role:'user',content:[{type:'input_text',text:'state'}]},
    {type:'function_call',name:'execute_action',arguments:'{}',call_id:'c1'},
    {type:'function_call_output',call_id:'c1',output:'done'}]);
  assert.equal(messages[0].role,'system');assert.equal(messages[2].tool_calls[0].id,'c1');
  assert.equal(messages[3].tool_call_id,'c1');
});
test('mocked Ollama completion emits upstream event contract and usage',async()=>{
  let sent;
  const provider=createProvider(settings,{chat:{completions:{create:async(body)=>{sent=body;return completion({content:'hello'});}}}});
  const stream=await provider.responses.create({input:[{role:'user',content:'test'}],stream:true});
  const events=[];for await(const event of stream) events.push(event);
  assert.equal(sent.model,settings.model);assert.equal(sent.stream,false);
  assert.equal(events.at(-1).type,'response.completed');assert.equal(events.at(-1).response.usage.total_tokens,10);
});
test('mocked tool calls preserve argument and call identity',async()=>{
  const response=convertResponse(completion({tool_calls:[{id:'tool1',type:'function',function:{name:'execute_action',arguments:'{"actions":[{"type":"keypress","keys":["a"]}]}'}}]},'tool_calls'));
  assert.equal(response.output[0].call_id,'tool1');
});
test('malformed JSON, parallel calls, failed and truncated responses are rejected',()=>{
  assert.throws(()=>convertResponse(completion({tool_calls:[{id:'x',type:'function',function:{name:'execute_action',arguments:'bad'}}]},'tool_calls')));
  assert.throws(()=>convertResponse(completion({content:'cut off'},'length')));
  assert.throws(()=>convertResponse({choices:[]}));
});
test('model timeout/failure is surfaced without automatic retry',async()=>{
  let calls=0;const provider=createProvider(settings,{chat:{completions:{create:async()=>{calls++;throw new Error('timeout');}}}});
  await assert.rejects(()=>provider.responses.create({input:[]}),/timeout/);assert.equal(calls,1);
});
test('provider rejects remote Ollama and requires optional OpenAI credentials',()=>{
  assert.throws(()=>createProvider({...settings,baseURL:'https://external.invalid/v1'}));
  assert.throws(()=>createProvider({...settings,provider:'openai'}));
  assert.doesNotThrow(()=>createProvider({...settings,provider:'openai',baseURL:'https://api.openai.com/v1',apiKey:'test-fixture-only'}));
});
test('local pathfinding respects known collision grid',()=>{
  assert.deepEqual(findPath([[1,0,1],[1,1,1]],{x:0,y:0},{x:2,y:0}),['down','right','right','up']);
  assert.throws(()=>findPath([[1,0,1]],{x:0,y:0},{x:2,y:0}));
  assert.equal(findPath([Array(15).fill(1)],{x:0,y:0},{x:14,y:0}).length,10);
});
test('operator gate starts paused and caps ten actions',()=>{
  supervision.pause();assert.throws(()=>supervision.consume());
  assert.throws(()=>supervision.resume(11));supervision.resume(2);supervision.consume();supervision.consume();
  assert.throws(()=>supervision.consume());assert.equal(supervision.status().active,false);
  supervision.resume(1);supervision.beginTurn();supervision.beginTurn();supervision.beginTurn();assert.throws(()=>supervision.beginTurn());
});
test('upstream state formatter connects map, party, inventory and battle data',()=>{
  const output=buildGameDataJson({player:{position:[2,3],money:500},map:{name:'PALLET_TOWN',group:3,number:0},party:[],bag:{},battle:{isActive:false}});
  assert.equal(output.current_trainer_data.position.x,2);assert.equal(output.current_trainer_data.money,500);
  assert.equal(output.current_trainer_data.position.map_id,'3-0');assert.equal(output.battle_data.in_battle,false);
});

test('real OpenAI-compatible client reaches mocked local Ollama without a key',async()=>{
  const http=require('node:http');
  let requestBody;
  const server=http.createServer((req,res)=>{
    const chunks=[]; req.on('data',chunk=>chunks.push(chunk));req.on('end',()=>{
      requestBody=JSON.parse(Buffer.concat(chunks));
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify(completion({content:'mock local answer'})));
    });
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  try{
    const provider=createProvider({...settings,baseURL:`http://127.0.0.1:${server.address().port}/v1`});
    const result=await provider.responses.create({input:[{role:'user',content:'hello'}]});
    assert.equal(result.output[0].content[0].text,'mock local answer');
    assert.equal(requestBody.model,'qwen3.8:27b');
  }finally{await new Promise(resolve=>server.close(resolve));}
});

test('dashboard serves health, static UI and WebSocket while agent stays paused',async()=>{
  const cp=require('node:child_process'),fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),net=require('node:net');
  const WebSocket=require('ws');
  const http=require('node:http');
  const pythonFixture=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,data:{player:{position:[7,9],money:100},map:{group:3,number:0,name:'PALLET_TOWN'},party:[],bag:{},battle:{isActive:false}}}));});
  await new Promise(resolve=>pythonFixture.listen(0,'127.0.0.1',resolve));
  const probe=net.createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));
  const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
  const session=await fs.mkdtemp(path.join(os.tmpdir(),'firered-node-session-'));
  const child=cp.spawn(process.execPath,['index.js'],{cwd:path.resolve(__dirname,'..'),env:{...process.env,WS_PORT:String(port),FIRERED_SESSION_DIR:session,PYTHON_BASE_URL:`http://127.0.0.1:${pythonFixture.address().port}`},stdio:['ignore','pipe','pipe']});
  let logs='';child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
  try{
    let health;
    for(let i=0;i<100;i++){
      try{health=await fetch(`http://127.0.0.1:${port}/health`).then(r=>r.json());break;}catch{await new Promise(r=>setTimeout(r,50));}
    }
    assert.ok(health,logs);assert.equal(health.supervision.active,false);assert.equal(health.provider,'ollama');
    const html=await fetch(`http://127.0.0.1:${port}/`).then(r=>r.text());assert.match(html,/team-list/);
    const observed=await fetch(`http://127.0.0.1:${port}/state`).then(r=>r.json());assert.equal(observed.current_trainer_data.position.x,7);
    await new Promise((resolve,reject)=>{
      const ws=new WebSocket(`ws://127.0.0.1:${port}`);const timer=setTimeout(()=>reject(new Error('no websocket initial state')),3000);
      ws.on('message',raw=>{const message=JSON.parse(raw);if(message.type==='full_state'){clearTimeout(timer);ws.close();resolve();}});
      ws.on('error',reject);
    });
  } finally {
    child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),new Promise(r=>setTimeout(r,6000))]);
    if(child.exitCode===null) child.kill('SIGKILL');
    await fs.rm(session,{recursive:true,force:true});
    await new Promise(resolve=>pythonFixture.close(resolve));
  }
});

test('persistent memory and objectives survive a local session reload',async()=>{
  const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path');
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'firered-memory-fixture-'));
  const previous=process.env.FIRERED_SESSION_DIR;
  process.env.FIRERED_SESSION_DIR=directory;
  const manager=require('../src/state/stateManager');
  try{
    manager.state.memory={fixture:'observed fact'};
    manager.state.objectives={primary:{text:'fixture objective'},secondary:{},third:{},others:[]};
    await manager.savePersistentState();
    manager.state.memory={};manager.state.objectives={};
    await manager.loadPersistentState();
    assert.equal(manager.state.memory.fixture,'observed fact');
    assert.equal(manager.state.objectives.primary.text,'fixture objective');
  }finally{
    if(previous===undefined)delete process.env.FIRERED_SESSION_DIR;else process.env.FIRERED_SESSION_DIR=previous;
    await fs.rm(directory,{recursive:true,force:true});
  }
});
