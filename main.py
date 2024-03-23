from os import getenv
import logging

from fastapi import FastAPI
from pydantic import BaseModel

from requests import post

import psycopg


class Activity(BaseModel):
    username: str
    show: str
    season: str
    episode: str


app = FastAPI()

conn = psycopg.connect(
    host=getenv("DB_HOST"),
    dbname=getenv("DB_DB"),
    user=getenv("DB_USER"),
    password=getenv("DB_PASS"),
)


def send_signal(message: str):
    resp = post(
        f"{getenv('SIGNAL_API')}/v2/send",
        json={
            "message": message,
            "number": getenv("SIGNAL_FROM"),
            "recipients": [getenv("SIGNAL_TO")],
        },
    )

    if resp.status_code >= 400:
        logging.error(resp.text)
    else:
        logging.info(resp.text)


@app.post("/activity")
def activity(activity: Activity):
    """
    Log a users activity
    """

    season = activity.season.zfill(2)
    episode = activity.episode.zfill(2)

    position, winner = log_activity(activity.username, season, episode)
    if not position:
        logging.info(f"rewatch: {activity.username}")
        return 0

    if position == 1:
        message = f"{activity.username} is watching S{season}E{episode} first! 🥇\nThey have been first {winner} times!"
    elif position == 2:
        message = f"{activity.username} is watching S{season}E{episode}! 🥈"
    elif position == 3:
        message = f"{activity.username} is watching S{season}E{episode}! 🥉"
    elif position == 4:
        message = f"{activity.username} is finally watching S{season}E{episode}! 💩\nWe no longer need spoiler tags."

    send_signal(message)

    if position == 4:
        score_message = "Current Scores:"
        for username, score in get_stats(season):
            score_message += f"\n{username}: {score}"
        send_signal(score_message)

    return position


@app.get("/test")
def test():
    return get_stats(46)


def log_activity(username: str, season: int, episode: int) -> tuple[int, int]:
    """
    Store activity in the database
    Get number of times the person in 1st has been 1st before
    """

    cur = conn.cursor()

    existing = """SELECT id FROM survivorLog WHERE username = %s season = %s AND episode = %s;"""

    cur.execute(existing, (username, season, episode))
    if len(cur.fetchall()) > 0:
        cur.close()
        return (None, None)

    select = """SELECT id FROM survivorLog WHERE season = %s AND episode = %s;"""

    cur.execute(select, (season, episode))
    position = len(cur.fetchall()) + 1

    insert = """INSERT INTO survivorLog(username, season, episode, position, timestamp)
            VALUES(%s, %s, %s, %s, current_timestamp)
            RETURNING id;"""

    cur.execute(insert, (username, season, episode, position))
    result = cur.fetchone()[0]

    counts = 0
    if position == 1:
        winner = """SELECT id FROM survivorLog WHERE username = %s AND position = 1;"""

        cur.execute(winner, (username,))
        counts = len(cur.fetchall())

    if result:
        logging.info(f"stored: {result}")
        conn.commit()

    cur.close()

    return (position, counts)


def get_stats(season: int) -> list:
    """
    Get the rankings for the current season
    """

    cur = conn.cursor()

    select = """SELECT username, position FROM survivorLog WHERE season = %s;"""

    cur.execute(select, (season,))

    user_points = {}
    for episode in cur.fetchall():
        username = episode[0]
        position = episode[1]

        points = abs((position - 1) - 3)

        if username not in user_points:
            user_points[username] = points
        else:
            user_points[username] = user_points[username] + points

    sorted_scores = sorted(user_points.items(), key=lambda x: x[1], reverse=True)

    return sorted_scores
