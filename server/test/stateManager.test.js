const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const configSource = fs.readFileSync(path.join(__dirname, '../src/config.js'), 'utf8');
const managerSource = fs.readFileSync(path.join(__dirname, '../src/state/stateManager.js'), 'utf8');
const win = path.win32;
const baseDir = 'D:\\projects\\FireRed-380\\server';

// Run the actual config and state manager with Windows path semantics on every
// host. Filesystem operations are in memory: no Windows machine/share is used.
function windowsSession(sessionDir) {
  const configModule = {exports:{}};
  vm.runInNewContext(configSource, {
    module:configModule, __dirname:win.join(baseDir, 'src'), URL,
    process:{env:sessionDir === undefined ? {} : {FIRERED_SESSION_DIR:sessionDir}},
    require(name) {assert.equal(name, 'path'); return win;},
  }, {filename:'config.js'});
  const {config} = configModule.exports;
  const files = new Map([[win.join(baseDir, 'progress_steps.json'),
    JSON.stringify([{id:'fixture-milestone',label:'Fixture milestone'}])]]);
  const directories = new Set();
  const mkdirCalls = [];
  const errors = [];
  const missing = name => Object.assign(new Error(`Missing fixture: ${name}`), {code:'ENOENT'});
  const mkdir = (name, kind) => {mkdirCalls.push({name,kind}); directories.add(name);};
  const fakeFs = {
    existsSync(name) {return files.has(name) || directories.has(name);},
    mkdirSync(name) {mkdir(name, 'sync');},
    promises:{
      async mkdir(name) {mkdir(name, 'async');},
      async readFile(name) {if (!files.has(name)) throw missing(name); return files.get(name);},
      async writeFile(name, data) {
        // Catch attempts to create a different directory from the file getters.
        if (!directories.has(win.dirname(name))) throw missing(win.dirname(name));
        files.set(name, data);
      },
    },
  };
  function newManager() {
    const managerModule = {exports:{}};
    vm.runInNewContext(managerSource, {
      module:managerModule,
      console:{log(){}, warn(...args){errors.push(args);}, error(...args){errors.push(args);}},
      require(name) {
        if (name === 'fs') return fakeFs;
        if (name === 'path') return win;
        assert.equal(name, '../config'); return {config};
      },
    }, {filename:'stateManager.js'});
    return managerModule.exports;
  }
  return {config, files, directories, mkdirCalls, errors, newManager};
}

for (const [label, sessionDir, expected] of [
  ['drive-qualified absolute', 'C:\\Users\\marks\\AppData\\Local\\Temp\\FireRed session',
    'C:\\Users\\marks\\AppData\\Local\\Temp\\FireRed session'],
  ['forward-slash absolute', 'C:/Users/marks/AppData/Local/Temp/FireRed session',
    'C:\\Users\\marks\\AppData\\Local\\Temp\\FireRed session'],
  ['UNC absolute', '\\\\fixture-host\\fixture-share\\FireRed session',
    '\\\\fixture-host\\fixture-share\\FireRed session'],
  ['relative', 'sessions\\local-run', win.join(baseDir, 'sessions\\local-run')],
  ['parent-relative', '..\\session-runs\\run-1', win.join(baseDir, '..\\session-runs\\run-1')],
  ['default', undefined, win.join(baseDir, 'gpt_data')],
]) {
  test(`Windows session directory: ${label}, initialise, save and reload`, async () => {
    const fixture = windowsSession(sessionDir);
    const manager = fixture.newManager();
    await manager.loadPersistentState();
    assert.equal(manager.state.progressSteps.length, 1, 'fresh directory must seed progress template');
    assert.ok(fixture.directories.has(expected), 'expected session directory must be created');
    assert.ok(fixture.mkdirCalls.length > 0);
    assert.ok(fixture.mkdirCalls.every(call => call.name === expected),
      `all directory creation must use ${expected}: ${JSON.stringify(fixture.mkdirCalls)}`);
    assert.equal(fixture.errors.length, 0, JSON.stringify(fixture.errors));
    manager.state.memory = {fact:'fixture memory'};
    manager.state.objectives = {primary:{text:'fixture objective'},secondary:{},third:{},others:[]};
    manager.state.history = [{role:'user',content:'fixture history'}];
    manager.state.counters.currentStep = 7;
    await manager.savePersistentState();
    assert.equal(JSON.parse(fixture.files.get(win.join(expected, 'memory.json'))).fact, 'fixture memory');
    const reloaded = fixture.newManager();
    await reloaded.loadPersistentState();
    assert.equal(reloaded.state.memory.fact, 'fixture memory');
    assert.equal(reloaded.state.objectives.primary.text, 'fixture objective');
    assert.equal(reloaded.state.history[0].content, 'fixture history');
    assert.equal(reloaded.state.counters.currentStep, 7);
    assert.equal(reloaded.state.progressSteps.length, 1);
    assert.equal(fixture.errors.length, 0, JSON.stringify(fixture.errors));
  });
}
