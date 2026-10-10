"""Build and exercise a wheel without importing the source checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

class PackagingTests(unittest.TestCase):
    def test_isolated_wheel_assets_and_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / 'source'
            source.mkdir()
            shutil.copyfile(ROOT / 'pyproject.toml', source / 'pyproject.toml')
            for name in ('langbench', 'tasks', 'configs'):
                shutil.copytree(ROOT / name, source / name,
                                ignore=shutil.ignore_patterns('target', '__pycache__', '*.pyc'))
            built = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                                   '--no-index', '--wheel-dir', str(base / 'wheels'), str(source)],
                                  text=True, capture_output=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            wheel = next((base / 'wheels').glob('*.whl'))
            with zipfile.ZipFile(wheel) as archive:
                paths = archive.namelist()
                self.assertIn('langbench_tasks/crash_store/cases.py', paths)
                self.assertIn('langbench_tasks/protocol_migration/references/rust/src/solution.rs', paths)
                self.assertIn('langbench_config/ruby-rust-pilot.json', paths)
                self.assertFalse(any('/target/' in p or '__pycache__' in p or p.endswith('.pyc') for p in paths))
            target = base / 'installed'
            installed = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-index',
                                        '--target', str(target), str(wheel)], text=True, capture_output=True, timeout=60)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1')
            def cli(*args):
                result = subprocess.run([sys.executable, '-m', 'langbench', *args], cwd=base,
                                        env=env, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertEqual(cli('list')['implemented_languages'], ['ruby', 'rust'])
            calibration = cli('plan', '--seed', '17')
            self.assertEqual(calibration['purpose'], 'calibration')
            self.assertEqual({c['task'] for c in calibration['cells']}, {'ledger_engine'})
            self.assertFalse(calibration['scored_execution_qualified'])
            plan = cli('plan', '--purpose', 'smoke', '--seed', '17')
            self.assertEqual(len(plan['cells']), 48)
            self.assertTrue(all(c['replicate'] in (1, 2) and c['block_id'] for c in plan['cells']))
            self.assertEqual(plan, cli('plan', '--purpose', 'smoke', '--seed', '17'))
            blocks = {}
            for cell in plan['cells']:
                blocks.setdefault(cell['block_id'], []).append(cell)
            self.assertEqual(len(blocks), 4)
            for block in blocks.values():
                self.assertEqual(len(block), 12)
                self.assertEqual(len({c['semantic_seed'] for c in block}), 1)
                self.assertEqual({c['base_seconds'] for c in block}, {2700})
                self.assertEqual({c['continuation_seconds'] for c in block}, {900})
            for task in ('crash_store', 'protocol_migration'):
                for lang in ('ruby', 'rust'):
                    workspace = base / f'{task}-{lang}'
                    cli('prepare', task, lang, str(workspace), '--tests', 'T1')
                    self.assertTrue((workspace / 'public_cases.json').is_file())
                    self.assertTrue((workspace / 'TASK.md').is_file())
                    self.assertTrue(os.access(workspace / 'run.sh', os.X_OK))
                    self.assertFalse((workspace / 'cases.py').exists())
                    self.assertFalse((workspace / 'references').exists())
