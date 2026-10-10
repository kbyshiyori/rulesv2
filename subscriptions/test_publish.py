import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('subscription_publish', Path(__file__).with_name('publish.py'))
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

PROVIDER = 'proxies:\n  - name: example\n    type: direct\n'
OTHER = PROVIDER.replace('example', 'new-name')
BASE = 'https://sub.example.com'
TOKEN = 'a' * 43


class PublisherTests(unittest.TestCase):
    def test_deployment_preserves_other_device_bindings(self):
        existing = [{'name': d.upper() + '_CONFIG', 'type': 'json' if d == 'macbook' else 'secret_text'} for d in publish.DEVICES]
        bindings = publish.deployment_bindings(existing, 'IPHONE_CONFIG', '{"provider":"example"}')
        self.assertEqual(bindings[0], {'name': 'IPHONE_CONFIG', 'type': 'json', 'json': '{"provider":"example"}'})
        self.assertEqual(bindings[1:], [{'name': 'ANDROID_CONFIG', 'type': 'inherit'}, {'name': 'MACBOOK_CONFIG', 'type': 'inherit'}])
        with self.assertRaises(ValueError):
            publish.deployment_bindings([{'name': 'unknown', 'type': 'secret_text'}], 'IPHONE_CONFIG', '{}')

    def test_bootstrap_refuses_existing_device_before_read_or_write(self):
        with patch.object(publish, 'read_env', return_value={'CLOUDFLARE_API_TOKEN': 'example'}), \
             patch.object(publish, 'api', return_value={'bindings': [{'name': 'ANDROID_CONFIG'}]}), \
             patch.object(publish, 'write_private') as write, patch.object(publish, 'deploy') as deploy:
            with self.assertRaises(ValueError):
                publish.bootstrap('account', 'worker', BASE, Path('/nonexistent/nodes.yaml'))
            write.assert_not_called()
            deploy.assert_not_called()

    def test_invalid_provider_rejected(self):
        for value in ('proxies: []\n', 'not: a-provider\n', 'proxies:\n - name: same\n   type: direct\n - name: same\n   type: direct\n'):
            with self.assertRaises(ValueError):
                publish.validate_yaml(value, provider=True)

    def test_multipart_separates_secrets_from_source(self):
        body, kind = publish.multipart({'bindings': [{'type': 'secret_text', 'text': 'EXAMPLE_SECRET'}]}, 'export default {};')
        self.assertIn(b'name="metadata"', body)
        self.assertIn(b'name="worker.mjs"; filename="worker.mjs"', body)
        self.assertIn('multipart/form-data; boundary=', kind)
        self.assertNotIn(b'EXAMPLE_SECRET', body.split(b'name="worker.mjs"')[1])

    def test_cloud_update_or_wrong_device_refuses_publish(self):
        state = publish.revision(BASE, TOKEN, PROVIDER)
        publish.ensure_current(state, BASE, TOKEN, PROVIDER)
        for base, token, text in [(BASE, TOKEN, OTHER), (BASE, 'b'*43, PROVIDER), ('https://other.example.com', TOKEN, PROVIDER)]:
            with self.assertRaises(ValueError):
                publish.ensure_current(state, base, token, text)

    def test_local_files_are_private_and_written_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'nodes.yaml'
            publish.write_private(path, PROVIDER)
            self.assertEqual(path.read_text(), PROVIDER)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            publish.write_private(path, OTHER)
            self.assertEqual(path.read_text(), OTHER)
            self.assertEqual(list(Path(directory).glob('.private-*')), [])

    def test_pull_preserves_unpublished_edits_then_explicitly_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root/'android-provider.yaml'
            state = root/'android-revision.json'
            publish.write_private(work, OTHER)
            publish.write_private(state, json.dumps(publish.revision(BASE,TOKEN,PROVIDER)))
            with patch.object(publish, 'PRIVATE_DIR', root), patch.object(publish, 'DEFAULT_PROVIDER', work), \
                 patch.object(publish, 'REVISION_FILE', state), \
                 patch.object(publish, 'load_revision', return_value=publish.revision(BASE,TOKEN,PROVIDER)), \
                 patch.object(publish, 'download_provider', return_value=PROVIDER):
                with self.assertRaises(ValueError):
                    publish.pull(BASE, TOKEN)
                self.assertEqual(work.read_text(), OTHER)
                publish.pull(BASE,TOKEN,discard_local=True)
                self.assertEqual(work.read_text(), PROVIDER)
                copies = list((root/'backups').glob('*.yaml'))
                self.assertEqual(len(copies), 1)
                self.assertEqual(copies[0].read_text(), OTHER)

    def test_publish_rejects_stale_revision_before_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)/'nodes.yaml'
            work.write_text(OTHER)
            with patch('sys.argv', ['publish.py','--publish','--provider',str(work)]), \
                 patch.object(publish,'load_settings',return_value=('a'*32,'example',BASE,TOKEN)), \
                 patch.object(publish,'download_provider',return_value=OTHER), \
                 patch.object(publish,'load_revision',return_value=publish.revision(BASE,TOKEN,PROVIDER)), \
                 patch.object(publish,'deploy') as deploy:
                with self.assertRaises(ValueError):
                    publish.main()
                deploy.assert_not_called()

    def test_deploy_code_uses_cloud_nodes_even_with_local_edits(self):
        with patch('sys.argv',['publish.py','--deploy-code']), \
             patch.object(publish,'load_settings',return_value=('a'*32,'example',BASE,TOKEN)), \
             patch.object(publish,'download_provider',return_value=PROVIDER), \
             patch.object(publish,'deploy') as deploy, \
             patch.object(publish,'verify'), \
             patch.object(publish,'verify_profile',return_value=('https://example.com','dummy')), \
             patch.object(publish,'save_outputs'), \
             patch.object(publish,'write_private') as write:
            publish.main()
            deploy.assert_called_once_with('a'*32,'example',TOKEN,PROVIDER)
            write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
