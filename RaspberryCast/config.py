import configparser


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class VideoPlayer(object):
    hide_background = True


class Downloader(object):
    dl_directory = "/tmp"


class Config(object):
    __metaclass__ = Singleton

    def __init__(self):
        self._parser = configparser.RawConfigParser()
        self._init_cache()

    def __getitem__(self, key):
        return self._entries.get(key)

    def load(self, path):
        with open(path, 'r') as file:
            self._parser.read_file(file)
            self._load_cache()

    def _init_cache(self):
        self._entries = {
            'VideoPlayer': VideoPlayer(),
            'Downloader': Downloader()
        }

    def _load_cache(self):
        for key, category in self._entries.items():
            if not self._parser.has_section(key):
                continue
            parser = self._parser[key]

            for entry_name in dir(category):
                if (
                    entry_name.startswith('__') or
                    not self._parser.has_option(key, entry_name)
                ):
                    continue
                self._parse_entry(parser, category, entry_name)

    def _parse_entry(self, parser, category, entry_name):
        entry = getattr(category, entry_name)
        entry_value = entry

        if type(entry) is int:
            entry_value = parser.getint(entry_name, fallback=entry)
        elif type(entry) is float:
            entry_value = parser.getfloat(entry_name, fallback=entry)
        elif type(entry) is bool:
            entry_value = parser.getboolean(entry_name, fallback=entry)
        else:
            entry_value = parser.get(entry_name, fallback=entry)

        setattr(category, entry_name, entry_value)


config = Config()