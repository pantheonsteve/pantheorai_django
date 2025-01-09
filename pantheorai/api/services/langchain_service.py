from langchain import hub
from langchain_core.messages import SystemMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_core.output_parsers import StrOutputParser
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate  # Make absolutely sure this is present
from langchain_core.runnables import RunnableMap, RunnablePassthrough, RunnableLambda
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, MessagesState, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
import logging
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (
    Namespace,
    NumericNamespace,
)
from pydantic import BaseModel, Field
from typing import Annotated, Dict, Literal, List, Sequence
from typing_extensions import List, TypedDict
from . import vertexai_service as vs
from . import gong_gcs_service as gcs
from .prompts.summarization import call_summary_1
from .prompts.products_services import simplified_taxonomy

logger = logging.getLogger(__name__)

# Constants
gcs = gcs.GongGCS()
# Chat memory
llm = vs.llm
embedding_model = vs.embedding_model
vector_store = vs.vector_store

class State(TypedDict):
    messages: Annotated[list, add_messages]

class QueryProcessor:
    def __init__(self):
        # Initialize services and models
        self.llm = vs.llm
        self.embeddings = vs.embedding_model
        self.vector_store = vs.vector_store

        # Initialize memory saver and compile graph
        self.state = {"messages": []}

        # Default configuration
        self.config = {
            "thread_id": "unique_thread_id",
            "checkpoint_ns": "namespace_for_checkpoints",
            "checkpoint_id": "unique_checkpoint_id",
        }
        # Persistent state to retain conversation history
        self.state = {"messages": []}

    def summarize_call(self, call_id: str):
        try:
            retriever = self.vector_store.as_retriever(
                search_kwargs={"k": 200, "filter": [Namespace(name="call_id", allow_tokens=[call_id])]}
            )

            call_transcript_result = gcs.call_transcript(call_id)
            if not call_transcript_result:
                logger.warning(f"No transcript found for call_id: {call_id}")
                return None

                # Pull the raw call transcript from Google Cloud Storage (the output is a dict
                # and "transcript" is one of the items)
            transcript = call_transcript_result["transcript"]
            # This pulls the prompt format with {transcript} as a placeholder at the end of the prompt.
            # See ./prompts/summarization.py for the prompt

            # Create a Document object from the transcript
            documents = [
                Document(page_content=transcript, metadata={"call_id": call_id})
            ]

            # Define the prompt template
            #prompt_template = ChatPromptTemplate.from_messages([
            #    ("system", "You are a helpful assistant trained to summarize call transcripts."),
            #    ("human", "Here is a call transcript to summarize:\n\n {context}\n\nPlease provide a summary using this format: {summary_format}"),
            #    ("ai", "{summary}")
            #])

            prompt = ChatPromptTemplate.from_template(call_summary_1())
            chain = create_stuff_documents_chain(llm, prompt)
            result = chain.invoke({"context": documents})



            # Define the runnable for a summary format
            #summary_format_runnable = RunnableLambda(lambda _: call_summary_1())


            # Define the LCEL pipeline
            #chain = RunnableMap({
            #    "context": lambda _: doc.page_content,
            #    "summary_format": summary_format_runnable,
            #})

            #inputs = chain.invoke({})

            # execute the chain and retrieve the response
            #response = prompt_template.invoke({
             #   "context": inputs["context"],
             #   "summary_format": inputs["summary_format"] # Retrieve the summary format dynamically
            #})

            #result = response.messages[-1].content

            return result

        except Exception as e:
            logger.error(f"Error in summarize_call: {e}", exc_info=True) # Log the full exception
            return None  # Or handle the error as needed



    def call_simplified_taxonomy(self, call_id: str):
        '''
        Takes in the simplified taxonomy as an argument, searches through a call,
        and highlights any relevant points from the call related to the simplified taxonomy.
        '''
        vector_store = vs.vector_store
        retriever = vector_store.as_retriever()
        filters = [Namespace(name="call_id", allow_tokens=[call_id])]
        retriever.search_kwargs = {"k":200, "filter": filters}

        call_transcript_result = gcs.call_transcript(call_id)
        if call_transcript_result:
            transcript = call_transcript_result['transcript']
            query = f'''
            The Pantheon simplified taxonomy serves as a reference for categorizing and understanding customer feedback and concerns within this specific domain.
            Additionally, it assigns ownership to different teams (e.g., User Management, Monetization & Billing) for addressing these areas.
            Overall, the purpose appears to be to provide a structured framework for capturing, analyzing, and acting upon customer insights related to business, finance, and communication aspects.

            Here is the complete Pantheon simplified taxonomy:
            {simplified_taxonomy(transcript)}

            Now that you understand the simlified taxonomy, your task is to analyze the following call transcript, highlighting any areas in the call that are relevant to the Pantheon simplified taxonomy.

            If the topic from the taxonomy is covered on the call, you are to note it and describe where it was discussed. If it was not discussed on the call, you are to omit mention of it.
            {transcript}
            '''
            rag_pipeline = RetrievalQA.from_chain_type(
                llm=llm, chain_type="stuff", retriever=retriever
            )
            response = rag_pipeline({"query": query})
            return response["result"]
        else:
            logger.error(f"Error: Could not retrieve transcript for call_id: {call_id}")
            return None  # Or handle the error as needed

    def summarize_opp(self, opp_id: str):
        retriever = vs.vector_store.as_retriever()
        query = f'''
        Summarize the opportunity to date.
        The opportunity consists of multiple transcripts to calls related to this opportunity.
        Include a list of people who have been involved in the opportunity, their roles, requirements, and sentiment.
        Summarize the conversation that has taken place in the opp.

        '''
        rag_pipeline = RetrievalQA.from_chain_type(
            llm=llm, chain_type="stuff", retriever=retriever
        )
        response = rag_pipeline({"query": query})
        return response["result"]
