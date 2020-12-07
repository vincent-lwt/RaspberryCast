""" Player behaviour changes resulting from events """

import structlog

from OpenCast.app.command import player as Cmd
from OpenCast.config import settings
from OpenCast.domain.service.identity import IdentityService
from OpenCast.infra.event import player as PlayerEvt

from .controller import Controller


class PlayerController(Controller):
    def __init__(self, app_facade, data_facade, service_factory):
        logger = structlog.get_logger(__name__)
        super().__init__(logger, app_facade)

        self._player_repo = data_facade.player_repo
        self._queueing_service = service_factory.make_queueing_service(
            data_facade.player_repo, data_facade.playlist_repo, data_facade.video_repo
        )

        self._observe(PlayerEvt, self._default_handler_factory)

    # Infra event handler interface implementation

    def _media_end_reached(self, evt):
        player = self._player_repo.get_player()
        video_id = self._queueing_service.next_video(
            player.queue, player.video_id, settings["player.loop_last"]
        )
        if video_id is None:
            self._dispatch(Cmd.StopPlayer)
        else:
            self._dispatch(Cmd.PlayVideo, video_id)

    def _dispatch(self, cmd_cls, *args, **kwargs):
        player_id = IdentityService.id_player()
        return super()._dispatch(cmd_cls, player_id, *args, **kwargs)
