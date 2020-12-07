from pathlib import Path

import OpenCast.app.command.video as Cmd
import OpenCast.domain.event.video as Evt
from OpenCast.app.service.error import OperationError
from OpenCast.app.workflow.video import Video, VideoWorkflow
from OpenCast.config import settings
from OpenCast.domain.model.video import Video as VideoModel
from OpenCast.domain.service.identity import IdentityService

from .util import WorkflowTestCase


class VideoWorkflowTest(WorkflowTestCase):
    def setUp(self):
        super(VideoWorkflowTest, self).setUp()
        self.video_repo = self.data_facade.video_repo
        self.video = Video(IdentityService.id_video("source"), "source", None)
        self.workflow = self.make_workflow(VideoWorkflow, self.video)

    def tearDown(self):
        # Reset modified config entries to their default value
        settings["subtitle.enabled"] = True

    def test_initial(self):
        self.assertTrue(self.workflow.is_INITIAL())

    def test_init_to_completed(self):
        self.video_repo.exists.return_value = True
        self.workflow.start()
        self.video_repo.exists.assert_called_once_with(self.video.id)
        self.assertTrue(self.workflow.is_COMPLETED())

    def test_init_to_creating(self):
        self.video_repo.exists.return_value = False
        self.workflow.start()
        self.video_repo.exists.assert_called_once_with(self.video.id)
        self.assertTrue(self.workflow.is_CREATING())

    def test_creating_to_aborted(self):
        self.workflow.to_CREATING()
        cmd = self.expect_dispatch(Cmd.CreateVideo, *self.video.to_tuple())
        self.raise_error(cmd)
        self.assertTrue(self.workflow.is_ABORTED())

    def test_creating_to_retrieving(self):
        self.workflow.to_CREATING()
        cmd = self.expect_dispatch(Cmd.CreateVideo, *self.video.to_tuple())
        self.raise_event(
            Evt.VideoCreated,
            cmd.id,
            *self.video.to_tuple(),
            "album",
            "title",
            "http",
            "thumbnail",
        )
        self.assertTrue(self.workflow.is_RETRIEVING())

    def test_retrieving_to_deleting(self):
        event = Evt.VideoCreated(
            None, *self.video.to_tuple(), "album", "title", "http", "thumbnail"
        )
        self.workflow.to_RETRIEVING(event)
        cmd = self.expect_dispatch(
            Cmd.RetrieveVideo, self.video.id, settings["downloader.output_directory"]
        )
        self.raise_error(cmd)
        self.assertTrue(self.workflow.is_DELETING())

    def test_retrieving_to_completed(self):
        event = Evt.VideoCreated(
            None, *self.video.to_tuple(), "album", "title", "m3u8", "thumbnail"
        )
        self.workflow.to_RETRIEVING(event)

        cmd = self.expect_dispatch(
            Cmd.RetrieveVideo, self.video.id, settings["downloader.output_directory"]
        )

        def return_video(id):
            self.assertEqual(self.video.id, id)
            return VideoModel(self.video.id, self.video.source, source_protocol="m3u8")

        self.video_repo.get.side_effect = return_video

        self.raise_event(
            Evt.VideoRetrieved,
            cmd.id,
            self.video.id,
            "https://url.m3u8",
        )
        self.assertTrue(self.workflow.is_COMPLETED())

    def test_retrieving_to_parsing(self):
        event = Evt.VideoCreated(
            None, *self.video.to_tuple(), "album", "title", "http", "thumbnail"
        )
        self.workflow.to_RETRIEVING(event)
        cmd = self.expect_dispatch(
            Cmd.RetrieveVideo, self.video.id, settings["downloader.output_directory"]
        )
        self.raise_event(
            Evt.VideoRetrieved,
            cmd.id,
            self.video.id,
            f"{settings['downloader.output_directory']}/video.mp4",
        )
        self.assertTrue(self.workflow.is_PARSING())

    def test_parsing_to_deleting(self):
        event = Evt.VideoRetrieved(
            None, self.video.id, f"{settings['downloader.output_directory']}/video.mp4"
        )
        self.workflow.to_PARSING(event)
        cmd = self.expect_dispatch(Cmd.ParseVideo, self.video.id)
        self.raise_error(cmd)
        self.assertTrue(self.workflow.is_DELETING())

    def test_parsing_to_completed(self):
        settings["subtitle.enabled"] = False
        event = Evt.VideoRetrieved(
            None, self.video.id, f"{settings['downloader.output_directory']}/video.mp4"
        )
        self.workflow.to_PARSING(event)
        cmd = self.expect_dispatch(Cmd.ParseVideo, self.video.id)
        self.raise_event(
            Evt.VideoParsed,
            cmd.id,
            self.video.id,
            {},
        )
        self.assertTrue(self.workflow.is_COMPLETED())

    def test_parsing_to_sub_fetching(self):
        event = Evt.VideoRetrieved(
            None, self.video.id, f"{settings['downloader.output_directory']}/video.mp4"
        )
        self.workflow.to_PARSING(event)
        cmd = self.expect_dispatch(Cmd.ParseVideo, self.video.id)
        self.raise_event(
            Evt.VideoParsed,
            cmd.id,
            self.video.id,
            {},
        )
        self.assertTrue(self.workflow.is_SUB_RETRIEVING())

    def test_sub_fetching_to_deleting(self):
        event = Evt.VideoParsed(None, self.video.id, {})
        self.workflow.to_SUB_RETRIEVING(event)
        cmd = self.expect_dispatch(
            Cmd.FetchVideoSubtitle, self.video.id, settings["subtitle.language"]
        )
        self.raise_error(cmd)
        self.assertTrue(self.workflow.is_DELETING())

    def test_sub_fetching_to_completed(self):
        event = Evt.VideoParsed(None, self.video.id, {})
        self.workflow.to_SUB_RETRIEVING(event)
        cmd = self.expect_dispatch(
            Cmd.FetchVideoSubtitle, self.video.id, settings["subtitle.language"]
        )
        self.raise_event(
            Evt.VideoSubtitleFetched,
            cmd.id,
            self.video.id,
            Path(settings["downloader.output_directory"]) / "video.srt",
        )
        self.assertTrue(self.workflow.is_COMPLETED())

    def test_deleting_to_aborted(self):
        cmd = Cmd.CreateVideo(None, self.video.id, "source", collection_id=None)
        error = OperationError(cmd, "")
        self.workflow.to_DELETING(error)
        cmd = self.expect_dispatch(Cmd.DeleteVideo, self.video.id)
        self.raise_event(
            Evt.VideoDeleted,
            cmd.id,
            self.video.id,
        )
        self.assertTrue(self.workflow.is_ABORTED())
