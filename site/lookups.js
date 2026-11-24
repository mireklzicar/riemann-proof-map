// Resolved and in-flight requests share a cache. Failed requests can be retried.
const textBlocks = new Map();
function blockRow(table, id) {
  const block = Math.floor(id / D.blockSize);
  const url = "text/" + table + "-" + block + ".gz";
  if (!textBlocks.has(url)) {
    textBlocks.set(url, fetchGz(url).then(r => r.text()).then(text => text.split("\n"))
      .catch(error => { textBlocks.delete(url); throw error; }));
  }
  return textBlocks.get(url).then(rows => rows[id % D.blockSize]);
}
function rememberNode(i, name, module) {
  D.names[i] = name;
  D.short[i] = name.slice(name.lastIndexOf(".") + 1);
  D.modnames[D.module[i]] = module;
}
function hasNodeText(i) {
  return D.names[i] !== undefined && D.modnames[D.module[i]] !== undefined;
}
async function loadNodeText(i) {
  if (hasNodeText(i)) return;
  const canonical = goal === "grh" ? D.rhId[i] : i;
  const mod = D.module[i];
  const [name, module] = await Promise.all([
    D.names[i] ?? blockRow("names", canonical), D.modnames[mod] ?? blockRow("modules", mod),
  ]);
  rememberNode(i, name, module);
}
let searchIndex, namesReady = false;
function loadSearchIndex() {
  return searchIndex ??= fetchGz(dataPrefix + "names.txt.gz").then(r => r.text()).then(text => {
    const names = text.split("\n");
    if (names.length !== M.n) throw Error("Search index size mismatch");
    D.short = names.map(s => s.slice(s.lastIndexOf(".") + 1));
    D.names = names;
    namesReady = true;
  }).catch(error => { searchIndex = undefined; throw error; });
}
let routeIndex;
function loadRoutes() {
  return routeIndex ??= fetchGz(dataPrefix + "routes.bin.gz").then(r => r.arrayBuffer()).then(bytes => {
    if (bytes.byteLength !== 10 * M.n) throw Error("Reference index size mismatch");
    D.up = new Int32Array(bytes, 0, M.n);
    D.down = new Int32Array(bytes, 4 * M.n, M.n);
    D.stage = new Uint16Array(bytes, 8 * M.n, M.n);
  }).catch(error => { routeIndex = undefined; throw error; });
}
