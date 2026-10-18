// Stub tests for ci/checks.mjs: a fake WebDriver BiDi socket and a fake bash.ws API
// replace the browser and the network, so no Firefox, Docker or network is needed.
// Usage: node ci/test-checks.mjs [path/to/checks.mjs]   exit 0 = every case as expected.
// Run against the pre-review-4 checks.mjs, it fails (missing baseline passed, DNS
// judged by country, no INCOMPLETE / exit 3).
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const CHECKS = resolve(process.argv[2] || join(here, 'checks.mjs'));
const SD = mkdtempSync(join(tmpdir(), 'pbchk-'));
process.on('exit', () => rmSync(SD, { recursive: true, force: true }));

// Preloaded into the checks.mjs process. Scenario comes from S_* env vars.
const STUB = String.raw`
const E = process.env;
const st = globalThis.setTimeout;
globalThis.setTimeout = (f, _ms, ...a) => st(f, [1000, 20000].includes(_ms) ? 150 : 0, ...a);   // no real waits
const EXIT = '203.0.113.9';
let exitCalls = 0;
AbortSignal.timeout = () => {
  const controller = new AbortController();
  st(() => controller.abort(new Error('timeout')), 30);
  return controller.signal;
};
const exitFetch = async (_url, options) => {
  if (!options.signal || options.cache !== 'no-store') throw new Error('missing deadline/cache policy');
  const n = ++exitCalls;
  const mode = E.S_EXIT === 'transient' && n > 1 ? 'ok' : E.S_EXIT === 'missingthenok' ? (n === 1 ? 'missing' : 'ok') : E.S_EXIT;
  if (mode === 'timeout') return new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('timeout')), { once: true });
  });
  if (mode === 'down') throw new TypeError('fetch failed');
  if (mode === 'http' || mode === 'transient') return new Response('{}', { status: 503 });
  if (mode === 'malformed') return new Response('<html>not JSON</html>');
  let j = { ip: EXIT, country: 'SG', org: 'AS64500 VPN' };
  if (mode === 'missing') j = {};
  if (mode === 'null') j = null;
  if (mode === 'badip') j.ip = 'not-an-ip';
  if (mode === 'noorg') delete j.org;
  if (mode === 'inconsistent' && n === 1) { delete j.org; j.ip = '192.0.2.1'; }
  if (mode === 'badcountry') j.country = 'Singapore';
  if (mode === 'wrong') j.country = 'US';
  if (mode === 'wrongmissing') { j.country = 'US'; delete j.ip; }
  if (mode === 'wrongthenok' && n === 1) j.country = 'US';
  return new Response(JSON.stringify(j));
};
const cf = (n) => ({ type: 'dns', ip: '198.51.100.' + n, country: 'sg', asn: 'AS13335 CloudFlare Inc' });
const lists = {
  ok: [{ type: 'ip', ip: EXIT, country: 'sg', asn: 'AS64500 VPN' }, cf(1), cf(2), { type: 'conclusion' }],
  empty: [{ type: 'ip', ip: EXIT, country: 'sg', asn: 'AS64500 VPN' }, { type: 'conclusion' }],
  foreign: [cf(1), { type: 'dns', ip: '192.0.2.53', country: 'sg', asn: 'AS64511 Home ISP' }],
  noasn: [cf(1), { type: 'dns', ip: '192.0.2.54', country: 'sg' }],
  // Every resolver in Cloudflare, but located in the "home" country: identity says PASS.
  homecc: [cf(1), { type: 'dns', ip: '198.51.100.9', country: 'de', asn: 'AS13335 CloudFlare Inc' }],
  notlist: { error: 'rate limited' },
  mismatch: [{ type: 'ip', ip: '192.0.2.1' }, cf(1)],
  badclient: [{ type: 'ip', ip: 'bad' }, cf(1)],
};
const fp = E.S_FP === 'none' ? null : {
  fonts: { fontFaceLoadFonts: ['DejaVu Sans', 'Liberation Mono', 'Noto Color Emoji'] },
  media: { mimeTypes: [1, 2] },
  navigator: { userAgent: 'Firefox/156.0', hardwareConcurrency: Number(E.S_CORES || 4) },
  timezone: { location: 'Atlantic, Reykjavik' },
  screen: { width: 1200, height: 500 },
};
const answer = (x) => {
  if (x.includes('navigator.userAgent')) return 'Mozilla/5.0 rv:156.0 Firefox/156.0';
  if (x.includes('Intl.DateTimeFormat')) return 'Atlantic/Reykjavik';
  if (x.includes("getContext('webgl')")) return 'false';
  if (x.includes("fetch('/json'")) return new Function('fetch', 'AbortSignal', 'return ' + x)(exitFetch, AbortSignal);
  if (x.includes('RTCPeerConnection')) return JSON.stringify(['abc.local host', (E.S_RTC === 'foreign' ? '192.0.2.77' : EXIT) + ' srflx']);
  if (x.includes('allSettled')) return 'ok';
  if (x.includes('window.Fingerprint')) return JSON.stringify(fp);
  throw new Error('stub: unexpected expression ' + x.slice(0, 40));
};
globalThis.WebSocket = class {
  constructor() { st(() => this.onopen?.(), 0); }
  send(s) {
    const m = JSON.parse(s);
    const reply = (result) => st(() => this.onmessage?.({ data: JSON.stringify({ id: m.id, type: 'success', result }) }), 0);
    switch (m.method) {
      case 'session.new': return reply({ capabilities: { browserVersion: '156.0.1' } });
      case 'browsingContext.getTree': return reply({ contexts: [{ context: 'c1' }] });
      case 'script.evaluate':
        if (E.S_EXIT === 'bidi-timeout' && m.params.expression.includes("fetch('/json'")) return;
        return Promise.resolve().then(() => answer(m.params.expression)).then(
          value => reply({ type: 'success', result: { type: 'string', value } }),
          error => reply({ type: 'exception', exceptionDetails: { text: error.message } }));
      default: return reply({});
    }
  }
};
globalThis.fetch = async (url, options) => {
  if (!options.signal) throw new Error('missing API deadline');
  if (E.S_API === 'timeout') return new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(new Error('timeout')), { once: true });
  });
  if (E.S_API === 'badjson' && url !== 'https://bash.ws/id') return new Response('<html>');
  if (E.S_API === 'down') throw new TypeError('fetch failed');
  if (url === 'https://bash.ws/id') return new Response(E.S_ID ?? 'abc123');
  if (E.S_API === '500') return new Response('oops', { status: 500 });
  return new Response(JSON.stringify(lists[E.S_DNS || 'ok']));
};
`;
const stubFile = join(SD, 'stub.mjs');
writeFileSync(stubFile, STUB);

