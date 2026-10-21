const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname,'..');
const checked = new Set();
let count = 0, inline = 0;
for (const entry of ['index.html','plan.html']) {
const html = fs.readFileSync(path.join(root,entry),'utf8');
for (const match of html.matchAll(/<script src="\.\/([^"]+)"/g)) {
  if (checked.has(match[1])) continue;
  const parts = match[1].split('/');
  if (parts.some(p => p.startsWith('_FORBIDDEN_') || p === '..')) throw Error('Path outside scope');
  let file = root;
  for (const part of parts) {
    file = path.join(file,part);
    if (fs.lstatSync(file).isSymbolicLink()) throw Error('Symlink outside scope');
  }
  new vm.Script(fs.readFileSync(file,'utf8'),{filename:match[1]});
  checked.add(match[1]);
  count++;
}
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
  new vm.Script(match[1],{filename:entry+':inline'}); inline++;
}
}
console.log(`Syntax OK: ${count} website scripts and ${inline} inline script.`);
