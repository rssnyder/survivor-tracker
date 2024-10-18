import logging

from requests import post


def send(api: str, number: str, recipient: str, message: str) -> str:
    resp = post(
        f"http://{api}/v2/send",
        json={
            "message": message,
            "number": number,
            "recipients": [recipient],
        },
    )

    if resp.status_code >= 400:
        logging.error(resp.text)
    else:
        logging.info(resp.text)
