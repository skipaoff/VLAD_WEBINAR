// Отдаёт эту папку на http://localhost:4321 — чтобы страница сборки могла
// перечитывать progress.json без запретов браузера. Зависимостей нет, нужен
// только Node, который и так стоит для сайта.
//
// Запуск:  node serve.js        (порт можно задать: node serve.js 4400)
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const PORT = Number(process.argv[2]) || 4321;
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml',
};

http.createServer((req, res) => {
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/') rel = '/Сборка.html';
  const file = path.join(ROOT, path.normalize(rel).replace(/^([.][.][/])+/, ''));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end('нельзя'); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('нет файла'); return; }
    res.writeHead(200, {
      'content-type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'cache-control': 'no-store',
    });
    res.end(data);
  });
}).listen(PORT, () => {
  console.log('окно сборки: http://localhost:' + PORT + '/');
});
