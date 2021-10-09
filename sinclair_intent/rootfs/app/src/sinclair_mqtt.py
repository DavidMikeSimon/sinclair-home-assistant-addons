import logging
import typing
from urllib.parse import urljoin
from uuid import uuid4

import aiohttp
from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient
from rhasspyhermes.handle import HandleToggleOff, HandleToggleOn
from rhasspyhermes.nlu import NluIntent
from rhasspyhermes.tts import TtsSay

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

        self.subscribe(NluIntent, HandleToggleOn, HandleToggleOff)

        self.handle_enabled = True

        self._http_session = None
    

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
        self, nlu_intent: NluIntent
    ) -> typing.AsyncIterable[TtsSay]:
        try:
            slots: typing.Dict[str, str] = {}

            if nlu_intent.slots:
                for slot in nlu_intent.slots:
                    slots[slot.slot_name] = slot.value["value"]

            # Add meta slots
            intent = Intent(intent_name=nlu_intent.intent.intent_name, slots=slots)

            _LOGGER.debug("Received intent: %s" % repr(intent))

            if intent.intent_name == "HassSwitchPower":
                await self.hass_switch_power(
                    entity_id=intent.slots['id'],
                    state=(intent.slots['action'] == "on")
                )

            # yield TtsSay(
            #     text="Received intent",
            #     id=str(uuid4()),
            #     site_id=nlu_intent.site_id,
            #     session_id=nlu_intent.session_id,
            # )
            yield None
        except Exception:
            _LOGGER.exception("handle_intent")


    async def on_message(
        self,
        message: Message,
        site_id: typing.Optional[str] = None,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        if isinstance(message, NluIntent):
            if self.handle_enabled:
                async for intent_result in self.handle_intent(message):
                    yield intent_result
        elif isinstance(message, HandleToggleOn):
            self.handle_enabled = True
            _LOGGER.debug("Intent handling enabled")
        elif isinstance(message, HandleToggleOff):
            self.handle_enabled = False
            _LOGGER.debug("Intent handling disabled")
        else:
            _LOGGER.warning("Unexpected message: %s", message) 
    
    
    async def send_hass_command(self, subpath: str, json: typing.Dict[str, typing.Any]):
        url = urljoin(self.ha_url, subpath)

        async with self.http_session.post(url, json=json) as response:
            response.raise_for_status()


    async def hass_switch_power(self, entity_id: str, state: bool):
        await self.send_hass_command(
            subpath=f"/api/services/switch/turn_{'on' if state else 'off'}",
            json={"entity_id": entity_id}
        )
