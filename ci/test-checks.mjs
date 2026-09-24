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
globalThis.setTimeout = (f, _ms, ...a) => st(f, 0, ...a);   // no real waits
const EXIT = '203.0.113.9';
const cf = (n) => ({ type: 'dns', ip: '198.51.100.' + n, country: 'sg', asn: 'AS13335 CloudFlare Inc' });
const lists = {
  ok: [{ type: 'ip', ip: EXIT, country: 'sg', asn: 'AS64500 VPN' }, cf(1), cf(2), { type: 'conclusion' }],
  empty: [{ type: 'ip', ip: EXIT, country: 'sg', asn: 'AS64500 VPN' }, { type: 'conclusion' }],
  foreign: [cf(1), { type: 'dns', ip: '192.0.2.53', country: 'sg', asn: 'AS64511 Home ISP' }],
  noasn: [cf(1), { type: 'dns', ip: '192.0.2.54', country: 'sg' }],
  // Every resolver in Cloudflare, but located in the "home" country: identity says PASS.
  homecc: [cf(1), { type: 'dns', ip: '198.51.100.9', country: 'de', asn: 'AS13335 CloudFlare Inc' }],
  notlist: { error: 'rate limited' },
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
  if (x.includes("fetch('/json')")) return JSON.stringify({ ip: EXIT, country: 'SG', org: 'AS64500 VPN' });
  if (x.includes('RTCPeerConnection')) return JSON.stringify(['abc.local host', EXIT + ' srflx']);
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
      case 'script.evaluate': return reply({ type: 'success', result: { type: 'string', value: answer(m.params.expression) } });
      default: return reply({});
    }
  }
};
globalThis.fetch = async (url) => {
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
