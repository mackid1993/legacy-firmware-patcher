class ResourceObject:
    def __init__(self, *args, **kwargs):
        self.data = b''
        self.is_system = False
        self.name = ''
        self.resource_id = 0
    def __setstate__(self, state):
        self.__dict__.update(state)
