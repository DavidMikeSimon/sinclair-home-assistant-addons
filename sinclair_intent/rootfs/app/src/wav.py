import audioop
import io
import logging
import typing
import wave
from pathlib import Path

_LOGGER = logging.getLogger("sinclair_intent")

def read_wav(sound_path: typing.Union[str, Path]) -> bytes:
    sound_path = str(sound_path)
    with wave.open(sound_path, "rb"):
        return open(sound_path, "rb").read()


def change_volume(wav_bytes: bytes, volume: float) -> bytes:
    """Scale WAV amplitude by factor (0-1)"""
    if volume == 1.0:
        return wav_bytes

    try:
        with io.BytesIO(wav_bytes) as wav_in_io:
            # Re-write WAV with adjusted volume
            with io.BytesIO() as wav_out_io:
                wav_out_file: wave.Wave_write = wave.open(wav_out_io, "wb")
                wav_in_file: wave.Wave_read = wave.open(wav_in_io, "rb")

                with wav_out_file:
                    with wav_in_file:
                        sample_width = wav_in_file.getsampwidth()

                        # Copy WAV details
                        wav_out_file.setframerate(wav_in_file.getframerate())
                        wav_out_file.setsampwidth(sample_width)
                        wav_out_file.setnchannels(wav_in_file.getnchannels())

                        # Adjust amplitude
                        wav_out_file.writeframes(
                            audioop.mul(
                                wav_in_file.readframes(wav_in_file.getnframes()),
                                sample_width,
                                volume,
                            )
                        )

                wav_bytes = wav_out_io.getvalue()

    except Exception:
        _LOGGER.exception("change_volume")

    return wav_bytes


def get_wav_duration(wav_bytes: bytes) -> float:
    """Return the real-time duration of a WAV file"""
    with io.BytesIO(wav_bytes) as wav_buffer:
        wav_file: wave.Wave_read = wave.open(wav_buffer, "rb")
        with wav_file:
            width = wav_file.getsampwidth()
            rate = wav_file.getframerate()

            # getnframes is not reliable.
            guess_frames = (len(wav_bytes) - 44) / width

            return guess_frames / float(rate)
