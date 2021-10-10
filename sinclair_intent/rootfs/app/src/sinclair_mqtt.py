import asyncio
import logging
import os
import typing
from urllib.parse import urljoin
from uuid import uuid4

import aiohttp
from rhasspyhermes.asr import (
    AsrToggleOff,
    AsrToggleOn,
    AsrToggleReason,
)
from rhasspyhermes.audioserver import AudioPlayBytes, AudioPlayFinished
from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient
from rhasspyhermes.handle import HandleToggleOff, HandleToggleOn
from rhasspyhermes.nlu import NluIntent
from rhasspyhermes.tts import TtsSay
from rhasspyhermes.wake import (
    HotwordToggleOff,
    HotwordToggleOn,
    HotwordToggleReason,
)

from . import wav

_LOGGER = logging.getLogger("sinclair_intent")

class Intent(typing.NamedTuple):
    intent_name: str
    slots: typing.Dict[str, str]

class SinclairIntentHermesMqtt(HermesClient):
    def __init__(
        self,
        client,
        ha_url: str,
        ha_access_token: str,
        site_ids: typing.Optional[typing.List[str]] = None,
    ):
        super().__init__("sinclair_intent", client, site_ids=site_ids)
        
        self.ha_url = ha_url
        self.ha_access_token = ha_access_token

        self.app_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
        self.handle_enabled = True
        self._http_session = None
        self.message_events: typing.Dict[
            typing.Type[Message], typing.Dict[typing.Optional[str], asyncio.Event]
        ] = typing.DefaultDict(dict)

        self.subscribe(NluIntent, HandleToggleOn, HandleToggleOff, AudioPlayFinished)
    

    @property
    def http_session(self):
        if self._http_session is None:
            self._http_session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.ha_access_token}",
                }
            )

        return self._http_session


    async def handle_intent(
        self, nlu_intent: NluIntent, site_id: str
    ) -> typing.AsyncIterable[TtsSay]:
        try:
            # Disable ASR/hotword at site
            yield HotwordToggleOff(
                site_id=site_id, reason=HotwordToggleReason.PLAY_AUDIO
            )
            yield AsrToggleOff(site_id=site_id, reason=AsrToggleReason.PLAY_AUDIO)

            slots: typing.Dict[str, str] = {}
            if nlu_intent.slots:
                for slot in nlu_intent.slots:
                    slots[slot.slot_name] = slot.value["value"]
            intent = Intent(intent_name=nlu_intent.intent.intent_name, slots=slots)

            _LOGGER.debug("Received intent: %s" % repr(intent))

            if intent.intent_name == "SwitchPower":
                async for msg in self.hass_switch_power(
                    site_id=site_id,
                    entity_id=intent.slots['id'],
                    state=(intent.slots['action'] == "on")
                ):
                    yield msg
            else:
                _LOGGER.warning("Unknown intent: %s" % repr(intent))

            # yield TtsSay(
            #     text="Received intent",
            #     id=str(uuid4()),
            #     site_id=nlu_intent.site_id,
            #     session_id=nlu_intent.session_id,
            # )
        except Exception:
            _LOGGER.exception("handle_intent")
        finally:
            # Re-enable ASR/hotword at site
            yield HotwordToggleOn(
                site_id=site_id, reason=HotwordToggleReason.PLAY_AUDIO
            )
            yield AsrToggleOn(site_id=site_id, reason=AsrToggleReason.PLAY_AUDIO)


    async def on_message(
        self,
        message: Message,
        site_id: str,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        if isinstance(message, NluIntent):
            if self.handle_enabled:
                async for intent_result in self.handle_intent(message, site_id=site_id):
                    yield intent_result
        elif isinstance(message, HandleToggleOn):
            self.handle_enabled = True
            _LOGGER.debug("Intent handling enabled")
        elif isinstance(message, HandleToggleOff):
            self.handle_enabled = False
            _LOGGER.debug("Intent handling disabled")
        elif isinstance(message, AudioPlayFinished):
            play_finished_event = self.message_events[AudioPlayFinished].get(message.id)
            if play_finished_event:
                play_finished_event.set()
        else:
            _LOGGER.warning("Unexpected message: %s", message) 
    

    async def play_sfx(
        self,
        sound_name: str,
        site_id: str,
        block: bool = True,
    ):
        _LOGGER.debug("Playing sound %s", str(sound_name))

        sound_path = os.path.join(self.app_dir, "sfx", f"{sound_name}.wav")
        if not os.path.isfile(sound_path):
            _LOGGER.error("Sound does not exist: %s", str(sound_path))
            return

        wav_bytes = wav.read_wav(sound_path)

        request_id = str(uuid4())
        finished_event = asyncio.Event()
        self.message_events[AudioPlayFinished][request_id] = finished_event

        try:
            yield (
                AudioPlayBytes(wav_bytes=wav_bytes),
                {"site_id": site_id, "request_id": request_id},
            )

            # Wait for finished event or WAV duration
            if block:
                wav_duration = wav.get_wav_duration(wav_bytes)
                wav_timeout = wav_duration + 0.25
                _LOGGER.debug(
                    "Waiting for playFinished (id=%s, timeout=%s)",
                    request_id,
                    wav_timeout,
                )
                await asyncio.wait_for(finished_event.wait(), timeout=wav_timeout)

        except asyncio.TimeoutError:
            _LOGGER.warning("Did not receive playFinished before timeout")
    

    async def send_hass_command(self, subpath: str, json: typing.Dict[str, typing.Any]):
        url = urljoin(self.ha_url, subpath)

        async with self.http_session.post(url, json=json) as response:
            response.raise_for_status()


    async def hass_switch_power(self, site_id: str, entity_id: str, state: bool):
        sfx_name = "running_1" if state else "running_2"
        async for msg in self.play_sfx(sfx_name, site_id=site_id, block=False):
            yield msg
        await self.send_hass_command(
            subpath=f"/api/services/switch/turn_{'on' if state else 'off'}",
            json={"entity_id": entity_id}
        )
