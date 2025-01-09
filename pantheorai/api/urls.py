from django.urls import path
from django.http import HttpResponse
from .views import ChatView, GongSummaryView, OpportunityView

def api_placeholder(request):
    return HttpResponse("API Placeholder: This is the API endpoint.")

urlpatterns = [
    path('test/', api_placeholder),
    path('chat/', ChatView.as_view(), name='chat'),
    path('gong/<str:id>/', GongSummaryView.as_view(), name='gong'),
    path('opportunity/<str:opp_id>/', OpportunityView.as_view(), name='opportunity')
]