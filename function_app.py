import os
import json
import logging
from datetime import datetime, timedelta
import azure.functions as func
from openai import AzureOpenAI
from azure.data.tables import TableClient


AZURE_STORAGE_CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING") or ""
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY") or ""
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or ""

AZURE_OPENAI_VERSION = "2023-12-01-preview"
SYSTEM_MESSAGE = "You are a helpful assistant."

AZURE_STORAGE_TABLE_NAME = "conversationhistory"


table_client = TableClient.from_connection_string(
    conn_str=AZURE_STORAGE_CONNECTION_STRING, table_name=AZURE_STORAGE_TABLE_NAME)
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class Conversation:
    class Message:
        def __init__(self, timestamp: datetime, content: str, role: str):
            self.timestamp = timestamp
            self.content = content
            self.role = role

        def to_dict(self):
            return {
                'timestamp': self.timestamp.isoformat(),
                'content': self.content,
                'role': self.role
            }

    def __init__(self):
        self.start_timestamp = datetime.utcnow()
        self.messages: list[Conversation.Message] = []

    def add_system_message(self):
        self.messages.append(Conversation.Message(
            self.start_timestamp, SYSTEM_MESSAGE, 'system'))

    def get_messages(self) -> list[dict[str, str]]:
        return [{'role': m.role, 'content': m.content} for m in self.messages]

    def timestamp_latest(self) -> datetime:
        return self.messages[-1].timestamp if self.messages else self.start_timestamp

    def add_message(self, content: str | None, role: str):
        if content:
            self.messages.append(Conversation.Message(
                datetime.utcnow(), content, role))

    def reset_if_timed_out(self, timeout_seconds: int):
        if self.messages and \
                (self.timestamp_latest() + timedelta(seconds=timeout_seconds) < datetime.utcnow()):
            self.__init__()  # Reinitialize the conversation
            self.add_system_message()


def get_current_conversation(user_id: str) -> Conversation:
    try:
        # Query to get all conversations for the user
        query_filter = f"PartitionKey eq '{user_id}'"
        entities = list(table_client.query_entities(
            query_filter, select=['RowKey', 'data']))

        logging.debug(f"Queried Table for entities: {entities}")

        if not entities:  # Check if the entities list is empty
            logging.info(
                f"No conversations found for user {user_id}. Initializing a new conversation.")
            convo = Conversation()
            convo.add_system_message()
            return convo

        # Sort entities by RowKey (timestamp) to find the latest
        latest_entity = sorted(
            entities, key=lambda x: x['RowKey'], reverse=True)[0]

        # todo: save a entity "Latest conversation" with the corresponding Row Key.
        # With that entity the exact conversation can be retrieved without the need of sorting a list"

        # Deserialize the conversation data
        convo_data = json.loads(latest_entity['data'])
        convo = Conversation()
        for msg in convo_data['messages']:
            convo.messages.append(Conversation.Message(
                timestamp=datetime.fromisoformat(msg['timestamp']), content=msg['content'], role=msg['role']))

        return convo
    except Exception as e:
        logging.error(
            f"Failed to retrieve the latest conversation for user {user_id}: {e}")
        # Return a new conversation if an error occurs or no conversation is found
        convo = Conversation()
        convo.add_system_message()
        return convo


def save_conversation(convo: Conversation, user_id: str):
    # Convert conversation messages to JSON string
    convo_data = json.dumps(
        {"messages": [m.to_dict() for m in convo.messages]})
    entity = {
        "PartitionKey": user_id,
        "RowKey": convo.start_timestamp.isoformat(),
        "data": convo_data
    }
    try:
        table_client.upsert_entity(entity=entity)
    except Exception as e:
        logging.error(f"Failed to save conversation: {e}")


@app.route(route="askopenai")
def askopenai(req: func.HttpRequest) -> func.HttpResponse:
    try:
        logging.info('Python HTTP askopenai function processed a request.')
        # logging.debug(f"Received request with headers: {req.headers}")
        # logging.debug(f"Request params: {req.params}")

        question = req.params.get('question')
        conversation_timeout = req.params.get(
            'conversation_timeout', 300)  # Default timeout 5 minutes =300 sek

        if not question:
            logging.warning("No question parameter provided in the request.")
            return func.HttpResponse("Please provide a question parameter.",
                                     status_code=400)

        # todo: create user_id based on session or authentication,
        # to not mix up conversations from independent sessions
        user_id = "default"
        convo = get_current_conversation(user_id)
        convo.reset_if_timed_out(int(conversation_timeout))

        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2023-12-01-preview",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

        deployment_name = 'smn-gpt35'

        convo.add_message(question, 'user')

        try:
            logging.debug(
                f"Sending message to Azure OpenAI: {convo.get_messages()}")
            response = client.chat.completions.create(
                model=deployment_name,
                messages=convo.get_messages()  # type: ignore
            )
            answer = response.choices[0].message.content \
                if response.choices else "No answer available."
        except Exception as e:
            logging.error(f"Error calling Azure OpenAI: {e}")
            return func.HttpResponse(f"Error processing your request. \
                    Error calling Azure OpenAI: {e}", status_code=500)

        convo.add_message(answer, 'assistant')

        save_conversation(convo, user_id)

        return func.HttpResponse(str(convo.get_messages()), status_code=200,
                                 headers={"Content-Type": "text/plain"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(f"Error processing your request: {e}", status_code=500)


@app.function_name(name="http_trigger")
@app.route(auth_level=func.AuthLevel.FUNCTION)
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    return func.HttpResponse(
        f"This HTTP triggered function executed successfully.{req}",
        status_code=200
    )
