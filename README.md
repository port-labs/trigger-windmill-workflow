# Triggering Windmill Workflows


## Getting started

The following example helps internal developer teams to trigger [Windmill](https://www.windmill.dev) jobs and workflows using Port's self service actions. In particular, you will create a blueprint for `windmillJobs` that will be connected to a backend action. You will then add some python script (`app.py`) to read from a Kafka topic and trigger your Windmill workflow.

## Job blueprint
Create the Windmill job blueprint in Port [using this json file](./resources/windmillJob.json)


## Create action UI
Use the action schema in [this json file](./resources/actionSetup.json) to setup the action UI

## Variables
The list of required variables to run the backend code in `app.py` are:
- `KAFKA_CONSUMER_BROKERS`
- `KAFKA_CONSUMER_USERNAME`
- `KAFKA_CONSUMER_PASSWORD`
- `KAFKA_CONSUMER_GROUP_ID`
- `KAFKA_CONSUMER_CLIENT_ID`
- `WINDMILL_API_TOKEN`
- `PORT_CLIENT_ID`
- `PORT_CLIENT_SECRET`

## Run action
Run this action with some input

```json showLineNumbers
{
    "workspace": "demo",
    "file_path": "f/examples/ban_user_example",
    "job_data": {
        "value": "wonderwoman",
        "reason": "First Attempt at webhook",
        "database": "$res:f/examples/demo_windmillshowcases",
        "username": "Jack",
        "slack_channel": "bans"
    }
}
```