import os
import requests
import slack
from flask import Flask
from slackeventsapi import SlackEventAdapter

from threading import Thread
from queue import Queue, Full
from langchain.agents import Tool
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

# from extractor_api import ExtractorAPI
# from ai import AI
# from database_access import sql_query

SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL')
SLACK_TOKEN = os.environ.get('SLACK_TOKEN')
SLACK_SIGNING_TOKEN = os.environ.get('SLACK_SIGNING_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
SERPAPI_API_KEY = os.environ.get('SERPAPI_API_KEY')
WOLFRAM_ALPHA_APPID = os.environ.get('WOLFRAM_ALPHA_APPID')


class AI:
    def __init__(self):
        self.llm = OpenAI(temperature=0.9)

        self.prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            You are a personal assistant. Your job is to find the best answer to the questions asked.
            ###
            {query}
            """,
        )

        self.tools = load_tools(["serpapi", "wolfram-alpha"], llm=self.llm)

        self.tools.append(
            Tool(
                name="extractorapi",
                func=ExtractorAPI().extract_from_url,
                description="Extracts text from a website. The input must be a valid URL to the website. In the output, you will get the text content. Example input: https://openai.com/blog/openai-and-microsoft-extend-partnership/",
            )
        )

        self.agent = initialize_agent(
            self.tools, self.llm,
            agent="zero-shot-react-description", verbose=True, max_iterations=10
        )

    def run(self, query):
        agent_prompt = self.prompt.format(query=query)
        return self.agent.run(agent_prompt)


class ExtractorAPI:
    def __init__(self):
        self.endpoint = "https://extractorapi.com/api/v1/extractor"
        self.api_key = os.environ.get("EXTRACTOR_API_KEY")

    def extract_from_url(self, url):
        try:
            params = {
                "apikey": self.api_key,
                "url": url
            }

            r = requests.get(self.endpoint, params=params)
            r = r.json()
            return r["text"]
        except Exception as e:
            return f"Error: {e}. Is the URL valid?"


app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(SLACK_SIGNING_TOKEN, '/slack/events', app)

client = slack.WebClient(token=SLACK_TOKEN)

ai = AI()
messages_to_handle = Queue(maxsize=32)


def reply_to_slack(thread_ts, response):
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
    app.run(port=5002, debug=True)

