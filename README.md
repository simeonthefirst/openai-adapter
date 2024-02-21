# openai-adapter
This Azure-Function provides as an interface for submitting messages Azure-hosted OpenAI model and receiving answers. 

It generates ongoing conversations by buffering past messages and it historizes past conversations in an Azure Storage Table. 
Additionally, it contains the system message for the ai model, and adds it to every start of a new conversation.



## How to set it up

- Create Azure storage Container and Azure OpenAI Model
- Publish to azure via ```func azure functionapp publish smn-openai-adapter```
- Set enviroment varanles for azure open ai connection:
    - ```AZURE_STORAGE_CONNECTION_STRING```
    - ```AZURE_STORAGE_TABLE_NAME```
    - ```AZURE_OPENAI_KEY```
    - ```AZURE_OPENAI_ENDPOINT```
    - ```AZURE_OPENAI_VERSION```
    - ```AZURE_OPENAI_DEPLOYMENTNAME```
    - ```AZURE_OPENAI_SYSTEM_MESSAGE```
    - ![enviroment variables](docu/env-vars.PNG)


## How to use it

### API Endpoint GET /askopenai

#### Parameters

- `code` (string, required): Access key to the Azure-Function
- `question` (string, required): The question to ask the AI model.
- `conversation_timeout` (integer, optional): The maximum time in seconds allowed between the last answer and the current question. If exceeded, a new conversation starts. Defaults to 300 seconds (5 minutes).
- `only_answer` (boolean, optional): If `true`, the response body will contain only the AI's answer. If `false`, the response body will include the entire conversation history in JSON format. Defaults to `true`.

#### Request Example

```http
GET /api/askopenai?question=What%20is%20the%20capital%20of%20France&conversation_timeout=300&only_answer=true&code={your_function_api_key}
```

#### Responses
##### Success Response

- **Status Code: `200 OK`**
- **Content-Type: `text/plain`** (when **`only_answer=true`**)
- **Body:** Just the AI's answer in plain text.

OR

- **Content-Type: `application/json`** (when **`only_answer=false`**)
- **Body:** A JSON representation of the entire - conversation, including the latest question and answer.

##### Error Responses

- **400 Bad Request:** Returned if the question parameter is missing.
- **500 Internal Server Error:** Returned if there's an error processing the request, including issues with calling the Azure OpenAI service or other internal errors.

##### Notes 
- Make sure to replace **`{your_function_api_key}`** in the request example with your actual Azure Function API key.
- The **`user_id for managing conversation contexts is currently set to a static value. There is no differentiation between diffrent clients jet!