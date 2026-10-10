#!/usr/bin/env python3
"""Standalone checks using temporary checkouts and mocked external services."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToolkitTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rom toolkit ')
        self.work = Path(self.temp.name)
        self.root = self.work / 'external rom'
        (self.root / 'build').mkdir(parents=True)
        (self.root / 'build/envsetup.sh').write_text('lunch() { printf "%s\\n" "$1" > lunch.txt; }\nm() { printf "%s\\n" "$1" > target.txt; }\n')
        self.tools = self.work / 'renamed toolkit'
        shutil.copytree(TOOLS, self.tools, ignore=shutil.ignore_patterns('archive', 'diagnostics', '__pycache__', '.git'))
        self.env = {**os.environ, 'ROM_ROOT': str(self.root), 'ROM_LUNCH_TARGET': 'another_aston-release-userdebug', 'ROM_BUILD_TARGET': 'otapackage', 'PYTHONDONTWRITEBYTECODE': '1'}
        self.env.pop('ROM_UPLOAD_DESTINATION', None)

    def tearDown(self):
        self.temp.cleanup()

    def run_script(self, path, *args, **kwargs):
        return subprocess.run(['bash', str(self.tools / path), *map(str, args)], cwd=self.work, env=self.env, capture_output=True, text=True, **kwargs)

    def test_external_worker_and_root_precedence(self):
        self.env['ROM_ROOT'] = str(self.work / 'nonexistent')
        result = self.run_script('scripts/build/worker.sh', 'build', '--root', self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'lunch.txt').read_text().strip(), self.env['ROM_LUNCH_TARGET'])
        self.assertEqual((self.root / 'target.txt').read_text().strip(), 'otapackage')
        self.assertEqual((self.root / 'local-build-out').resolve(), self.root / '.local-build/out')

    def test_conflicting_output_is_preserved(self):
        (self.root / 'local-build-out').write_text('user file')
        result = self.run_script('scripts/build/worker.sh', 'configure')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'local-build-out').read_text(), 'user file')
        self.assertFalse((self.root / 'lunch.txt').exists())

    def test_launcher_passes_configuration(self):
        binpath = self.work / 'bin'
        binpath.mkdir()
        capture = self.work / 'service-args'
        (binpath / 'systemd-run').write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["CAPTURE"],"w").write(json.dumps(sys.argv[1:]))\n')
        (binpath / 'systemctl').write_text('#!/usr/bin/env bash\nexit 0\n')
        for path in binpath.iterdir():
            path.chmod(0o755)
        self.env.update(PATH=str(binpath) + ':' + self.env['PATH'], CAPTURE=str(capture))
        result = self.run_script('scripts/build/build.sh', 'build')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(capture.read_text())
        for key in ('ROM_ROOT', 'ROM_LUNCH_TARGET', 'ROM_BUILD_TARGET'):
            self.assertIn(key + '=' + self.env[key], args)

    def test_wrapper_preserves_failure_and_skips_upload(self):
        # Mock helper calls so no Telegram request or background upload can occur.
        for name in ('telegram-notify.py', 'telegram-upload.py'):
            (self.tools / 'scripts/telegram' / name).write_text('import sys\nsys.exit(0)\n')
        command = 'source "$1"; tgbuild bash -c "exit 23"'
        result = subprocess.run(['bash', '-c', command, 'test', str(self.tools / 'scripts/telegram/telegram-build.sh')], cwd=self.work, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 23)
        self.assertTrue(list((self.root / 'build-logs').glob('*.log')))
        result = subprocess.run(['bash', '-c', 'source "$1"; tgbuild true', 'test', str(self.tools / 'scripts/telegram/telegram-build.sh')], cwd=self.work, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Upload skipped', result.stdout)

    def test_upload_configuration_and_notification_failure(self):
        module = load('upload', self.tools / 'scripts/telegram/telegram-upload.py')
        directory = self.root / 'out'
        directory.mkdir()
        package = directory / 'other-aston.zip'
        for name in (package.name, *module.IMAGES):
            (directory / name).write_bytes(b'artifact')
        log = self.work / 'build.log'
        log.write_text('Output File: out/other-aston.zip\n')
        module.DESTINATION = 'testremote:builds/'
        module.PACKAGE_PREFIX = 'other-'
        with patch.dict(os.environ, {'ROM_UPLOAD_DESTINATION': module.DESTINATION}), patch('sys.argv', ['upload', str(self.root), str(log)]), patch.object(module.shutil, 'which', return_value='/mock/rclone'), patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
            module.main()
            self.assertEqual(run.call_count, 8)
            self.assertEqual(run.call_args_list[0].args[0][3], 'testremote:builds/other-aston.zip')

    def test_private_config_and_sanitized_errors(self):
        module = load('notify', self.tools / 'scripts/telegram/telegram-notify.py')
        module.CONFIG = self.root / '.telegram-build.json'
        with patch.object(module.getpass, 'getpass', return_value='test-placeholder'), patch('builtins.input', return_value=''), patch.object(module, 'request', side_effect=[{'username': 'test'}, [{'message': {'chat': {'id': 42, 'type': 'private'}}}]]), patch.object(module, 'message'):
            module.setup()
        self.assertEqual(module.CONFIG.stat().st_mode & 0o777, 0o600)
        error = module.urllib.error.URLError('sensitive URL')
        with patch.object(module.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, '^Cannot reach Telegram$'):
                module.request('getMe')

    def test_incompatible_feature_has_no_source_changes(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for script, args in [('apply-emoji-selection.sh', ['--check', self.root]), ('apply-aston-camera.sh', ['--check', '--root', self.root]), ('apply-separate-app-sound.sh', ['--check', self.root]), ('setup-lindroid.sh', ['--check', self.root])]:
            result = self.run_script('scripts/features/' + script, *args)
            self.assertNotEqual(result.returncode, 0, script)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_staged_audit_excludes_private_material(self):
        audit = self.tools / 'scripts/maintenance/publication_check.py'
        def git(*args):
            return subprocess.run(['git', '-C', str(self.tools), *args], check=True, capture_output=True)
        git('init', '-q')
        private = self.tools / 'diagnostics/local.txt'
        private.parent.mkdir()
        private.write_text('private placeholder')
        git('add', '.')
        result = subprocess.run(['python3', str(audit), '--staged'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        git('add', '-f', 'diagnostics/local.txt')
        result = subprocess.run(['python3', str(audit), '--staged'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Non-public staged file', result.stdout + result.stderr)

    def test_camera_bundle_and_pinned_patch_integrity(self):
        runner = load('camera_runner', self.tools / 'maintainer/camera-port/installer.py')
        script = self.tools / 'scripts/features/apply-aston-camera.sh'
        self.assertIn((self.tools / 'maintainer/camera-port/installer.py').read_text(), script.read_text())
        bundle = runner.load_bundle(script)
        self.assertEqual(len(bundle['sources']), 188)
        self.assertEqual(len(bundle['assets']), 1333)
        preflight = load('camera_preflight', self.tools / 'maintainer/camera-port/preflight.py')
        self.assertTrue(preflight.validate_patches(self.tools / 'maintainer/camera-port'))

    def test_audit_rejects_private_file_and_decoded_secret(self):
        audit = self.tools / 'scripts/maintenance/publication_check.py'
        result = subprocess.run(['python3', str(audit)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.tools / '.env').write_text('private placeholder')
        result = subprocess.run(['python3', str(audit)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        module = load('audit', audit)
        # Assemble a synthetic token at runtime; no live credential is embedded.
        token = '123456789' + ':' + 'x' * 35
        import base64, gzip
        payload = base64.b64encode(gzip.compress(json.dumps({'sources': [], 'test': token}).encode())).decode()
        units = module.decoded_units(Path('apply-aston-camera.sh'), '# CAMERA_PAYLOAD_BEGIN\n# ' + payload + '\n# CAMERA_PAYLOAD_END\n')
        self.assertTrue(module.PATTERNS['Telegram token'].search(units[-1][1]))


if __name__ == '__main__':
    unittest.main()
