import slack
from flask import Flask
from slackeventsapi import SlackEventAdapter
from ai import AI
from database_access import sql_query
from threading import Thread
from queue import Queue, Full

SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL')
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')
SLACK_SIGNING_TOKEN = os.environ.get('SLACK_SIGNING_TOKEN')

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(SLACK_SIGNING_TOKEN, '/slack/events', app)

client = slack.WebClient(token=SLACK_TOKEN)

ai = AI(sql_query)
messages_to_handle = Queue(maxsize=32)


def reply_to_slack(thread_ts: object, response: object) -> object:
    client.chat_postMessage(channel=SLACK_CHANNEL, text=response, thread_ts=thread_ts)


def confirm_message_received(channel, thread_ts):
    client.reactions_add(
        channel=channel,
        name="thumbsup",
        timestamp=thread_ts
    )


def handle_message():
    while True:
        message_id, thread_ts, user_id, text = messages_to_handle.get()
        print(f'Handling message {message_id} with text {text}')
        text = " ".join(text.split(" ", 1)[1:])
        try:
            response = ai.run(text)
            reply_to_slack(thread_ts, response)
        except Exception as e:
            response = f":exclamation::exclamation::exclamation: Error: {e}"
            reply_to_slack(thread_ts, response)
        finally:
            messages_to_handle.task_done()


@slack_event_adapter.on('app_mention')
def message(payload):
    print(payload)
    event = payload.get('event', {})
    message_id = event.get('client_msg_id')
    thread_ts = event.get('ts')
    channel = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')
    try:
        messages_to_handle.put_nowait((message_id, thread_ts, user_id, text))
        confirm_message_received(channel, thread_ts)
    except Full:
        response = f":exclamation::exclamation::exclamation:Error: Too many requests"
        reply_to_slack(thread_ts, response)
    except Exception as e:
        response = f":exclamation::exclamation::exclamation: Error: {e}"
        reply_to_slack(thread_ts, response)
        print(e)


if __name__ == "__main__":
    Thread(target=handle_message, daemon=True).start()
    app.run(debug=True)
