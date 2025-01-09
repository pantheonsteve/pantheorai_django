from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.embeddings import VertexAIEmbeddings
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from . import vertexai_service as vs



class State(TypedDict):
    messages: Annotated[list, add_messages]

class SimpleChatbot:

    def __init__(self):
        self.model = vs.llm
        self.builder = StateGraph(State)
        self.builder.add_node("chatbot", self.chatbot)  # Add the node with a key
        self.builder.add_edge(START, "chatbot")  # Connect START to the chatbot node using the key
        self.builder.add_edge("chatbot", END)  # Connect chatbot node to END using the key
        self.graph = self.builder.compile()


    def chatbot(self, state: State):
        answer = self.model.invoke(state["messages"])
        output = {"messages": [answer]}
        return output

    def ask(self, user_input):
        input_data = {"messages": [HumanMessage(user_input)]}
        all_messages = []

        for chunk in self.graph.stream(input_data):  # chunk represents the entire state after each node execution
            # Extract the current chatbot message from the state
            current_message = chunk.get("chatbot", {}).get("messages", [])
            if current_message:  # Check if there are any chatbot messages in this chunk.
                all_messages.extend(current_message)  #Extend using current_message

        return {"messages": all_messages}



class ChatbotWithMemory:

    def __init__(self, thread_id):
        self.model = vs.llm
        self.vector_store = vs.vector_store
        self.graph_builder = StateGraph(State)
        self.graph_builder.add_node("chatbot", self.chatbot)
        self.graph_builder.add_edge(START, "chatbot")
        self.graph = self.graph_builder.compile(checkpointer=MemorySaver())
        self.config = {"configurable": {"thread_id": thread_id}}

    def chatbot(self, state:State):
        answer = self.model.invoke(state["messages"])
        output = {"messages": [answer]}
        return output

    def ask(self, user_input):
        events = self.graph.stream(
            {"messages": [("user", user_input)]}, config = self.config, stream_mode="values"
        )
        messages = []
        for event in events:
            messages.append(event["messages"][-1])
        return messages[-1].content

class ChatbotFromVectorStore:

    def __init__(self, thread_id):
        self.model = vs.llm
        self.vector_store = vs.vector_store
        self.embeddings = vs.embedding_model
        self.graph_builder = StateGraph(State)
        self.graph_builder.add_node("chatbot", self.chatbot)
        self.graph_builder.add_edge(START, "chatbot")
        self.graph = self.graph_builder.compile(checkpointer=MemorySaver())
        self.config = {"configurable": {"thread_id": thread_id}}

    def retrieve_relevant_documents(self, query: str, k=50):
        docs = self.vector_store.similarity_search(query, k=k) # Use similarity_search with text
        return docs


    def chatbot(self, state:State):
        current_query = state["messages"][-1].content
        retrieved_docs = self.retrieve_relevant_documents(current_query)

        # Format retrieved documents for the prompt
        retrieved_content = "\n\n".join([doc.page_content for doc in retrieved_docs])

        # Updated Prompt with RAG
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="Answer the user's query using the provided context."),
            MessagesPlaceholder(variable_name="messages"),  # Existing conversation history
            SystemMessage(content=f"Context:\n{retrieved_content}"), # Include the retrieved documents
        ])

        messages = state["messages"]

        # Create a Chain or Runnable for your prompt and LLM
        chain = prompt | self.model
        answer = chain.invoke({"messages": messages})

        output = {"messages": messages + [answer]}  # Append the LLM's response
        return output

    def ask(self, user_input):
        events = self.graph.stream(
            {"messages": [("user", user_input)]}, config = self.config, stream_mode="values"
        )
        messages = []
        for event in events:
            messages.append(event["messages"][-1])
        return messages[-1].content