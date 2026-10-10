// Each device has an account-visible JSON CONFIG variable and token hash.
const headers = {
  'Cache-Control': 'private, no-store, max-age=0',
  'Content-Type': 'text/plain; charset=utf-8',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
};

function reply(text, status, head = false) {
  return new Response(head ? null : text, { status, headers });
}

async function tokenHash(token) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
}

const DEVICES = {
  android: { binding: 'ANDROID_CONFIG', profile: 'flclash.yaml', ipv6Off: true },
  iphone: { binding: 'IPHONE_CONFIG', profile: 'clash-backcn.yaml', ipv6Off: false },
  macbook: { binding: 'MACBOOK_CONFIG', profile: 'clash-backcn-muse.yaml', ipv6Off: false },
};

export function renderProfile(source, providerUrl, ipv6Off = true) {
  // This is the known rulesv2 emitter's block format; fail closed on format drift.
  const pattern = /^  private-provider:\n(?:(?:[ ]{4,}[^\n]*|[ ]*)\n)*/gm;
  const blocks = [...source.matchAll(pattern)];
  if (blocks.length !== 1 || !/^proxy-providers:$/m.test(source) || !/^rules:$/m.test(source)) {
    throw new Error('Unsupported public profile');
  }
  let block = blocks[0][0].replace(/^    (?:type|url|interval|path):[^\n]*\n/gm, '');
  block = block.replace('  private-provider:\n',
    '  private-provider:\n    type: http\n    url: ' + JSON.stringify(providerUrl) +
    '\n    path: "./providers/private-provider.yaml"\n    interval: 3600\n');
  const start = blocks[0].index;
  const output = source.slice(0, start) + block + source.slice(start + blocks[0][0].length);
  // Android's owner explicitly disabled IPv6 for this device.
  return ipv6Off ? output.replace(/^(\s*ipv6:) true[ \t]*$/gm, '$1 false') : output;
}

export default {
  async fetch(request, env) {
    const head = request.method === 'HEAD';
    if (request.method !== 'GET' && !head) return reply('Not found\n', 404);
    const url = new URL(request.url);
    if (url.protocol !== 'https:') return reply('Not found\n', 404, head);
    const match = /^\/(android|iphone|macbook)\/([A-Za-z0-9_-]{43})\/(provider|config)\.yaml$/.exec(url.pathname);
    const bearer = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(request.headers.get('Authorization') || '');
    const plain = /^\/(android|iphone|macbook)\/(provider|config)\.yaml$/.exec(url.pathname);
    const device = match?.[1] || plain?.[1];
    const token = match?.[2] || (plain ? bearer?.[1] : null);
    const kind = match?.[3] || plain?.[2];
    const spec = DEVICES[device];
    if (!token || !spec) return reply('Not found\n', 404, head);
    let config;
    try { const value = env[spec.binding]; config = typeof value === 'string' ? JSON.parse(value) : value; } catch { return reply('Unavailable\n', 503, head); }
    if (!/^[a-f0-9]{64}$/.test(config?.tokenHash) || typeof config.provider !== 'string') {
      return reply('Unavailable\n', 503, head);
    }
    if (await tokenHash(token) !== config.tokenHash) return reply('Not found\n', 404, head);
    if (kind === 'provider') return reply(config.provider, 200, head);
    try {
      // Fetch only the fixed public source, without device credentials or redirects.
      const upstream = await fetch('https://kbyshiyori.github.io/rulesv2/' + spec.profile, {
        headers: { 'User-Agent': 'rulesv2-subscriptions', 'Cache-Control': 'no-cache' },
        redirect: 'manual', signal: AbortSignal.timeout(10000),
        cf: { cacheTtl: 0, cacheEverything: false },
      });
      if (!upstream.ok) return reply(`Rules unavailable: upstream HTTP ${upstream.status}\n`, 502, head);
      const source = await upstream.text();
      if (new TextEncoder().encode(source).length > 1048576) return reply('Rules unavailable\n', 502, head);
      const providerUrl = `${url.origin}/${device}/${token}/provider.yaml`;
      let rendered;
      try { rendered = renderProfile(source, providerUrl, spec.ipv6Off); } catch { return reply('Rules unavailable: unsupported format\n', 502, head); }
      return reply(rendered, 200, head);
    } catch {
      return reply('Rules unavailable: fetch failed\n', 502, head);
    }
  },
};