const BASE = { fonts: ['DejaVu Sans', 'Liberation Mono', 'Noto Color Emoji'], webglBlocked: true,
  timezone: 'Atlantic, Reykjavik', cores: 4 };

let pass = 0, failn = 0;
// t(name, wantRc, mustMatch, mustNotMatch, env, baseline)   baseline: object | string | null
function t(name, want, must, mustnot, env = {}, baseline = BASE) {
  const w = mkdtempSync(join(SD, 'w-')), o = mkdtempSync(join(SD, 'o-'));
  if (baseline !== null) {
    writeFileSync(join(w, 'creep-baseline.json'), typeof baseline === 'string' ? baseline : JSON.stringify(baseline));
  }
  const r = spawnSync(process.execPath, ['--import', stubFile, CHECKS], {
    env: { PATH: process.env.PATH, CHECKS_IN: w, CHECKS_OUT: o, EXPECT: '156.0.1', ...env },
    encoding: 'utf8', timeout: 30000,
  });
  const text = (r.stdout || '') + (r.stderr || '');
  const why = [];
  if (r.status !== want) why.push(`rc=${r.status} want ${want}`);
  if (must && !must.test(text)) why.push(`missing ${must}`);
  if (mustnot && mustnot.test(text)) why.push(`found ${mustnot}`);
  if (why.length) { failn++; console.log(`FAIL  ${name}: ${why.join('; ')}`); console.log(text.replace(/^/gm, '        | ')); }
  else { pass++; console.log(`ok    ${name}`); }
  return { w, o, text };
}

