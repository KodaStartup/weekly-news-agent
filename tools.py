from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.tools import Tool
#import wikipedia
import smtplib
import os
from email.message import EmailMessage
import feedparser
from datetime import datetime, timedelta, timezone
from time import mktime

FEEDS = [
    "https://news.google.com/rss/search?q=h%C3%B4tellerie%20ia&hl=fr&gl=FR&ceid=FR%3Afr",
    # add trade-press RSS URLs here
]

def collect_week_news() -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    seen, items = set(), []
    for url in FEEDS:
        for e in feedparser.parse(url).entries:
            if not getattr(e, "published_parsed", None):
                continue
            published = datetime.fromtimestamp(mktime(e.published_parsed), timezone.utc)
            if published < cutoff or e.link in seen:
                continue
            seen.add(e.link)
            items.append(f"- {e.title} ({published:%d/%m}) {e.link}")
    return "\n".join(items)

# Wikipedia rate-limits the library's default User-Agent (HTTP 429), so identify ourselves
#wikipedia.set_user_agent("KronoaResearchAgent/1.0 (personal project)")

def send_to_email(data: str, recipient: str | list[str] = ["salima.bt@kronoa.fr", "selim.bt@kronoa.fr"], subject: str = "Kronoa agent report") -> str:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("EMAIL_ADDRESS")
    msg["To"] = ", ".join(recipient) if isinstance(recipient, list) else recipient
    msg.set_content(data)

    try:
        with smtplib.SMTP_SSL('ssl0.ovh.net', 465) as server:
            server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
            server.send_message(msg)
        return f"Data successfully sent to {recipient}"
    except Exception as e:
        return f"Failed to send email: {e}"

def save_to_txt(data: str, filename: str = 'research_output.txt'):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_text = f"--- Research Output ---\ntimestamp: {timestamp} \n\n{data}\n\n"

    with open(filename, 'a', encoding='utf-8') as f:
        f.write(formatted_text)

    return f"Data successfully saved to {filename}"

save_tool = Tool(
    name="save_text_to_file",
    func=save_to_txt,
    description="Saves structured research data to a text file.",
)

send_email_tool = Tool(
    name="send_email",
    func=send_to_email,
    description="Sends structured research data to an email address. Requires the data and recipient email as input.",
)

news_tool = Tool(
    name="collect_week_news",
    func=lambda _: collect_week_news(),
    description="Get the last 7 days of news headlines and links about "
                "the hotel industry (hôtellerie) in France. Input is ignored.",
)

def _safe(fn):
    # Report tool failures (rate limits, network errors) back to the agent instead of crashing
    def wrapper(query: str) -> str:
        try:
            return fn(query)
        except Exception as e:
            return f"Tool failed: {e}. Try a different tool or query."
    return wrapper

search = DuckDuckGoSearchRun()
search_tool = Tool(
    name="search",
    func=_safe(search.run),
    description="Search the web for the latest news",
)

api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
wiki_tool = Tool(
    name="wikipedia",
    func=_safe(api_wrapper.run),
    description="Look up a topic on Wikipedia. Input should be a search query.",
)
