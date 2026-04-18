"""Base skeleton for a camera accessory.

This wraps ``pyhap.camera.Camera`` with the same template-method pattern used
by the other Bifrost base accessories.  Subclasses implement snapshot and
stream lifecycle hooks; all HAP/RTP negotiation is handled by pyhap.
"""

from pyhap.camera import (  # noqa: F401
    AUDIO_CODEC_PARAM_SAMPLE_RATE_TYPES,
    VIDEO_CODEC_PARAM_LEVEL_TYPES,
    VIDEO_CODEC_PARAM_PROFILE_ID_TYPES,
)
from pyhap.camera import (
    Camera as HAPCamera,
)

DEFAULT_OPTIONS: dict = {
    "video": {
        "codec": {
            "profiles": [
                VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["BASELINE"],
                VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["MAIN"],
                VIDEO_CODEC_PARAM_PROFILE_ID_TYPES["HIGH"],
            ],
            "levels": [
                VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE3_1"],
                VIDEO_CODEC_PARAM_LEVEL_TYPES["TYPE4_0"],
            ],
        },
        "resolutions": [
            [1920, 1080, 30],
            [1280, 720, 30],
            [640, 480, 30],
            [640, 360, 30],
            [480, 360, 30],
            [320, 240, 15],
        ],
    },
    "audio": {
        "codecs": [
            {"type": "OPUS", "samplerate": 24},
            {"type": "AAC-eld", "samplerate": 16},
        ],
    },
}


class Camera(HAPCamera):
    """A camera accessory with sensible defaults.

    Subclass this and implement:

    * ``_get_snapshot`` -- return JPEG bytes for a still image.
    * ``_start_stream`` / ``_stop_stream`` -- start and stop the video/audio
      stream for a given session (optional; the default ffmpeg behaviour from
      pyhap is used if not overridden).

    The ``options`` dict passed to ``__init__`` follows the pyhap camera spec.
    See ``DEFAULT_OPTIONS`` for a reasonable starting point.
    """

    def __init__(
        self,
        options: dict | None,
        driver,
        name: str,
    ) -> None:
        opts = {**DEFAULT_OPTIONS, **(options or {})}

        if "address" not in opts:
            raise ValueError(
                "Camera options must include 'address' -- the IP the camera will stream from."
            )

        super().__init__(opts, driver, name)

    # -- snapshots -----------------------------------------------------------------

    def get_snapshot(self, image_size: dict) -> bytes:
        """Return a JPEG snapshot from the camera.

        The default implementation delegates to ``_get_snapshot``.  Override
        ``_get_snapshot`` in your subclass rather than this method.

        Args:
            image_size: Dict with ``image-width`` and ``image-height`` keys.

        Returns:
            Raw JPEG bytes.
        """
        return self._get_snapshot(image_size)

    def _get_snapshot(self, image_size: dict) -> bytes:
        """Return JPEG bytes for a snapshot at the requested size.

        Args:
            image_size: Dict with ``image-width`` and ``image-height`` keys.
        """
        raise NotImplementedError

    # -- stream lifecycle ----------------------------------------------------------

    async def start_stream(self, session_info: dict, stream_config: dict) -> bool:
        """Start a stream for the given session.

        Override ``_start_stream`` to provide a custom implementation.
        Falls back to pyhap's default ffmpeg-based streaming if not overridden.

        Returns:
            ``True`` if the stream started successfully.
        """
        return await self._start_stream_impl(session_info, stream_config)

    async def _start_stream_impl(self, session_info: dict, stream_config: dict) -> bool:
        """Default delegates to pyhap's ffmpeg-based start_stream."""
        return await super().start_stream(session_info, stream_config)

    async def stop_stream(self, session_info: dict) -> None:
        """Stop the stream for the given session.

        Override ``_stop_stream_impl`` to provide custom teardown logic.
        """
        await self._stop_stream_impl(session_info)

    async def _stop_stream_impl(self, session_info: dict) -> None:
        """Default delegates to pyhap's ffmpeg-based stop_stream."""
        await super().stop_stream(session_info)
