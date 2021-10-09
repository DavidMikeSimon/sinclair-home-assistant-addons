import typing
from dataclasses import dataclass

from rhasspyhermes.base import Message

@dataclass
class HassSwitchPower(Message):
    entityId: str
    state: bool

    @classmethod
    def topic(cls, **kwargs) -> str:
        entityId = kwargs.get("entityId", "#")
        return "home-assistant/switch/%s/power"  % entityId
    
    def to_topic_kwargs(self) -> typing.Dict[str, typing.Any]:
        return {"entityId": self.entityId}
    
    def payload(self) -> typing.Union[str, bytes]:
        return "ON" if self.state else "OFF"
