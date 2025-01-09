from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from langchain_core.messages import AIMessage
from .services import langchain_service as ls
from .services import gong_gcs_service as gcs
from .services import chatbot_service as cs
import logging
import uuid

qp = ls.QueryProcessor()

def generate_session_id():
    return str(uuid.uuid4())

session_id = generate_session_id()
chatbot = cs.ChatbotFromVectorStore(session_id)

logger = logging.getLogger(__name__)

class ChatView(APIView):
    #@csrf_exempt
    #@never_cache

    def post(self, request):
        # Extract the message and conversation state from the request body
        system_prompt = '''
        Your task is to respond to me questions in Spanish.
        '''
        message = request.data.get("message")

        if not message:
           return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Received message: {message}")
            #This is the chatbot function.  It takes the message and the conversation state and returns a response.
            response = chatbot.ask(message)
            logger.info(f"Generated response: {response}")

            # Validate and process the response
            if response:
                # Extract the content of the last AI message
                return Response({"content": response}, status=status.HTTP_200_OK)  # Return the content directly
            else:
                logger.error(f"Empty or invalid response: {response}")
                return Response({"error": "Empty or invalid response"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return Response(
                {"error": f"An internal error occurred. Details: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GongSummaryView(APIView):
    renderer_classes = [JSONRenderer]

    @method_decorator(csrf_exempt)
    @method_decorator(never_cache)
    def get(self, request, id=None): # Gong call ID as parameter
        if not id:
            return Response({"error": "ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            gcs_service = gcs.GongGCS()
            transcript = gcs_service.call_transcript(id)
            summary = qp.summarize_call(id)
            if summary:
                return Response({
                    "title": transcript['title'],
                    "started": transcript['started'],
                    "url": transcript['url'],
                    "call_id": id,
                    "transcript": transcript['transcript'],
                    "summary": summary
                    }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Summary not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving transcript: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GongTranscriptView(APIView):
    def get(self, request, id):  # Correct signature
        try:
            gcs_service = gcs.GongGCS()
            transcript = gcs_service.call_transcript(id) # Use kwargs consistently
            if transcript:
                return Response({"call_id": self.kwargs['id'], "transcript": transcript}, status=status.HTTP_200_OK) # Use kwargs consistently
            else:
                return Response({"error": "Transcript not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving transcript: {e}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OpportunityView(APIView):
    def get(self, request, *args, **kwargs):
        opp_id = kwargs.get('opp_id')

        if opp_id:
            try:
                gcs_service = gcs.GongGCS() # Assuming GongGCS is a custom class
                opportunity = gcs_service.get_calls_by_opp(opp_id)


                if opportunity:  # Check if opportunity data was retrieved successfully
                    full_opp_transcript = gcs_service.collate_transcripts(opportunity['call_ids'])
                    opportunity['transcript'] = full_opp_transcript

                    summary = ls.summarize_opp(opp_id) # Use opp_id here, not id
                    if summary:
                        opportunity['summary'] = summary
                    return Response(opportunity, status=status.HTTP_200_OK)
                else:
                     return Response({"message": "Opportunity not found"}, status=status.HTTP_404_NOT_FOUND)

            except Exception as e: # Broad except clause for unexpected errors
                logger.error(f"Error retrieving calls or generating summary for opportunity {opp_id}: {e}", exc_info=True) # Log the error with more details
                return Response({"message": "An error occurred while fetching the summary."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # More appropriate for server-side issues
        else:
            return Response({"message": "opp_id is required"}, status=status.HTTP_400_BAD_REQUEST)