from pathlib import Path
from unittest.mock import patch

from OpenCast.app.command import video as Cmd
from OpenCast.app.service.error import OperationError
from OpenCast.config import settings
from OpenCast.domain.event import playlist as PlaylistEvt
from OpenCast.domain.event import video as VideoEvt
from OpenCast.domain.model.video import Stream
from OpenCast.domain.service.identity import IdentityService
from OpenCast.infra.event.downloader import DownloadError, DownloadSuccess

from .util import ServiceTestCase


class VideoServiceTest(ServiceTestCase):
    def setUp(self):
        super(VideoServiceTest, self).setUp()

        self.video_repo = self.data_facade.video_repo
        self.player_repo = self.data_facade.player_repo
        self.player_id = IdentityService.id_player()

    def test_create_video(self):
        source = "source"
        video_id = IdentityService.id_video(source)
        collection_id = IdentityService.random()

        metadata = {
            "title": "title",
            "source_protocol": "http",
            "collection_name": "album",
            "thumbnail": "thumbnail_url",
        }
        self.downloader.download_metadata.return_value = metadata

        self.evt_expecter.expect(
            VideoEvt.VideoCreated,
            video_id,
            source,
            collection_id,
            **metadata,
        ).from_(Cmd.CreateVideo, video_id, source, collection_id)

    @patch("OpenCast.app.service.video.Path")
    def test_create_disk_video(self, path_cls_mock):
        path_inst = path_cls_mock.return_value
        source = "source"
        video_id = IdentityService.id_video(source)
        collection_id = None

        path_inst.is_file.return_value = True
        metadata = {
            "collection_name": None,
            "title": "test_title",
            "source_protocol": None,
            "thumbnail": None,
        }
        path_inst.stem = metadata["title"]

        self.evt_expecter.expect(
            VideoEvt.VideoCreated,
            video_id,
            source,
            collection_id,
            **metadata,
        ).from_(Cmd.CreateVideo, video_id, source, collection_id)

    def test_create_video_missing_metadata(self):
        source = "source"
        video_id = IdentityService.id_video(source)

        metadata = None
        self.downloader.download_metadata.return_value = metadata

        self.evt_expecter.expect(OperationError, "Unavailable metadata").from_(
            Cmd.CreateVideo, video_id, source, collection_id=None
        )

    def test_delete_video(self):
        self.data_producer.player().video("source").video("source2").populate(
            self.data_facade
        )

        player = self.player_repo.get_player()
        video_id = IdentityService.id_video("source")
        self.evt_expecter.expect(VideoEvt.VideoDeleted, video_id).expect(
            PlaylistEvt.PlaylistContentUpdated,
            player.queue,
            [IdentityService.id_video("source2")],
        ).from_(Cmd.DeleteVideo, video_id)

        other_video_id = IdentityService.id_video("source2")
        self.assertListEqual(
            [self.video_repo.get(other_video_id)], self.video_repo.list()
        )

    @patch("OpenCast.domain.model.video.Path")
    def test_retrieve_video_from_disk_success(self, path_cls_mock):
        video_id = IdentityService.id_video("/tmp/video.mp4")
        self.data_producer.video("/tmp/video.mp4").populate(self.data_facade)

        path_cls_mock.return_value.is_file.return_value = True
        output_dir = settings["downloader.output_directory"]
        self.evt_expecter.expect(
            VideoEvt.VideoRetrieved, video_id, "/tmp/video.mp4"
        ).from_(Cmd.RetrieveVideo, video_id, output_dir)

    def test_retrieve_video_from_stream_success(self):
        video_id = IdentityService.id_video("http://url")
        self.data_producer.video("http://url", source_protocol="m3u8").populate(
            self.data_facade
        )

        metadata = {
            "url": "http://stream-url.m3u8",
        }
        self.downloader.download_metadata.return_value = metadata

        output_dir = settings["downloader.output_directory"]
        self.evt_expecter.expect(
            VideoEvt.VideoRetrieved, video_id, metadata["url"]
        ).from_(Cmd.RetrieveVideo, video_id, output_dir)

    def test_retrieve_video_from_stream_error(self):
        video_id = IdentityService.id_video("http://url")
        self.data_producer.video("http://url", source_protocol="m3u8").populate(
            self.data_facade
        )

        metadata = {}
        self.downloader.download_metadata.return_value = metadata

        output_dir = settings["downloader.output_directory"]
        self.evt_expecter.expect(OperationError, "Unavailable stream URL").from_(
            Cmd.RetrieveVideo, video_id, output_dir
        )

    def test_retrieve_video_download_success(self):
        video_id = IdentityService.id_video("source")
        video_title = "video_title"
        self.data_producer.video("source", title=video_title).populate(self.data_facade)

        def dispatch_downloaded(op_id, *args):
            self.app_facade.evt_dispatcher.dispatch(DownloadSuccess(op_id))

        self.downloader.download_video.side_effect = dispatch_downloaded
        output_dir = settings["downloader.output_directory"]
        location = str(Path(output_dir) / f"{video_title}.mp4")
        self.evt_expecter.expect(VideoEvt.VideoRetrieved, video_id, location).from_(
            Cmd.RetrieveVideo, video_id, output_dir
        )

    def test_retrieve_video_download_error(self):
        video_id = IdentityService.id_video("source")
        video_title = "video_title"
        self.data_producer.video("source", title=video_title).populate(self.data_facade)

        def dispatch_error(op_id, *args):
            self.app_facade.evt_dispatcher.dispatch(
                DownloadError(op_id, "Download error")
            )

        self.downloader.download_video.side_effect = dispatch_error
        output_dir = settings["downloader.output_directory"]
        self.evt_expecter.expect(OperationError, "Download error").from_(
            Cmd.RetrieveVideo, video_id, output_dir
        )

    def test_parse_video(self):
        self.data_producer.video("source", location="/tmp/source.mp4").populate(
            self.data_facade
        )

        streams = [
            (0, "video", None),
            (1, "audio", None),
            (2, "subtitle", "subtitle_lang"),
        ]
        self.video_parser.parse_streams.return_value = streams

        expected = [Stream(*stream) for stream in streams]
        video_id = IdentityService.id_video("source")
        self.evt_expecter.expect(VideoEvt.VideoParsed, video_id, expected).from_(
            Cmd.ParseVideo, video_id
        )

    def test_fetch_video_subtitle(self):
        self.data_producer.video("source", location="/tmp/source.mp4").populate(
            self.data_facade
        )

        # Load from disk
        self.file_service.list_directory.return_value = []

        # Download from source
        source_subtitle = "/tmp/source.vtt"
        self.downloader.download_subtitle.return_value = source_subtitle

        video_id = IdentityService.id_video("source")
        subtitle_language = settings["subtitle.language"]
        self.evt_expecter.expect(
            VideoEvt.VideoSubtitleFetched, video_id, Path(source_subtitle)
        ).from_(Cmd.FetchVideoSubtitle, video_id, subtitle_language)
