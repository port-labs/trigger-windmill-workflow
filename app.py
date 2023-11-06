import logging
import signal
from typing import Any, Callable
import requests
import json

from confluent_kafka import Consumer, KafkaException, Message

KAFKA_CONSUMER_BROKERS: str = "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-2-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-3-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"
KAFKA_CONSUMER_SECURITY_PROTOCOL: str = "SASL_SSL"
KAFKA_CONSUMER_AUTHENTICATION_MECHANISM: str = "SCRAM-SHA-512"
KAFKA_CONSUMER_USERNAME: str = os.getenv("KAFKA_CONSUMER_USERNAME")
KAFKA_CONSUMER_PASSWORD: str = os.getenv("KAFKA_CONSUMER_PASSWORD")
KAFKA_CONSUMER_SESSION_TIMEOUT_MS: int = 45000
KAFKA_CONSUMER_AUTO_OFFSET_RESET: str = "earliest"
KAFKA_CONSUMER_GROUP_ID: str = os.getenv("KAFKA_CONSUMER_GROUP_ID")
KAFKA_CONSUMER_CLIENT_ID = os.getenv("KAFKA_CONSUMER_CLIENT_ID")
KAFKA_RUNS_TOPIC: str = os.getenv("KAFKA_RUNS_TOPIC")

LOG_LEVEL: str = os.getenv("LOG_LEVEL")

PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID")
PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET")

API_URL = os.getenv("API_URL", default = "https://api.getport.io/v1")

WINDMILL_API_TOKEN = os.getenv("WINDMILL_API_TOKEN")
WINDMILL_API_URL = os.getenv("WINDMILL_API_URL")



logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def trigger_windmill_job(workspace: str, script_path: str, data: dict[str, Any]):
	windmill_webhook_endpoint = f"{WINDMILL_API_URL}/w/{workspace}/jobs/run_wait_result/f/{script_path}"
	headers = {
            "Authorization": f"Bearer {WINDMILL_API_TOKEN}",
			"Content-Type": "application/json"
    }
	webhook_response = requests.post(windmill_webhook_endpoint, json=data, headers=headers)
	webhook_response.raise_for_status()
	logger.info('Windmill job successfully triggered')
	return webhook_response

def msg_process(msg: Message) -> None:

	try:
		msg_value = json.loads(msg.value().decode())
		logger.info("Raw message value: %s", msg.value())

		access_token_res = requests.post(f"{API_URL}/auth/access_token", json={
			"clientId": PORT_CLIENT_ID,
			"clientSecret": PORT_CLIENT_SECRET
		})

		access_token = access_token_res.json().get('accessToken')

		headers = {
			"Authorization": f"Bearer {access_token}"
		}

		run_id = msg_value['context']['runId']
		properties = msg_value['payload']['properties']
		insertLogsEndpoint = f"{API_URL}/actions/runs/{run_id}/logs"
		updateRunEndpoint = f"{API_URL}/actions/runs/{run_id}"

		# Triiger windmill job/workflow
		windmill_webhook_response = trigger_windmill_job(workspace=properties['workspace'], script_path=properties['file_path'], data=properties['job_data'])
		trigger_status = "SUCCESS" if windmill_webhook_response.json() is None else "FAILURE"
		
        # Create run log
		requests.post(insertLogsEndpoint, json={
			"message": "Run completed successfully"
		}, headers=headers)
		print('Successfully created run log')

		# Update the status of the run
		requests.patch(updateRunEndpoint, json={
			"status": trigger_status
		}, headers=headers)
		print('Successfully updated the run status')

	except Exception as e:
		raise Exception('Something went wrong', str(e))

	return 'OK'


class KafkaConsumer():
	def __init__(
		self, msg_process: Callable[[Message], None], consumer: Consumer = None
	) -> None:
		self.running = False
		signal.signal(signal.SIGINT, self.exit_gracefully)
		signal.signal(signal.SIGTERM, self.exit_gracefully)

		self.msg_process = msg_process

		if consumer:
			self.consumer = consumer
		else:
			conf = {
				"bootstrap.servers": KAFKA_CONSUMER_BROKERS,
				"client.id": KAFKA_CONSUMER_CLIENT_ID,
				"security.protocol": KAFKA_CONSUMER_SECURITY_PROTOCOL,
				"sasl.mechanism": KAFKA_CONSUMER_AUTHENTICATION_MECHANISM,
				"sasl.username": KAFKA_CONSUMER_USERNAME,
				"sasl.password": KAFKA_CONSUMER_PASSWORD,
				"group.id": KAFKA_CONSUMER_GROUP_ID,
				"session.timeout.ms": KAFKA_CONSUMER_SESSION_TIMEOUT_MS,
				"auto.offset.reset": KAFKA_CONSUMER_AUTO_OFFSET_RESET,
				"enable.auto.commit": "false",
			}
			self.consumer = Consumer(conf)

	def start(self) -> None:
		try:
			self.consumer.subscribe(
				[KAFKA_RUNS_TOPIC],
				on_assign=lambda _, partitions: logger.info(
					"Assignment: %s", partitions
				),
			)
			self.running = True
			while self.running:
				try:
					msg = self.consumer.poll(timeout=1.0)
					if msg is None:
						continue
					if msg.error():
						raise KafkaException(msg.error())
					else:
						try:
							logger.info(
								"Process message"
								" from topic %s, partition %d, offset %d",
								msg.topic(),
								msg.partition(),
								msg.offset(),
							)
							self.msg_process(msg)
						except Exception as process_error:
							logger.error(
								"Failed process message"
								" from topic %s, partition %d, offset %d: %s",
								msg.topic(),
								msg.partition(),
								msg.offset(),
								str(process_error),
							)
						finally:
							self.consumer.commit(asynchronous=False)
				except Exception as message_error:
					logger.error(str(message_error))
		finally:
			self.consumer.close()

	def exit_gracefully(self, *_: Any) -> None:
		logger.info("Exiting gracefully...")
		self.running = False

if __name__ == "__main__":
	consumer = KafkaConsumer(msg_process)
	consumer.start()