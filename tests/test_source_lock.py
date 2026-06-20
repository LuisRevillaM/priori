from __future__ import annotations

import unittest

from tqe.idsse.source_lock import select_match_files


class SourceLockTests(unittest.TestCase):
    def test_select_match_files_requires_metadata_events_and_tracking(self) -> None:
        article = {
            "files": [
                {
                    "id": 1,
                    "name": "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOH.xml",
                    "size": 10,
                    "download_url": "https://example.test/metadata",
                    "computed_md5": "metadata-md5",
                },
                {
                    "id": 2,
                    "name": "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOH.xml",
                    "size": 20,
                    "download_url": "https://example.test/events",
                    "computed_md5": "events-md5",
                },
                {
                    "id": 3,
                    "name": (
                        "DFL_04_03_positions_raw_observed_DFL-COM-000002_"
                        "DFL-MAT-J03WOH.xml"
                    ),
                    "size": 30,
                    "download_url": "https://example.test/tracking",
                    "computed_md5": "tracking-md5",
                },
            ]
        }

        selected = select_match_files(article, "J03WOH")

        self.assertEqual(["metadata", "events", "tracking"], [file.kind for file in selected])
        self.assertEqual(["J03WOH", "J03WOH", "J03WOH"], [file.match_id for file in selected])


if __name__ == "__main__":
    unittest.main()
