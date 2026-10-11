"""
Graph shape:

    check_flood -> check_earthquake -> combine_risk -> explain -> END

The final decision is always rule-based (from the two agents above).
The "explain" node only ever ADDS an optional, human-readable sentence
on top when online -- it can never change the alert decision itself.
"""

from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END

from agents.flood_agent import check_flood_risk
from agents.earthquake_agent import check_earthquake_risk, check_earthquake_risk_isolated
from agents.storm_agent import check_storm_risk
from agents.tsunami_agent import check_tsunami_risk
from config.settings import USE_LLM_EXPLANATION, GROQ_API_KEY


class AgentState(TypedDict):
    sensors: dict
    location: dict
    weather_context: Optional[dict]
    historical_earthquake: Optional[dict]
    online: bool

    flood_risk: str
    flood_reason: str
    earthquake_risk: str
    earthquake_reason: str
    storm_risk: str
    storm_hazard: str
    storm_reason: str
    tsunami_risk: str
    tsunami_reason: str

    overall_risk: str
    hazard_type: str
    reasoning: str


def _node_check_flood(state: AgentState) -> AgentState:
    result = check_flood_risk(state["sensors"], state.get("weather_context"))
    state["flood_risk"] = result["risk"]
    state["flood_reason"] = result["reason"]
    return state


def _node_check_earthquake(state: AgentState) -> AgentState:
    result = check_earthquake_risk(state["sensors"], state.get("historical_earthquake"))
    state["earthquake_risk"] = result["risk"]
    state["earthquake_reason"] = result["reason"]
    return state


def _node_check_storm(state: AgentState) -> AgentState:
    result = check_storm_risk(state["sensors"], state.get("weather_context"))
    state["storm_risk"] = result["risk"]
    state["storm_hazard"] = result["hazard"]
    state["storm_reason"] = result["reason"]
    return state


def _node_check_tsunami(state: AgentState) -> AgentState:
    result = check_tsunami_risk(state["sensors"])
    state["tsunami_risk"] = result["risk"]
    state["tsunami_reason"] = result["reason"]
    return state


def _node_combine_risk(state: AgentState) -> AgentState:
    if state["tsunami_risk"] == "high":
        state["overall_risk"] = "high"
        state["hazard_type"] = "tsunami"
        state["reasoning"] = state["tsunami_reason"]
    elif state["earthquake_risk"] == "high":
        state["overall_risk"] = "high"
        state["hazard_type"] = "earthquake"
        state["reasoning"] = state["earthquake_reason"]
    elif state["storm_risk"] == "high":
        state["overall_risk"] = "high"
        state["hazard_type"] = state["storm_hazard"]
        state["reasoning"] = state["storm_reason"]
    elif state["flood_risk"] == "high":
        state["overall_risk"] = "high"
        state["hazard_type"] = "flood"
        state["reasoning"] = state["flood_reason"]
    else:
        state["overall_risk"] = "low"
        state["hazard_type"] = "none"
        state["reasoning"] = "all signals normal"
    return state


def _node_explain(state: AgentState) -> AgentState:
    """Optional online explanation. It only enriches the stored reasoning text;
    the rule-based risk decision has already been made and cannot be changed here."""
    if not (USE_LLM_EXPLANATION and state["online"] and GROQ_API_KEY):
        return state

    try:
        from groq import Groq  # imported lazily so the app runs without this package offline
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{
                "role": "user",
                "content": (
                    f"In one short sentence, explain this disaster alert for a public "
                    f"notification: risk={state['overall_risk']}, hazard={state['hazard_type']}, "
                    f"reason={state['reasoning']}. Do not add facts or change the risk level."
                ),
            }],
            timeout=4,
        )
        state["reasoning"] = resp.choices[0].message.content.strip()
    except Exception:
        pass
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("check_flood", _node_check_flood)
    graph.add_node("check_earthquake", _node_check_earthquake)
    graph.add_node("check_storm", _node_check_storm)
    graph.add_node("check_tsunami", _node_check_tsunami)
    graph.add_node("combine_risk", _node_combine_risk)
    graph.add_node("explain", _node_explain)

    graph.add_edge(START, "check_flood")
    graph.add_edge("check_flood", "check_earthquake")
    graph.add_edge("check_earthquake", "check_storm")
    graph.add_edge("check_storm", "check_tsunami")
    graph.add_edge("check_tsunami", "combine_risk")
    graph.add_edge("combine_risk", "explain")
    graph.add_edge("explain", END)

    return graph.compile()


_compiled_graph = build_graph()


def run_agent(
    sensors: dict,
    location: dict,
    weather_context: dict | None,
    online: bool,
    historical_earthquake: dict | None = None,
) -> AgentState:
    initial_state: AgentState = {
        "sensors": sensors,
        "location": location,
        "weather_context": weather_context,
        "historical_earthquake": historical_earthquake,
        "online": online,
        "flood_risk": "",
        "flood_reason": "",
        "earthquake_risk": "",
        "earthquake_reason": "",
        "storm_risk": "",
        "storm_hazard": "",
        "storm_reason": "",
        "tsunami_risk": "",
        "tsunami_reason": "",
        "overall_risk": "",
        "hazard_type": "",
        "reasoning": "",
    }
    return _compiled_graph.invoke(initial_state)


def run_agent_isolated(
    sensors: dict,
    location: dict,
    weather_context: dict | None,
    online: bool,
) -> AgentState:
    """
    Same shape as run_agent, but for the Testing tab: scores the earthquake
    check against a synthetic quiet baseline (check_earthquake_risk_isolated)
    instead of this process's shared rolling vibration history, so a
    manually entered value gives the same, repeatable verdict every time
    it's tried -- not run through the compiled graph, since that graph is
    wired to the shared-history check and swapping nodes per-call isn't
    worth building; this is the same four steps run directly instead.
    """
    state: AgentState = {
        "sensors": sensors,
        "location": location,
        "weather_context": weather_context,
        "historical_earthquake": None,
        "online": online,
        "flood_risk": "",
        "flood_reason": "",
        "earthquake_risk": "",
        "earthquake_reason": "",
        "storm_risk": "",
        "storm_hazard": "",
        "storm_reason": "",
        "tsunami_risk": "",
        "tsunami_reason": "",
        "overall_risk": "",
        "hazard_type": "",
        "reasoning": "",
    }
    state = _node_check_flood(state)

    quake_result = check_earthquake_risk_isolated(sensors["vibration_g"])
    state["earthquake_risk"] = quake_result["risk"]
    state["earthquake_reason"] = quake_result["reason"]

    state = _node_check_storm(state)
    state = _node_check_tsunami(state)

    state = _node_combine_risk(state)
    state = _node_explain(state)
    return state
