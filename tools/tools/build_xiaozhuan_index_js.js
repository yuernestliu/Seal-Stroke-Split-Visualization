// 把 xiaozhuan-index.json 转成 xiaozhuan-index.js，
// 这样可以用 <script src="./data/xiaozhuan-index.js"></script> 加载，
// 在 file:// 协议下也能正常工作。
const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, '..', 'data');
const jsonPath = path.join(dataDir, 'xiaozhuan-index.json');
const jsPath = path.join(dataDir, 'xiaozhuan-index.js');

if (!fs.existsSync(jsonPath)) {
  console.error('Cannot find', jsonPath);
  process.exit(1);
}

const json = fs.readFileSync(jsonPath, 'utf8');
const obj = JSON.parse(json);

const header = '/* AUTO-GENERATED from xiaozhuan-index.json by tools/build_xiaozhuan_index_js.js. Do not hand-edit. */\nwindow.__xiaozhuanData = ';
const out = header + JSON.stringify(obj) + ';\n';

fs.writeFileSync(jsPath, out, 'utf8');
console.log('Wrote', jsPath, '(' + out.length + ' bytes)');
