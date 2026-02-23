#!/usr/bin/env python3
"""
Email wrapper for OpenClaw agent
Connects to EWS MCP server and provides simple JSON-based email operations
"""

import json
import sys
import os
from exchangelib import Account, Configuration, Credentials, Message

def get_account():
    """Connect to AWS WorkMail via EWS"""
    email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('WORKMAIL_PASSWORD')
    server_url = os.getenv('EWS_SERVER_URL', 'ews.mail.us-east-1.awsapps.com')
    
    if not email or not password:
        raise ValueError("EMAIL_ADDRESS and WORKMAIL_PASSWORD environment variables must be set")
    
    creds = Credentials(email, password)
    config = Configuration(server=server_url, credentials=creds)
    account = Account(email, config=config, autodiscover=False)
    return account

def read_unread_emails(account, max_results=10):
    """Get unread emails from inbox"""
    try:
        inbox = account.inbox
        unread = list(inbox.filter(is_read=False).order_by('-datetime_received')[:max_results])
        
        emails = []
        for msg in unread:
            email_dict = {
                'message_id': msg.id,
                'sender': msg.sender.email_address,
                'sender_name': msg.sender.name,
                'subject': msg.subject,
                'body': msg.body or msg.text_body or '(no body)',
                'datetime_received': str(msg.datetime_received),
            }
            emails.append(email_dict)
        
        return {'success': True, 'emails': emails}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def reply_to_email(account, message_id, reply_body):
    """Reply to an email with proper threading"""
    try:
        inbox = account.inbox
        msg = inbox.get(id=message_id)
        
        # Build the subject with Re: prefix
        subject = msg.subject if msg.subject.startswith("Re:") else f"Re: {msg.subject}"
        
        # Create reply message
        reply_msg = Message(
            account=account,
            subject=subject,
            body=reply_body,
            to_recipients=[msg.sender],
        )
        
        # Extract original message-id from headers (for Gmail threading)
        original_msg_id = None
        if hasattr(msg, 'message_id') and msg.message_id:
            original_msg_id = msg.message_id
        elif hasattr(msg, 'headers') and msg.headers and 'Message-ID' in msg.headers:
            original_msg_id = msg.headers.get('Message-ID')
        
        # Set in_reply_to header
        if original_msg_id:
            reply_msg.in_reply_to = original_msg_id
        
        # Build references chain (include all previous message-ids)
        references_list = []
        if hasattr(msg, 'references') and msg.references:
            # Original email has references; append to them
            references_list = [msg.references]
        
        if original_msg_id:
            references_list.append(original_msg_id)
        
        if references_list:
            reply_msg.references = ' '.join(references_list)
        
        reply_msg.send()
        
        return {'success': True, 'message': 'Reply sent'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def mark_email_read(account, message_id):
    """Mark email as read"""
    try:
        inbox = account.inbox
        msg = inbox.get(id=message_id)
        msg.is_read = True
        msg.save(update_fields=['is_read'])
        
        return {'success': True, 'message': 'Email marked as read'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_email(account, to_address, subject, body):
    """Send an email"""
    try:
        from exchangelib import Message, HTMLBody
        
        # Detect if body is HTML
        is_html = body.strip().startswith('<!DOCTYPE') or body.strip().startswith('<html')
        
        msg = Message(
            account=account,
            subject=subject,
            to_recipients=[to_address],
        )
        
        if is_html:
            msg.body = HTMLBody(body)
        else:
            msg.body = body
        
        msg.send()
        
        return {'success': True, 'message': f'Email sent to {to_address}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: python email-wrapper.py <action> [arg]'}))
        sys.exit(1)
    
    action = sys.argv[1]
    
    try:
        account = get_account()
        
        if action == 'read':
            max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            result = read_unread_emails(account, max_results)
        
        elif action == 'reply':
            message_id = sys.argv[2]
            reply_body = sys.argv[3]
            result = reply_to_email(account, message_id, reply_body)
        
        elif action == 'mark-read':
            message_id = sys.argv[2]
            result = mark_email_read(account, message_id)
        
        elif action == 'send':
            to_address = sys.argv[2]
            subject = sys.argv[3]
            body = sys.argv[4]
            result = send_email(account, to_address, subject, body)
        
        else:
            result = {'error': f'Unknown action: {action}'}
        
        print(json.dumps(result))
    
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()