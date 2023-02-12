import os
import requests
from langchain.agents import Tool
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate

# from extractor_api import ExtractorAPI

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


ai = AI()
print(ai.run("Mitä ravintoloita ostoskeskus Redissä on?"))
