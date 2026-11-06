from django.apps import AppConfig


class ManagerConfig(AppConfig):
    name = 'manager'

    def ready(self):
        # pylint: disable=import-outside-toplevel,unused-import
        from manager import receivers  # noqa: F401, PLC0415
