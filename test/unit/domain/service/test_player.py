from test.shared.infra.data.producer import DataProducer
from test.util import TestCase

from OpenCast.domain.service.identity import IdentityService
from OpenCast.domain.service.player import QueueingService
from OpenCast.infra.data.manager import DataManager, StorageType
from OpenCast.infra.data.repo.factory import RepoFactory


class QueueingServiceTest(TestCase):
    def setUp(self):
        repo_factory = RepoFactory()
        data_manager = DataManager(repo_factory)
        self.data_facade = data_manager.connect(StorageType.MEMORY)
        self.data_producer = DataProducer.make()
        self.video_repo = self.data_facade.video_repo
        self.playlist_repo = self.data_facade.playlist_repo

        self.service = QueueingService(
            self.data_facade.player_repo,
            self.data_facade.playlist_repo,
            self.data_facade.video_repo,
        )

        self.data_producer.player().populate(self.data_facade)
        self.queue_id = self.data_facade.player_repo.get_player().queue

    def test_queue_back(self):
        self.data_producer.player().video("source1").video("source2").video(
            "source3"
        ).parent_producer().video("source4").populate(self.data_facade)

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        queue.ids = self.service.queue(queue, videos[-1].id, front=False)
        expected = [video.id for video in videos]
        self.assertListEqual(expected, queue.ids)

    def test_queue_front_empty_queue(self):
        self.data_producer.video("source1").video("source2").video("source3").populate(
            self.data_facade
        )

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        for video in videos:
            queue.ids = self.service.queue(queue, video.id, front=True)
        expected = [video.id for video in reversed(videos)]
        self.assertListEqual(expected, queue.ids)

    def test_queue_front_playlist_empty_queue(self):
        collection_id = IdentityService.random()
        self.data_producer.video("source1", collection_id=collection_id).video(
            "source2", collection_id=collection_id
        ).video("source3", collection_id=collection_id).populate(self.data_facade)

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        for video in videos:
            queue.ids = self.service.queue(queue, video.id, front=True)

        expected = [video.id for video in videos]
        self.assertListEqual(expected, queue.ids)

    def test_queue_front_playlist_while_playing(self):
        collection_1_id = IdentityService.random()
        collection_2_id = IdentityService.random()
        self.data_producer.player().video(
            "source1", collection_id=collection_1_id
        ).video("source2", collection_id=collection_1_id).play(
            "source1"
        ).parent_producer().video(
            "source3", collection_id=collection_2_id
        ).video(
            "source4", collection_id=collection_2_id
        ).populate(
            self.data_facade
        )

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        playlist2 = [
            video for video in videos if video.collection_id == collection_2_id
        ]
        for video in playlist2:
            queue.ids = self.service.queue(queue, video.id, front=True)

        expected = [videos[0].id, videos[2].id, videos[3].id, videos[1].id]
        self.assertListEqual(expected, queue.ids)

    def test_queue_front_merge_playlist(self):
        collection_id = IdentityService.random()
        self.data_producer.video("source1", collection_id=collection_id).video(
            "source2"
        ).video("source3", collection_id=collection_id).populate(self.data_facade)

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        queue.ids = self.service.queue(queue, videos[0].id, front=True)
        queue.ids = self.service.queue(queue, videos[1].id, front=False)
        queue.ids = self.service.queue(queue, videos[2].id, front=True)
        expected = [videos[0].id, videos[2].id, videos[1].id]
        self.assertListEqual(expected, queue.ids)

    def test_queue_no_merge_past_index(self):
        collection_id = IdentityService.random()
        self.data_producer.player().video("source1", collection_id=collection_id).video(
            "source2"
        ).play("source2").parent_producer().video(
            "source3", collection_id=collection_id
        ).populate(
            self.data_facade
        )

        queue = self.playlist_repo.get(self.queue_id)
        videos = self.video_repo.list()
        queue.ids = self.service.queue(queue, videos[2].id, front=True)
        expected = [videos[0].id, videos[1].id, videos[2].id]
        self.assertListEqual(expected, queue.ids)

    def test_next(self):
        self.data_producer.player().video("source1").video("source2").populate(
            self.data_facade
        )

        videos = self.video_repo.list()
        self.assertEqual(
            videos[1].id,
            self.service.next_video(self.queue_id, videos[0].id, loop_last=False),
        )
        self.assertEqual(
            None, self.service.next_video(self.queue_id, videos[1].id, loop_last=False)
        )

    def test_next_no_loop(self):
        self.data_producer.player().video("source1").populate(self.data_facade)

        video_id = IdentityService.id_video("source1")
        self.assertEqual(
            None, self.service.next_video(self.queue_id, video_id, loop_last=False)
        )

    def test_next_loop_last_track(self):
        self.data_producer.player().video("source1").video("source2").populate(
            self.data_facade
        )

        videos = self.video_repo.list()
        self.assertEqual(
            videos[1].id,
            self.service.next_video(self.queue_id, videos[0].id, loop_last="track"),
        )
        self.assertEqual(
            videos[1].id,
            self.service.next_video(self.queue_id, videos[1].id, loop_last="track"),
        )

    def test_next_loop_last_album(self):
        collection_id = IdentityService.random()
        self.data_producer.player().video("source1").video(
            "source2", collection_id=collection_id
        ).video("source3", collection_id=collection_id).populate(self.data_facade)

        videos = self.video_repo.list()
        expected = videos[1].id
        self.assertEqual(
            expected,
            self.service.next_video(self.queue_id, videos[2].id, loop_last="album"),
        )

    def test_next_loop_last_album_no_album(self):
        collection_id = IdentityService.random()
        self.data_producer.player().video("source1", collection_id=collection_id).video(
            "source2"
        ).video("source3").populate(self.data_facade)

        videos = self.video_repo.list()
        expected = videos[2].id
        self.assertEqual(
            expected,
            self.service.next_video(self.queue_id, videos[2].id, loop_last="album"),
        )

    def test_next_invalid_video(self):
        self.data_producer.player().video("source1").video("source2").populate(
            self.data_facade
        )

        video_id = IdentityService.id_video("source3")
        self.assertEqual(
            None, self.service.next_video(self.queue_id, video_id, loop_last="track")
        )
