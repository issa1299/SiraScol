from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q

from .models import Message


@login_required
def message_inbox(request):
    inbox = Message.objects.filter(recipient=request.user).select_related('sender').order_by('-sent_at')[:100]
    sent = Message.objects.filter(sender=request.user).select_related('recipient').order_by('-sent_at')[:50]
    return render(request, 'communication/messages.html', {
        'inbox': inbox,
        'sent': sent,
    })


@login_required
def message_compose(request):
    users = User.objects.filter(is_active=True).order_by('username')
    if request.method == 'POST':
        to_id = request.POST.get('recipient')
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        if not to_id or not subject or not body:
            messages.error(request, 'Destinataire, sujet et message requis.')
            return redirect('communication:compose')
        recipient = get_object_or_404(User, pk=to_id, is_active=True)
        Message.objects.create(
            sender=request.user,
            recipient=recipient,
            subject=subject,
            body=body,
            attachment=request.FILES.get('attachment'),
        )
        messages.success(request, 'Message envoyé.')
        return redirect('communication:inbox')
    ctx = {'users': users, 'form_action': request.path}
    if request.GET.get('modal') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'communication/message_compose_modal.html', ctx)
    return render(request, 'communication/message_compose.html', ctx)


@login_required
def message_detail(request, pk):
    msg = get_object_or_404(
        Message.objects.select_related('sender', 'recipient'),
        pk=pk,
    )
    if msg.recipient_id != request.user.id and msg.sender_id != request.user.id:
        messages.error(request, 'Accès refusé.')
        return redirect('communication:inbox')
    if msg.recipient_id == request.user.id and not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=['is_read'])
    return render(request, 'communication/message_detail.html', {'msg': msg})
