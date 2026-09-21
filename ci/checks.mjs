// Headless browser checks for the private browser: leak + fingerprint.
// Runs in a node:22-slim sidecar sharing the browser's network namespace (Gluetun's,
// or a plain bridge in CI) and drives the headless Firefox its wrapper script started,
// over WebDriver BiDi. Node 22 has a built-in
// WebSocket client and fetch: nothing to install.
//
// env: EXPECT   Firefox version the image should report ("156.0"); UA check skipped if unset
//      COUNTRY  expected VPN exit country (ISO-2, default SG)
//      HOME_CC  the country a leak would show (default IN)
//      MODE     "ci" = fingerprint checks only (no VPN: skips exitIp, webrtc, dnsLeak);
//               used by the public repo's CI job (ci/fingerprint.sh). Same file there.
// Reads /w/creep-baseline.json if present (no file = record-only run, used once to
// create it). Writes /out/checks-out.json (summary) + /out/creep-full.json.
// Exit 0 = every check PASS; exit 1 = any FAIL.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const EXPECT = process.env.EXPECT || '';
const COUNTRY = (process.env.COUNTRY || 'SG').toUpperCase();
const HOME_CC = (process.env.HOME_CC || 'IN').toLowerCase();
const CI = process.env.MODE === 'ci';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function open(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    ws.onopen = () => resolve(ws);
    ws.onerror = () => reject(new Error('connect failed'));
  });
}

// Firefox needs a few seconds to start; retry for up to 30 s.
let ws;
for (let i = 0; i < 30 && !ws; i++) {
  try { ws = await open('ws://127.0.0.1:9222/session'); } catch { await sleep(1000); }
}
if (!ws) { console.error('FAIL: no BiDi endpoint on :9222 after 30 s'); process.exit(1); }

let nextId = 1;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id === undefined || !pending.has(msg.id)) return;  // events
  const { resolve, reject } = pending.get(msg.id);
  pending.delete(msg.id);
  msg.type === 'error' ? reject(new Error(`${msg.error}: ${msg.message}`)) : resolve(msg.result);
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});

const out = { when: new Date().toISOString(), expect: EXPECT, checks: {} };
const session = await send('session.new', { capabilities: {} });
out.browserVersion = session.capabilities.browserVersion;
const tree = await send('browsingContext.getTree', {});
const context = tree.contexts[0].context;

// Every expression returns a string, so the result is always result.value.
async function js(expression) {
  const r = await send('script.evaluate', {
    expression, target: { context }, awaitPromise: true,
  });
  if (r.type === 'exception') throw new Error(`page exception: ${r.exceptionDetails.text}`);
  return r.result.value;
}
const go = (url) => send('browsingContext.navigate', { context, url, wait: 'complete' });

// fn returns [ok, detail]. A thrown error is a FAIL: a check that could not run
// has not proven anything.
async function check(name, fn) {
  let ok = false, detail;
  try { [ok, detail] = await fn(); } catch (e) { detail = `ERROR: ${e.message}`; }
  out.checks[name] = { result: ok ? 'PASS' : 'FAIL', detail };
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
}

