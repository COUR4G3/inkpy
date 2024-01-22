from enum import Enum

from .object import InkObject


class ControlCommand(InkObject):
    class CommandType(Enum):
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

    def __init__(self, type: CommandType):
        self.type = type

    @staticmethod
    def PopFunction() -> "ControlCommand":
        return ControlCommand(ControlCommand.CommandType.PopFunction)

    @staticmethod
    def PopTunnel() -> "ControlCommand":
        return ControlCommand(ControlCommand.CommandType.PopTunnel)
