import argparse
import asyncio
import logging

import paho.mqtt.client as mqtt
import rhasspyhermes.cli as hermes_cli

from . import sinclair_mqtt

_LOGGER = logging.getLogger("sinclair_intent")

def main():
    parser = argparse.ArgumentParser(prog="sinclair-intent")
    parser.add_argument("--ha-url", required=True,
        help="URL of Home Assistant server"
    )
    parser.add_argument("--ha-access-token", required=True,
        help="Home Assistant authorization bearer token"
    )

    hermes_cli.add_hermes_args(parser)
    args = parser.parse_args()

    hermes_cli.setup_logging(args)
    _LOGGER.debug(args)

    # Listen for messages
    client = mqtt.Client()
    hermes = sinclair_mqtt.SinclairIntentHermesMqtt(
        client,
        ha_url=args.ha_url,
        ha_access_token=args.ha_access_token,
        site_ids=args.site_id
    )

    _LOGGER.info("Connecting to %s:%s", args.host, args.port)
    hermes_cli.connect(client, args)
    client.loop_start()

    try:
        # Run event loop
        asyncio.run(hermes.handle_messages_async())
    except KeyboardInterrupt:
        pass
    finally:
        _LOGGER.debug("Shutting down")
        client.loop_stop()

