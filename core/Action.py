class Action:
    def __init__(self, type, l, r):
        self.type = type
        self.l = l
        self.r = r


class ReplaceAction(Action):
    def __init__(self, l, r, replace_data):
        super().__init__("replace", l, r)
        self.replace_data = replace_data


class RemoveAction(Action):
    def __init__(self, l, r):
        super().__init__("remove", l, r)
