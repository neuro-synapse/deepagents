import os
import sys
import json
import time
import logging
from typing import Dict, Any

# Ensure we can import sibling example module
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Lazy import of research agent to avoid import-time env failures
_AGENT = None

def _get_agent():
    global _AGENT
    if _AGENT is None:
        if not os.environ.get("TAVILY_API_KEY"):
            raise RuntimeError("TAVILY_API_KEY is required; set it before running the worker")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is required for the default model; set it before running the worker")
        # Import after validating env to avoid KeyError in research_agent
        from research_agent import agent as _imported_agent
        _AGENT = _imported_agent
    return _AGENT


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("event_worker")


def _extract_text_from_json(body: str) -> str:
    try:
        data = json.loads(body)
        if isinstance(data, dict) and "text" in data and isinstance(data["text"], str):
            return data["text"]
        # Fallback: stringify
        return body
    except Exception:
        return body


def _invoke_agent(user_text: str) -> Dict[str, Any]:
    logger.info("Invoking agent (chars=%s)", len(user_text))
    agent = _get_agent()
    result = agent.invoke({
        "messages": [{"role": "user", "content": user_text}],
    })
    files = result.get("files", {}) or {}
    report = files.get("final_report.md")
    if report:
        logger.info("final_report.md produced (%s chars)", len(report))
    else:
        logger.warning("No final_report.md produced; check agent prompt and tools")
    return result


# --- SQS ---

def run_sqs_worker() -> None:
    try:
        import boto3  # type: ignore
    except Exception as e:
        logger.error("boto3 is required for SQS. Install with: pip install boto3 (%s)", e)
        sys.exit(2)

    queue_url = os.environ.get("SQS_QUEUE_URL")
    if not queue_url:
        logger.error("SQS_QUEUE_URL env var is required for SQS mode")
        sys.exit(2)

    wait_time = int(os.environ.get("SQS_WAIT_TIME_SECONDS", "20"))  # long polling
    max_msgs = 1
    sqs = boto3.client("sqs")

    logger.info("Starting SQS worker on %s", queue_url)
    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_msgs,
                WaitTimeSeconds=wait_time,
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                continue

            for m in msgs:
                receipt = m["ReceiptHandle"]
                body = m.get("Body", "")
                text = _extract_text_from_json(body)
                try:
                    _invoke_agent(text)
                    # Only delete on success
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                    logger.info("Message processed and deleted")
                except Exception as e:
                    logger.exception("Processing failed; message will return to queue: %s", e)
        except KeyboardInterrupt:
            logger.info("Shutting down SQS worker")
            break
        except Exception as e:
            logger.exception("SQS polling error: %s", e)
            time.sleep(5)


# --- Kafka ---

def run_kafka_worker() -> None:
    try:
        from kafka import KafkaConsumer  # type: ignore
    except Exception as e:
        logger.error("kafka-python is required for Kafka. Install with: pip install kafka-python (%s)", e)
        sys.exit(2)

    topic = os.environ.get("KAFKA_TOPIC")
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    if not topic:
        logger.error("KAFKA_TOPIC env var is required for Kafka mode")
        sys.exit(2)

    group_id = os.environ.get("KAFKA_GROUP_ID", "research-agent")
    max_poll_interval_ms = int(os.environ.get("KAFKA_MAX_POLL_INTERVAL_MS", "1800000"))  # 30m

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=False,  # commit only after success
        value_deserializer=lambda v: v.decode("utf-8"),
        max_poll_interval_ms=max_poll_interval_ms,
        auto_offset_reset=os.environ.get("KAFKA_AUTO_OFFSET_RESET", "earliest"),
    )

    logger.info("Starting Kafka worker on topic=%s bootstrap=%s", topic, bootstrap)
    try:
        for msg in consumer:
            text = _extract_text_from_json(msg.value)
            try:
                _invoke_agent(text)
                consumer.commit()
                logger.info("Message processed and committed (partition=%s offset=%s)", msg.partition, msg.offset)
            except Exception as e:
                logger.exception("Processing failed; will not commit so it can be retried: %s", e)
    except KeyboardInterrupt:
        logger.info("Shutting down Kafka worker")
    finally:
        consumer.close()


# --- Email (IMAP poll) ---

def run_email_poller() -> None:
    import imaplib
    import email
    from email.header import decode_header

    host = os.environ.get("IMAP_HOST")
    username = os.environ.get("IMAP_USERNAME")
    password = os.environ.get("IMAP_PASSWORD")
    folder = os.environ.get("IMAP_FOLDER", "INBOX")
    poll_secs = int(os.environ.get("IMAP_POLL_SECONDS", "30"))

    if not all([host, username, password]):
        logger.error("IMAP_HOST, IMAP_USERNAME, and IMAP_PASSWORD env vars are required for email mode")
        sys.exit(2)

    logger.info("Connecting to IMAP %s", host)
    M = imaplib.IMAP4_SSL(host)
    M.login(username, password)

    def fetch_unseen_ids() -> list[str]:
        M.select(folder)
        typ, data = M.search(None, 'UNSEEN')
        if typ != 'OK' or not data or not data[0]:
            return []
        return data[0].decode().split()

    def decode_subject(msg) -> str:
        subj = msg.get("Subject", "")
        parts = decode_header(subj)
        decoded = []
        for t, enc in parts:
            if isinstance(t, bytes):
                try:
                    decoded.append(t.decode(enc or 'utf-8', errors='ignore'))
                except Exception:
                    decoded.append(t.decode('utf-8', errors='ignore'))
            else:
                decoded.append(t)
        return ''.join(decoded)

    logger.info("Starting IMAP poller on folder=%s", folder)
    try:
        while True:
            try:
                ids = fetch_unseen_ids()
                if not ids:
                    time.sleep(poll_secs)
                    continue

                for i in ids:
                    typ, msg_data = M.fetch(i, '(RFC822)')
                    if typ != 'OK':
                        continue
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = decode_subject(msg)
                    body_text = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            disp = str(part.get("Content-Disposition", ""))
                            if ctype == "text/plain" and "attachment" not in disp:
                                try:
                                    body_text = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                except Exception:
                                    body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        try:
                            body_text = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                        except Exception:
                            body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

                    text = f"Subject: {subject}\n\n{body_text.strip()}"

                    try:
                        _invoke_agent(text)
                        # Mark as seen after success
                        M.store(i, '+FLAGS', '\\Seen')
                        logger.info("Email UID %s processed and marked seen", i)
                    except Exception as e:
                        logger.exception("Processing failed for email UID %s: %s", i, e)

                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down IMAP poller")
                break
            except Exception as e:
                logger.exception("IMAP polling error: %s", e)
                time.sleep(poll_secs)
    finally:
        try:
            M.logout()
        except Exception:
            pass


def main() -> None:
    # Auto-detect mode by env vars to keep CLI minimal
    if os.environ.get("SQS_QUEUE_URL"):
        run_sqs_worker()
    elif os.environ.get("KAFKA_TOPIC"):
        run_kafka_worker()
    elif os.environ.get("IMAP_HOST"):
        run_email_poller()
    else:
        logger.error(
            "No event source configured. Set one of: SQS_QUEUE_URL | KAFKA_TOPIC | IMAP_HOST (with IMAP_USERNAME/IMAP_PASSWORD)."
        )
        sys.exit(2)


if __name__ == "__main__":
    # Validate core API keys up-front for clearer failures
    if not os.environ.get("TAVILY_API_KEY"):
        logger.warning("TAVILY_API_KEY is not set; internet_search tool will fail")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY is not set; default model will fail")

    main()