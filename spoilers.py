from websockets import connect
from asyncio import get_event_loop
from json import loads
from os import getenv
from base64 import b64decode
import logging

from requests import get
from tomli import load

from signalm import send


logging.basicConfig(level=getenv("LOGLEVEL", "INFO").upper())

with open("config.toml", mode="rb") as fp:
    config = load(fp)


async def receive():
    # receive messages from signal via json rpc

    try:
        async with connect(
            f"ws://{config['signal']['api']}/v1/receive/{config['signal']['number']}",
            ping_interval=None,
        ) as websocket:
            async for raw_message in websocket:
                yield raw_message
    except Exception as e:
        raise e


async def wait_for_spoilers(groupId: str, season: str):
    # loop through all new messages

    logging.info("waiting for spoilers...")

    async for raw_message in receive():

        # load in message
        try:
            message = loads(raw_message)
        except Exception as e:
            print("unable to load message: ", e)
            continue

        # only watch messages in our group
        if (
            ("dataMessage" not in message["envelope"])
            or ("groupInfo" not in message["envelope"]["dataMessage"])
            or (message["envelope"]["dataMessage"]["groupInfo"]["groupId"] != groupId)
        ):
            logging.debug("not from our group")
            continue

        # skip non spoilers
        if not [
            x
            for x in message["envelope"]["dataMessage"].get("textStyles", [])
            if x.get("style") == "SPOILER"
        ]:
            logging.debug("not a spoiler")
            continue

        signal_user = message["envelope"]["source"]

        resp = get(
            f"http://{config['tautulli']['api']}/api/v2?apikey={getenv('TAUTULLI_KEY')}&cmd=get_activity"
        )

        resp.raise_for_status()

        # get current streams of survivor
        # in the current season
        # for the current player
        for stream in [
            x
            for x in resp.json()["response"]["data"]["sessions"]
            if (
                (x.get("grandparent_title") == "Survivor")
                and (x.get("parent_title").split(" ")[-1] == season)
                and (config["signal_players"].get(signal_user) == x.get("username"))
            )
        ]:
            # calculate position in the episode
            min = (
                float(stream.get("progress_percent"))
                * float(stream.get("stream_duration"))
                / 6000000
            )
            if min > 60:
                position = f"1h{int(min - 60)}m"
            else:
                position = f"{int(min)}m"

            print(
                send(
                    config["signal"]["api"],
                    config["signal"]["number"],
                    config["signal"]["group"],
                    position,
                )
            )

            logging.info(f"tagged spoiler for {signal_user} at {position}")


if __name__ == "__main__":

    # decode the group id
    groupId = b64decode(config["signal"]["group"].split(".")[-1]).decode("utf-8")

    event_loop = get_event_loop()

    event_loop.run_until_complete(
        wait_for_spoilers(groupId, config["survivor"]["season"])
    )
