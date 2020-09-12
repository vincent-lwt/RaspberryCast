""" Video commands """

from .command import Command, ModelId, command


@command
class CreateVideo(Command):
    source: str
    playlist_id: ModelId


@command
class DeleteVideo(Command):
    pass


@command
class IdentifyVideo(Command):
    pass


@command
class RetrieveVideo(Command):
    output_directory: str


@command
class ParseVideo(Command):
    pass


@command
class FetchVideoSubtitle(Command):
    language: str