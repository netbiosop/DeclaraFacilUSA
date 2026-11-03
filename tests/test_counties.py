"""Descarga de condados del Censo (sin red)."""
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from taxapp import counties  # noqa: E402


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class CensusDownloadTests(unittest.TestCase):
    def test_short_list_reports_reason(self):
        short = b"STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME|CLASSFP|FUNCSTAT\nAL|01|001|00161526|Autauga County|H1|A\n"
        with mock.patch.object(counties.urllib.request, "urlopen", side_effect=lambda *a, **k: Resp(short)), \
                mock.patch.object(counties, "save_lists") as save:
            with self.assertRaises(RuntimeError) as cm:
                counties.download_from_census()
        save.assert_not_called()
        self.assertNotIn("None", str(cm.exception))
        self.assertIn("1", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