await go(CI ? 'http://localhost:8080/' : 'https://ipinfo.io/');
const major = EXPECT.split('.')[0];
if (major) {
  // RFP reports <major>.0 whatever the dot release.
  await check('userAgent', async () => {
    const ua = await js('navigator.userAgent');
    return [ua.includes(`Firefox/${major}.0`), ua];
  });
}
// RFP reports Atlantic/Reykjavik, so this proves the copied prefs apply.
await check('rfpTimeZone', async () => {
  const tz = await js('Intl.DateTimeFormat().resolvedOptions().timeZone');
  return [tz === 'Atlantic/Reykjavik', tz];
});
await check('webglBlocked', async () => {
  const v = await js("String(!!document.createElement('canvas').getContext('webgl'))");
  return [v === 'false', `getContext('webgl') available=${v}`];
});
let exitIp = '';
if (!CI) {
  await check('exitIp', async () => {
    const j = JSON.parse(await js("fetch('/json').then(r => r.text())"));
    exitIp = j.ip;
    return [j.country === COUNTRY, `${j.ip} ${j.country} ${j.org}`];
  });
  // Every ICE candidate's address + type. Pass = only mDNS .local names and the exit IP.
  await check('webrtc', async () => {
    const seen = JSON.parse(await js(`new Promise((res) => {
      const seen = new Set();
      const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
      const done = () => { pc.close(); res(JSON.stringify([...seen])); };
      pc.createDataChannel('x');
      pc.onicecandidate = (e) => {
        if (!e.candidate) return done();
        const f = e.candidate.candidate.split(' ');
        if (f.length > 7) seen.add(f[4] + ' ' + f[7]);
      };
      pc.createOffer().then((o) => pc.setLocalDescription(o));
      setTimeout(done, 8000);
    })`));
    const bad = seen.filter((c) => { const a = c.split(' ')[0]; return !a.endsWith('.local') && a !== exitIp; });
    return [exitIp !== '' && bad.length === 0, seen];
  });

  // DNS leak via bash.ws's JSON API: the BROWSER resolves 10 unique
  // names under <id>.bash.ws; bash.ws lists the resolvers that asked. Pass = at least
  // one resolver seen and none in the home country.
  await check('dnsLeak', async () => {
    const id = (await (await fetch('https://bash.ws/id')).text()).trim();
    if (!/^[a-z0-9]+$/.test(id)) throw new Error(`bad id ${JSON.stringify(id)}`);
    await js(`Promise.allSettled([...Array(10).keys()].map((i) =>
      Promise.race([fetch('https://' + (i + 1) + '.${id}.bash.ws/', { mode: 'no-cors' }),
                    new Promise((r) => setTimeout(r, 5000))]))).then(() => 'ok')`);
    await sleep(2000);
    const list = await (await fetch(`https://bash.ws/dnsleak/test/${id}?json`)).json();
    const dns = list.filter((e) => e.type === 'dns');
    const home = list.filter((e) => (e.type === 'dns' || e.type === 'ip') && e.country === HOME_CC);
    return [dns.length > 0 && home.length === 0,
      list.filter((e) => e.type !== 'conclusion').map((e) => `${e.type} ${e.ip} ${e.country} ${e.asn}`)];
  });
}  // !CI

// CreepJS, self-hosted at :8080 in this namespace. Compare fields, never the FP ID
// (headless differs from the GUI). mediaMimes is recorded, not gated: it varied
// 8-10/12 across reloads of one unchanged image.
await check('creepjs', async () => {
  await go('http://localhost:8080/');
  let fp = null;
  for (let i = 0; i < 60 && !fp; i++) {
    const s = await js("JSON.stringify(window.Fingerprint || null)");
    fp = JSON.parse(s);
    if (!fp) await sleep(1000);
  }
  if (!fp) throw new Error('window.Fingerprint not set after 60 s');
  writeFileSync('/out/creep-full.json', JSON.stringify(fp, null, 2));
  const summary = {
    fonts: fp.fonts?.fontFaceLoadFonts ?? null,
    mediaMimes: fp.media?.mimeTypes?.length ?? null,
    userAgent: fp.navigator?.userAgent ?? null,
    webglBlocked: !fp.canvasWebgl,  // CreepJS drops the section when WebGL is off
    timezone: fp.timezone?.location ?? null,  // .zone reads "Greenwich Mean Time"
    cores: fp.navigator?.hardwareConcurrency ?? null,
    screen: fp.screen ? `${fp.screen.width}x${fp.screen.height}` : null,  // headless window, not the GUI 1800x900
  };
  out.creep = summary;
  const bfile = '/w/creep-baseline.json';
  if (!existsSync(bfile)) return [true, 'record-only (no creep-baseline.json)'];
  const base = JSON.parse(readFileSync(bfile, 'utf8'));
  const diff = Object.keys(base).filter((k) => JSON.stringify(base[k]) !== JSON.stringify(summary[k]))
    .map((k) => `${k}: baseline ${JSON.stringify(base[k])} now ${JSON.stringify(summary[k])}`);
  return [diff.length === 0, diff.length ? diff : `${Object.keys(base).length} fields = baseline`];
});

try { await send('browser.close'); } catch { /* the wrapper kills it anyway */ }
writeFileSync('/out/checks-out.json', JSON.stringify(out, null, 2));
const failed = Object.entries(out.checks).filter(([, v]) => v.result !== 'PASS').map(([k]) => k);
console.log(failed.length ? `FAIL: ${failed.join(' ')}` : 'ALL PASS');
process.exit(failed.length ? 1 : 0);
