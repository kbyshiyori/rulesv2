import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import worker from './worker.mjs';

const token = 'a'.repeat(43);
const provider = 'proxies:\n  - name: example\n    type: direct\n';
const env = { ANDROID_CONFIG: JSON.stringify({ tokenHash: createHash('sha256').update(token).digest('hex'), provider }) };
const url = `https://sub.example.com/android/${token}/provider.yaml`;

test('only an authenticated Android request returns the provider', async () => {
  for (const address of [url, 'https://sub.example.com/android/provider.yaml']) {
    const r = await worker.fetch(new Request(address, { headers: { Authorization: `Bearer ${token}` } }), env);
    assert.equal(r.status, 200);
    assert.equal(await r.text(), provider);
    assert.match(r.headers.get('Cache-Control'), /no-store/);
  }
});
test('wrong tokens, devices, methods, and HTTP do not disclose credentials', async () => {
  for (const request of [
    new Request(url.replace(token, 'b'.repeat(43))),
    new Request(url.replace('/android/', '/windows/')),
    new Request('https://sub.example.com/android/provider.yaml'),
    new Request(url, { method: 'POST' }),
    new Request(url.replace('https:', 'http:')),
  ]) {
    const r = await worker.fetch(request, env);
    assert.equal(r.status, 404);
    assert.ok(!(await r.text()).includes('proxies:'));
  }
});
test('missing or malformed config fails closed', async () => {
  for (const e of [{}, { ANDROID_CONFIG: 'broken' }, { ANDROID_CONFIG: '{}' }]) {
    assert.equal((await worker.fetch(new Request(url), e)).status, 503);
  }
});
test('HEAD authenticates without returning node credentials', async () => {
  const r = await worker.fetch(new Request(url, { method: 'HEAD' }), env);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '');
});

const mainProfile = `ipv6: true
 dnsPlaceholder: ignored
proxy-providers:
  private-provider:
    type: file
    path: "./providers/private-provider.yaml"
    health-check:
      enable: true
      url: "https://captive.apple.com"
      interval: 600
proxy-groups:
  - name: China
    type: select
    use:
      - private-provider
rules:
  - MATCH,China
`.replace(' dnsPlaceholder: ignored\n', '');

test('full subscription follows updated public rules and retains private provider', async () => {
  const originalFetch = globalThis.fetch;
  let source = mainProfile;
  globalThis.fetch = async (address, options) => {
    assert.equal(address, 'https://kbyshiyori.github.io/rulesv2/flclash.yaml');
    assert.equal(options.headers.Authorization, undefined);
    assert.equal(options.redirect, 'manual');
    assert.ok(!address.includes(token));
    return new Response(source);
  };
  try {
    const address = url.replace('provider.yaml', 'config.yaml');
    const result = await worker.fetch(new Request(address), env);
    assert.equal(result.status, 200);
    const content = await result.text();
    assert.ok(content.includes(`url: "${url}"`));
    assert.ok(content.includes('    type: http\n'));
    assert.ok(content.includes('ipv6: false\n'));
    assert.ok(content.includes('      interval: 600\n'));
    assert.ok(content.includes('rules:\n  - MATCH,China'));
    source = mainProfile.replace('  - MATCH,China', '  - DOMAIN-SUFFIX,example.com,China\n  - MATCH,China');
    const updated = await worker.fetch(new Request(address), env);
    assert.ok((await updated.text()).includes('DOMAIN-SUFFIX,example.com,China'));
  } finally { globalThis.fetch = originalFetch; }
});

test('full config rejects unauthenticated users before fetching public rules', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error('must not fetch'); };
  try {
    const bad = url.replace(token, 'b'.repeat(43)).replace('provider.yaml', 'config.yaml');
    assert.equal((await worker.fetch(new Request(bad), env)).status, 404);
  } finally { globalThis.fetch = originalFetch; }
});

test('upstream errors and profile format drift fail without exposing secrets', async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const upstream of [() => new Response('bad', {status: 500}), () => new Response('unexpected yaml'), () => {throw new Error('timeout');}]) {
      globalThis.fetch = async () => upstream();
      const result = await worker.fetch(new Request(url.replace('provider.yaml', 'config.yaml')), env);
      assert.equal(result.status, 502);
      assert.match(await result.text(), /^Rules unavailable/);
    }
  } finally { globalThis.fetch = originalFetch; }
});


test('device secrets are isolated and each device selects its public rules', async () => {
  const devices = {android: 'flclash.yaml', iphone: 'clash-backcn.yaml', macbook: 'clash-backcn-muse.yaml'};
  const tokens = {android: 'a'.repeat(43), iphone: 'b'.repeat(43), macbook: 'c'.repeat(43)};
  const multiEnv = Object.fromEntries(Object.keys(devices).map(d => [d.toUpperCase() + '_CONFIG', JSON.stringify({tokenHash: createHash('sha256').update(tokens[d]).digest('hex'), provider: provider.replace('example', d)})]));
  const originalFetch = globalThis.fetch;
  try {
    for (const [device, profile] of Object.entries(devices)) {
      for (const [owner, credential] of Object.entries(tokens)) {
        const r = await worker.fetch(new Request(`https://sub.example.com/${device}/${credential}/provider.yaml`), multiEnv);
        assert.equal(r.status, owner === device ? 200 : 404);
        if (owner === device) assert.equal(await r.text(), provider.replace('example', device));
      }
      globalThis.fetch = async address => {
        assert.equal(address, `https://kbyshiyori.github.io/rulesv2/${profile}`);
        return new Response(mainProfile);
      };
      const r = await worker.fetch(new Request(`https://sub.example.com/${device}/${tokens[device]}/config.yaml`), multiEnv);
      assert.equal(r.status, 200);
      const content = await r.text();
      assert.ok(content.includes(`/${device}/${tokens[device]}/provider.yaml`));
      assert.ok(content.includes(`ipv6: ${device === 'android' ? 'false' : 'true'}`));
    }
  } finally { globalThis.fetch = originalFetch; }
});


test('native JSON binding and legacy string binding return identical authenticated nodes', async () => {
  const jsonEnv = { ANDROID_CONFIG: JSON.parse(env.ANDROID_CONFIG) };
  const r = await worker.fetch(new Request(url), jsonEnv);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), provider);
  const bad = await worker.fetch(new Request(url.replace(token, 'b'.repeat(43))), jsonEnv);
  assert.equal(bad.status, 404);
});
