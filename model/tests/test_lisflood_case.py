"""Behavior checks for the standalone recorded-case utility (no CUDA required)."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from urban_flow import lisflood_case as lf


class RecordedCaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = self.root / 'case'
        (self.case / 'inputs').mkdir(parents=True)
        (self.case / 'solver').mkdir()
        for name in lf.INPUTS:
            (self.case / 'inputs' / name).write_text('fixture\n')
        (self.case / 'inputs/rain.par').write_text(
            'DEMfile DSM_final.dem\nstartfile normal.start\ndynamicrainfile rain.nc\n'
            'bcifile open.bci\nstagefile monitor.stage\nresroot rain\ndirroot results-open\n'
            'sim_time 3\nacceleration\ncuda\n')
        (self.case / 'solver/acc_conservation.patch').write_text('fixture patch\n')
        self.binary = self.root / 'solver'
        self.binary.write_text('fixture binary\n')
        self.lock()

    def lock(self):
        self.manifest = {
            'schema': lf.SCHEMA, 'case_id': 'test-only', 'simulation_seconds': 3,
            'solver': {'reference_binary_sha256': lf.digest(self.binary)},
            'files': [{'path': p.relative_to(self.case).as_posix(), 'bytes': p.stat().st_size,
                       'sha256': lf.digest(p)} for p in sorted(self.case.rglob('*'))
                      if p.is_file() and p.name != 'reproduction.json']}
        lf.write_json(self.case / 'reproduction.json', self.manifest)

    def test_detects_altered_input(self):
        lf.verify(self.case)
        (self.case / 'inputs/rain.nc').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            lf.verify(self.case)

    def test_rejects_extra_file(self):
        (self.case / 'accidental-output').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'Unlisted'):
            lf.verify(self.case)

    def test_rejects_escape_and_symlink(self):
        for bad in ('../outside', '/outside', 'inputs/../rain.nc'):
            with self.subTest(path=bad), self.assertRaises(ValueError):
                lf.bounded(self.case, bad)
        target = self.case / 'inputs/rain.nc'
        target.unlink()
        target.symlink_to(self.binary)
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            lf.verify(self.case)

    def test_dry_run_does_not_execute_or_write(self):
        target = self.root / 'run'
        before = lf.digest(self.case / 'inputs/rain.par')
        with patch.object(lf.subprocess, 'run') as process:
            result = lf.run(self.case, target, self.binary, dry_run=True)
        process.assert_not_called()
        self.assertFalse(target.exists())
        self.assertTrue(result['is_full_event'])
        self.assertEqual(before, lf.digest(self.case / 'inputs/rain.par'))

    def test_rejects_unknown_binary_and_existing_output(self):
        with self.assertRaisesRegex(ValueError, 'new run directory'):
            lf.run(self.case, self.root, self.binary)
        self.binary.write_text('unverified replacement')
        with self.assertRaisesRegex(ValueError, 'Binary differs'):
            lf.run(self.case, self.root / 'run', self.binary)

    def test_failed_solver_is_recorded_and_inputs_preserved(self):
        before = lf.digest(self.case / 'inputs/rain.par')
        with patch.object(lf.subprocess, 'run') as process:
            process.return_value.returncode = 7
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                lf.run(self.case, self.root / 'run', self.binary, seconds=1)
        record = json.loads((self.root / 'run/run-record.json').read_text())
        self.assertEqual(record['status'], 'failed')
        self.assertFalse(record['is_full_event'])
        self.assertEqual(before, lf.digest(self.case / 'inputs/rain.par'))

    def prepare_balance(self, depth):
        try:
            from netCDF4 import Dataset
            import rasterio  # noqa: F401
        except ImportError:
            self.skipTest('Optional LISFLOOD audit dependencies are unavailable')
        def grid(path, value):
            path.write_text('ncols 2\nnrows 2\nxllcorner 0\nyllcorner 0\ncellsize 1\n'
                            f'NODATA_value -9999\n{value} {value}\n{value} {value}\n')
        grid(self.case / 'inputs/normal.start', 1)
        ncpath = self.case / 'inputs/rain.nc'
        ncpath.unlink()
        with Dataset(ncpath, 'w') as ds:
            for name, size in [('time', 2), ('y', 1), ('x', 1)]:
                ds.createDimension(name, size)
            ds.createVariable('time', 'f8', ('time',))[:] = [0, 1]
            ds.createVariable('rainfall_depth', 'f8', ('time', 'y', 'x'))[:] = 3600
        self.lock()
        out = self.root / 'run'
        with patch.object(lf.subprocess, 'run') as process:
            process.return_value.returncode = 0
            lf.run(self.case, out, self.binary)
        log = ('ACC shared-face donor limiter and boundary volume budget enabled; double precision\n'
               't=0 dt=1\nWriting snapshot at t=1\nt=1 dt=1\nt=2 dt=1\nWriting snapshot at t=3\n')
        (out / 'rain.log').write_text(log)
        rec = json.loads((out / 'run-record.json').read_text())
        rec['log_sha256'] = lf.digest(out / 'rain.log')
        lf.write_json(out / 'run-record.json', rec)
        (out / 'results').mkdir()
        (out / 'results/rain.boundary_budget.csv').write_text('time,in,out\n1,0,0\n3,0,0.002\n')
        grid(out / 'results/rain-0000.wd', 1)
        grid(out / 'results/rain-0001.wd', depth)
        return out

    def test_independent_rain_and_boundary_balance(self):
        # Four cells: 4 m3 initially + two 1 mm increments - 0.002 m3 outflow.
        out = self.prepare_balance(1.0015)
        report = lf.audit(self.case, out)
        self.assertTrue(report['passed'])
        self.assertAlmostEqual(report['snapshots'][-1]['rain_m3'], 0.008)
        self.assertAlmostEqual(report['snapshots'][-1]['volume_m3'], 4.006)

    def test_rejects_nonconservative_successful_run(self):
        out = self.prepare_balance(2)
        with self.assertRaisesRegex(ValueError, 'water balance failed'):
            lf.audit(self.case, out)
        self.assertFalse(json.loads((out / 'verification.json').read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
