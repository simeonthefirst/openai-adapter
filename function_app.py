import azure.functions as func
import logging
import os
from openai import AzureOpenAI

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="http_trigger")
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered \
                                 function executed successfully.")
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a name \
            in the query string or in the request body for a personalized \
                response.",
            status_code=200
        )


@app.route(route="askopenai", auth_level=func.AuthLevel.ANONYMOUS)
def askopenai(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function askopenai processed a request.')

    question = req.params.get('question')

    if question:

        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2023-12-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        deployment_name = 'smn-gpt35'

        # Send a completion call to generate an answer
        print('Sending a test completion job')
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question},
            ]
        )

        answer = response.choices[0].message.content

    return func.HttpResponse(
        answer,
        status_code=200
    )
