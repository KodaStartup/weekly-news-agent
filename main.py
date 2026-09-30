from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, send_to_email, news_tool
load_dotenv()

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


llm = ChatAnthropic(model="claude-sonnet-5-5")
parser = PydanticOutputParser(pydantic_object=ResearchResponse)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system", 
         """ 
         You are a research assistant that will help generate a research paper. 
         You will provide a summary, sources, and tools used for the research. 
         Answer the query and use necessary tools. 
         Wrap the output in this format and provide no other text\n{format_instructions}
         """,
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}")
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [search_tool, news_tool]
agent = create_tool_calling_agent(
    llm=llm,
    prompt=prompt,
    tools=tools,
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
query= "write a report on the french hotel industry and its recent trends"
raw_response = agent_executor.invoke({"query": query})

try: 
    output = raw_response.get("output")
    if isinstance(output, list):
        output = "".join(
            block.get("text", "") for block in output
            if isinstance(block, dict) and block.get("type") == "text"
        )
    structured_response = parser.parse(output)
    body = (
        f"Topic: {structured_response.topic}\n\n"
        f"{structured_response.summary}\n\n"
        "Sources:\n" + "\n".join(f"- {s}" for s in structured_response.sources)
    )
    print(send_to_email(body, subject=f"Research: {structured_response.topic}"))
except Exception as e:
    print("Failed to parse structured response", e, "Raw response:", raw_response)
