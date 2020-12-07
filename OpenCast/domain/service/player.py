""" Player external operations """

from typing import List, Union

import structlog

from OpenCast.config import settings
from OpenCast.domain.model import Id
from OpenCast.domain.model.player import State as PlayerState
from OpenCast.domain.model.playlist import Playlist


class QueueingService:
    def __init__(self, player_repo, playlist_repo, video_repo):
        self._logger = structlog.get_logger(__name__)
        self._player_repo = player_repo
        self._playlist_repo = playlist_repo
        self._video_repo = video_repo

    def queue(self, playlist: Playlist, video_id: Id, front: bool) -> List[Id]:
        if not front:
            playlist.ids.append(video_id)
            return playlist.ids

        player = self._player_repo.get_player()
        player_video_idx = (
            0
            if player.video_id not in playlist.ids
            else playlist.ids.index(player.video_id)
        )
        # Position the video after the last one of the same collection
        video = self._video_repo.get(video_id)
        videos = self._video_repo.list(playlist.ids[player_video_idx:])
        insert_idx = player_video_idx
        collection_match = False
        if video.collection_id is not None:
            for playlist_video in videos:
                if (
                    not collection_match
                    and video.collection_id == playlist_video.collection_id
                ):
                    collection_match = True
                if (
                    collection_match
                    and video.collection_id != playlist_video.collection_id
                ):
                    break
                insert_idx += 1
        if not collection_match:
            player_started = player.state is not PlayerState.STOPPED
            insert_idx = player_video_idx + player_started

        playlist.ids.insert(insert_idx, video_id)
        return playlist.ids

    def next_video(
        self, playlist_id: Id, video_id: Id, loop_last: Union[bool, str]
    ) -> Id:
        playlist = self._playlist_repo.get(playlist_id)
        if video_id not in playlist.ids:
            self._logger.warning("unknown video", video=video_id, playlist=playlist)
            return None

        video_idx = playlist.ids.index(video_id)
        if video_idx + 1 < len(playlist.ids):
            return playlist.ids[video_idx + 1]

        if loop_last == "track":
            return playlist.ids[video_idx]
        if loop_last == "album":
            videos = self._video_repo.list(playlist.ids)
            while (
                video_idx > 0
                and videos[video_idx].collection_id is not None
                and videos[video_idx - 1].collection_id
                == videos[video_idx].collection_id
            ):
                video_idx -= 1
            return playlist.ids[video_idx]
        # else: loop_last is False
        return None
