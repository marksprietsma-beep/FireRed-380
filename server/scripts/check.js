const fs=require('node:fs');const path=require('node:path');const cp=require('node:child_process');
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const files=['index.js',...walk('src'),...walk('../frontend')].filter(f=>f.endsWith('.js'));
for(const file of files){const check=cp.spawnSync(process.execPath,['--check',file],{stdio:'inherit'});if(check.status)process.exit(check.status);}
console.log(`Checked ${files.length} server/frontend JavaScript files; frontend is static (no bundle step).`);
