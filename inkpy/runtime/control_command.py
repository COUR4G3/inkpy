from enum import Enum

from .object import InkObject


class ControlCommand(InkObject):
    class CommandType(Enum):
        NotSet = -1
        EvalStart = "ev"
        EvalOutput = "out"
        EvalEnd = "/ev"
        Duplicate = "du"
        PopEvaluatedValue = "pop"
        PopFunction = "~ret"
        PopTunnel = "->->"
        BeginString = "str"
        EndString = "/str"
        NoOp = "nop"
        ChoiceCount = "choiceCnt"
        Turns = "turn"
        TurnsSince = "turns"
        ReadCount = "readc"
        Random = "rnd"
        SeedRandom = "srnd"
        VisitIndex = "visit"
        SequenceShuffleIndex = "seq"
        StartThread = "thread"
        Done = "done"
        End = "end"
        ListFromInt = "listInt"
        ListRange = "range"
        ListRandom = "lrnd"
        BeginTag = "#"
        EndTag = "/#"

    COMMAND_TYPE_TO_STRING = {t: t.value for t in CommandType}
    STRING_TO_COMMAND_TYPE = {t.value: t for t in CommandType}

    def __init__(self, type: CommandType | str = CommandType.NotSet):
        if isinstance(type, str):
            type = self.STRING_TO_COMMAND_TYPE[type]
        self.type = type

        super().__init__()

    def __repr__(self):
        return f"{self.type.name} '{self.type.value}'"

    @classmethod
    def exists_with_name(cls, type: str):
        return type in cls.STRING_TO_COMMAND_TYPE

    @classmethod
    def PopFunction(cls):
        return cls(ControlCommand.CommandType.PopFunction)

    @classmethod
    def PopTunnel(cls):
        return cls(ControlCommand.CommandType.PopTunnel)
