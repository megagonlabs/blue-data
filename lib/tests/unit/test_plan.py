import pytest
from blue_data.core.plan import Plan, PlanNode, PlanEdge, NodeType, NodeStatus


# ---------------------------------------------------------------------------
# PlanNode
# ---------------------------------------------------------------------------

def test_node_defaults():
    node = PlanNode(id="n1", type=NodeType.INPUT)
    assert node.status == NodeStatus.INITED
    assert node.label is None
    assert node.value is None
    assert node.properties == {}
    assert node.metadata == {}


def test_node_with_all_fields():
    node = PlanNode(
        id="n2",
        type=NodeType.OPERATOR,
        label="filter",
        value={"op": "gt", "threshold": 5},
        status=NodeStatus.EXECUTING,
        properties={"timeout": 30},
        metadata={"created_by": "test"},
    )
    assert node.id == "n2"
    assert node.type == NodeType.OPERATOR
    assert node.status == NodeStatus.EXECUTING
    assert node.properties["timeout"] == 30


# ---------------------------------------------------------------------------
# PlanEdge
# ---------------------------------------------------------------------------

def test_edge_defaults():
    edge = PlanEdge(source="a", target="b")
    assert edge.properties == {}


def test_edge_with_properties():
    edge = PlanEdge(source="a", target="b", properties={"weight": 1.0})
    assert edge.properties["weight"] == 1.0


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------

@pytest.fixture
def plan():
    p = Plan(id="p1", label="test plan")
    p.add_node(PlanNode(id="in", type=NodeType.INPUT, label="input"))
    p.add_node(PlanNode(id="op", type=NodeType.OPERATOR, label="transform"))
    p.add_node(PlanNode(id="out", type=NodeType.OUTPUT, label="output"))
    p.add_edge("in", "op")
    p.add_edge("op", "out")
    p.set_input("in")
    p.set_output("out")
    return p


def test_add_node(plan):
    assert "in" in plan.nodes
    assert "op" in plan.nodes
    assert "out" in plan.nodes


def test_get_node(plan):
    node = plan.get_node("op")
    assert node is not None
    assert node.label == "transform"


def test_get_node_missing(plan):
    assert plan.get_node("ghost") is None


def test_add_edge(plan):
    assert len(plan.edges) == 2
    assert plan.edges[0].source == "in"
    assert plan.edges[0].target == "op"


def test_set_input_output(plan):
    assert plan.input_node_id == "in"
    assert plan.output_node_id == "out"


def test_add_edge_with_properties():
    p = Plan(id="p2")
    p.add_node(PlanNode(id="a", type=NodeType.INPUT))
    p.add_node(PlanNode(id="b", type=NodeType.OUTPUT))
    edge = p.add_edge("a", "b", label="main_flow", weight=1.0)
    assert edge.properties["label"] == "main_flow"
    assert edge.properties["weight"] == 1.0


# ---------------------------------------------------------------------------
# Plan.to_dict()
# ---------------------------------------------------------------------------

def test_to_dict_structure(plan):
    d = plan.to_dict()
    assert d["id"] == "p1"
    assert d["label"] == "test plan"
    assert "in" in d["nodes"]
    assert len(d["edges"]) == 2
    assert d["input_node_id"] == "in"
    assert d["output_node_id"] == "out"


def test_to_dict_node_fields(plan):
    node_dict = plan.to_dict()["nodes"]["op"]
    assert node_dict["type"] == "OPERATOR"
    assert node_dict["status"] == "INITED"
    assert node_dict["label"] == "transform"


def test_to_dict_edge_fields(plan):
    edge = plan.to_dict()["edges"][0]
    assert edge["source"] == "in"
    assert edge["target"] == "op"
    assert "properties" in edge


def test_to_dict_empty_plan():
    p = Plan()
    d = p.to_dict()
    assert d["nodes"] == {}
    assert d["edges"] == []
    assert d["id"] is None


# ---------------------------------------------------------------------------
# NodeStatus / NodeType enums
# ---------------------------------------------------------------------------

def test_node_status_values():
    assert NodeStatus.INITED.value == "INITED"
    assert NodeStatus.EXECUTED.value == "EXECUTED"
    assert NodeStatus.FAILED.value == "FAILED"


def test_node_type_values():
    assert NodeType.INPUT.value == "INPUT"
    assert NodeType.OUTPUT.value == "OUTPUT"
    assert NodeType.OPERATOR.value == "OPERATOR"
