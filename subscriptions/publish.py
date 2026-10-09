#!/usr/bin/env python3
"""Publish a device's private provider to Cloudflare, without third-party Python packages."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEVICES = {'android': 'flclash.yaml', 'iphone': 'clash-backcn.yaml', 'macbook': 'clash-backcn-muse.yaml'}
DEVICE = 'android'
PRIVATE_DIR = ROOT / 'dist/subscriptions'
DEFAULT_PROVIDER = PRIVATE_DIR / 'android-provider.yaml'
REVISION_FILE = PRIVATE_DIR / 'android-revision.json'


def read_env(path):
    result = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if not sep:
                raise ValueError('Invalid local environment file')
            result[key.strip()] = value.strip().strip('\"\'')
    return result


def write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.private-')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_yaml(content, provider=False):
    # macOS supplies Ruby/Psych. Never print parser messages containing private YAML.
    code = 'require "psych"; d=Psych.safe_load(STDIN.read, aliases: false); abort unless d.is_a?(Hash); '
    if provider:
        code += ('n=d.fetch("proxies"); abort unless n.is_a?(Array) && !n.empty?; '
                 'abort unless n.all?{|x|x.is_a?(Hash) && x["name"].is_a?(String) && x["type"].is_a?(String)}; '
                 'abort unless n.map{|x|x["name"]}.uniq.size==n.size; puts n.size')
    result = subprocess.run(['ruby', '-e', code], input=content, text=True, capture_output=True)
    if result.returncode:
        raise ValueError('YAML validation failed; private parser output suppressed')
    return int(result.stdout.strip()) if provider else None


def api(token, path, method='GET', body=None, content_type='application/json'):
    request = urllib.request.Request('https://api.cloudflare.com/client/v4/' + path,
        data=body, method=method, headers={'Authorization': 'Bearer ' + token, 'Content-Type': content_type})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        # API errors may echo uploaded secrets. Report only status, never the body.
        raise RuntimeError(f'Cloudflare API returned HTTP {error.code}') from None
    except urllib.error.URLError:
        raise RuntimeError('Cloudflare API network request failed') from None
    if not data.get('success'):
        raise RuntimeError('Cloudflare API rejected the request; response suppressed')
    return data.get('result')


def multipart(metadata, source):
    boundary = 'rulesv2-' + secrets.token_hex(24)
    chunks = []
    for name, filename, kind, payload in [
        ('metadata', None, 'application/json', json.dumps(metadata).encode()),
        ('worker.mjs', 'worker.mjs', 'application/javascript+module', source.encode()),
    ]:
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disposition += f'; filename="{filename}"'
        chunks.append(f'--{boundary}\r\n{disposition}\r\nContent-Type: {kind}\r\n\r\n'.encode() + payload + b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), 'multipart/form-data; boundary=' + boundary



def verify(base, token, expected):
    url = base + f'/{DEVICE}/provider.yaml'
    for credentials, status in [(token, 200), ('x' * 43, 404)]:
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + credentials, 'User-Agent': 'mihomo/1.19.0'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                actual = response.status
                body = response.read()
                if credentials == token:
                    if body != expected.encode() or 'no-store' not in response.headers.get('Cache-Control', ''):
                        raise RuntimeError('Published provider differs from local file or lacks no-store')
        except urllib.error.HTTPError as error:
            actual = error.code
        except urllib.error.URLError:
            raise RuntimeError('Subscription verification network request failed') from None
        if actual != status:
            raise RuntimeError('Subscription authentication check failed')
    # Exercise the URL form that the client will actually use.
    try:
        request = urllib.request.Request(base + f'/{DEVICE}/' + token + '/provider.yaml', headers={'User-Agent': 'mihomo/1.19.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.read() != expected.encode():
                raise RuntimeError('Subscription URL verification failed')
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise RuntimeError('Subscription URL request failed; private URL suppressed') from None



def verify_profile(base, token):
    private_url = base + f'/{DEVICE}/' + token + '/provider.yaml'
    url = base + f'/{DEVICE}/' + token + '/config.yaml'
    request = urllib.request.Request(url, headers={'User-Agent': 'mihomo/1.19.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read().decode()
            if 'no-store' not in response.headers.get('Cache-Control', ''):
                raise RuntimeError('Full profile lacks private cache policy')
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise RuntimeError('Full profile request failed; private URL suppressed') from None
    validate_yaml(content)
    # Parse independently, ensuring the response can be imported as a main profile.
    code = ('require "psych"; require "json"; i=JSON.parse(STDIN.read); '
            'd=Psych.safe_load(i.fetch("yaml"), aliases: false); '
            'p=d.fetch("proxy-providers").fetch("private-provider"); '
            'abort unless p["type"]=="http" && p["url"]==i.fetch("url") && p["interval"]==3600; '
            'abort unless d["rules"].is_a?(Array) && !d["rules"].empty? && d["proxy-groups"].is_a?(Array); '
            'abort unless i.fetch("device")!="android" || (d["ipv6"]==false && d.fetch("dns")["ipv6"]==false)')
    result = subprocess.run(['ruby', '-e', code], input=json.dumps({'yaml': content, 'url': private_url, 'device': DEVICE}),
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('Full profile validation failed; private parser output suppressed')
    request = urllib.request.Request(base + f'/{DEVICE}/' + 'x' * 43 + '/config.yaml',
                                     headers={'User-Agent': 'mihomo/1.19.0'})
    try:
        with urllib.request.urlopen(request, timeout=30):
            raise RuntimeError('Unauthenticated full profile request unexpectedly succeeded')
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise RuntimeError('Full profile authentication check failed') from None
    except urllib.error.URLError:
        raise RuntimeError('Full profile authentication network check failed') from None
    return url, content


def load_settings(require_token=True):
    settings = read_env(ROOT / '.env.subscriptions')
    account = settings.get('CLOUDFLARE_ACCOUNT_ID', '')
    worker = settings.get('CLOUDFLARE_WORKER', '')
    base = settings.get('SUBSCRIPTION_BASE_URL', '').rstrip('/')
    token = settings.get(DEVICE.upper() + '_SUBSCRIPTION_TOKEN', '')
    if not re.fullmatch(r'[a-f0-9]{32}', account) or not re.fullmatch(r'[a-z0-9-]+', worker):
        raise ValueError('Set account ID and Worker name in .env.subscriptions')
    if not re.fullmatch(r'https://[a-zA-Z0-9.-]+', base):
        raise ValueError('Set an HTTPS base URL in .env.subscriptions')
    if require_token and not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise ValueError('Provide the EXISTING device token in .env.subscriptions; never recreate it automatically')
    return account, worker, base, token


def download_provider(base, token):
    # Header auth keeps the device token out of request URLs and diagnostics.
    request = urllib.request.Request(base + f'/{DEVICE}/provider.yaml',
        headers={'Authorization': 'Bearer ' + token, 'User-Agent': 'mihomo/1.19.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read(1048577)
            if len(content) > 1048576:
                raise RuntimeError('Cloud provider exceeds size limit')
            if 'no-store' not in response.headers.get('Cache-Control', ''):
                raise RuntimeError('Cloud provider lacks private cache policy')
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise RuntimeError('Cannot download current cloud provider; check existing token and network') from None
    text = content.decode()
    validate_yaml(text, provider=True)
    return text


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def revision(base, token, provider):
    return {'schema': 1, 'base': base, 'device': DEVICE,
            'tokenHash': digest(token), 'providerSha256': digest(provider)}


def load_revision(path=None):
    path = REVISION_FILE if path is None else path
    if not path.exists():
        raise ValueError('Run --pull before editing or publishing nodes')
    try:
        return json.loads(path.read_text())
    except (ValueError, TypeError):
        raise ValueError('Local revision is invalid; recover with --pull --discard-local') from None


def ensure_current(state, base, token, cloud_provider):
    if state != revision(base, token, cloud_provider):
        raise ValueError('Cloud nodes changed since --pull; stop and merge a fresh cloud copy before publishing')


def backup(content):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_private(PRIVATE_DIR / 'backups' / (stamp + '-' + DEVICE + '-provider.yaml'), content)


def pull(base, token, discard_local=False):
    cloud = download_provider(base, token)
    if DEFAULT_PROVIDER.exists():
        local = DEFAULT_PROVIDER.read_text()
        try:
            state = load_revision()
            clean = state == revision(base, token, local)
        except ValueError:
            clean = False
        if not clean and not discard_local:
            raise ValueError('Unpublished local edits exist; --pull refused. Merge them or use --discard-local (backs them up)')
        if local != cloud:
            backup(local)
    write_private(DEFAULT_PROVIDER, cloud)
    write_private(REVISION_FILE, json.dumps(revision(base, token, cloud), indent=2) + '\n')
    print(f'Cloud nodes downloaded to dist/subscriptions/{DEVICE}-provider.yaml; baseline saved')


def save_outputs(base, token, full_profile):
    write_private(PRIVATE_DIR / (DEVICE + '-url.txt'), base + f'/{DEVICE}/' + token + '/provider.yaml\n')
    write_private(PRIVATE_DIR / (DEVICE + '-config-url.txt'), base + f'/{DEVICE}/' + token + '/config.yaml\n')
    write_private(PRIVATE_DIR / DEVICES[DEVICE], full_profile)


def deploy(account, worker, token, provider):
    cf = read_env(ROOT / '.env.cloudflare')
    api_token = os.environ.get('CLOUDFLARE_API_TOKEN') or cf.get('CLOUDFLARE_API_TOKEN')
    if not api_token:
        raise ValueError('Provide CLOUDFLARE_API_TOKEN through the agent Secret/environment before publishing')
    existing = api(api_token, f'accounts/{account}/workers/scripts/{worker}/settings').get('bindings', [])
    config = json.dumps({'tokenHash': digest(token), 'provider': provider})
    metadata = {
        'main_module': 'worker.mjs', 'compatibility_date': '2025-01-01',
        'bindings': deployment_bindings(existing, DEVICE.upper() + '_CONFIG', config),
        'observability': {'enabled': False},
    }
    body, content_type = multipart(metadata, (ROOT / 'subscriptions/worker.mjs').read_text())
    path = f'accounts/{account}/workers/scripts/{worker}'
    api(api_token, path, 'PUT', body, content_type)
    api(api_token, path + '/subdomain', 'POST', json.dumps({'enabled': True, 'previews_enabled': False}).encode())


def deployment_bindings(existing, target, config):
    bindings = [{'name': target, 'type': 'json', 'json': config}]
    for entry in existing:
        if entry.get('name') == target:
            continue
        if entry.get('type') not in ('secret_text', 'json') or entry.get('name') not in {d.upper() + '_CONFIG' for d in DEVICES}:
            raise ValueError('Unexpected Worker binding; review before deploying rather than deleting it')
        bindings.append({'name': entry['name'], 'type': 'inherit'})
    return bindings


def bootstrap(account, worker, base, provider_path):
    # New-device onboarding is explicit; ordinary publishing never creates tokens.
    cf = read_env(ROOT / '.env.cloudflare')
    api_token = os.environ.get('CLOUDFLARE_API_TOKEN') or cf.get('CLOUDFLARE_API_TOKEN')
    if not api_token:
        raise ValueError('Cloudflare API token required for bootstrap')
    bindings = api(api_token, f'accounts/{account}/workers/scripts/{worker}/settings').get('bindings', [])
    if any(e.get('name') == DEVICE.upper() + '_CONFIG' for e in bindings):
        raise ValueError('Device already exists in Cloudflare; use --pull, never bootstrap over it')
    provider = provider_path.read_text()
    print(f'Onboarding {DEVICE}: {validate_yaml(provider, provider=True)} nodes')
    env_path = ROOT / '.env.subscriptions'
    settings = read_env(env_path)
    key = DEVICE.upper() + '_SUBSCRIPTION_TOKEN'
    token = settings.get(key) or secrets.token_urlsafe(32)
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise ValueError('Invalid bootstrap device token')
    settings[key] = token
    write_private(env_path, ''.join(k + '=' + v + '\n' for k, v in settings.items()))
    deploy(account, worker, token, provider)
    verify(base, token, provider)
    _, full_profile = verify_profile(base, token)
    write_private(DEFAULT_PROVIDER, provider)
    write_private(REVISION_FILE, json.dumps(revision(base, token, provider), indent=2) + '\n')
    save_outputs(base, token, full_profile)
    print(f'{DEVICE} onboarded and verified; private subscription URLs saved, not printed')


def main():
    global DEVICE, DEFAULT_PROVIDER, REVISION_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--pull', action='store_true', help='Download authoritative Cloudflare nodes into ignored working file')
    actions.add_argument('--publish', action='store_true', help='Publish validated local edits after cloud baseline check')
    actions.add_argument('--deploy-code', action='store_true', help='Deploy Worker source while preserving current cloud nodes')
    actions.add_argument('--check', action='store_true', help='Validate working provider offline; no deployment')
    actions.add_argument('--verify', action='store_true', help='Verify live subscription; recover after uncertain deployment')
    actions.add_argument('--bootstrap', action='store_true', help='Explicitly onboard a new device from --provider, never overwrite an existing device')
    parser.add_argument('--device', choices=DEVICES, default='android')
    parser.add_argument('--provider', type=Path, default=None, help='Edited node file for --check/--publish/--verify')
    parser.add_argument('--discard-local', action='store_true', help='With --pull, back up unpublished edits before replacing them')
    args = parser.parse_args()
    DEVICE = args.device
    DEFAULT_PROVIDER = PRIVATE_DIR / (DEVICE + '-provider.yaml')
    REVISION_FILE = PRIVATE_DIR / (DEVICE + '-revision.json')
    if args.bootstrap and args.provider is None:
        parser.error('--bootstrap requires an explicit --provider')
    args.provider = args.provider or DEFAULT_PROVIDER
    if args.discard_local and not args.pull:
        parser.error('--discard-local requires --pull')
    if args.check:
        print(f'Provider YAML valid: {validate_yaml(args.provider.read_text(), provider=True)} nodes')
        return
    if args.bootstrap:
        account, worker, base, _ = load_settings(require_token=False)
        bootstrap(account, worker, base, args.provider)
        return
    account, worker, base, token = load_settings()
    if args.pull:
        pull(base, token, args.discard_local)
        return
    cloud = download_provider(base, token)
    provider = cloud if args.deploy_code else args.provider.read_text()
    print(f'Provider YAML valid: {validate_yaml(provider, provider=True)} nodes')
    if args.publish:
        ensure_current(load_revision(), base, token, cloud)
        backup(cloud)
        deploy(account, worker, token, provider)
    elif args.deploy_code:
        deploy(account, worker, token, cloud)
    # --verify does no upload. Matching local/remote contents permits baseline recovery.
    verify(base, token, provider)
    _, full_profile = verify_profile(base, token)
    save_outputs(base, token, full_profile)
    if not args.deploy_code:
        write_private(REVISION_FILE, json.dumps(revision(base, token, provider), indent=2) + '\n')
        if args.provider.resolve() != DEFAULT_PROVIDER.resolve():
            if DEFAULT_PROVIDER.exists() and DEFAULT_PROVIDER.read_text() != provider:
                backup(DEFAULT_PROVIDER.read_text())
            write_private(DEFAULT_PROVIDER, provider)
    print('Verified live nodes, full profile and authentication; private outputs saved in dist/subscriptions')
    print('No iCloud files are read or written')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        # OSError can include a path, but never read back secret content or HTTP URLs.
        print(str(error), file=sys.stderr)
        sys.exit(1)
