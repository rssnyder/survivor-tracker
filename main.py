from os import getenv
import logging

from fastapi import FastAPI
from pydantic import BaseModel
from tomli import load

import psycopg

from signalm import send


class Activity(BaseModel):
    username: str
    show: str
    season: str
    episode: str


with open("config.toml", mode="rb") as fp:
    config = load(fp)

app = FastAPI()

conn = psycopg.connect(
    host=config["database"]["host"],
    dbname=config["database"]["db"],
    user=config["database"]["user"],
    password=getenv("DB_PASS"),
)


@app.post("/activity")
def activity(activity: Activity):
    """
    Log a users activity
    """

    season = activity.season.zfill(2)
    episode = activity.episode.zfill(2)

    """
    Update username so it shows personalized names
    """
    watcher = activity.username
    if watcher:
        if watcher == "riley_snyder":
            watcher = "Riley and Nicole"
        elif watcher == "hmfis":
            watcher = "Hannah and Sweepy"
        elif watcher == "mose162":
            watcher = "Hunter"
        elif watcher == "barry.sa":
            watcher = "Barry and Marcin"
        return watcher

    if season != config["survivor"]["season"]:
        logging.info(f"off season viewing: {watcher}")
        return season

    position, winner = log_activity(activity.username, season, episode)
    if not position:
        logging.info(f"rewatch: {watcher}")
        return 0

    if position == 1:
        message = f"{watcher} started watching S{season}E{episode} first! 🥇\nThey have been first {winner} time{'s' if winner > 1 else ''} this season!"
    elif position == 2:
        message = f"{watcher} started watching S{season}E{episode}! 🥈"
    elif position == 3:
        message = f"{watcher} started watching S{season}E{episode}! 🥉"
    elif position == 4:
        message = f"{watcher} finally started watching S{season}E{episode}! 💩\nWe no longer need spoiler tags."

    send(
        config["signal"]["api"],
        config["signal"]["number"],
        config["signal"]["group"],
        message,
    )

    if position == 4:
        score_message = "Current Scores:"
        for username, score in get_stats(season):
            score_message += f"\n{watcher}: {score}"
        send(
            config["signal"]["api"],
            config["signal"]["number"],
            config["signal"]["group"],
            score_message,
        )

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

    existing = """SELECT id FROM survivorLog WHERE username = %s AND season = %s AND episode = %s;"""

    cur.execute(existing, (username, season, episode))
    if cur.rowcount:
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
        winner = """SELECT id FROM survivorLog WHERE username = %s AND season = %s AND position = 1;"""

        cur.execute(winner, (username, season))
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
