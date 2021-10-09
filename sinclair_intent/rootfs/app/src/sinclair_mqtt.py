import logging
import typing
from urllib.parse import urljoin
from uuid import uuid4

from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient
from rhasspyhermes.handle import HandleToggleOff, HandleToggleOn
from rhasspyhermes.nlu import NluIntent
from rhasspyhermes.tts import TtsSay

from .hass_messages import HassSwitchPower

_LOGGER = logging.getLogger("sinclair_intent")

class Intent(typing.NamedTuple):
    intentName: str
    slots: typing.Dict[str, str]

class SinclairIntentHermesMqtt(HermesClient):
    def __init__(
        self,
        client,
        site_ids: typing.Optional[typing.List[str]] = None,
    ):
        super().__init__("sinclair_intent", client, site_ids=site_ids)

        self.subscribe(NluIntent, HandleToggleOn, HandleToggleOff)

        self.handle_enabled = True


    async def handle_intent(
        self, nlu_intent: NluIntent
    ) -> typing.AsyncIterable[TtsSay]:
        """Handle intent with Home Assistant."""
        try:
            slots: typing.Dict[str, str] = {}

            if nlu_intent.slots:
                for slot in nlu_intent.slots:
                    slots[slot.slot_name] = slot.value["value"]

            # Add meta slots
            intent = Intent(intentName=nlu_intent.intent.intent_name, slots=slots)

            _LOGGER.debug("Received intent: %s" % repr(intent))

            response = None
            if intent.intentName == "HassSwitchPower":
                response = HassSwitchPower(entityId=intent.slots['id'], state=(intent.slots['action'] == "on"))

            _LOGGER.debug("Response message: %s" % repr(response))
            
            if response:
                yield (response, response.to_topic_kwargs())

            yield TtsSay(
                text="Received intent",
                id=str(uuid4()),
                site_id=nlu_intent.site_id,
                session_id=nlu_intent.session_id,
            )
        except Exception:
            _LOGGER.exception("handle_intent")

    async def on_message(
        self,
        message: Message,
        site_id: typing.Optional[str] = None,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        """Received message from MQTT broker."""
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
