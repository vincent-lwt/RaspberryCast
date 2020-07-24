import uuid

from OpenCast.app.command import player as Cmd
from OpenCast.app.service.error import OperationError
from OpenCast.app.workflow.player import (
    QueuePlaylistWorkflow,
    QueueVideoWorkflow,
    StreamPlaylistWorkflow,
    StreamVideoWorkflow,
    Video,
)
from OpenCast.domain.event import player as Evt
from OpenCast.domain.model.player import Player
from OpenCast.domain.service.identity import IdentityService
from OpenCast.util.conversion import str_to_bool

from .monitor import MonitorController


class PlayerMonitController(MonitorController):
    def __init__(self, app_facade, infra_facade, data_facade, service_factory):
        super().__init__(app_facade, infra_facade, "/player")

        media_factory = infra_facade.media_factory
        self._io_factory = infra_facade.io_factory
        self._source_service = service_factory.make_source_service(
            media_factory.make_downloader(app_facade.evt_dispatcher),
            media_factory.make_video_parser(),
        )
        self._player_repo = data_facade.player_repo
        self._video_repo = data_facade.video_repo

        self._route("GET", "/", self._get)
        self._route("POST", "/stream", self._stream)
        self._route("POST", "/queue", self._queue)
        self._route("POST", "/video", self._pick_video)
        self._route("POST", "/stop", self._stop)
        self._route("POST", "/pause", self._pause)
        self._route("POST", "/seek", self._seek)
        self._route("POST", "/volume", self._volume)
        self._route("POST", "/subtitle/toggle", self._subtitle_toggle)
        self._route("POST", "/subtitle/seek", self._subtitle_seek)

    async def _get(self, _):
        player = self._player_repo.get_player()
        return self._ok(player)

    async def _stream(self, req):
        source = req.query["url"]
        if self._source_service.is_playlist(source):
            sources = self._source_service.unfold(source)
            playlist_id = IdentityService.id_playlist(source)
            videos = [
                Video(IdentityService.id_video(source), source, playlist_id)
                for source in sources
            ]

            self._start_workflow(
                StreamPlaylistWorkflow, playlist_id, self._video_repo, videos
            )
            return

        video_id = IdentityService.id_video(source)
        video = Video(video_id, source, None)
        self._start_workflow(StreamVideoWorkflow, video_id, self._video_repo, video)

        return self._ok()

    async def _queue(self, req):
        source = req.query["url"]
        if self._source_service.is_playlist(source):
            sources = self._source_service.unfold(source)
            playlist_id = IdentityService.id_playlist(source)
            videos = [
                Video(IdentityService.id_video(source), source, playlist_id)
                for source in sources
            ]

            self._start_workflow(
                QueuePlaylistWorkflow, playlist_id, self._video_repo, videos
            )
            return

        video_id = IdentityService.id_video(source)
        video = Video(video_id, source, None)
        self._start_workflow(QueueVideoWorkflow, video_id, self._video_repo, video)

        return self._ok()

    async def _pick_video(self, req):
        video_id = uuid.UUID(req.query["id"])
        handlers, channel = self._make_default_handlers(Evt.VideoPicked)
        self._observe_dispatch(handlers, Cmd.PickVideo, video_id)

        return await channel.receive()

    async def _stop(self, _):
        handlers, channel = self._make_default_handlers(Evt.PlayerStopped)
        self._observe_dispatch(handlers, Cmd.StopPlayer)

        return await channel.receive()

    async def _pause(self, _):
        handlers, channel = self._make_default_handlers(Evt.PlayerStateToggled)
        self._observe_dispatch(handlers, Cmd.TogglePlayerState)

        return await channel.receive()

    async def _seek(self, req):
        forward = str_to_bool(req.query["forward"])
        long = str_to_bool(req.query["long"])
        side = 1 if forward is True else -1
        step = Player.LONG_TIME_STEP if long is True else Player.SHORT_TIME_STEP
        handlers, channel = self._make_default_handlers(Evt.VideoSeeked)
        self._observe_dispatch(handlers, Cmd.SeekVideo, side * step)

        return await channel.receive()

    async def _volume(self, req):
        volume = int(req.query["value"])
        handlers, channel = self._make_default_handlers(Evt.VolumeUpdated)
        self._observe_dispatch(handlers, Cmd.ChangeVolume, volume)

        return await channel.receive()

    async def _subtitle_toggle(self, _):
        handlers, channel = self._make_default_handlers(Evt.SubtitleStateUpdated)
        self._observe_dispatch(handlers, Cmd.ToggleSubtitle)

        return await channel.receive()

    async def _subtitle_seek(self, req):
        forward = str_to_bool(req.query["forward"])
        step = Player.SUBTITLE_DELAY_STEP if forward else -Player.SUBTITLE_DELAY_STEP
        handlers, channel = self._make_default_handlers(Evt.SubtitleDelayUpdated)
        self._observe_dispatch(handlers, Cmd.IncreaseSubtitleDelay, step)

        return await channel.receive()

    def _make_default_handlers(self, evt_cls):
        channel = self._io_factory.make_janus_channel()

        def on_success(evt):
            player = self._player_repo.get_player()
            channel.send(self._ok(player))

        def on_error(error):
            channel.send(self._bad_request())

        evtcls_handler = {evt_cls: on_success, OperationError: on_error}
        return evtcls_handler, channel

    def _observe_dispatch(self, evtcls_handler, cmd_cls, *args, **kwargs):
        player_id = IdentityService.id_player()
        super()._observe_dispatch(evtcls_handler, cmd_cls, player_id, *args, **kwargs)
