from langchain_google_vertexai import (
    VectorSearchVectorStore,
    VectorSearchVectorStoreDatastore,
    ChatVertexAI,
    VertexAIEmbeddings
)
from google.cloud import aiplatform
from langchain_core.documents import Document
from langchain_google_community import (
    VertexAIMultiTurnSearchRetriever,
    VertexAISearchRetriever
)

PROJECT_ID="pantheon-sales"
REGION="us-central1"

#GCS Bucket for embedding and indexing
STAGING_BUCKET="gong_vector_data"
STAGING_BUCKET_URI = f"gs://{STAGING_BUCKET}"

# Vector Search Index Constants
DISPLAY_NAME = "gong_vectorsearch_index"
DEPLOYED_INDEX_ID = "5962515217987403776"

embedding_model = VertexAIEmbeddings(model_name="textembedding-gecko@003")
#embedding_model = VertexAIEmbeddings()
DIMENSIONS = 768

# Instantiate aiplatform.init()
aiplatform.init(project=PROJECT_ID, location=REGION, staging_bucket=STAGING_BUCKET_URI)

# Instantiate Vector Search Indexes
gong_vectorsearch_index = aiplatform.MatchingEngineIndex(f"{DEPLOYED_INDEX_ID}")
gong_vectorsearch_index_endpoint = aiplatform.MatchingEngineIndexEndpoint("2332279666791940096")

# Initialize the parent class (VectorSearchVectorStore)
# Provide the required arguments to from_components()
vector_store = VectorSearchVectorStore.from_components(  # Call __init__ on the class
    project_id=PROJECT_ID,
    region=REGION,
    gcs_bucket_name=STAGING_BUCKET,
    index_id=gong_vectorsearch_index.name,
    endpoint_id=gong_vectorsearch_index_endpoint.name,
    embedding=embedding_model,
    stream_update=True,
    )

retriever = VertexAISearchRetriever(
    project_id=PROJECT_ID,
    location_id=REGION,
    data_store_id=gong_vectorsearch_index.name,
    max_documents=3,
)

# Initialize VertexAI LLM and Embeddings
llm = ChatVertexAI(  # Should already be "gemini-1.5-flash" but make sure it's consistent.
    model_name="gemini-1.5-flash",  # Corrected model name
    max_output_tokens=1024,
    temperature=0.1,
    streaming=True,
)

