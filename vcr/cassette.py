import yaml


class Cassette(object):
    def __init__(self):
        self.requests = []
        self.responses = []

    def serialize(self):
        return yaml.dump([{
            'request': req,
            'response': res,
        }  for req,res in zip(self.requests,self.responses)])



