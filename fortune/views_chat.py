from django.shortcuts import render, get_object_or_404, redirect
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from .models import ChatSession, ChatMessage, UserSajuProfile, FortuneResult
from .utils.chat_logic import build_system_prompt
from .utils.chat_ai import get_ai_response_stream
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def chat_main_page(request):
    """
    Render the main chat page.
    Lists user's profiles to start chat with.
    """
    profiles = UserSajuProfile.objects.filter(user=request.user)
    # Check for active session
    active_session = ChatSession.objects.filter(user=request.user, is_active=True).select_related('profile').first()
    
    return render(request, 'fortune/chat_main.html', {
        'profiles': profiles, 
        'active_session': active_session
    })

@login_required
@require_POST
def create_chat_session(request):
    """
    Create a new chat session. deactivates old one automatically via model save.
    """
    profile_id = request.POST.get('profile_id')
    # If using test client, profile_id is string '1'.
    profile = get_object_or_404(UserSajuProfile, id=profile_id, user=request.user)
    
    # Create new session
    session = ChatSession.objects.create(
        user=request.user,
        profile=profile,
        max_turns=10
    )
    
    logger.info(f"[Fortune] Action: CHAT_SESSION_CREATE, Status: SUCCESS, SessionID: {session.id}, User: {request.user.username}")
    
    # Render chat room partial or redirect
    return render(request, 'fortune/partials/chat_room.html', {'session': session})

@login_required
@require_POST
def send_chat_message(request):
    """
    Handle user message and stream AI response.
    """
    session_id = request.POST.get('session_id')
    content = request.POST.get('message', '').strip()
    
    if not content:
        return JsonResponse({'error': 'Message required'}, status=400)

    # Allow session lookup by user (security)
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
    except ChatSession.DoesNotExist:
         return JsonResponse({'error': 'Session not found'}, status=404)
    
    if not session.is_active:
        return JsonResponse({'error': 'Session expired'}, status=403)
        
    if session.current_turns >= session.max_turns:
        # Return partial for limit reached message?
        return render(request, 'fortune/partials/chat_message.html', {
            'message': {'role': 'system', 'content': '상담 횟수가 초과되었습니다.'}
        })
    
    # Save User Message
    user_msg_obj = ChatMessage.objects.create(session=session, role='user', content=content)
    session.current_turns += 1
    session.save()
    
    logger.info(f"[Fortune] Action: CHAT_MSG_USER, Status: RECEIVED, SessionID: {session.id}")

    # Build context
    natal_chart = session.profile.natal_chart or {}
    system_prompt = build_system_prompt(session.profile, natal_chart)
    
    # Fetch history excluding current user message
    previous_history = ChatMessage.objects.filter(session=session).exclude(id=user_msg_obj.id).order_by('created_at')

    # Create generators
    user_html = render_to_string('fortune/partials/chat_message.html', {'message': user_msg_obj})
    
    def stream_response():
        # 1. Yield User Message immediately
        yield user_html
        
        # 2. Yield AI Message start structure (manually constructed based on template style)
        yield """
<div class="flex flex-col space-y-2 mb-6 w-full animate-in fade-in slide-in-from-bottom-2 duration-500">
    <div class="flex items-start gap-3 self-start max-w-[90%] mr-auto">
        <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-white text-lg shadow-lg shrink-0 border border-white/20 relative top-1">
            🧙‍♂️
        </div>
        <div class="glass-card p-5 rounded-tl-none bg-white/5 text-gray-100 leading-relaxed shadow-lg backdrop-blur-md border border-white/10 relative group prose prose-invert prose-p:my-1 prose-headings:text-purple-300 prose-strong:text-yellow-400 break-words whitespace-pre-wrap">
"""
        # 3. Stream content
        # Note: get_ai_response_stream saves full message to DB at the end.
        for chunk in get_ai_response_stream(session, system_prompt, previous_history, content):
            yield chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
            
        # 4. Closing tags
        yield """
            <span class="text-[10px] text-gray-400 mt-2 block opacity-0 group-hover:opacity-100 transition-opacity absolute bottom-1 left-4">Now</span>
        </div>
    </div>
</div>
<script>
    // Auto-scroll to bottom after message complete
    document.getElementById('chat-messages-container').scrollTop = document.getElementById('chat-messages-container').scrollHeight;
</script>
"""

    return StreamingHttpResponse(stream_response(), content_type='text/html')

@login_required
@require_POST
def save_chat_to_history(request):
    """
    Save current chat session to FortuneResult.
    """
    session_id = request.POST.get('session_id')
    session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    
    # Format chat history to Markdown
    history = ChatMessage.objects.filter(session=session).order_by('created_at')
    markdown_content = f"# Saju Chat with {session.profile.person_name}\n\n"
    for msg in history:
        role = "Teacher" if msg.role == 'assistant' else "Student"
        content = msg.content.replace('\n', '\n> ') # Quote style
        markdown_content += f"**{role}**: {content}\n\n"
    
    FortuneResult.objects.create(
        user=request.user,
        mode='teacher',
        natal_chart=session.profile.natal_chart or {},
        result_text=markdown_content,
        target_date=None
    )
    
    logger.info(f"[Fortune] Action: CHAT_SAVE, Status: SUCCESS, SessionID: {session.id}")
    
    return JsonResponse({'status': 'success', 'message': 'Saved to history'})
