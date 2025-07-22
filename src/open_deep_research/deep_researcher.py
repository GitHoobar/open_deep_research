from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, get_buffer_string, filter_messages
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command
import asyncio
from typing import Literal
from .configuration import (
    Configuration, 
)
from .state import (
    AgentState,
    AgentInputState,
    SupervisorState,
    AnalyzerState,
    ClarifyWithUser,
    DesignDocQuery,
    AnalyzeRepository,
    AnalysisComplete,
    AnalyzerOutputState
)
from .prompts import (
    clarify_with_user_instructions,
    transform_messages_into_design_query_prompt,
    repository_analysis_system_prompt,
    compress_analysis_system_prompt,
    compress_analysis_simple_human_message,
    final_design_doc_generation_prompt,
    lead_analyzer_prompt
)
from .utils import (
    get_today_str,
    is_token_limit_exceeded,
    get_model_token_limit,
    get_all_tools,
    remove_up_to_last_ai_message,
    get_api_key_for_model,
    get_notes_from_tool_calls,
    analyze_repository_structure
)

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)

async def clarify_with_user(state: AgentState, config: RunnableConfig) -> Command[Literal["write_design_brief", "__end__"]]:
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        return Command(goto="write_design_brief")
    messages = state["messages"]
    model_config = {
        "model": configurable.analysis_model,
        "max_tokens": configurable.analysis_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.analysis_model, config),
        "tags": ["langsmith:nostream"]
    }
    model = configurable_model.with_structured_output(ClarifyWithUser).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(model_config)
    response = await model.ainvoke([HumanMessage(content=clarify_with_user_instructions.format(messages=get_buffer_string(messages), date=get_today_str()))])
    if response.need_clarification:
        return Command(goto=END, update={"messages": [AIMessage(content=response.question)]})
    else:
        return Command(goto="write_design_brief", update={"messages": [AIMessage(content=response.verification)]})


async def write_design_brief(state: AgentState, config: RunnableConfig)-> Command[Literal["analysis_supervisor"]]:
    configurable = Configuration.from_runnable_config(config)
    analysis_model_config = {
        "model": configurable.analysis_model,
        "max_tokens": configurable.analysis_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.analysis_model, config),
        "tags": ["langsmith:nostream"]
    }
    analysis_model = configurable_model.with_structured_output(DesignDocQuery).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(analysis_model_config)
    response = await analysis_model.ainvoke([HumanMessage(content=transform_messages_into_design_query_prompt.format(
        messages=get_buffer_string(state.get("messages", [])),
        date=get_today_str()
    ))])
    
    # Set up the repository for analysis
    repo_setup_result = await analyze_repository_structure(response.repo_url, config)
    
    return Command(
        goto="analysis_supervisor", 
        update={
            "repo_url": response.repo_url,
            "design_brief": response.design_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=lead_analyzer_prompt.format(
                        date=get_today_str(),
                        max_concurrent_analysis_units=configurable.max_concurrent_analysis_units
                    )),
                    HumanMessage(content=f"Repository: {response.repo_url}\n\nDesign Brief: {response.design_brief}\n\nRepo Setup: {repo_setup_result}")
                ]
            }
        }
    )


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    configurable = Configuration.from_runnable_config(config)
    analysis_model_config = {
        "model": configurable.analysis_model,
        "max_tokens": configurable.analysis_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.analysis_model, config),
        "tags": ["langsmith:nostream"]
    }
    lead_analyzer_tools = [AnalyzeRepository, AnalysisComplete]
    analysis_model = configurable_model.bind_tools(lead_analyzer_tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(analysis_model_config)
    supervisor_messages = state.get("supervisor_messages", [])
    response = await analysis_model.ainvoke(supervisor_messages)
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "analysis_iterations": state.get("analysis_iterations", 0) + 1
        }
    )


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    analysis_iterations = state.get("analysis_iterations", 0)
    most_recent_message = supervisor_messages[-1]
    # Exit Criteria
    # 1. We have exceeded our max guardrail analysis iterations
    # 2. No tool calls were made by the supervisor
    # 3. The most recent message contains an AnalysisComplete tool call and there is only one tool call in the message
    exceeded_allowed_iterations = analysis_iterations >= configurable.max_analyzer_iterations
    no_tool_calls = not most_recent_message.tool_calls
    analysis_complete_tool_call = any(tool_call["name"] == "AnalysisComplete" for tool_call in most_recent_message.tool_calls)
    if exceeded_allowed_iterations or no_tool_calls or analysis_complete_tool_call:
        return Command(
            goto=END,
            update={
                "analysis_notes": get_notes_from_tool_calls(supervisor_messages),
                "repo_url": state.get("repo_url", ""),
                "design_brief": state.get("design_brief", "")
            }
        )
    # Otherwise, conduct analysis and gather results.
    try:
        all_analyze_repository_calls = [tool_call for tool_call in most_recent_message.tool_calls if tool_call["name"] == "AnalyzeRepository"]
        analyze_repository_calls = all_analyze_repository_calls[:configurable.max_concurrent_analysis_units]
        overflow_analyze_repository_calls = all_analyze_repository_calls[configurable.max_concurrent_analysis_units:]
        analyzer_system_prompt = repository_analysis_system_prompt.format(date=get_today_str())
        coros = [
            analyzer_subgraph.ainvoke({
                "analyzer_messages": [
                    SystemMessage(content=analyzer_system_prompt),
                    HumanMessage(content=tool_call["args"]["analysis_topic"])
                ],
                "analysis_topic": tool_call["args"]["analysis_topic"]
            }, config) 
            for tool_call in analyze_repository_calls
        ]
        tool_results = await asyncio.gather(*coros)
        tool_messages = [ToolMessage(
                            content=observation.get("compressed_analysis", "Error synthesizing analysis report: Maximum retries exceeded"),
                            name=tool_call["name"],
                            tool_call_id=tool_call["id"]
                        ) for observation, tool_call in zip(tool_results, analyze_repository_calls)]
        # Handle any tool calls made > max_concurrent_analysis_units
        for overflow_analyze_repository_call in overflow_analyze_repository_calls:
            tool_messages.append(ToolMessage(
                content=f"Error: Did not run this analysis as you have already exceeded the maximum number of concurrent analysis units. Please try again with {configurable.max_concurrent_analysis_units} or fewer analysis units.",
                name="AnalyzeRepository",
                tool_call_id=overflow_analyze_repository_call["id"]
            ))
        raw_analysis_concat = "\n".join(["\n".join(observation.get("raw_analysis", [])) for observation in tool_results])
        return Command(
            goto="supervisor",
            update={
                "supervisor_messages": tool_messages,
                "raw_analysis": [raw_analysis_concat]
            }
        )
    except Exception as e:
        if is_token_limit_exceeded(e, configurable.analysis_model):
            print(f"Token limit exceeded while analyzing: {e}")
        else:
            print(f"Other error in analysis phase: {e}")
        return Command(
            goto=END,
            update={
                "analysis_notes": get_notes_from_tool_calls(supervisor_messages),
                "repo_url": state.get("repo_url", ""),
                "design_brief": state.get("design_brief", "")
            }
        )


supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge(START, "supervisor")
supervisor_subgraph = supervisor_builder.compile()


async def analyzer(state: AnalyzerState, config: RunnableConfig) -> Command[Literal["analyzer_tools"]]:
    configurable = Configuration.from_runnable_config(config)
    analyzer_messages = state.get("analyzer_messages", [])
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError("No tools found to conduct analysis: Please configure GitHub access token and repository URL.")
    analysis_model_config = {
        "model": configurable.analysis_model,
        "max_tokens": configurable.analysis_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.analysis_model, config),
        "tags": ["langsmith:nostream"]
    }
    analysis_model = configurable_model.bind_tools(tools).with_retry(stop_after_attempt=configurable.max_structured_output_retries).with_config(analysis_model_config)
    # NOTE: Need to add fault tolerance here.
    response = await analysis_model.ainvoke(analyzer_messages)
    return Command(
        goto="analyzer_tools",
        update={
            "analyzer_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )


async def execute_tool_safely(tool, args, config):
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def analyzer_tools(state: AnalyzerState, config: RunnableConfig) -> Command[Literal["analyzer", "compress_analysis"]]:
    configurable = Configuration.from_runnable_config(config)
    analyzer_messages = state.get("analyzer_messages", [])
    most_recent_message = analyzer_messages[-1]
    # Early Exit Criteria: No tool calls were made by the analyzer
    if not most_recent_message.tool_calls:
        return Command(
            goto="compress_analysis",
        )
    # Otherwise, execute tools and gather results.
    tools = await get_all_tools(config)
    tools_by_name = {tool.name if hasattr(tool, "name") else tool.get("name", "github_analysis"):tool for tool in tools}
    tool_calls = most_recent_message.tool_calls
    coros = [execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) for tool_call in tool_calls]
    observations = await asyncio.gather(*coros)
    tool_outputs = [ToolMessage(
                        content=observation,
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"]
                    ) for observation, tool_call in zip(observations, tool_calls)]
    
    # Late Exit Criteria: We have exceeded our max guardrail tool call iterations or the most recent message contains an AnalysisComplete tool call
    # These are late exit criteria because we need to add ToolMessages
    if state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls or any(tool_call["name"] == "AnalysisComplete" for tool_call in most_recent_message.tool_calls):
        return Command(
            goto="compress_analysis",
            update={
                "analyzer_messages": tool_outputs,
            }
        )
    return Command(
        goto="analyzer",
        update={
            "analyzer_messages": tool_outputs,
        }
    )


async def compress_analysis(state: AnalyzerState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    synthesis_attempts = 0
    synthesizer_model = configurable_model.with_config({
        "model": configurable.compression_model,
        "max_tokens": configurable.compression_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.compression_model, config),
        "tags": ["langsmith:nostream"]
    })
    analyzer_messages = state.get("analyzer_messages", [])
    # Update the system prompt to now focus on compression rather than analysis.
    analyzer_messages[0] = SystemMessage(content=compress_analysis_system_prompt.format(date=get_today_str()))
    analyzer_messages.append(HumanMessage(content=compress_analysis_simple_human_message))
    while synthesis_attempts < 3:
        try:
            response = await synthesizer_model.ainvoke(analyzer_messages)
            return {
                "compressed_analysis": str(response.content),
                "raw_analysis": ["\n".join([str(m.content) for m in filter_messages(analyzer_messages, include_types=["tool", "ai"])])]
            }
        except Exception as e:
            synthesis_attempts += 1
            if is_token_limit_exceeded(e, configurable.analysis_model):
                analyzer_messages = remove_up_to_last_ai_message(analyzer_messages)
                print(f"Token limit exceeded while synthesizing: {e}. Pruning the messages to try again.")
                continue         
            print(f"Error synthesizing analysis report: {e}")
    return {
        "compressed_analysis": "Error synthesizing analysis report: Maximum retries exceeded",
        "raw_analysis": ["\n".join([str(m.content) for m in filter_messages(analyzer_messages, include_types=["tool", "ai"])])]
    }


analyzer_builder = StateGraph(AnalyzerState, output=AnalyzerOutputState, config_schema=Configuration)
analyzer_builder.add_node("analyzer", analyzer)
analyzer_builder.add_node("analyzer_tools", analyzer_tools)
analyzer_builder.add_node("compress_analysis", compress_analysis)
analyzer_builder.add_edge(START, "analyzer")
analyzer_builder.add_edge("compress_analysis", END)
analyzer_subgraph = analyzer_builder.compile()


async def final_design_doc_generation(state: AgentState, config: RunnableConfig):
    analysis_notes = state.get("analysis_notes", [])
    cleared_state = {"analysis_notes": {"type": "override", "value": []},}
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_design_doc_model,
        "max_tokens": configurable.final_design_doc_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.analysis_model, config),
    }
    
    findings = "\n".join(analysis_notes)
    max_retries = 3
    current_retry = 0
    while current_retry <= max_retries:
        final_design_doc_prompt = final_design_doc_generation_prompt.format(
            repo_url=state.get("repo_url", ""),
            design_brief=state.get("design_brief", ""),
            findings=findings,
            date=get_today_str()
        )
        try:
            final_design_doc = await configurable_model.with_config(writer_model_config).ainvoke([HumanMessage(content=final_design_doc_prompt)])
            return {
                "final_design_doc": final_design_doc.content, 
                "messages": [final_design_doc],
                **cleared_state
            }
        except Exception as e:
            if is_token_limit_exceeded(e, configurable.final_design_doc_model):
                if current_retry == 0:
                    model_token_limit = get_model_token_limit(configurable.final_design_doc_model)
                    if not model_token_limit:
                        return {
                            "final_design_doc": f"Error generating final design document: Token limit exceeded, however, we could not determine the model's maximum context length. Please update the model map in deep_researcher/utils.py with this information. {e}",
                            **cleared_state
                        }
                    findings_token_limit = model_token_limit * 4
                else:
                    findings_token_limit = int(findings_token_limit * 0.9)
                print("Reducing the chars to", findings_token_limit)
                findings = findings[:findings_token_limit]
                current_retry += 1
            else:
                # If not a token limit exceeded error, then we just throw an error.
                return {
                    "final_design_doc": f"Error generating final design document: {e}",
                    **cleared_state
                }
    return {
        "final_design_doc": "Error generating final design document: Maximum retries exceeded",
        "messages": [final_design_doc],
        **cleared_state
    }

design_doc_agent_builder = StateGraph(AgentState, input=AgentInputState, config_schema=Configuration)
design_doc_agent_builder.add_node("clarify_with_user", clarify_with_user)
design_doc_agent_builder.add_node("write_design_brief", write_design_brief)
design_doc_agent_builder.add_node("analysis_supervisor", supervisor_subgraph)
design_doc_agent_builder.add_node("final_design_doc_generation", final_design_doc_generation)
design_doc_agent_builder.add_edge(START, "clarify_with_user")
design_doc_agent_builder.add_edge("analysis_supervisor", "final_design_doc_generation")
design_doc_agent_builder.add_edge("final_design_doc_generation", END)

design_doc_agent = design_doc_agent_builder.compile()