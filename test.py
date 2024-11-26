from flask import Flask, request

app = Flask(__name__)


@app.route("/sms", methods=["POST"])
def receive_sms():
    incoming_message = request.form.get("Body")  # Get the message body
    sender = request.form.get("From")  # Get the sender's phone number
    print(f"Message from {sender}: {incoming_message}")
    return "Message received", 200

if __name__ == "__main__":
    app.run(port=5000)