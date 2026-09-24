// Headless browser checks for the private browser: leak + fingerprint.
// Runs in a node:22-slim sidecar sharing the browser's network namespace (Gluetun's,
// or a plain bridge in CI) and drives the headless Firefox its wrapper script started,
// over WebDriver BiDi. Node 22 has a built-in
// WebSocket client and fetch: nothing to install.
//
// env: EXPECT   Firefox version the image should report ("156.0"); UA check skipped if unset
//      COUNTRY  expected VPN exit country (ISO-2, default SG)
//      DNS_ASN  the ASN every DNS resolver must belong to (default AS13335, Cloudflare:
//               matches DNS_UPSTREAM_RESOLVERS=cloudflare in docker-compose.yml)
//      HOME_CC  optional, informational only: counts resolvers in that country. Never
//               decides PASS/FAIL.
//      MODE     "ci" = fingerprint checks only (no VPN: skips exitIp, webrtc, dnsLeak);
//               used by the public repo's CI job (ci/fingerprint.sh). Same file there.
//      RECORD   "1" = write the CreepJS fields to /out/creep-baseline.json instead of
//               comparing (the creepjs check is then INCOMPLETE, never PASS).
// Reads /w/creep-baseline.json: missing or empty = FAIL unless RECORD=1.
// Writes /out/checks-out.json (summary) + /out/creep-full.json.
// Exit 0 = every check PASS; 1 = any FAIL; 3 = none FAIL but some INCOMPLETE
// (evidence missing: not a pass).
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const EXPECT = process.env.EXPECT || '';
const COUNTRY = (process.env.COUNTRY || 'SG').toUpperCase();
const DNS_ASN = (process.env.DNS_ASN || 'AS13335').toUpperCase();
const HOME_CC = (process.env.HOME_CC || '').toLowerCase();
const CI = process.env.MODE === 'ci';
const RECORD = process.env.RECORD === '1';
const W = process.env.CHECKS_IN || '/w';     // overridden only by ci/test-checks.mjs
const OUT = process.env.CHECKS_OUT || '/out';
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

// fn returns [ok, detail]; ok is true, false or 'INCOMPLETE' (the evidence needed to
// decide is missing). A thrown error is a FAIL: a check that could not run has not
// proven anything.
async function check(name, fn) {
  let ok = false, detail;
  try { [ok, detail] = await fn(); } catch (e) { detail = `ERROR: ${e.message}`; }
  const result = ok === 'INCOMPLETE' ? 'INCOMPLETE' : ok === true ? 'PASS' : 'FAIL';
  out.checks[name] = { result, detail };
  console.log(`${result}  ${name}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
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

  // DNS resolver identity via bash.ws's JSON API: the BROWSER resolves 10 unique names
  // under <id>.bash.ws; bash.ws lists the resolvers that asked. This checks WHO
  // resolved, not the network path (a packet capture is the path proof).
  // FAIL = any resolver outside DNS_ASN. INCOMPLETE = the API failed, no resolver was
  // listed, or a resolver has no ASN. PASS = every resolver is in DNS_ASN.
  await check('dnsLeak', async () => {
    const api = async (url, how) => {
      try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return await r[how]();
      } catch (e) { throw Object.assign(new Error(`bash.ws API: ${e.message}`), { incomplete: true }); }
    };
    try {
      const id = String(await api('https://bash.ws/id', 'text')).trim();
      if (!/^[a-z0-9]+$/.test(id)) return ['INCOMPLETE', `bash.ws API: bad id ${JSON.stringify(id)}`];
      await js(`Promise.allSettled([...Array(10).keys()].map((i) =>
        Promise.race([fetch('https://' + (i + 1) + '.${id}.bash.ws/', { mode: 'no-cors' }),
                      new Promise((r) => setTimeout(r, 5000))]))).then(() => 'ok')`);
      await sleep(2000);
      const list = await api(`https://bash.ws/dnsleak/test/${id}?json`, 'json');
      if (!Array.isArray(list)) return ['INCOMPLETE', 'bash.ws API: the reply is not a list'];
      const dns = list.filter((e) => e?.type === 'dns');
      const asnOf = (e) => (typeof e.asn === 'string' ? e.asn.trim().split(/\s+/)[0].toUpperCase() : '');
      const known = (e) => /^AS\d+$/.test(asnOf(e));
      const foreign = dns.filter((e) => known(e) && asnOf(e) !== DNS_ASN);
      const unknown = dns.filter((e) => !known(e));
      const seen = list.filter((e) => e?.type !== 'conclusion')
        .map((e) => `${e?.type} ${e?.ip} ${e?.country} ${e?.asn}`);
      if (HOME_CC) {
        const n = dns.filter((e) => String(e.country).toLowerCase() === HOME_CC).length;
        seen.push(`info: ${n} resolver(s) in HOME_CC=${HOME_CC} (informational, not gated)`);
      }
      if (foreign.length) return [false, [`${foreign.length} resolver(s) outside ${DNS_ASN}`, ...seen]];
      if (!dns.length) return ['INCOMPLETE', ['no resolver identity returned', ...seen]];
      if (unknown.length) return ['INCOMPLETE', [`${unknown.length} resolver(s) with no ASN`, ...seen]];
      return [true, [`all ${dns.length} resolvers in ${DNS_ASN} (resolver identity, not path proof)`, ...seen]];
    } catch (e) {
      if (e.incomplete) return ['INCOMPLETE', e.message];
      throw e;
    }
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
  writeFileSync(`${OUT}/creep-full.json`, JSON.stringify(fp, null, 2));
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
  if (RECORD) {
    const { fonts, webglBlocked, timezone, cores } = summary;  // the gated fields
    writeFileSync(`${OUT}/creep-baseline.json`, JSON.stringify({ fonts, webglBlocked, timezone, cores }, null, 2) + '\n');
    return ['INCOMPLETE', `RECORD=1: wrote ${OUT}/creep-baseline.json, compared nothing`];
  }
  // No baseline = nothing to compare = FAIL (a missing file once passed as "record-only").
  const bfile = `${W}/creep-baseline.json`;
  if (!existsSync(bfile)) return [false, 'no creep-baseline.json (record one with RECORD=1)'];
  const base = JSON.parse(readFileSync(bfile, 'utf8'));
  if (!base || typeof base !== 'object' || Array.isArray(base) || !Object.keys(base).length) {
    return [false, 'creep-baseline.json is empty: nothing to compare'];
  }
  const diff = Object.keys(base).filter((k) => JSON.stringify(base[k]) !== JSON.stringify(summary[k]))
    .map((k) => `${k}: baseline ${JSON.stringify(base[k])} now ${JSON.stringify(summary[k])}`);
  return [diff.length === 0, diff.length ? diff : `${Object.keys(base).length} fields = baseline`];
});

try { await send('browser.close'); } catch { /* the wrapper kills it anyway */ }
writeFileSync(`${OUT}/checks-out.json`, JSON.stringify(out, null, 2));
const named = (r) => Object.entries(out.checks).filter(([, v]) => v.result === r).map(([k]) => k);
const failed = named('FAIL'), incomplete = named('INCOMPLETE');
if (failed.length) { console.log(`FAIL: ${failed.join(' ')}`); process.exit(1); }
if (incomplete.length) { console.log(`INCOMPLETE: ${incomplete.join(' ')} (not a pass)`); process.exit(3); }
console.log('ALL PASS');
process.exit(0);
