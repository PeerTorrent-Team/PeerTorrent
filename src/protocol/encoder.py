import json
from .message import Message

class Encoder:
    def encode(self, message: Message) -> bytes:
        # Convert the Message object into simple structure used on the wire.
        data={
            "type": message.type.value,
            "payload": message.payload,
        }
        # JSON gives us a readable, structured formats
        seriailized=json.dumps(data)

        # TCP works with bytes, so encoding the JSON string into UTF-8
        return seriailized.encode("utf-8")