console.log('== checks.mjs (live mode)');
t('all good', 0, /^ALL PASS$/m, /INCOMPLETE/);
t('DNS PASS is labelled identity, not path', 0, /^PASS {2}dnsLeak: .*resolver identity, not path proof/m, null);
t('no resolver listed', 3, /^INCOMPLETE {2}dnsLeak: .*no resolver identity/m, /^ALL PASS/m, { S_DNS: 'empty' });
t('resolver outside the ASN', 1, /^FAIL {2}dnsLeak: .*outside AS13335/m, null, { S_DNS: 'foreign' });
t('resolver without an ASN', 3, /^INCOMPLETE {2}dnsLeak: .*with no ASN/m, null, { S_DNS: 'noasn' });
t('bash.ws unreachable', 3, /^INCOMPLETE {2}dnsLeak: bash\.ws API/m, null, { S_API: 'down' });
t('bash.ws HTTP 500', 3, /^INCOMPLETE {2}dnsLeak: bash\.ws API: HTTP 500/m, null, { S_API: '500' });
t('bash.ws reply not a list', 3, /^INCOMPLETE {2}dnsLeak: .*not a list/m, null, { S_DNS: 'notlist' });
t('bash.ws bad id', 3, /^INCOMPLETE {2}dnsLeak: .*bad id/m, null, { S_ID: '<html>' });
t('geography does not decide (no HOME_CC)', 0, /^PASS {2}dnsLeak/m, null, { S_DNS: 'homecc' });
t('HOME_CC is informational only', 0, /1 resolver\(s\) in HOME_CC=de \(informational/, null,
  { S_DNS: 'homecc', HOME_CC: 'DE' });
t('DNS_ASN selects the provider', 1, /^FAIL {2}dnsLeak: .*outside AS64511/m, null, { DNS_ASN: 'AS64511' });
t('FAIL outranks INCOMPLETE', 1, /^FAIL: creepjs/m, null, { S_DNS: 'empty', S_CORES: '8' });

console.log('== exit metadata failure paths');
for (const mode of ['missing', 'null', 'malformed', 'badip', 'badcountry', 'noorg', 'http', 'down', 'timeout', 'bidi-timeout']) {
  const r = t('exit ' + mode, 3, /^INCOMPLETE {2}exitIp/m, /^PASS {2}(exitIp|webrtc)/m, { S_EXIT: mode });
  const report = JSON.parse(readFileSync(join(r.o, 'checks-out.json'), 'utf8'));
  if (report.exitMetadataAttempts.length === 3 && report.checks.webrtc.result === 'INCOMPLETE' &&
      report.checks.webrtc.detail.seen.length === 2) {
    pass++; console.log('ok    three attempts, dependent observations retained: ' + mode);
  } else { failn++; console.log('FAIL  attempt/dependency evidence: ' + mode); }
}
const recovered = t('transient exit HTTP recovery', 0, /^PASS {2}exitIp/m, /^INCOMPLETE {2}webrtc/m, { S_EXIT: 'transient' });
const attempts = JSON.parse(readFileSync(join(recovered.o, 'checks-out.json'), 'utf8')).exitMetadataAttempts;
if (attempts.length === 2 && attempts[0].result === 'INCOMPLETE' && attempts[1].result === 'PASS') {
  pass++; console.log('ok    transient failure retained');
} else { failn++; console.log('FAIL  transient failure not retained'); }
for (const mode of ['wrong', 'wrongmissing', 'wrongthenok']) {
  const r = t('wrong country ' + mode, 1, /^FAIL {2}exitIp: country US/m, /^PASS {2}(exitIp|webrtc)/m, { S_EXIT: mode });
  if (JSON.parse(readFileSync(join(r.o, 'checks-out.json'), 'utf8')).exitMetadataAttempts.length === 1) {
    pass++; console.log('ok    wrong country never retried: ' + mode);
  } else { failn++; console.log('FAIL  wrong country retried'); }
}
t('missing metadata recovers', 0, /^PASS {2}exitIp/m, /^INCOMPLETE {2}webrtc/m, { S_EXIT: 'missingthenok' });
t('exit inconsistent after incomplete metadata', 1, /^FAIL {2}exitIp: inconsistent observed/m, /^PASS {2}webrtc/m, { S_EXIT: 'inconsistent' });
t('DNS client disagrees with exit', 1, /^FAIL {2}dnsLeak: .*inconsistent/m, null, { S_DNS: 'mismatch' });
t('DNS client malformed', 3, /^INCOMPLETE {2}dnsLeak: .*malformed/m, null, { S_DNS: 'badclient' });
t('WebRTC foreign address', 1, /^FAIL {2}webrtc/m, null, { S_RTC: 'foreign' });
t('DNS prohibited identity still FAIL without exit reference', 1, /^FAIL {2}dnsLeak/m, /^PASS {2}webrtc/m, { S_EXIT: 'missing', S_DNS: 'foreign' });
t('DNS timeout', 3, /^INCOMPLETE {2}dnsLeak/m, /^ALL PASS/m, { S_API: 'timeout' });
t('DNS malformed JSON', 3, /^INCOMPLETE {2}dnsLeak/m, /^ALL PASS/m, { S_API: 'badjson' });

console.log('== checks.mjs (baseline, MODE=ci)');
t('ci: all good', 0, /^ALL PASS$/m, /dnsLeak/, { MODE: 'ci' });
t('ci: baseline missing', 1, /^FAIL {2}creepjs: no creep-baseline\.json/m, null, { MODE: 'ci' }, null);
t('ci: baseline empty object', 1, /^FAIL {2}creepjs: .*empty/m, null, { MODE: 'ci' }, {});
t('ci: baseline empty file', 1, /^FAIL {2}creepjs/m, null, { MODE: 'ci' }, '');
t('ci: field differs', 1, /cores: baseline 4 now 8/, null, { MODE: 'ci', S_CORES: '8' });
t('ci: CreepJS never loads', 1, /^FAIL {2}creepjs: ERROR/m, null, { MODE: 'ci', S_FP: 'none' });
const rec = t('ci: RECORD=1 is not a pass', 3, /^INCOMPLETE {2}creepjs: RECORD=1/m, /^ALL PASS/m,
  { MODE: 'ci', RECORD: '1' }, null);
const bf = join(rec.o, 'creep-baseline.json');
if (existsSync(bf) && JSON.stringify(JSON.parse(readFileSync(bf, 'utf8'))) === JSON.stringify(BASE)) {
  pass++; console.log('ok    ci: RECORD=1 writes the 4 gated fields');
} else { failn++; console.log('FAIL  ci: RECORD=1 did not write the expected baseline'); }

console.log(`\nchecks.mjs: ${pass} passed, ${failn} failed`);
process.exit(failn ? 1 : 0);
