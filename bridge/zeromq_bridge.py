import zmq

class ZeroMQBridge:
    def __init__(self):
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://*:5555")

    def send_signal(self, signal):
        self.publisher.send_json(signal)