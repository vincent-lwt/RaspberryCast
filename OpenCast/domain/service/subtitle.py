""" Subtitle operations """

from pathlib import Path

import structlog


class SubtitleService:
    def __init__(self, file_service, downloader):
        self._logger = structlog.get_logger(__name__)
        self._file_service = file_service
        self._downloader = downloader

    def fetch_subtitle(self, video, language: str, search_online=True) -> Path:
        subtitle = self._load_from_disk(video.path, language)
        if subtitle is not None:
            return subtitle

        if not video.from_disk():
            subtitle = self._download_from_source(video.source, video.path, language)
            if subtitle is not None:
                return subtitle

        if search_online:
            pass  # TODO

        return None

    def _load_from_disk(self, video_path: Path, language: str) -> Path:
        parent_path = video_path.parents[0]
        subtitle = str(video_path.with_suffix(".srt"))
        # Find the matching subtitle from a .srt file
        srtFiles = self._file_service.list_directory(parent_path, "*.srt")
        if Path(subtitle) in srtFiles:
            self._logger.debug("Found srt file", subtitle=subtitle)
            return subtitle
        return None

    def _download_from_source(
        self, video_source: str, video_path: Path, language: str
    ) -> Path:
        dest = str(video_path.with_suffix(""))
        subtitle = self._downloader.download_subtitle(
            video_source, dest, language, ["vtt"]
        )
        return None if subtitle is None else Path(subtitle)
