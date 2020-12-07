from pathlib import Path
from test.util import TestCase
from unittest.mock import Mock

from OpenCast.config import settings
from OpenCast.domain.service.subtitle import SubtitleService


class SubtitleServiceTest(TestCase):
    def setUp(self):
        self.lang = settings["subtitle.language"]

        self.video = Mock()
        self.video.location = "/tmp/video.mp4"

        self.file_service = Mock()
        self.downloader = Mock()
        self.service = SubtitleService(self.file_service, self.downloader)

    def expect_from_disk(self, disk_files):
        self.file_service.list_directory.return_value = [
            Path(file) for file in disk_files
        ]

    def expect_from_source(self, file):
        self.video.from_disk.return_value = False
        self.downloader.download_subtitle.return_value = file

    def test_load_from_disk(self):
        disk_subtitle = "/tmp/video.srt"
        self.expect_from_disk([disk_subtitle])

        subtitle = self.service.fetch_subtitle(self.video, self.lang)
        self.assertEqual(Path(disk_subtitle), subtitle)

    def test_download_from_source(self):
        self.expect_from_disk([])

        source_subtitle = "/tmp/source.vtt"
        self.expect_from_source(source_subtitle)

        subtitle = self.service.fetch_subtitle(self.video, self.lang)
        self.assertEqual(Path(source_subtitle), subtitle)

    def test_fetch_online(self):
        self.expect_from_disk([])
        self.expect_from_source(None)

        subtitle = self.service.fetch_subtitle(self.video, self.lang)
        self.assertEqual(None, subtitle)
